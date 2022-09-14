# ----------------------------------------------------------------------
# |
# |  Results.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 13:31:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Results produced during the code coverage validation process"""

import datetime

from dataclasses import dataclass, field
from typing import Optional


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CodeCoverageResult(object):
    """Code coverage result"""

    # ----------------------------------------------------------------------
    execution_time: datetime.timedelta

    coverage_percentage: float
    minimum_percentage: float

    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.coverage_percentage >= 0.0 and self.coverage_percentage <= 1.0, self.coverage_percentage
        assert self.minimum_percentage >= 0.0 and self.minimum_percentage <= 1.0, self.minimum_percentage

        result = 0 if self.coverage_percentage > self.minimum_percentage else -1

        object.__setattr__(self, "result", result)
        object.__setattr__(
            self,
            "short_desc",
            "{:.02f}% {} {:.02f}%".format(
                self.coverage_percentage * 100,
                ">=" if result == 0 else "<",
                self.minimum_percentage * 100,
            ),
        )
