# ----------------------------------------------------------------------
# |
# |  CommandLineInvocationMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:29:24
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CommandLineInvocationMixin object"""

from abc import abstractmethod
from typing import Any, Callable, Dict, Optional

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx

from .IInvocation import IInvocation
from ..ICompilerImpl import InvokeReason


# ----------------------------------------------------------------------
class CommandLineInvocationMixin(IInvocation):
    """Implements invocation by invoking a command line"""

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def CreateInvokeCommandLine(
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> str:
        """Create the command line to be invoked"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _GetNumStepsImpl(
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> int:
        return 1

    # ----------------------------------------------------------------------
    @classmethod
    def _InvokeImpl(
        cls,
        invoke_reason: InvokeReason,  # pylint: disable=unused-argument
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
        with dm.Nested("Creating command line...") as command_line_dm:
            command_line = cls.CreateInvokeCommandLine(command_line_dm, context)

        on_progress(0, "Running")
        with dm.Nested(
            "Invoking '{}'...".format(command_line),
        ) as invoke_dm:
            # TODO: This should stream output

            result = SubprocessEx.Run(command_line)

            invoke_dm.result = result.returncode
            invoke_dm.WriteLine(result.output)

            return None
