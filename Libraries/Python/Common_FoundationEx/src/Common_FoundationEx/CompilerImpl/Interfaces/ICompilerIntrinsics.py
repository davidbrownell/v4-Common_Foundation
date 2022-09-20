# ----------------------------------------------------------------------
# |
# |  ICompilerIntrinsics.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-17 16:43:45
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ICompilerIntrinsics interface"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Generator, List, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
class ICompilerIntrinsics(ABC):
    """Interface for a compiler and mixins"""

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        """\
        Metadata that should be applied to generated context items if it doesn't already exist.
        """
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        """Names that must be a part of generated metadata."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _GetRequiredContextNames(self) -> List[str]:
        """Names that must be a part of generated context."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Returns a context object tuned specifically for the metadata provided."""
        raise Exception("Abstract method")
