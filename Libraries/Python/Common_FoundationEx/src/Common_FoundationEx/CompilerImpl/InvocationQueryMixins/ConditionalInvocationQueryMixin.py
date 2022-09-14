# ----------------------------------------------------------------------
# |
# |  ConditionalInvocationQueryMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 16:18:56
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ConditionalInvocationQueryMixin object"""

import base64
import pickle
import textwrap

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Pattern, Tuple

from Common_Foundation.RegularExpression import TemplateStringToRegex
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import extensionmethod

from Common_FoundationEx.InflectEx import inflect

from ..ICompilerImpl import ICompilerImpl, InvokeReason


# ----------------------------------------------------------------------
class ConditionalInvocationQueryMixin(ICompilerImpl):
    """Mixin for compilers that determine invocation by conditions"""

    # Required
    OUTPUT_DIR_ATTRIBUTE_NAME                           = "output"

    # Optional
    FORCE_ATTRIBUTE_NAME                                = "force"
    OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME          = "output_data_filename_prefix"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _EnumerateOptionalMetadata(cls) -> Generator[Tuple[str, Any], None, None]:
        yield cls.FORCE_ATTRIBUTE_NAME, False
        yield cls.OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME, ""

        yield from super(ConditionalInvocationQueryMixin, cls)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @classmethod
    def _GetRequiredMetadataNames(cls) -> List[str]:
        return [cls.OUTPUT_DIR_ATTRIBUTE_NAME, ] + super(ConditionalInvocationQueryMixin, cls)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @classmethod
    def _CreateContext(
        cls,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata[cls.OUTPUT_DIR_ATTRIBUTE_NAME] = metadata[cls.OUTPUT_DIR_ATTRIBUTE_NAME].resolve()

        if not metadata[cls.OUTPUT_DIR_ATTRIBUTE_NAME].is_dir():
            metadata[cls.OUTPUT_DIR_ATTRIBUTE_NAME].mkdir(parents=True, exists_ok=True)

        return super(ConditionalInvocationQueryMixin, cls)._CreateContext(dm, metadata)

    # ----------------------------------------------------------------------
    def _GetInvokeReason(
        self,
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> Optional[InvokeReason]:
        load_result = _PersistInfo.Load(dm, context)

        if load_result is None:
            prev_info = None
            prev_modified_time = 0.0
        else:
            prev_info, prev_modified_time = load_result

        # Don't persist force
        force = context.pop(self.__class__.FORCE_ATTRIBUTE_NAME, False)

        # Check the basic reasons
        for invoke_reason, desc, functor in [
            (InvokeReason.Force, "force was specified", lambda: force),
            (InvokeReason.PreviousContextMissing, "previous context is missing", lambda: not prev_info),
        ]:
            if functor():
                dm.WriteLine("Invoking because {}.".format(desc))
                return invoke_reason

        # Check calculated reasons

        # ----------------------------------------------------------------------
        def HaveGeneratorFilesBeenModified() -> bool:
            raise NotImplementedError("TODO: Not implemented yet")

        # ----------------------------------------------------------------------
        def AreGeneratedItemsMissing() -> Optional[str]:
            for fullpath in self.GetOutputItems(context):
                if not fullpath.exists():
                    return str(fullpath)

                return None

        # ----------------------------------------------------------------------
        def HaveOutputsBeenModified() -> bool:
            assert prev_info is not None
            return self.GetOutputItems(context) != prev_info.output_items

        # ----------------------------------------------------------------------
        def HaveInputsChanged() -> bool:
            raise NotImplementedError("TODO: Not implemented yet")

        # ----------------------------------------------------------------------
        def HaveInputsBeenModified() -> bool:
            assert prev_info is not None
            return self.GetInputItems(context) != prev_info.input_items

        # ----------------------------------------------------------------------
        def HasContextChanged() -> Optional[str]:
            assert prev_info is not None

            prev_context_keys = list(prev_info.context.keys())

            for k, v in context.items():
                if k.startswith("_"):
                    continue

                if k not in prev_context_keys:
                    return "'{}' has been added".format(k)

                if v != prev_info.context[k]:
                    return "'{}' has changed".format(k)

                prev_context_keys.remove(k)

            if prev_context_keys:
                return "{} {} been removed".format(
                    ", ".join("'{}'".format(key) for key in prev_context_keys),
                    inflect.plural("has", len(prev_context_keys)),
                )

            return None

        # ----------------------------------------------------------------------
        def HasCustomContextChanged() -> Optional[str]:
            assert prev_info is not None
            return self._CustomContextComparison(context, prev_info.context)

        # ----------------------------------------------------------------------
        def ShouldGenerate() -> bool:
            return self._ShouldGenerateImpl(context)

        # ----------------------------------------------------------------------

        for invoke_reason, desc_template, functor in [
            (InvokeReason.NewerGenerators, "generator files have been modified ({result})", HaveGeneratorFilesBeenModified),
            (InvokeReason.MissingOutput, "items to generate are missing ({result})", AreGeneratedItemsMissing),
            (InvokeReason.DifferentOutput, "items to generate have changed", HaveOutputsBeenModified),
            (InvokeReason.NewerInput, "input has been modified ({result})", HaveInputsBeenModified),
            (InvokeReason.DifferentInputs, "input items have changed", HaveInputsChanged),
            (InvokeReason.DifferentMetadata, "context has changed ({result}) [standard]", HasContextChanged),
            (InvokeReason.DifferentMetadata, "context has changed ({result}) [custom]", HasCustomContextChanged),
            (InvokeReason.OptIn, "the generator opted-in to generation", ShouldGenerate),
        ]:
            result = functor()
            if result:
                dm.WriteLine("Invoking because {}.\n".format(desc_template.format(result=result)))
                return invoke_reason

        return None

    # ----------------------------------------------------------------------
    @classmethod
    def _PersistContext(
        cls,
        context: Dict[str, Any],
    ) -> None:
        _PersistInfo.Create(cls, context).Save()

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def _ShouldGenerateImpl(
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> bool:
        """Last chance for derived generators to force generation"""

        # By default, don't force generation
        return False

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def _CustomContextComparison(
        context: Dict[str, Any],            # pylint: disable=unused-argument
        prev_context: Dict[str, Any],       # pylint: disable=unused-argument
    ) -> Optional[Any]:
        """\
        Opportunity for a compiler to perform custom comparison when determining if invocation should
        continue. Returns a string describing mis-compare reasons (if any).
        """

        # No custom comparison by default
        return None


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _PersistInfo(object):
    FILENAME                                = "Compiler.ConditionalInvocationQueryMixin.data"
    TEMPLATE                                = textwrap.dedent(
        """\
        - Generated by ConditionalInvocationQueryMixin to track context changes between
        - compilation invocations.
        -
        - ***** Please do not modify this file *****
        {data}

        Version 1.0.0
        """,
    )

    # ----------------------------------------------------------------------
    context: Dict[str, Any]
    input_items: List[Path]
    output_items: List[Path]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        compiler: Any,
        context: Dict[str, Any],
    ):
        return cls(
            context,
            compiler.GetInputItems(context),
            compiler.GetOutputItems(context),
        )

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> Optional[Tuple["_PersistInfo", float]]:
        filename = cls._GetFilename(context)

        if filename.is_file():
            try:
                with filename.open() as f:
                    content = f.read()

                regex: Pattern = TemplateStringToRegex(cls.TEMPLATE)

                match = regex.match(content)
                if match:
                    data = base64.b64decode(match.group("data"))
                    data = bytearray(data)
                    data = pickle.loads(data)

                    return data, filename.stat().st_mtime

            except:  # pylint: disable=bare-except
                dm.WriteWarning("Context information associated with the previous compilation appears to be corrupt; new data will be generated.\n")

        return None

    # ----------------------------------------------------------------------
    def Save(self) -> None:
        data = pickle.dumps(self)
        data = base64.b64encode(data)
        data = data.decode()

        filename = self._GetFilename(self.context)

        with filename.open("w") as f:
            f.write(self.TEMPLATE.format(data=data))

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _GetFilename(
        cls,
        context: Dict[str, Any],
    ) -> Path:
        return context["output_dir"] / "{}{}".format(context[ConditionalInvocationQueryMixin.OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME], cls.FILENAME)
