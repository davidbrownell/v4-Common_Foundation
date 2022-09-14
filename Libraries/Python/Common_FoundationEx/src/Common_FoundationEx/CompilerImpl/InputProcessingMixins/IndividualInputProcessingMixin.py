# ----------------------------------------------------------------------
# |
# |  IndividualInputProcessingMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:27:30
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IndividualInputProcessingMixin object"""

import copy

from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

from .IInputProcessing import IInputProcessing


# ----------------------------------------------------------------------
class IndividualInputProcessingMixin(IInputProcessing):
    """Each input is processed in isolation"""

    # Generated
    ATTRIBUTE_NAME                          = "input"

    # ----------------------------------------------------------------------
    @classmethod
    def GetInputItems(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return [metadata_or_context[cls.ATTRIBUTE_NAME], ]

    # ----------------------------------------------------------------------
    @classmethod
    def GetDisplayName(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        return str(metadata_or_context[cls.ATTRIBUTE_NAME])

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

        for input_item in input_items:
            metadata = copy.deepcopy(user_provided_metadata)

            metadata[cls.ATTRIBUTE_NAME] = input_item.resolve()
            yield metadata
