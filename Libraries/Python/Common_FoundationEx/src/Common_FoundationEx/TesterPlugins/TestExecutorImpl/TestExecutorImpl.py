# ----------------------------------------------------------------------
# |
# |  TestExecutorImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:01:26
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TestExecutorImpl object"""

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import extensionmethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx import TyperEx

from .Results import ExecuteResult


# ----------------------------------------------------------------------
class TestExecutorImpl(ABC):
    """\
    Abstract base class for objects that are able to execute a test and potentially extract code
    coverage information from the results.
    """

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        name: str,
        description: str,
        *,
        is_code_coverage_executor: bool,
    ):
        self.name                           = name
        self.description                    = description
        self.is_code_coverage_executor      = is_code_coverage_executor

    # ----------------------------------------------------------------------
    @extensionmethod
    def ValidateEnvironment(self) -> Optional[str]:
        """\
        Opportunity to validate that a test executor can be run in the current environment.

        Overload this method when a test executor will never be successful when running in
        a specific environment (for example, trying to run a Windows compiler in a Linux
        environment).

        Return None if the environment is valid or a string that describes why the
        current environment is invalid for this test executor.
        """

        # Do nothing by default
        return None

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return type annotations for any arguments that can be provided on the command line"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def IsSupportedCompiler(
        self,
        compiler: CompilerImpl,
    ) -> bool:
        """Returns True if the compiler produces results that can be consumed by this test parser."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def IsSupportedTestItem(
        self,
        item: Path,
    ) -> bool:
        """Returns True if the test parser is able to process this test item."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @extensionmethod
    def GetNumSteps(
        self,
        compiler: CompilerImpl,             # pylint: disable=unused-argument
        compiler_context: Dict[str, Any],   # pylint: disable=unused-argument
    ) -> Optional[int]:
        """\
        Returns the number of steps to be executed by the test itself. Return None if this information
        cannot be extracted by the executor.
        """

        # This information isn't available by default
        return None

    # ----------------------------------------------------------------------
    @abstractmethod
    def Execute(
        self,
        dm: DoneManager,                    # Writes to file
        compiler: CompilerImpl,
        context: Dict[str, Any],
        command_line: str,
        on_progress_func: Callable[         # UX status updates
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Tuple[
        ExecuteResult,
        str,                                # Execute output
    ]:
        """\
        Executes a test and returns the results.

        This method signature is complicated out of necessity; here is how the moving pieces work together:

            dm:                             Writes to a file; wrapped in a DoneManager for easier scoped-semantics (e.g. "DONE! suffixes").
            on_progress_func:               Updated a progress bar, but is not persisted.
            Execute output return value:    Data that will be parsed by an object derived from `TestParserImpl` to determine test results. This content
                                            will also be written to the file associated with `dm`.
        """
        raise Exception("Abstract method")
