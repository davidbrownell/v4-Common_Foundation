# ----------------------------------------------------------------------
# |
# |  AtomicOutputProcessorMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 12:58:33
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AtomicOutputProcessMixin"""

from pathlib import Path
from typing import Any, Dict, Generator, List, TextIO, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ...Interfaces.ICompilerIntrinsics import ICompilerIntrinsics
from ...Interfaces.IInputProcessor import IInputProcessor
from ...Interfaces.IOutputProcessor import IOutputProcessor


# ----------------------------------------------------------------------
class AtomicOutputProcessorMixin(
    ICompilerIntrinsics,
    IOutputProcessor,
):
    """Mixin for compilers that generate a single file"""

    # Required
    ATTRIBUTE_NAME                          = "output_filename"

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
        return [metadata_or_context[AtomicOutputProcessorMixin.ATTRIBUTE_NAME], ]

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(
        self,
        dm: DoneManager,                    # Status information generated with the process is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        if (
            context[AtomicOutputProcessorMixin.ATTRIBUTE_NAME] not in self._input_processor.GetInputItems(context)
            and context[AtomicOutputProcessorMixin.ATTRIBUTE_NAME].is_file()
        ):
            output_filename = context[AtomicOutputProcessorMixin.ATTRIBUTE_NAME]

            with dm.Nested("Removing '{}'...".format(output_filename)):
                output_filename.unlink()
                output_stream.write("Removed '{}'.\n".format(output_filename))

        super(AtomicOutputProcessorMixin, self).Clean(dm, output_stream, context)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(AtomicOutputProcessorMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(AtomicOutputProcessorMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return [
            AtomicOutputProcessorMixin.ATTRIBUTE_NAME,
        ] + super(AtomicOutputProcessorMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata[AtomicOutputProcessorMixin.ATTRIBUTE_NAME] = metadata[AtomicOutputProcessorMixin.ATTRIBUTE_NAME].resolve()
        metadata[AtomicOutputProcessorMixin.ATTRIBUTE_NAME].parent.mkdir(parents=True, exist_ok=True)

        return super(AtomicOutputProcessorMixin, self)._CreateContext(dm, metadata)
