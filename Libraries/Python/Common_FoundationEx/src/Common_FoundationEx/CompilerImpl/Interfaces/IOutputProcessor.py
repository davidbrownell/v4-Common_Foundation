# ----------------------------------------------------------------------
# |
# |  IOutputProcessor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-17 17:03:38
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IOutputProcessor object"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, TextIO

from Common_Foundation.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
class IOutputProcessor(ABC):
    """Interface for mixins that have knowledge about output files generated during compilation"""

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetOutputItems(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        """Returns output items associated with the provided metadata/context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def Clean(
        self,
        dm: DoneManager,                    # Status information generated with the process is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        """Handles the specifics of cleaning previously generated content"""
        raise Exception("Abstract method")
