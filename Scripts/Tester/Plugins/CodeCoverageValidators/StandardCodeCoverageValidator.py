# ----------------------------------------------------------------------
# |
# |  StandardCodeCoverageValidator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:40:30
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Standard implementation of code coverage validator."""

import datetime
import time

from pathlib import Path
from typing import Optional

from Common_Foundation.Streams.DoneManager import DoneManager

from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageResult, CodeCoverageValidatorImpl
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class CodeCoverageValidator(CodeCoverageValidatorImpl):
    """Code coverage validator that validates at a specified percentage"""

    # ----------------------------------------------------------------------
    # |  Public Types
    DEFAULT_MIN_CODE_COVERAGE_PERCENTAGE                = 0.70

    # Optional
    PASSING_PERCENTAGE_ATTRIBUTE_NAME                   = "passing_percentage"

    # Generated
    EXPLICIT_PASSING_PERCENTAGE_ATTRIBUTE_NAME          = "explicit_passing_percentage"

    # Read the minimum coverage percentage from this file if it appears anywhere the directory
    # structure of the file being tested. The contents of the file should be a single value that
    # represents the minimum code coverage percentage (0.0 <= N <= 1.0).
    MIN_COVERAGE_PERCENTAGE_FILENAME                    = "MinCodeCoverage.yaml"

    # ----------------------------------------------------------------------
    def __init__(
        self,
        min_coverage_percentage: float=DEFAULT_MIN_CODE_COVERAGE_PERCENTAGE,
    ):
        assert 0.0 <= min_coverage_percentage <= 1.0, min_coverage_percentage

        self._min_coverage_percentage       = min_coverage_percentage

        super(CodeCoverageValidator, self).__init__(
            "Standard",
            "Ensures that the measured code coverage is at least N%.",
        )

    # ----------------------------------------------------------------------
    @classmethod
    def GetCustomCommandLineArgs(cls) -> TyperEx.TypeDefinitionsType:
        return {
            cls.PASSING_PERCENTAGE_ATTRIBUTE_NAME: (Optional[float], dict(min=0.0, max=1.0)),
        }

    # ----------------------------------------------------------------------
    def Validate(
        self,
        dm: DoneManager,
        filename: Path,
        measured_coverage: float,
    ) -> CodeCoverageResult:
        min_coverage = self._min_coverage_percentage

        start_time = time.perf_counter()

        # Look for a configuration file
        for parent in filename.parents:
            potential_filename = parent / self.__class__.MIN_COVERAGE_PERCENTAGE_FILENAME
            if potential_filename.exists():
                with potential_filename.open() as f:
                    content = f.read().strip()

                try:
                    content = float(content)
                except ValueError:
                    dm.WriteWarning("The minimum code coverage percentage in '{}' is not a valid float value.".format(potential_filename))
                    continue

                if content < 0.0 or content > 1.0:
                    dm.WriteWarning("The minimum code coverage percentage in '{}' is not between 0.0 and 1.0.".format(potential_filename))
                    continue

                min_coverage = content
                break

        return CodeCoverageResult(
            datetime.timedelta(seconds=time.perf_counter() - start_time),
            measured_coverage,
            min_coverage,
        )
