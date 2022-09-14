# ----------------------------------------------------------------------
# |
# |  CompilerImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 14:29:23
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

import textwrap

from abc import abstractmethod
from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Union, TextIO, Tuple

from rich import print as rich_print
from rich import box
from rich.panel import Panel
from rich.text import Text

from Common_Foundation.EnumSource import EnumSource
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx
from Common_Foundation.Types import extensionmethod

from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx

from .ICompilerImpl import ICompilerImpl, InvokeReason


# ----------------------------------------------------------------------
class InputType(Enum):
    """\
    Signals if a compiler operates on individual files or directories.
    """

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
class DiagnosticException(Exception):
    """Exceptions whose call stack should not be displayed"""
    pass


# ----------------------------------------------------------------------
class CompilerImpl(ICompilerImpl):
    """\
    Base class for compilers, code generators, validators, and other compiler-like
    constructs. For simplicity, all of these classes are referred to as compilers, but
    customize this object is slightly different ways.
    """

    # ----------------------------------------------------------------------
    class Steps(Enum):
        DetectingChanges                    = 0
        ExtractingInputItems                = auto()
        Executing                           = auto()
        # Custom steps here, as defined by derived classes
        PersistingContext                   = auto()

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        invocation_method_name: str,        # (e.g. "Compile")
        invoke_description: str,            # (e.g. "Compiling")
        name: str,
        description: str,
        input_type: InputType,
        *,
        execute_in_parallel: bool=True,
    ):
        self.invocation_method_name         = invocation_method_name
        self.name                           = name
        self.description                    = description
        self.input_type                     = input_type
        self.execute_in_parallel            = execute_in_parallel

        self._invoke_description            = invoke_description

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def ValidateEnvironment() -> Optional[str]:
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
    @staticmethod
    @abstractmethod
    def GetCustomArgs() -> TyperEx.TypeDefinitionsType:
        """Return type annotations for any arguments that can be provided on the command line"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @extensionmethod
    def IsSupported(
        self,
        filename_or_directory: Path,
    ) -> bool:
        """Return True if the filename provided is valid for compilation by this compiler"""

        return self.input_type.IsValid(filename_or_directory) and self.IsSupportedContent(filename_or_directory)

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def IsSupportedContent(
        filename_or_directory: Path,  # pylint: disable=unused-argument
    ) -> bool:
        """\
        Return True if the given input is supported by the compiler.

        In most cases, `IsSupported` is sufficient to determine if an input is valid. However, this
        method exists in case it is necessary to look at the content of the item itself.
        """

        # No custom actions by default
        return True

    # ----------------------------------------------------------------------
    @extensionmethod
    def IsTestItem(
        self,
        item: Path,
    ) -> bool:
        """Return True if the item looks like a test item."""

        return (
            item.name.lower().endswith("test")
            or any(parent.name.lower().endswith("tests") for parent in item.parents)
        )

    # ----------------------------------------------------------------------
    @extensionmethod
    def ItemToTestName(
        self,
        item: Path,
        test_type_name: str,
    ) -> Optional[Path]:
        """\
        Convert from a item path to its corresponding test file name.

        Override this method if the derived compiler uses custom conventions to convert from an item's
        name to the corresponding test name.
        """

        if self.input_type == InputType.Directories:
            # We can't reason about test directories, so just return the input. Derived classes may
            # want to handle this scenario more gracefully.
            return item

        elif self.input_type == InputType.Files:
            if self.IsTestItem(item):
                return item

            return item.parent / "{}.{}{}".format(
                item.stem,
                inflect.singular_noun(test_type_name) or test_type_name,
                item.suffix,
            )

        else:
            assert False, self.input_type  # pragma: no cover

    # ----------------------------------------------------------------------
    @extensionmethod
    def TestItemToName(
        self,
        item: Path,
    ) -> Optional[Path]:
        """\
        Converts from a test name to its system-under-test name,

        Override this method if the derived compiler using custom conventions to convert between a
        test and the system-under-test name,
        """

        if self.input_type == InputType.Directories:
            # We can't reason about test directories, so just return the input. Derived classes may
            # want to handle this scenario more gracefully.
            return item

        elif self.input_type == InputType.Files:
            raise NotImplementedError("TODO: Not implemented yet")

        else:
            assert False, self.input_type  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def IsSupportedTestItem(
        item: Path,  # pylint: disable=unused-argument
    ) -> bool:
        """\
        Return True if the item is a valid test file.

        Implement this method if a test files must have unique attributes for use with this compiler.
        """

        # Assume no special requirements
        return True

    # ----------------------------------------------------------------------
    def GenerateContextItems(
        self,
        dm: DoneManager,
        input_or_inputs: Union[Path, List[Path]],
        metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """\
        Generates one or more context items based on the provided input.

        Context items are arbitrary python objects used to capture the state/context of the input
        to determine if compilation is necessary.

        Context objects must support pickling.
        """

        if isinstance(input_or_inputs, list):
            inputs = input_or_inputs
        else:
            inputs = [input_or_inputs, ]

        input_items: List[Path] = []

        for input_item in inputs:
            if input_item.is_file():
                if self.input_type == InputType.Files:
                    input_items.append(input_item)
                elif self.input_type == InputType.Directories:
                    raise DiagnosticException("The filename '{}' was provided as input, but this compiler operates on directories.".format(str(input)))
                else:
                    assert False, self.input_type  # pragma: no cover

            elif input_item.is_dir():
                if self.input_type == InputType.Files:
                    for root, _, filenames in EnumSource(input_item):
                        for filename in filenames:
                            fullpath = root / filename

                            if fullpath.is_file() and self.IsSupported(fullpath):
                                input_items.append(fullpath)

                elif self.input_type == InputType.Directories:
                    input_items.append(input_item)
                else:
                    assert False, self.input_type  # pragma: no cover

            else:
                raise DiagnosticException("The input '{}' is not a valid filename or directory.".format(str(input)))

        for k, v in self._EnumerateOptionalMetadata():
            if k not in metadata or metadata[k] is None or metadata[k] == "":
                metadata[k] = v

        required_metadata_names = self._GetRequiredMetadataNames()
        required_context_names = self._GetRequiredContextNames()

        for generated_metadata in self._GenerateMetadataItems(input_items, metadata):
            for required_name in required_metadata_names:
                if required_name not in generated_metadata:
                    raise DiagnosticException("'{}' is required metadata.".format(required_name))

            if not self.GetInputItems(generated_metadata):
                continue

            display_name = self.GetDisplayName(generated_metadata)
            if display_name:
                generated_metadata["display_name"] = display_name

            context = self._CreateContext(dm, generated_metadata)
            if not context:
                continue

            for required_name in required_context_names:
                if required_name not in context:
                    raise DiagnosticException(
                        "'{}' is required for {} ({})".format(
                            required_name,
                            self.name,
                            ", ".join("'{}'".format(str(input)) for input in self.GetInputItems(context)),
                        ),
                    )

            yield context

    # ----------------------------------------------------------------------
    def GetContextItem(
        self,
        dm: DoneManager,
        input_dir: Path,
        metadata: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Calls GenerateContextItems, ensuring that there is only one generated context item"""

        contexts = list(self.GenerateContextItems(dm, input_dir, metadata))
        if not contexts:
            return None

        if len(contexts) != 1:
            raise DiagnosticException("Multiple contexts were found ({}).".format(len(contexts)))

        return contexts[0]

    # ----------------------------------------------------------------------
    def GetNumSteps(
        self,
        context: Dict[str, Any],
    ) -> int:
        """Returns the number of steps required to compile the provided context"""

        return len(CompilerImpl.Steps) + self._GetNumStepsImpl(context)

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _Invoke(
        self,
        context: Dict[str, Any],
        output_stream: TextIO,              # Log output
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        verbose: bool,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        invoke_reason: Optional[InvokeReason] = None
        input_items: List[Path] = []

        with DoneManager.Create(
            output_stream,
            "{}...".format(self._invoke_description),
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
                on_progress(CompilerImpl.Steps.DetectingChanges.value, "Detecting changes")

                with verbose_dm.Nested(
                    "Detecting changes...",
                    lambda: "No changes were detected" if invoke_reason is None else str(invoke_reason),
                ) as changes_dm:
                    invoke_reason = self._GetInvokeReason(changes_dm, context)

                    if invoke_reason is None:
                        return verbose_dm.result

                # Get the inputs
                on_progress(CompilerImpl.Steps.ExtractingInputItems.value, "Extracting input items")

                with verbose_dm.Nested(
                    "Extracting input items...",
                    lambda: "{} found".format(inflect.no("item", len(input_items))),
                ) as extract_dm:
                    input_items += self.GetInputItems(context)

                    if not input_items:
                        return extract_dm.result

            with dm.Nested(
                self._GetStatusText(self._invoke_description, context, input_items),
            ) as invoke_dm:
                with invoke_dm.YieldVerboseStream() as stream:
                    rich_print(
                        Panel(
                            Text(
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
                            ),
                            expand=False,
                            padding=(1, 2),
                            box=box.ASCII,
                        ),
                        file=stream,  # type: ignore
                    )

                    stream.write("\n")

                on_progress(CompilerImpl.Steps.Executing.value, "Executing")

                step_offset = CompilerImpl.Steps.Executing.value + 1

                short_desc = self._InvokeImpl(
                    invoke_reason,
                    invoke_dm,
                    context,
                    lambda step, status: on_progress(step + step_offset, status),
                )

                if invoke_dm.result >= 0:
                    with invoke_dm.VerboseNested("Persisting context..."):
                        on_progress(num_internal_steps + len(CompilerImpl.Steps) - 1, "Persisting context")

                        self._PersistContext(context)

                if short_desc:
                    return invoke_dm.result, short_desc

                return invoke_dm.result

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def _CreateContext(
        dm: DoneManager,  # pylint: disable=unused-argument
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        # No conversion between metadata and context by default
        return metadata

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def _EnumerateOptionalMetadata() -> Generator[Tuple[str, Any], None, None]:
        # No optional metadata by default
        if False:
            yield

    # ----------------------------------------------------------------------
    @staticmethod
    def _GetRequiredMetadataNames() -> List[str]:
        # No required metadata names by default
        return []

    # ----------------------------------------------------------------------
    @staticmethod
    def _GetRequiredContextNames() -> List[str]:
        # No required context names by default
        return []

    # ----------------------------------------------------------------------
    def _GetStatusText(
        self,
        description: str,
        context: Dict[str, Any],
        input_items: List[Path],
    ) -> str:
        display_name_value = context.get("display_name", None)
        if display_name_value is not None:
            status_suffix = "'{}'...".format(display_name_value)
        elif len(input_items) == 1:
            status_suffix = "'{}'...".format(str(input_items[0]))
        else:
            status_suffix = textwrap.dedent(
                """\

                {}
                """,
            ).format(
                "\n".join("    - {}".format(str(input_item)) for input_item in input_items),
            )

        return "{} {}".format(description, status_suffix)
