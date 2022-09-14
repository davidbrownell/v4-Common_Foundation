# ----------------------------------------------------------------------
# |
# |  IOutput.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:03:36
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IOutput object"""

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, Dict, List, TextIO

from Common_Foundation.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
class IOutput(ABC):
    """Interface for output mixin objects"""

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def GetOutputItems(
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        """Returns output items associated with the provided metadata/context"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def Clean(
        dm: DoneManager,                    # Status information while the program is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        """Handles the specific of cleaning previously generated output"""
        raise Exception("Abstract method")
