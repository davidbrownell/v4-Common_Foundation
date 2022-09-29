# ----------------------------------------------------------------------
# |
# |  PythonUnittestTestParser.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 07:53:58
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the PythonUnittestTestParser object"""

import datetime
import re
import time

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl, TestResult
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class TestParser(TestParserImpl):
    """\
    Test parser that runs python files and looks at the process exit code to determine if a test
    passed or failed.
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        super(TestParser, self).__init__("PythonUnittest", "Parses python unittest output.")

        self._failure_regex                 = re.compile(
            r"""(?#
            Start of line                   )^(?#
            FAILED                          )FAILED\s+(?#
            Num Failures                    )\(failures=(?P<failures>\d+)\)(?#
            )""",
            re.MULTILINE,
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
        return compiler.IsSupported(Path(__file__))

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedTestItem(
        self,
        item: Path,
    ) -> bool:
        return (
            item.is_file()
            and item.suffix == ".py"
            and "import unittest" in item.open().read()
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def CreateInvokeCommandLine(
        self,
        compiler: CompilerImpl,
        context: Dict[str, Any],
        *,
        debug_on_error: bool = False,
    ) -> str:
        return 'python "{}"'.format(
            super(TestParser, self).CreateInvokeCommandLine(
                compiler,
                context,
                debug_on_error=debug_on_error,
            ),
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Parse(
        self,
        compiler: CompilerImpl,
        compiler_context: Dict[str, Any],
        test_data: str,
        on_progress_func: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> TestResult:
        start_time = time.perf_counter()

        result: Optional[int] = None
        short_desc: Optional[str] = None

        match = self._failure_regex.search(test_data)
        if match is not None:
            result = -1
            short_desc = inflect.no("failure", int(match.group("failures")))

        elif test_data.rstrip().endswith("OK"):
            result = 0

        else:
            result = 1

        assert result is not None

        return TestResult(
            result,
            datetime.timedelta(seconds=time.perf_counter() - start_time),
            short_desc,
            None,
            None,
        )
