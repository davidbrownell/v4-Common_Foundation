# ----------------------------------------------------------------------
# |
# |  ConditionalInvocationQueryMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:53:48
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ConditionalInvocationQueryMixin object"""

import base64
import inspect
import pickle
import textwrap
import traceback

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Set, Tuple

from Common_Foundation import RegularExpression
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import extensionmethod, overridemethod

from Common_FoundationEx.InflectEx import inflect

from ..IntrinsicsBase import IntrinsicsBase

from ...Interfaces.IInputProcessor import IInputProcessor
from ...Interfaces.IInvocationQuery import IInvocationQuery, InvokeReason
from ...Interfaces.IOutputProcessor import IOutputProcessor


# ----------------------------------------------------------------------
class ConditionalInvocationQueryMixin(
    IntrinsicsBase,
    IInvocationQuery,
):
    """Mixin for compilers that determine invocation by conditions"""

    # Optional
    FORCE_ATTRIBUTE_NAME                                = "force"
    OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME          = "output_data_filename_prefix"

    # Required
    OUTPUT_DIR_ATTRIBUTE_NAME                           = "output_dir"

    # ----------------------------------------------------------------------
    def __init__(
        self,
        input_processor: IInputProcessor,
        output_processor: IOutputProcessor,
        *,
        always_generate: bool=False,
    ):
        self._input_processor               = input_processor
        self._output_processor              = output_processor
        self._always_generate               = always_generate

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @extensionmethod
    def _CustomContextComparison(
        self,
        current_context: Dict[str, Any],    # pylint: disable=unused-argument
        prev_context: Dict[str, Any],       # pylint: disable=unused-argument
    ) -> Optional[str]:
        """Opportunity for derived classes to influence the change detection process by implementing custom comparison logic between contexts"""

        # No custom comparison by default
        return None

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _GetInvokeReason(
        self,
        dm: DoneManager,                    # pylint: disable=unused-argument
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> Optional[InvokeReason]:

        # Don't persist force
        force = context.pop(ConditionalInvocationQueryMixin.FORCE_ATTRIBUTE_NAME, False)

        persisted_filename = _PersistedInfo.GetPersistedFilename(context)

        # Check the basic reasons
        for invoke_reason, desc, func in [
            (InvokeReason.Force, "force was specified", lambda: force),
            (InvokeReason.PreviousContextMissing, "previous context is missing", lambda: not persisted_filename.is_file()),
        ]:
            if func():
                dm.WriteInfo("Invoking because {}.\n\n".format(desc))
                return invoke_reason

        # Check calculated reasons
        prev_info, prev_modified_time = _PersistedInfo.Load(
            dm,
            self._input_processor,
            self._output_processor,
            context,
        )

        # ----------------------------------------------------------------------
        def HaveGeneratorFilesBeenModified() -> Optional[Path]:
            for filename in self._EnumerateGeneratorFiles(context):
                if filename.stat().st_mtime > prev_modified_time:
                    return filename

            return None

        # ----------------------------------------------------------------------
        def AreOutputsMissing() -> Optional[Path]:
            for output_item in self._output_processor.GetOutputItems(context):
                if not output_item.exists():
                    return output_item

            return None

        # ----------------------------------------------------------------------
        def HaveOutputsChanged() -> bool:
            return sorted(self._output_processor.GetOutputItems(context)) != sorted(prev_info.output_items)

        # ----------------------------------------------------------------------
        def HaveInputsBeenModified() -> Optional[Path]:
            input_filenames: List[Path] = []

            for input_item in self._input_processor.GetInputItems(context):
                if input_item.is_file():
                    input_filenames.append(input_item)
                elif input_item.is_dir():
                    for item in input_item.iterdir():
                        if item.is_file():
                            input_filenames.append(item)

            for input_filename in input_filenames:
                if input_filename.stat().st_mtime > prev_modified_time:
                    return input_filename

            return None

        # ----------------------------------------------------------------------
        def HaveInputsChanged() -> bool:
            return sorted(self._input_processor.GetInputItems(context)) != sorted(prev_info.input_items)

        # ----------------------------------------------------------------------
        def HasMetadataChanged() -> Optional[str]:
            prev_metadata_keys: Set[str] = set(key for key in prev_info.context if not key.startswith("_"))

            for k, v in context.items():
                if k.startswith("_"):
                    continue

                if k not in prev_metadata_keys:
                    return "'{}' has been added".format(k)

                if v != prev_info.context[k]:
                    return "'{}' has been modified".format(k)

                prev_metadata_keys.remove(k)

            if prev_metadata_keys:
                return "{} {} removed".format(
                    ", ".join("'{}'".format(k) for k in prev_metadata_keys),
                    inflect.plural("has", len(prev_metadata_keys)),
                )

            return None

        # ----------------------------------------------------------------------
        def HasCustomMetadataChanged() -> Optional[str]:
            return self._CustomContextComparison(context, prev_info.context)

        # ----------------------------------------------------------------------
        def ShouldGenerate() -> bool:
            return self._always_generate

        # ----------------------------------------------------------------------

        for invoke_reason, desc_template, func in [
            (InvokeReason.NewerGenerators, "generator files have been modified ({result})", HaveGeneratorFilesBeenModified),
            (InvokeReason.MissingOutput, "items to generate are missing ({result})", AreOutputsMissing),
            (InvokeReason.DifferentOutput, "items to generate have changed", HaveOutputsChanged),
            (InvokeReason.NewerInput, "input has been modified ({result})", HaveInputsBeenModified),
            (InvokeReason.DifferentInputs, "input items have changed", HaveInputsChanged),
            (InvokeReason.DifferentMetadata, "metadata has changed ({result}) [standard]", HasMetadataChanged),
            (InvokeReason.DifferentMetadata, "metadata has changed ({result}) [custom]", HasCustomMetadataChanged),
            (InvokeReason.OptIn, "the generator opted-in to generation", ShouldGenerate),
        ]:
            result = func()
            if result:
                dm.WriteInfo("Invoking because {}.\n\n".format(desc_template.format(result=str(result))))
                return invoke_reason

        return None

    # ----------------------------------------------------------------------
    @overridemethod
    def _PersistContext(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        _PersistedInfo.Create(
            self._input_processor,
            self._output_processor,
            context,
        ).Save()

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield ConditionalInvocationQueryMixin.FORCE_ATTRIBUTE_NAME, False
        yield ConditionalInvocationQueryMixin.OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME, ""

        yield from super(ConditionalInvocationQueryMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(ConditionalInvocationQueryMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return [
            ConditionalInvocationQueryMixin.OUTPUT_DIR_ATTRIBUTE_NAME,
        ] + super(ConditionalInvocationQueryMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata[ConditionalInvocationQueryMixin.OUTPUT_DIR_ATTRIBUTE_NAME].resolve()
        metadata[ConditionalInvocationQueryMixin.OUTPUT_DIR_ATTRIBUTE_NAME].mkdir(parents=True, exist_ok=True)

        return super(ConditionalInvocationQueryMixin, self)._CreateContext(dm, metadata)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _PersistedInfo(object):
    # ----------------------------------------------------------------------
    FILENAME                                = "Compiler.ConditionalInvocationQueryMixin.data"
    TEMPLATE                                = textwrap.dedent(
        """\
        - Generated by ConditionalInvocationQueryMixin to trace context changes between compilation invocations.
        -
        - ***** Please do not modify this file *****
        {data}
        """,
    )

    # ----------------------------------------------------------------------
    context: Dict[str, Any]
    input_items: List[Path]
    output_items: List[Path]

    # ----------------------------------------------------------------------
    @classmethod
    def GetPersistedFilename(
        cls,
        context: Dict[str, Any],
    ) -> Path:
        return context[ConditionalInvocationQueryMixin.OUTPUT_DIR_ATTRIBUTE_NAME] / "{}{}".format(
            context[ConditionalInvocationQueryMixin.OUTPUT_DATA_FILENAME_PREFIX_ATTRIBUTE_NAME],
            cls.FILENAME,
        )

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        input_processor: IInputProcessor,
        output_processor: IOutputProcessor,
        context: Dict[str, Any],
    ) -> "_PersistedInfo":
        return cls(
            context,
            input_processor.GetInputItems(context),
            output_processor.GetOutputItems(context),
        )

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        dm: DoneManager,
        input_processor: IInputProcessor,
        output_processor: IOutputProcessor,
        context: Dict[str, Any],
    ) -> Tuple["_PersistedInfo", float]:
        filename = cls.GetPersistedFilename(context)

        if filename.exists():
            try:
                match = RegularExpression.TemplateStringToRegex(cls.TEMPLATE).match(filename.open().read())
                if match:
                    data = base64.b64decode(match.group("data"))
                    return pickle.loads(bytearray(data)), filename.stat().st_mtime

            except Exception as ex:
                if dm.is_debug:
                    error = traceback.format_exc()
                else:
                    error = str(ex)

                dm.WriteWarning(
                    textwrap.dedent(
                        """\
                        Context information associated with the previous compilation appears to be corrupt; new data will be generated.

                        {}
                        """,
                    ).format(error.rstrip()),
                    update_result=False,
                )

        return cls.Create(input_processor, output_processor, context), 0.0

    # ----------------------------------------------------------------------
    def Save(self) -> None:
        data = pickle.dumps(self)
        data = base64.b64encode(data)
        data = data.decode("utf-8")

        filename = self.__class__.GetPersistedFilename(self.context)

        filename.parent.mkdir(parents=True, exist_ok=True)

        with filename.open("w") as f:
            f.write(self.__class__.TEMPLATE.format(data=data))
