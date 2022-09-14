# ----------------------------------------------------------------------
# |
# |  IInvocation.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 08:59:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInvocation object"""

from abc import abstractmethod, ABC
from typing import Any, Callable, Dict, Optional

from Common_Foundation.Streams.DoneManager import DoneManager

from ..InvocationQueryMixins.IInvocationQuery import InvokeReason


# ----------------------------------------------------------------------
class IInvocation(ABC):
    """Interface for invocation mixin objects"""

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _GetNumStepsImpl(
        context: Dict[str, Any],
    ) -> int:
        """\
        Return the number of steps involved in compiling the provided context.

        This information is used to create progress bars and other visual indicators of progress
        and should be implemented by derived classes if it is possible to extract more information.
        """
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _InvokeImpl(
        invoke_reason: InvokeReason,
        dm: DoneManager,
        context: Dict[str, Any],
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Optional[str]:                     # Optional short description that provides info about the result
        """Invokes the compiler functionality"""
        raise Exception("Abstract method")
