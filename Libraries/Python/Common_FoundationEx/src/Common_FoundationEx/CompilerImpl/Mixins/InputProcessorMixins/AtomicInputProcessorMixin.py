# ----------------------------------------------------------------------
# |
# |  AtomicInputProcessorMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:32:39
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AtomicInputProcessorMixin object"""

import copy

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.InflectEx import inflect

from ..IntrinsicsBase import IntrinsicsBase

from ...Interfaces.IInputProcessor import IInputProcessor


# ----------------------------------------------------------------------
class AtomicInputProcessorMixin(
    IntrinsicsBase,
    IInputProcessor,
):
    """Mixin where all inputs are grouped as a single group"""

    # Generated
    ATTRIBUTE_NAME                          = "inputs"
    INPUT_ROOT_ATTRIBUTE_NAME               = "input_root"

    # ----------------------------------------------------------------------
    @overridemethod
    def GetInputItems(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return metadata_or_context[AtomicInputProcessorMixin.ATTRIBUTE_NAME]

    # ----------------------------------------------------------------------
    @overridemethod
    def GetDisplayName(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        inputs = metadata_or_context[AtomicInputProcessorMixin.ATTRIBUTE_NAME]
        input_root = metadata_or_context[AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME]

        return "{} under '{}'".format(inflect.no("item", len(inputs)), input_root)

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(AtomicInputProcessorMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return [
            AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME,
            AtomicInputProcessorMixin.ATTRIBUTE_NAME,
        ] + super(AtomicInputProcessorMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(AtomicInputProcessorMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return super(AtomicInputProcessorMixin, self)._CreateContext(dm, metadata)

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _GenerateMetadataItems(
        self,
        input_root: Path,
        input_items: List[Path],
        user_provided_metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        for keyword in [
            AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME,
            AtomicInputProcessorMixin.ATTRIBUTE_NAME,
        ]:
            if keyword in user_provided_metadata:
                raise Exception("'{}' is a reserved keyword.".format(keyword))

        metadata = copy.deepcopy(user_provided_metadata)

        metadata[AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME] = input_root
        metadata[AtomicInputProcessorMixin.ATTRIBUTE_NAME] = input_items

        yield metadata
