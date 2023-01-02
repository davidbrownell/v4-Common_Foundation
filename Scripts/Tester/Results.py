# ----------------------------------------------------------------------
# |
# |  Results.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-01 12:37:02
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains result types"""

import datetime
import itertools

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageResult
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import ExecuteResult
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl, TestResult as ParseResult

# Convenience imports
from Common_FoundationEx.TesterPlugins.TestParserImpl import BenchmarkStat  # pylint: disable=unused-import


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class BuildResult(object):
    """Result generated from a build"""

    result: int
    execution_time: datetime.timedelta      # Includes time spent configuring, waiting, etc
    log_filename: Path

    short_desc: Optional[str]

    build_execution_time: datetime.timedelta
    output_dir: Path
    binary: Path


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TestIterationResult(object):
    execute_result: ExecuteResult
    parse_result: ParseResult

    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)
    total_time: datetime.timedelta          = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        # ----------------------------------------------------------------------
        def GetInfo() -> Tuple[int, Optional[str], datetime.timedelta]:
            total_time = datetime.timedelta()

            total_time += self.execute_result.execution_time
            if self.parse_result is not None:
                total_time += self.parse_result.execution_time

            if self.execute_result.result < 0:
                return (
                    self.execute_result.result,
                    self.execute_result.short_desc or "Test execution failure",
                    total_time,
                )
            elif self.parse_result and self.parse_result.result < 0:
                return (
                    self.parse_result.result,
                    self.parse_result.short_desc or "Test extraction failure",
                    total_time,
                )
            elif self.execute_result.result > 0:
                return (
                    self.execute_result.result,
                    self.execute_result.short_desc or "Test execution warning",
                    total_time,
                )
            elif self.parse_result and self.parse_result.result > 0:
                return (
                    self.parse_result.result,
                    self.parse_result.short_desc or "Test extraction warning",
                    total_time,
                )

            assert self.parse_result
            return self.parse_result.result, self.parse_result.short_desc, total_time

        # ----------------------------------------------------------------------

        result, short_desc, total_time = GetInfo()

        object.__setattr__(self, "result", result)
        object.__setattr__(self, "short_desc", short_desc)
        object.__setattr__(self, "total_time", total_time)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TestResult(object):
    """Result of executing one or more tests for a specific configuration"""

    execution_time: datetime.timedelta

    test_results: List[TestIterationResult]
    has_multiple_iterations: bool           = field(kw_only=True)

    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)
    average_time: datetime.timedelta        = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.test_results

        # ----------------------------------------------------------------------
        def GetInfo() -> Tuple[int, Optional[str], datetime.timedelta]:
            average_time = datetime.timedelta()

            success_info: Optional[Tuple[int, Optional[str]]] = None
            error_info: Optional[Tuple[int, Optional[str]]] = None
            warning_info: Optional[Tuple[int, Optional[str]]] = None

            for result in self.test_results:
                average_time += result.total_time

                if result.result < 0 and error_info is None:
                    error_info = result.result, result.short_desc
                elif result.result > 0 and warning_info is None:
                    warning_info = result.result, result.short_desc
                elif result.result == 0 and success_info is None:
                    success_info = result.result, result.short_desc

            average_time /= len(self.test_results)

            if error_info:
                return error_info[0], error_info[1], average_time
            if warning_info:
                return warning_info[0], warning_info[1], average_time
            if success_info:
                return success_info[0], success_info[1], average_time

            return 0, None, average_time

        # ----------------------------------------------------------------------

        info = GetInfo()

        object.__setattr__(self, "result", info[0])
        object.__setattr__(self, "short_desc", info[1])
        object.__setattr__(self, "average_time", info[2])


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ConfigurationResult(object):
    """Build, test, and coverage results"""

    configuration: str
    output_dir: Path
    log_filename: Path

    compiler_name: str
    test_execution_name: str
    test_parser_name: str
    code_coverage_validator_name: Optional[str]

    build_result: Optional[BuildResult]
    test_result: Optional[TestResult]
    coverage_result: Optional[CodeCoverageResult]

    has_multiple_iterations: bool

    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)
    average_time: datetime.timedelta        = field(init=False)
    execution_time: datetime.timedelta      = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.build_result is None or self.test_result is None or self.build_result.result == 0
        assert self.build_result is None or self.coverage_result is None or self.build_result.result == 0
        assert self.build_result is None or self.coverage_result is None or self.code_coverage_validator_name

        # ----------------------------------------------------------------------
        def GetInfo() -> Tuple[
            int,
            Optional[str],
            datetime.timedelta,
            datetime.timedelta,
        ]:
            # Get the average and total times
            if self.build_result is None:
                average_time = datetime.timedelta()
                total_time = datetime.timedelta()
            else:
                average_time = self.build_result.execution_time
                total_time = self.build_result.execution_time

            if self.test_result is not None:
                if isinstance(self.test_result, TestResult):
                    average_time += self.test_result.average_time

                total_time += self.test_result.execution_time

            if self.coverage_result is not None:
                average_time += self.coverage_result.execution_time
                total_time += self.coverage_result.execution_time

            warning_info: Optional[Tuple[int, Optional[str]]] = None
            success_desc: Optional[str] = None

            for result in itertools.chain(
                [self.build_result, ] if self.build_result else [],
                [self.test_result, ] if self.test_result else [],
                [self.coverage_result, ] if self.coverage_result else [],
            ):
                if result.result < 0:
                    return result.result, result.short_desc, average_time, total_time

                if result.result > 0 and warning_info is None:
                    warning_info = result.result, result.short_desc
                elif result.result == 0:
                    success_desc = result.short_desc


            if warning_info is not None:
                return warning_info[0], warning_info[1], average_time, total_time

            return 0, success_desc, average_time, total_time

        # ----------------------------------------------------------------------

        info = GetInfo()

        object.__setattr__(self, "result", info[0])
        object.__setattr__(self, "short_desc", info[1])
        object.__setattr__(self, "average_time", info[2])
        object.__setattr__(self, "execution_time", info[3])


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Result(object):
    """Result of executing a test across multiple configurations"""

    # ----------------------------------------------------------------------
    test_item: Path
    output_dir: Path

    debug: Optional[ConfigurationResult]
    release: Optional[ConfigurationResult]

    # ----------------------------------------------------------------------
    @property
    def result(self) -> int:
        result = 0

        for config_result in [self.debug, self.release]:
            if not config_result:
                continue

            if config_result.result < 0 and result >= 0:
                result = config_result.result
            elif config_result.result > 0 and result == 0:
                result = config_result.result

        return result


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FindResult(object):

    # ----------------------------------------------------------------------
    compiler: CompilerImpl
    test_parser: TestParserImpl
    configurations: Optional[List[str]]
    test_type: str

    path: Path

    is_enabled: bool                        = field(kw_only=True)
