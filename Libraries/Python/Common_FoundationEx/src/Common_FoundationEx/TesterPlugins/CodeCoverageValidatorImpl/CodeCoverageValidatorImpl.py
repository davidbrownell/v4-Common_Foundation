# ----------------------------------------------------------------------
# |
# |  CodeCoverageValidatorImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:30:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeCoverageValidatorImpl object"""

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Optional

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import extensionmethod

from Common_FoundationEx import TyperEx

from .Results import CodeCoverageResult


# ----------------------------------------------------------------------
class CodeCoverageValidatorImpl(ABC):
    """Abstract base class for objects that are able to validate code coverage results"""

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
        Opportunity to validate that a code coverage validator can be run in the current environment.

        Overload this method when a code coverage validator will never be successful when running in
        a specific environment (for example, trying to run a Windows code coverage validator in a Linux
        environment).

        Return None if the environment is valid or a string that describes why the
        current environment is invalid for this code coverage validator.
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
    def Validate(
        self,
        dm: DoneManager,
        filename: Path, # This can be used to find filename that indicate the min passing percentage
        measured_coverage: float,
    ) -> CodeCoverageResult:
        """Validates that the measured coverage meets expectations"""
        raise Exception("Abstract method")
