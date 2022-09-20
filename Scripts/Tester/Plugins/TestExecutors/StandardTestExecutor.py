# ----------------------------------------------------------------------
# |
# |  StandardTestExecutor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:59:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Standard test executor which executes the command line that it is given."""

import datetime
import time

from typing import Any, Callable, Dict, List, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import ExecuteResult, TestExecutorImpl
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class TestExecutor(TestExecutorImpl):
    """Executor that invokes tests via the provided command line but doesn't generate code coverage information."""

    # ----------------------------------------------------------------------
    def __init__(self):
        super(TestExecutor, self).__init__(
            "Standard",
            "Executes the test without extracting code coverage information.",
            is_code_coverage_executor=False,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedCompiler(
        self,
        compiler: CompilerImpl,
    ) -> bool:
        return True

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,                                # pylint: disable=unused-argument
        compiler: CompilerImpl,                         # pylint: disable=unused-argument
        context: Dict[str, Any],                        # pylint: disable=unused-argument
        command_line: str,
        on_progress: Callable[..., Any],                # pylint: disable=unused-argument
        includes: Optional[List[str]]=None,             # pylint: disable=unused-argument
        excludes: Optional[List[str]]=None,             # pylint: disable=unused-argument
    ) -> Tuple[ExecuteResult, str]:
        start_time = time.perf_counter()

        result = SubprocessEx.Run(command_line)

        return (
            ExecuteResult(
                result.returncode,
                datetime.timedelta(seconds=time.perf_counter() - start_time),
                None,
                None,
            ),
            result.output,
        )
