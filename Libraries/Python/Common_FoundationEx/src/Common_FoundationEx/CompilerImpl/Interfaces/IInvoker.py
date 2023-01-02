# ----------------------------------------------------------------------
# |
# |  IInvoker.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-17 16:52:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInvoker object"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

from Common_Foundation.Streams.DoneManager import DoneManager

from .IInvocationQuery import InvokeReason


# ----------------------------------------------------------------------
class IInvoker(ABC):
    """Interface for mixins that invoke functionality on a context"""

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],
    ) -> int:
        """\
        Return the number of display steps invoked in compiling the provided context.

        This information is used to create progress bars and other visual indicators
        of progress.
        """
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _InvokeImpl(
        self,
        invoke_reason: InvokeReason,
        dm: DoneManager,
        context: Dict[str, Any],
        on_progress_func: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, false to terminate
        ],
    ) -> Optional[str]:                     # Optional short description that provides input about the result
        """Invokes the compiler functionality"""
        raise Exception("Abstract method")
