# ----------------------------------------------------------------------
# |
# |  MultipleOutputProcessorMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:14:21
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the MultipleOutputProcessorMixin object"""

from pathlib import Path
from typing import Any, Dict, Generator, List, Set, TextIO, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ..IntrinsicsBase import IntrinsicsBase

from ...Interfaces.IInputProcessor import IInputProcessor
from ...Interfaces.IOutputProcessor import IOutputProcessor


# ----------------------------------------------------------------------
class MultipleOutputProcessorMixin(
    IntrinsicsBase,
    IOutputProcessor,
):
    """Mixin for compilers that generate multiple output files"""

    # Required
    ATTRIBUTE_NAME                          = "output_filenames"

    # ----------------------------------------------------------------------
    def __init__(
        self,
        input_processor: IInputProcessor,
    ):
        self._input_processor               = input_processor

    # ----------------------------------------------------------------------
    @overridemethod
    def GetOutputItems(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return metadata_or_context[MultipleOutputProcessorMixin.ATTRIBUTE_NAME]

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(
        self,
        dm: DoneManager,                    # Status information generated with the process is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        input_items: Set[Path] = set(self._input_processor.GetInputItems(context))

        for output_filename in context[MultipleOutputProcessorMixin.ATTRIBUTE_NAME]:
            if output_filename in input_items:
                continue

            with dm.Nested("Removing '{}'...".format(output_filename)):
                output_stream.write("Removing '{}'...".format(output_filename))
                output_filename.unlink()
                output_stream.write("DONE!\n")

        super(MultipleOutputProcessorMixin, self).Clean(dm, output_stream, context)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(MultipleOutputProcessorMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(MultipleOutputProcessorMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return [
            MultipleOutputProcessorMixin.ATTRIBUTE_NAME,
        ] + super(MultipleOutputProcessorMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        assert MultipleOutputProcessorMixin.ATTRIBUTE_NAME in metadata, "Derived classes should have added '{}' to `metadata` before this functionality is invoked".format(MultipleOutputProcessorMixin.ATTRIBUTE_NAME)
        output_filenames = metadata[MultipleOutputProcessorMixin.ATTRIBUTE_NAME]

        for index, output_filename in enumerate(output_filenames):
            output_filenames[index] = output_filename.resolve()
            output_filename.parent.mkdir(parents=True, exist_ok=True)

        return super(MultipleOutputProcessorMixin, self)._CreateContext(dm, metadata)
