# ----------------------------------------------------------------------
# |
# |  SimplePythonTestParser.py
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
"""Contains the SimplePythonTestParser object"""

import datetime
import os
import sys

from pathlib import Path
from typing import Any, Dict

from Common_Foundation.ContextlibEx import ExitStack

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl, TestResult
from Common_FoundationEx import TyperEx


sys.path.insert(0, str(Path(__file__).parent.parent / "Compilers"))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from SimplePythonVerifier import Verifier as SimplePythonVerifier  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
class TestParser(TestParserImpl):
    """\
    Test parser that runs python files and looks at the process exit code to determine if a test
    passed or failed.

    This test parser exists to demonstrate the capabilities of Tester and should not be used with
    any real code. A real Python test parser is available as part of the `Common_PythonDevelopment`
    repository, available at `https://github.com/davidbrownell/v4-Common_PythonDevelopment`.
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        super(TestParser, self).__init__(
            "SimplePython",
            "Sample Test Parser intended to demonstrate the capabilities of Tester; DO NOT USE with real workloads.",
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def GetCustomCommandLineArgs() -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    @staticmethod
    def IsSupportedCompiler(
        compiler: CompilerImpl,
    ) -> bool:
        return isinstance(compiler, SimplePythonVerifier)

    # ----------------------------------------------------------------------
    @staticmethod
    def IsSupportedTestItem(
        item: Path,
    ) -> bool:
        return item.is_file() and item.suffix == ".py"

    # ----------------------------------------------------------------------
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
    @staticmethod
    def Parse(*args, **kwargs) -> TestResult:  # pylint: disable=unused-argument
        # Nothing to do here, as the test is successful if the process exited successfully.
        # If here, it exited successfully.
        return TestResult(
            0,
            datetime.timedelta(),
            None,
            None,
            None,
        )
