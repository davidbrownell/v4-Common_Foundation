# ----------------------------------------------------------------------
# |
# |  CompilerImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-18 13:01:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CompilerImpl object"""

import re
import textwrap

from abc import abstractmethod
from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Pattern, TextIO, Tuple, Union

from rich import print as rich_print
from rich import box
from rich.panel import Panel

from Common_Foundation.EnumSource import EnumSource
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx
from Common_Foundation.Types import extensionmethod, overridemethod

from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx

from .Interfaces.ICompilerIntrinsics import ICompilerIntrinsics
from .Interfaces.IInputProcessor import IInputProcessor
from .Interfaces.IInvocationQuery import IInvocationQuery, InvokeReason
from .Interfaces.IInvoker import IInvoker
from .Interfaces.IOutputProcessor import IOutputProcessor

from .Mixins.IntrinsicsBase import IntrinsicsBase


# ----------------------------------------------------------------------
class InputType(Enum):
    """Signals if a compiler operators on file input(s) or directory input(s)."""

    Files                                   = auto()
    Directories                             = auto()

    # ----------------------------------------------------------------------
    def IsValid(
        self,
        path: Path,
    ) -> bool:
        if self == self.__class__.Files:
            return path.is_file()
        if self == self.__class__.Directories:
            return path.is_dir()

        assert False, self  # pragma: no cover


