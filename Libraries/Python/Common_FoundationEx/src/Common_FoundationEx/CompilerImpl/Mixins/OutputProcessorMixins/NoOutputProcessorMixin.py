# ----------------------------------------------------------------------
# |
# |  NoOutputProcessorMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:06:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the NoOutputProcessorMixin object"""

from pathlib import Path
from typing import Any, Dict, Generator, List, TextIO, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ...Interfaces.ICompilerIntrinsics import ICompilerIntrinsics
from ...Interfaces.IOutputProcessor import IOutputProcessor


# ----------------------------------------------------------------------
class NoOutputProcessorMixin(
    ICompilerIntrinsics,
    IOutputProcessor,
):
    """Mixin for compilers that don't generate any output"""

    # ----------------------------------------------------------------------
    @overridemethod
    def GetOutputItems(
        self,
        metadata_or_context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> List[Path]:
        return []

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(
        self,
        dm: DoneManager,                    # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> None:
        # Nothing to clean
        pass

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(NoOutputProcessorMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(NoOutputProcessorMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(NoOutputProcessorMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return super(NoOutputProcessorMixin, self)._CreateContext(dm, metadata)
