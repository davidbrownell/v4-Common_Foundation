# ----------------------------------------------------------------------
# |
# |  IndividualInputProcessorMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:39:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IndividualInputProcessorMixin object"""

import copy

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ..IntrinsicsBase import IntrinsicsBase

from ...Interfaces.IInputProcessor import IInputProcessor


# ----------------------------------------------------------------------
class IndividualInputProcessorMixin(
    IntrinsicsBase,
    IInputProcessor,
):
    """Mixin where all inputs are processed as individual items"""

    # Generated
    ATTRIBUTE_NAME                          = "input"

    # ----------------------------------------------------------------------
    @overridemethod
    def GetInputItems(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return [metadata_or_context[IndividualInputProcessorMixin.ATTRIBUTE_NAME], ]

    # ----------------------------------------------------------------------
    @overridemethod
    def GetDisplayName(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        return str(metadata_or_context[IndividualInputProcessorMixin.ATTRIBUTE_NAME])

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(IndividualInputProcessorMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return [
            IndividualInputProcessorMixin.ATTRIBUTE_NAME,
        ] + super(IndividualInputProcessorMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(IndividualInputProcessorMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return super(IndividualInputProcessorMixin, self)._CreateContext(dm, metadata)

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _GenerateMetadataItems(
        self,
        input_root: Path,  # pylint: disable=unused-argument
        input_items: List[Path],
        user_provided_metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        if IndividualInputProcessorMixin.ATTRIBUTE_NAME in user_provided_metadata:
            raise Exception("'{}' is a reserved keyword.".format(IndividualInputProcessorMixin.ATTRIBUTE_NAME))

        for input_item in input_items:
            metadata = copy.deepcopy(user_provided_metadata)

            metadata[IndividualInputProcessorMixin.ATTRIBUTE_NAME] = input_item.resolve()
            yield metadata
