# ----------------------------------------------------------------------
# |
# |  IInputProcessing.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 08:56:10
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInputProcessing object"""

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


# ----------------------------------------------------------------------
class IInputProcessing(ABC):
    """Interface for input processing mixin objects"""

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def GetInputItems(
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        """Returns all input items associated with the provided context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def GetDisplayName(
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        """Returns a name suitable for disable for the provide context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _GenerateMetadataItems(
        input_items: List[Path],
        user_provided_metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """Generates metadata items associated with the input items and user-provided content"""
        raise Exception("Abstract method")
