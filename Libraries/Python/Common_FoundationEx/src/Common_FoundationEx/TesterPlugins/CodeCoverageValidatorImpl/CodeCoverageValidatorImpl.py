# ----------------------------------------------------------------------
# |
# |  CodeCoverageValidatorImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:30:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeCoverageValidatorImpl object"""

from abc import abstractmethod, ABC
from pathlib import Path

from Common_Foundation.Streams.DoneManager import DoneManager
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
