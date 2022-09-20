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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    @staticmethod
    @extensionmethod
    def ValidateEnvironment() -> Optional[str]:
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
    @staticmethod
    @abstractmethod
    def GetCustomCommandLineArgs() -> TyperEx.TypeDefinitionsType:
        """Return type annotations for any arguments that can be provided on the command line"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def IsSupportedCompiler(
        compiler: CompilerImpl,
    ) -> bool:
        """Returns True if the compiler produces results that can be consumed by this test parser."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @extensionmethod
    def GetNumSteps(
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
    @staticmethod
    @abstractmethod
    def Execute(
        dm: DoneManager,
        compiler: CompilerImpl,
        context: Dict[str, Any],
        command_line: str,
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        includes: Optional[List[str]]=None,
        excludes: Optional[List[str]]=None,
    ) -> Tuple[ExecuteResult, str]:
        """Executes a test and returns the results"""
        raise Exception("Abstract method")
