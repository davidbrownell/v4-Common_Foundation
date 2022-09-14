# ----------------------------------------------------------------------
# |
# |  NoOutputMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:36:27
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the NoOutputMixin object"""

from pathlib import Path
from typing import Any, Dict, List, TextIO

from Common_Foundation.Streams.DoneManager import DoneManager

from .IOutput import IOutput


# ----------------------------------------------------------------------
class NoOutputMixin(IOutput):
    """Mixin for compilers that don't generate any output"""

    # ----------------------------------------------------------------------
    @staticmethod
    def GetOutputItems(
        metadata_or_context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> List[Path]:
        return []

    # ----------------------------------------------------------------------
    @staticmethod
    def Clean(
        dm: DoneManager,                    # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> None:
        # Nothing to do here
        pass
