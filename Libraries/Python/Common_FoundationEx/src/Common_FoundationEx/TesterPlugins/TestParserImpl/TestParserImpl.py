# ----------------------------------------------------------------------
# |
# |  TestParserImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 21:51:03
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TestParserImpl object"""

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from Common_Foundation.Types import extensionmethod

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.CompilerImpl.Mixins.InputProcessorMixins.AtomicInputProcessorMixin import AtomicInputProcessorMixin
from Common_FoundationEx.CompilerImpl.Mixins.InputProcessorMixins.IndividualInputProcessorMixin import IndividualInputProcessorMixin
from Common_FoundationEx import TyperEx

from .Results import TestResult


# ----------------------------------------------------------------------
class TestParserImpl(ABC):
    """Abstract base class for objects able to consume and interpret test execution results."""

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        name: str,
        description: str,
    ):
        self.name                           = name
        self.description                    = description

    # ----------------------------------------------------------------------
    @extensionmethod
    def ValidateEnvironment(self) -> Optional[str]:
        """\
        Opportunity to validate that a test parser can be run in the current environment.

        Overload this method when a test parser will never be successful when running in
        a specific environment (for example, trying to run a Windows test parser in a Linux
        environment).

        Return None if the environment is valid or a string that describes why the
        current environment is invalid for this test parser.
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
        command_line: str,                  # pylint: disable=unused-argument
        compiler: CompilerImpl,             # pylint: disable=unused-argument
        compiler_context: Dict[str, Any],   # pylint: disable=unused-argument
    ) -> Optional[int]:
        """\
        Returns the number of steps to be executed by the test itself.This information is not
        required and only serves to create a more fluid user experience.
        """

        # This information isn't available by default
        return None

    # ----------------------------------------------------------------------
    @extensionmethod
    def CreateInvokeCommandLine(
        self,
        compiler: CompilerImpl,             # pylint: disable=unused-argument
        context: Dict[str, Any],
        *,
        debug_on_error: bool=False,         # pylint: disable=unused-argument
    ) -> str:
        """Returns a command line used to invoke the test execution engine for the given context."""

        single_input = context.get(IndividualInputProcessorMixin.ATTRIBUTE_NAME, None)
        if single_input is not None:
            return str(single_input)

        multiple_inputs = context.get(AtomicInputProcessorMixin.ATTRIBUTE_NAME, None)
        if multiple_inputs is not None:
            assert isinstance(multiple_inputs, list)
            assert multiple_inputs

            return str(multiple_inputs[0])

        raise Exception("Unknown input")

    # ----------------------------------------------------------------------
    @abstractmethod
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
        """Parses the given data looking for signs of successful execution."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @extensionmethod
    def RemoveTemporaryArtifacts(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        """Remove any additional artifacts once test execution is complete"""

        # By default, nothing to remove
        pass