# ----------------------------------------------------------------------
class CompilerImpl(
    IntrinsicsBase,
    IInputProcessor,
    IInvocationQuery,
    IInvoker,
    IOutputProcessor,
):
    """\
    Base class for compilers, code generators, validators, and other compiler-like
    constructors. For simplicity, all of these classes are referred to as compilers but
    each customize this object in slightly different ways.
    """

    # ----------------------------------------------------------------------
    class Steps(Enum):
        DetectingChanges                    = 0
        ExtractingInputItems                = auto()
        Executing                           = auto()
        # Custom steps here, as defined by derived classes
        PersistingContent                   = auto()

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        invocation_method_name: str,        # (e.g. "Compile")
        invocation_description: str,        # (e.g. "Compiling")
        name: str,
        description: str,
        input_type: InputType,
        *,
        requires_output_dir: bool,
        can_execute_in_parallel: bool=True,
    ):
        self.invocation_method_name         = invocation_method_name
        self.name                           = name
        self.description                    = description
        self.input_type                     = input_type
        self.requires_output_dir            = requires_output_dir
        self.can_execute_in_parallel        = can_execute_in_parallel

        self._invocation_description        = invocation_description

    # ----------------------------------------------------------------------
    @extensionmethod
    def ValidateEnvironment(self) -> Optional[str]:
        """\
        Opportunity to validate that a compiler can be run in the current environment.

        Overload this method when a compiler will never be successful when running in
        a specific environment (for example, trying to run a Windows compiler in a Linux
        environment).

        Return None if the environment is valid or a string that describes why the
        current environment is invalid for this compiler.
        """

        # Do nothing by default
        return None

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return type annotations for any arguments that can be provided on the command line when invoking the compiler"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @extensionmethod
    def IsIgnoredDirectory(
        self,
        directory: Path,  # pylint: disable=unused-argument
    ) -> bool:
        """Return True if the directory and its children should be ignored."""

        # No directories are ignored by default
        return False

    # ----------------------------------------------------------------------
    @abstractmethod
    def IsSupported(
        self,
        filename_or_directory: Path,        # filename if self.input_type == InputType.Files, directory if self.input_type == InputType.Directories
    ) -> bool:
        """Return True if the given input is supported by the compiler."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @extensionmethod
    def IsSupportedTestItem(
        self,
        item: Path,
    ) -> bool:
        """Return True if the item looks like a test item."""

        if self.input_type == InputType.Files and item.name.lower().endswith("test"):
            return True
        if self.input_type == InputType.Directories and item.name.lower().endswith("tests"):
            return True

        return any(parent.name.lower().endswith("tests") for parent in item.parents)

    # ----------------------------------------------------------------------
    @extensionmethod
    def ItemToTestName(
        self,
        item: Path,
        test_type_name: str,
    ) -> Optional[Path]:
        """\
        Convert from an item path to its corresponding test file name.

        Override this method if the derived compiler uses custom conventions to
        convert from an item's name to the corresponding test name.
        """

        if self.input_type == InputType.Directories:
            # We can't reason about test directories, so just return the input.
            # Derived classes may want to handle this scenario more gracefully.
            return item

        if self.input_type == InputType.Files:
            if self.IsSupportedTestItem(item):
                return item

            return item.parent / "{}.{}{}".format(
                item.stem,
                inflect.singular_noun(test_type_name) or test_type_name,
                item.suffix,
            )

        assert False, self.input_type  # pragma: no cover

    # ----------------------------------------------------------------------
    _TestItemToName_regex: Optional[Pattern]            = None

    @extensionmethod
    def TestItemToName(
        self,
        item: Path,
    ) -> Optional[Path]:
        """\
        Convert from a test name to its system-under-test name.

        Override this method if the derived compiler uses custom conventions to
        convert from a test to the system-under-test name.
        """

        if self.input_type == InputType.Directories:
            # We can't reason about test directories, so just return the input.
            # Derived classes may want to handle this scenario more gracefully.
            return item

        if self.input_type == InputType.Files:
            if self.__class__._TestItemToName_regex is None:                # pylint: disable=protected-access
                self.__class__._TestItemToName_regex = re.compile(          # pylint: disable=protected-access
                    r"""(?#
                    Start                   )^(?#
                    Prefix                  )(?P<prefix>.+)(?#
                    Test Type Name          )\.[^\.]+?Test(?#
                    Extension               )(?P<extension>\..+)(?#
                    End                     )$(?#
                    )""",
                )

            match = self.__class__._TestItemToName_regex.match(item.name)   # pylint: disable=protected-access
            if not match:
                return None

            return item.parent / "{}{}".format(match.group("prefix"), match.group("extension"))

        assert False, self.input_type  # pragma: no cover

    # ----------------------------------------------------------------------
    def GenerateContextItems(
        self,
        dm: DoneManager,
        input_or_inputs: Union[Path, List[Path]],
        metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """\
        Generates one or more context items based on the provided metadata input.

        Context items are arbitrary python objects used to capture the state/context of
        the input to determine if compilation is necessary.

        Context objects must support pickling.
        """

        if isinstance(input_or_inputs, list):
            input_items = input_or_inputs
        else:
            input_items = [input_or_inputs, ]

        # Collect the inputs
        all_input_items: Dict[Path, List[Path]] = {}

        for input_item in input_items:
            if input_item.is_file():
                if self.input_type == InputType.Files:
                    if self.IsSupported(input_item):
                        all_input_items[input_item.parent] = [input_item, ]
                elif self.input_type == InputType.Directories:
                    raise Exception("The filename '{}' was provided as an input, but '{}' operates on directories.".format(input_item, self.name))
                else:
                    assert False, self.input_type  # pragma: no cover

            elif input_item.is_dir():
                if self.IsSupported(input_item):
                    all_input_items[input_item] = [input_item, ]
                else:
                    these_inputs: List[Path] = []

                    for root, directories, filenames in EnumSource(input_item):
                        if self.IsIgnoredDirectory(root):
                            directories[:] = []
                            continue

                        if self.input_type == InputType.Files:
                            for filename in filenames:
                                fullpath = root / filename

                                if self.IsSupported(fullpath):
                                    these_inputs.append(fullpath)

                        elif self.input_type == InputType.Directories:
                            for directory in directories:
                                fullpath = root / directory

                                if self.IsSupported(fullpath):
                                    these_inputs.append(fullpath)

                        else:
                            assert False, self.input_type  # pragma: no cover

                    if these_inputs:
                        all_input_items[input_item] = these_inputs

            else:
                assert False, input_item  # pragma: no cover

        if not all_input_items:
            return

        # Augment the metadata
        for k, v in self._EnumerateOptionalMetadata():
            existing_value = metadata.get(k, self.__class__._does_not_exist)  # pylint: disable=protected-access

            if (
                existing_value is self.__class__._does_not_exist  # pylint: disable=protected-access
                or existing_value is None
                or existing_value == ""
            ):
                metadata[k] = v

        required_metadata_names = self._GetRequiredMetadataNames()
        required_context_names = self._GetRequiredContextNames()

        # Generate the context items
        for index, (item_root, input_items) in enumerate(all_input_items.items()):
            if (
                self.requires_output_dir
                and (
                    len(input_items) != 1
                    or input_items[0] != item_root
                )
            ):
                len_item_root_parts = len(item_root.parts)

                # ----------------------------------------------------------------------
                def DecoratedGeneratedMetadata(
                    metadata: Dict[str, Any],
                ) -> None:
                    if "input" in metadata:
                        metadata["output_dir"] /= Path(*metadata["input"].parts[len_item_root_parts:])
                    elif "inputs" in metadata:
                        if len(all_input_items) != 1:
                            metadata["output_dir"] /= str(index)
                    else:
                        assert False, metadata  # pragma: no cover

                # ----------------------------------------------------------------------

                decorate_generated_metadata_func = DecoratedGeneratedMetadata
            else:
                decorate_generated_metadata_func = lambda _: None

            for generated_metadata in self._GenerateMetadataItems(item_root, input_items, metadata):
                decorate_generated_metadata_func(generated_metadata)

                # Validate required metadata names
                for required_name in required_metadata_names:
                    if required_name not in generated_metadata:
                        raise Exception(
                            "'{}' is required metadata for '{}'.".format(required_name, self.name),
                        )

                if not self.GetInputItems(generated_metadata):
                    continue

                display_name = self.GetDisplayName(generated_metadata)
                if display_name:
                    generated_metadata["display_name"] = display_name

                # Create the context
                with dm.Nested(
                    "Creating context for '{}'...".format(generated_metadata["display_name"]),
                ) as this_dm:
                    context = self._CreateContext(this_dm, generated_metadata)
                    if not context or this_dm.result != 0:
                        continue

                # Validate required context name
                for required_name in required_context_names:
                    if required_name not in context:
                        raise Exception(
                            "'{}' is required for '{}' ({}).".format(
                                required_name,
                                self.name,
                                ", ".join("'{}'".format(str(input)) for input in self.GetInputItems(context)),
                            ),
                        )

                yield context

    # ----------------------------------------------------------------------
    def GetSingleContextItem(
        self,
        dm: DoneManager,
        input_item: Path,
        metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Calls `GenerateContextItems`, ensuring that there is only one context item generated"""

        contexts = list(self.GenerateContextItems(dm, input_item, metadata))
        if not contexts:
            return None

        if len(contexts) != 1:
            raise Exception("Multiple contexts were found ({}).".format(len(contexts)))

        return contexts[0]

    # ----------------------------------------------------------------------
    def GetNumSteps(
        self,
        context: Dict[str, Any],
    ) -> int:
        """Returns the number of steps required to compile the provided context"""

        return len(CompilerImpl.Steps) + self._GetNumStepsImpl(context)

    # ----------------------------------------------------------------------
    @extensionmethod
    def RemoveTemporaryArtifacts(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        """Opportunity to remove any artifacts created during the compilation process"""

        # Nothing to remove by default
        return

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _Invoke(
        self,
        context: Dict[str, Any],            # Status output
        output_stream: TextIO,              # Log output
        on_progress_func: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        verbose: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short description that provides contextual information about the return code
        ],
    ]:
        invoke_reason: Optional[InvokeReason] = None
        input_items: List[Path] = []

        with DoneManager.Create(
            output_stream,
            "{}...".format(self._invocation_description),
            output_flags=DoneManagerFlags.Create(
                verbose=verbose,
            ),
        ) as dm:
            num_internal_steps = self._GetNumStepsImpl(context)

            with dm.VerboseNested(
                "Preparing compilation...",
                suffix="\n",
            ) as verbose_dm:
                # Get the invoke reason
                on_progress_func(CompilerImpl.Steps.DetectingChanges.value, "Detecting Changes...")
                with verbose_dm.Nested(
                    "Detecting changes...",
                    lambda: "No changes were detected" if invoke_reason is None else str(invoke_reason),
                ) as changes_dm:
                    invoke_reason = self._GetInvokeReason(changes_dm, context)
                    if invoke_reason is None:
                        return verbose_dm.result

                # Get the inputs
                on_progress_func(CompilerImpl.Steps.ExtractingInputItems.value, "Extracting Input Items...")
                with verbose_dm.Nested(
                    "Extracting input items...",
                    lambda: "{} found".format(inflect.no("item", len(input_items))),
                ) as extract_dm:
                    input_items += self.GetInputItems(context)
                    if not input_items:
                        return extract_dm.result

            with dm.Nested(
                self._GetStatusText(self._invocation_description, context, input_items),
            ) as invoke_dm:
                with invoke_dm.YieldVerboseStream() as stream:
                    rich_print(
                        Panel(
                            textwrap.dedent(
                                """\
                                {}
                                        ->
                                {}
                                """,
                            ).format(
                                "\n".join(str(input_item) for input_item in input_items),
                                TextwrapEx.Indent(
                                    "\n".join(
                                        str(output_item or "[None]")
                                        for output_item in self.GetOutputItems(context)
                                    ),
                                    4,
                                ),
                            ),
                            expand=False,
                            padding=(1, 2),
                            box=box.ASCII,
                        ),
                        file=stream,  # type: ignore
                    )

                    stream.write("\n")

                on_progress_func(CompilerImpl.Steps.Executing.value, "Executing...")

                step_offset = CompilerImpl.Steps.Executing.value + 1

                short_desc = self._InvokeImpl(
                    invoke_reason,
                    invoke_dm,
                    context,
                    lambda step, status: on_progress_func(step + step_offset, status),
                )

                if invoke_dm.result >= 0:
                    on_progress_func(num_internal_steps + len(CompilerImpl.Steps) - 1, "Persisting Context...")
                    with invoke_dm.VerboseNested("Persisting context..."):
                        self._PersistContext(context)

                if short_desc:
                    return invoke_dm.result, short_desc

                return invoke_dm.result

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _DoesNotExist(object):
        pass

    # ----------------------------------------------------------------------
    _does_not_exist                         = _DoesNotExist()

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _GetStatusText(
        self,
        description: str,
        context: Dict[str, Any],
        input_items: List[Path],
    ) -> str:
        """Returns initial status information about the context"""

        display_name_value = context.get("display_name", None)
        if display_name_value is not None:
            status_suffix = "'{}'...".format(display_name_value)
        else:
            if len(input_items) == 1:
                status_suffix = "'{}'...".format(str(input_items[0]))
            else:
                status_suffix = textwrap.dedent(
                    """\

                    {}
                    """,
                ).format(
                    "\n".join("    - {}".format(input_item) for input_item in input_items),
                )

        return "{} {}".format(description, status_suffix)
