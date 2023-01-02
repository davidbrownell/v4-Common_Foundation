# ----------------------------------------------------------------------
# |
# |  ExecuteResult.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:02:56
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ExecuteResult object"""

import datetime

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CoverageResult(object):
    """Results associated with a code coverage extraction"""

    # ----------------------------------------------------------------------
    result: int
    execution_time: datetime.timedelta

    short_desc: Optional[str]

    coverage_data_filename: Optional[Path]

    coverage_percentage: Optional[float]
    coverage_percentages: Optional[
        Dict[
            str,                            # module/component name
            Union[
                float,                      # percentage
                Tuple[float, str],          # percentage and short desc
            ],
        ]
    ]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        # ----------------------------------------------------------------------
        def IsValidPercentage(
            value: float,
        ) -> bool:
            return value >= 0.0 and value <= 1.0

        # ----------------------------------------------------------------------

        if self.result == 0:
            assert self.coverage_data_filename is not None and self.coverage_data_filename.exists(), self.coverage_data_filename
            assert self.coverage_percentage is not None and IsValidPercentage(self.coverage_percentage), self.coverage_percentage
            assert (
                self.coverage_percentages is None
                or all(
                    IsValidPercentage(value[0] if isinstance(value, tuple) else value)
                    for value in self.coverage_percentages.values()
                )
            ), self.coverage_percentages

            assert self.coverage_data_filename is None or self.coverage_data_filename.exists(), self.coverage_data_filename

        else:
            assert self.coverage_percentage is None
            assert self.coverage_data_filename is None
            assert self.coverage_percentages is None


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ExecuteResult(object):
    """Results associated with a test execution"""

    # ----------------------------------------------------------------------
    result: int
    execution_time: datetime.timedelta

    short_desc: Optional[str]

    coverage_result: Optional[CoverageResult]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        if self.coverage_result and self.coverage_result.result != 0 and self.result == 0:
            object.__setattr__(self, "result", self.coverage_result.result)
