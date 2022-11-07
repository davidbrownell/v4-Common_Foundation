# ----------------------------------------------------------------------
# |
# |  IInputProcessor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-17 16:48:05
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInputProcessor interface"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional


# ----------------------------------------------------------------------
class IInputProcessor(ABC):
    """Interface for mixins that process input"""

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetInputItems(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        """Returns all input items associated with the provided context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetDisplayName(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> Optional[str]:
        """Returns a name suitable for display given the provided context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def _GenerateMetadataItems(
        self,
        input_root: Path,
        input_items: List[Path],
        user_provided_metadata: Dict[str, Any],
    ) -> Generator[Dict[str, Any], None, None]:
        """Generates metadata items associated with the input items and user-provided content"""
        raise Exception("Abstract method")
