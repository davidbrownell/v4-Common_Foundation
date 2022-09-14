# ----------------------------------------------------------------------
# |
# |  BenchmarkStat.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 21:38:40
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains results produced by TestParserImpl objects"""

import datetime

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class SubtestResult(object):
    """Fine-grained result that may be produced when running tests"""

    # ----------------------------------------------------------------------
    result: int
    execution_time: datetime.timedelta


# ----------------------------------------------------------------------
class Units(str, Enum):
    Nanoseconds                             = "ns"
    Macroseconds                            = "us"
    Milliseconds                            = "ms"
    Seconds                                 = "s"


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class BenchmarkStat(object):
    """A single benchmark result"""

    # ----------------------------------------------------------------------
    name: str
    source_filename: Path
    source_line: int
    extractor: str
    min_value: float
    max_value: float
    mean_value: float
    standard_deviation: float
    samples: int
    units: Units
    iterations: int

    # ----------------------------------------------------------------------
    @staticmethod
    def ConvertTime(
        value: int,
        current_units: Units,
        dest_units: Units,
    ) -> int:
        if current_units == dest_units:
            return value

        if current_units == Units.Seconds:
            value *= 1000
            current_units = Units.Milliseconds

        if current_units == Units.Milliseconds:
            value *= 1000
            current_units = Units.Macroseconds

        if current_units == Units.Macroseconds:
            value *= 1000
            current_units = Units.Nanoseconds

        assert current_units == Units.Nanoseconds, current_units

        if dest_units == Units.Nanoseconds:
            return value

        value //= 1000
        if dest_units == Units.Macroseconds:
            return value

        value //= 1000
        if dest_units == Units.Milliseconds:
            return value

        value //= 1000

        assert dest_units == Units.Seconds, dest_units
        return value


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TestResult(object):
    """Result produced when running a test"""

    # ----------------------------------------------------------------------
    result: int
    execution_time: datetime.timedelta

    short_desc: Optional[str]

    subtest_results: Optional[Dict[str, SubtestResult]]

    benchmarks: Optional[List[BenchmarkStat]]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.subtest_results is None or self.subtest_results
        assert self.benchmarks is None or self.benchmarks
