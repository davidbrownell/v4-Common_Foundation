# ----------------------------------------------------------------------
# |
# |  CommandLineInvokerMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:25:16
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CommandLineInvoker object"""

from abc import abstractmethod
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from ...Interfaces.ICompilerIntrinsics import ICompilerIntrinsics
from ...Interfaces.IInvocationQuery import InvokeReason
from ...Interfaces.IInvoker import IInvoker


# ----------------------------------------------------------------------
class CommandLineInvokerMixin(
    ICompilerIntrinsics,
    IInvoker,
):
    """Mixin for compilers that invoke functionality by running an external command via the command line"""

    # ----------------------------------------------------------------------
    @abstractmethod
    def CreateInvokeCommandLine(
        self,
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> str:
        """Return the command line to be invoked"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> int:
        return 1

    # ----------------------------------------------------------------------
    @overridemethod
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
        with dm.Nested("Creating command line...") as command_line_dm:
            command_line = self.CreateInvokeCommandLine(command_line_dm, context)

        on_progress_func(0, "Running")
        with dm.Nested(
            "Invoking '{}'...".format(command_line),
        ) as invoke_dm:
            with invoke_dm.YieldStream() as stream:
                invoke_dm.result = SubprocessEx.Stream(command_line, stream)

            return None

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(CommandLineInvokerMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(CommandLineInvokerMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(CommandLineInvokerMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return super(CommandLineInvokerMixin, self)._CreateContext(dm, metadata)
