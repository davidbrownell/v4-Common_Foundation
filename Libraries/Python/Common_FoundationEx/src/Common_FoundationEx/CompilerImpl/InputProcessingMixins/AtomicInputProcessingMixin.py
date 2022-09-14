# ----------------------------------------------------------------------
# |
# |  AtomicInputProcessingMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:22:57
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AtomicInputProcessingMixin object"""

import copy

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from Common_Foundation import PathEx
from Common_FoundationEx.InflectEx import inflect

from .IInputProcessing import IInputProcessing


# ----------------------------------------------------------------------
class AtomicInputProcessingMixin(IInputProcessing):
    """All inputs are grouped together as a single group"""

    # Generated
    ATTRIBUTE_NAME                          = "inputs"

    # ----------------------------------------------------------------------
    @classmethod
    def GetInputItems(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return metadata_or_context[cls.ATTRIBUTE_NAME]

    # ----------------------------------------------------------------------
    @classmethod
    def GetDisplayName(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        inputs = metadata_or_context[cls.ATTRIBUTE_NAME]

        common_path = PathEx.GetCommonPath(*inputs)
        if common_path is None:
            return None

        return "{} under '{}'".format(inflect.no("item", len(inputs)), common_path)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _GenerateMetadataItems(
        cls,
        input_items: List[Path],
        user_provided_metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        if cls.ATTRIBUTE_NAME in user_provided_metadata:
            raise Exception("'{}' is a reserved keyword.".format(cls.ATTRIBUTE_NAME))

        metadata = copy.deepcopy(user_provided_metadata)

        metadata[cls.ATTRIBUTE_NAME] = input_items
        yield metadata
