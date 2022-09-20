# ----------------------------------------------------------------------
# |
# |  ExecuteTests.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-01 12:04:11
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Implements functionality to execute tests"""

import multiprocessing
import socket
import textwrap
import threading
import time
import traceback

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, cast, Dict, Generator, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

from rich.progress import Progress, TaskID

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import JsonEx
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.CompilerImpl.Compiler import Compiler
from Common_FoundationEx.CompilerImpl.Verifier import Verifier
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageValidatorImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import TestExecutorImpl
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl

from Results import BenchmarkStat, BuildResult, CodeCoverageResult, ConfigurationResult, ErrorResult, ExecuteResult, Result, TestIterationResult, TestResult


# ----------------------------------------------------------------------
class ExecuteTests(object):
    """Container for the parameters so we don't need to continually pass them around"""

    CATASTROPHIC_TASK_FAILURE_RESULT        = -123456789

    # ----------------------------------------------------------------------
    @classmethod
    def Execute(
        cls,
        dm: DoneManager,
        test_items: List[Path],
        output_dir: Path,
        compiler: CompilerImpl,
        test_parser: TestParserImpl,
        test_executor: TestExecutorImpl,
        code_coverage_validator: Optional[CodeCoverageValidatorImpl],
        metadata: Dict[str, Any],
        *,
        parallel_tests: Optional[bool],
        single_threaded: bool,
        iterations: int,
        continue_iterations_on_error: bool,
        debug_only: bool,
        release_only: bool,
        build_only: bool,
        skip_build: bool,
        quiet: bool,
        junit_xml_output_filename: Optional[str],
    ) -> List[Result]:
        # Check for compatible plugins
        result = compiler.ValidateEnvironment()
        if result is not None:
            raise Exception(
                textwrap.dedent(
                    """\
                    The compiler '{}' does not support the current environment.

                    {}
                    """,
                ).format(compiler.name, TextwrapEx.Indent(result.rstrip(), 4)),
            )

        result = test_executor.ValidateEnvironment()
        if result is not None:
            raise Exception(
                textwrap.dedent(
                    """\
                    The test parser '{}' does not support the current environment.

                    {}
                    """,
                ).format(test_parser.name, TextwrapEx.Indent(result.rstrip(), 4)),
            )

        if not test_parser.IsSupportedCompiler(compiler):
            raise Exception("The test parser '{}' does not support the compiler '{}'.".format(test_parser.name, compiler.name))

        if not test_executor.IsSupportedCompiler(compiler):
            raise Exception("The test executor '{}' does not support the compiler '{}'.".format(test_executor.name, compiler.name))

        if skip_build and not isinstance(compiler, Verifier):
            raise Exception("The build can only be skipped for compilers that act as verifiers.")

        if debug_only and release_only:
            raise Exception("Debug only and Release only are mutually exclusive options.")

        # Update flags for code coverage builds
        if code_coverage_validator is not None:
            parallel_tests = False

            if isinstance(compiler, Compiler):
                debug_only = True
                release_only = False

        # Prepare the working data
        output_dir.mkdir(parents=True, exist_ok=True)

        working_data_items: List[ExecuteTests._WorkingData] = []

        with dm.Nested(
            "Preparing data...",
            lambda: "{} to process".format(inflect.no("configuration", len(working_data_items))),
            suffix="\n",
        ) as prep_dm:
            # Prepare the data
            common_path = PathEx.GetCommonPath(*test_items)
            assert common_path is not None

            len_common_path_parts = len(common_path.parts)

            for test_item in test_items:
                if not compiler.IsSupported(test_item):
                    prep_dm.WriteVerbose("'{}' is not supported by the compiler '{}'.\n".format(test_item, compiler.name))
                    continue

                if not compiler.IsSupportedTestItem(test_item):
                    prep_dm.WriteVerbose("'{}' is not a supported test item for the compiler '{}'.\n".format(test_item, compiler.name))
                    continue

                if not test_parser.IsSupportedTestItem(test_item):
                    prep_dm.WriteVerbose("'{}' is not a supported test item for the test parser '{}'.\n".format(test_item, test_parser.name))
                    continue

                assert len(test_item.parts) > len_common_path_parts, (test_item, common_path)
                display_name_template = "{} ({{}})".format(Path(*test_item.parts[len_common_path_parts:]))

                # Create a suitable output dir
                this_output_dir = output_dir / CurrentShell.ScrubFilename(
                    "_".join(test_item.parts[len_common_path_parts:]),
                    replace_char="-",
                )

                # Create the contexts and working data
                debug_context: Optional[ExecuteTests._WorkingDataContext] = None
                release_context: Optional[ExecuteTests._WorkingDataContext] = None

                if not isinstance(compiler, Compiler):
                    if release_only:
                        prep_dm.WriteVerbose(
                            "The Debug configuration for '{}' will not be processed due to command line options.\n".format(
                                test_item,
                            ),
                        )
                    else:
                        debug_context = cls._WorkingDataContext(
                            display_name_template.format("Debug"),
                            this_output_dir / "Debug",
                        )

                else:
                    if debug_only:
                        prep_dm.WriteVerbose(
                            "The Release configuration for '{}' will not be processed due to command line options.\n".format(
                                test_item,
                            ),
                        )
                    else:
                        release_context = cls._WorkingDataContext(
                            display_name_template.format("Release"),
                            this_output_dir / "Release",
                        )

                if debug_context or release_context:
                    working_data_items.append(
                        cls._WorkingData(test_item, this_output_dir, debug_context, release_context),
                    )

        if not working_data_items:
            return []

        tester = cls(
            dm,
            common_path,
            working_data_items,
            compiler,
            test_parser,
            test_executor,
            code_coverage_validator,
            metadata,
            parallel_tests=parallel_tests,
            single_threaded=single_threaded,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=quiet,
        )

        # Prepare the output dirs
        for task_data in tester._CreateTasks():
            # Prepare the output dir
            if task_data.context.output_dir.is_dir():
                PathEx.RemoveTree(task_data.context.output_dir)

            task_data.context.output_dir.mkdir(parents=True)

        tester._Build()

        if not build_only:
            tester._Test()
            dm.WriteLine("")

        all_results: List[Result] = []

        for working_data in tester._working_items:
            all_results.append(
                Result(
                    working_data.input_item,
                    working_data.debug_context.ToConfigurationResult("Debug", iterations != 1) if working_data.debug_context else None,
                    working_data.release_context.ToConfigurationResult("Release", iterations != 1) if working_data.release_context else None,
                ),
            )

        common_path = PathEx.GetCommonPath(*(result.test_item for result in all_results))

        if all(result.result == 0 for result in all_results):
            tester._CreateBenchmarks(
                dm,
                output_dir / "Benchmarks.json",
                all_results,
                common_path,
            )

        if junit_xml_output_filename:
            tester._CreateJunitResults(
                dm,
                output_dir / junit_xml_output_filename,
                all_results,
                common_path,
            )

        dm.WriteLine("")

        return all_results

    # ----------------------------------------------------------------------
    def __init__(
        self,
        dm: DoneManager,
        common_path: Path,
        working_items: List["ExecuteTests._WorkingData"],
        compiler: CompilerImpl,
        test_parser: TestParserImpl,
        test_executor: TestExecutorImpl,
        code_coverage_validator: Optional[CodeCoverageValidatorImpl],
        compiler_metadata: Dict[str, Any],
        *,
        parallel_tests: Optional[bool],
        single_threaded: bool,
        iterations: int,
        continue_iterations_on_error: bool,
        debug_only: bool,
        release_only: bool,
        build_only: bool,
        skip_build: bool,
        quiet: bool,
    ):
        self._dm                            = dm
        self._common_path                   = common_path
        self._working_items                 = working_items
        self._compiler                      = compiler
        self._test_parser                   = test_parser
        self._test_executor                 = test_executor
        self._code_coverage_validator       = code_coverage_validator
        self._compiler_metadata             = compiler_metadata
        self._parallel_tests                = parallel_tests
        self._single_threaded               = single_threaded
        self._iterations                    = iterations
        self._continue_iterations_on_error  = continue_iterations_on_error
        self._debug_only                    = debug_only
        self._release_only                  = release_only
        self._build_only                    = build_only
        self._skip_build                    = skip_build
        self._quiet                         = quiet

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    @dataclass
    class _WorkingDataContext(object):
        # ----------------------------------------------------------------------
        display_name: str
        output_dir: Path

        compiler_context: Optional[Dict[str, Any]]                          = field(init=False, default=None)

        build_result: Union[None, ErrorResult, BuildResult]                 = field(init=False, default=None)
        test_result: Union[None, ErrorResult, TestResult]                   = field(init=False, default=None)
        coverage_result: Union[None, ErrorResult, CodeCoverageResult]       = field(init=False, default=None)

        # ----------------------------------------------------------------------
        @property
        def has_errors(self) -> bool:
            if self.build_result and self.build_result.result != 0:
                return True

            if self.test_result and self.test_result.result != 0:
                return True

            if self.coverage_result and self.coverage_result.result != 0:
                return True

            return False

        # ----------------------------------------------------------------------
        def GetBuildLogFilename(self) -> Path:
            return self.output_dir / "build.log"

        # ----------------------------------------------------------------------
        def GetTestLogFilename(self) -> Path:
            return self.output_dir / "test.log"

        # ----------------------------------------------------------------------
        def GetTestIterationExecutionLogFilename(
            self,
            iteration: int,
            num_iterations: int,
        ) -> Path:
            if num_iterations == 1:
                filename = "test_execution.log"
            else:
                filename = "test_execution.{:06d}.log".format(iteration + 1)

            return self.output_dir / filename

        # ----------------------------------------------------------------------
        def ToConfigurationResult(
            self,
            configuration: str,
            has_multiple_iterations: bool,
        ) -> ConfigurationResult:
            assert self.build_result is not None
            assert self.test_result is None or (self.build_result and self.build_result.result == 0)
            assert self.coverage_result is None or (self.build_result and self.build_result.result == 0)

            return ConfigurationResult(
                configuration,
                self.output_dir,
                self.build_result,
                self.test_result,
                self.coverage_result,
                has_multiple_iterations,
            )

    # ----------------------------------------------------------------------
    @dataclass
    class _WorkingData(object):
        # ----------------------------------------------------------------------
        input_item: Path
        output_dir: Path

        debug_context: Optional["ExecuteTests._WorkingDataContext"]
        release_context: Optional["ExecuteTests._WorkingDataContext"]

        execution_lock: threading.Lock          = field(init=False, default_factory=threading.Lock)

    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class _TaskData(object):
        # ----------------------------------------------------------------------
        working_data: "ExecuteTests._WorkingData"
        context: "ExecuteTests._WorkingDataContext"
        is_debug_configuration: bool

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _CreateTasks(self) -> List["ExecuteTests._TaskData"]:
        debug_tasks: List[ExecuteTests._TaskData] = []
        release_tasks: List[ExecuteTests._TaskData] = []

        for working_data in self._working_items:
            if (
                not self._release_only
                and working_data.debug_context is not None
                and not working_data.debug_context.has_errors
            ):
                debug_tasks.append(ExecuteTests._TaskData(working_data, working_data.debug_context, True))

            if (
                not self._debug_only
                and working_data.release_context is not None
                and not working_data.release_context.has_errors
            ):
                release_tasks.append(ExecuteTests._TaskData(working_data, working_data.release_context, False))

        return debug_tasks + release_tasks

    # ----------------------------------------------------------------------
    def _Build(self) -> None:
        # ----------------------------------------------------------------------
        def TaskDance(
            task_data: ExecuteTests._TaskData,
        ) -> Any:
            total_start_time = time.perf_counter()
            log_filename = task_data.context.GetBuildLogFilename()

            # Return the log filename and receive the initial progress callback
            initial_progress_func = yield log_filename

            # Create the name of the binary file that may be generated; some
            # plugins use this information to calculate outputs (even if the
            # file itself doesn't exist).
            if isinstance(self._compiler, Verifier):
                binary_filename = task_data.working_data.input_item
            else:
                binary_filename = task_data.context.output_dir / "test_artifact"

                ext = getattr(self._compiler, "binary_extension", None)
                if ext:
                    binary_filename += ext

            # Open the log file and generate the results
            with log_filename.open("w") as f:
                with DoneManager.Create(
                    f,
                    "",
                    line_prefix="",
                    display=False,
                    output_flags=DoneManagerFlags.Create(
                        debug=True,
                    ),
                ) as file_dm:
                    initial_progress_func("Configuring...")

                    # Create the metadata that will be used to create the context item
                    metadata: Dict[str, Any] = {
                        **self._compiler_metadata,
                        **{
                            "debug_build": task_data.is_debug_configuration,
                            "profile_build": bool(self._code_coverage_validator),
                            "output_filename": binary_filename,
                            "output_dir": task_data.context.output_dir,
                            "force": True,
                        },
                    }

                    # Create the context from the metadata
                    object.__setattr__(
                        task_data.context,
                        "compiler_context",
                        self._compiler.GetSingleContextItem(
                            file_dm,
                            task_data.working_data.input_item,
                            metadata,
                        ),
                    )

                    # Return the number of steps and receive the updated progress func
                    if (
                        task_data.context.compiler_context is None
                        or self._skip_build
                        or file_dm.result != 0
                    ):
                        yield 0 # Num steps, receives progress func

                        if task_data.context.compiler_context is None:
                            file_dm.WriteLine("The compiler returned an empty context.")
                            short_desc = "Skipped by the compiler"
                        elif self._skip_build:
                            short_desc = "Skipped via command line"
                        elif file_dm.result != 0:
                            short_desc = "Context generation failed"
                        else:
                            assert False  # pragma: no cover

                        task_data.context.build_result = BuildResult(
                            file_dm.result,
                            timedelta(seconds=time.perf_counter() - total_start_time),
                            log_filename,
                            short_desc if self._skip_build else "{}: {}".format(self._compiler.name, short_desc) if short_desc else "",
                            timedelta(),
                            task_data.context.output_dir,
                            binary_filename,
                        )

                    else:
                        # Return the number of build steps, receive an updated progress func
                        num_steps = self._compiler.GetNumSteps(task_data.context.compiler_context)
                        progress_func = yield num_steps

                        with file_dm.YieldStream() as stream:
                            build_start_time = time.perf_counter()

                            return_value = getattr(
                                self._compiler,
                                self._compiler.invocation_method_name,
                            )(
                                task_data.context.compiler_context,
                                stream,
                                lambda step, status: progress_func(step + 1, status),
                                verbose=self._dm.is_verbose,
                            )

                            if isinstance(return_value, tuple):
                                result, short_desc = return_value
                            else:
                                result = return_value
                                short_desc = None

                        # Remove temporary artifacts
                        self._compiler.RemoveTemporaryArtifacts(task_data.context.compiler_context)

                        now_perf_counter = time.perf_counter()

                        task_data.context.build_result = BuildResult(
                            result,
                            timedelta(seconds=now_perf_counter - total_start_time),
                            log_filename,
                            "{}: {}".format(self._compiler.name, short_desc) if short_desc else "",
                            timedelta(seconds=now_perf_counter - build_start_time),
                            task_data.context.output_dir,
                            binary_filename,
                        )

                    yield (
                        task_data.context.build_result.result,
                        task_data.context.build_result.short_desc,
                    )

        # ----------------------------------------------------------------------
        def OnErrorResult(
            task_data: ExecuteTests._TaskData,
            result: ErrorResult,
        ) -> None:
            assert task_data.context.build_result is None
            task_data.context.build_result = result

        # ----------------------------------------------------------------------
        #
        self._ExecuteTasks("Building", TaskDance, OnErrorResult)

    # ----------------------------------------------------------------------
    def _Test(self) -> None:
        # ----------------------------------------------------------------------
        class CodeCoverageSteps(Enum):
            ValidatingCodeCoverage          = 0

        # ----------------------------------------------------------------------
        class IterationSteps(Enum):
            Executing                       = 0
            RemovingTemporaryArtifacts      = auto()
            ParsingResults                  = auto()

        # ----------------------------------------------------------------------
        def TaskDance(
            task_data: ExecuteTests._TaskData,
        ) -> Any:
            test_log_filename = task_data.context.GetTestLogFilename()

            with test_log_filename.open("w") as f:
                with DoneManager.Create(
                    f,
                    "",
                    line_prefix="",
                    display=False,
                    output_flags=DoneManagerFlags.Create(
                        debug=True,
                    ),
                ) as dm:
                    # Return the log filename and receive the initial progress callback
                    initial_progress_func = yield test_log_filename

                    # Create the command line to invoke the test
                    assert task_data.context.compiler_context is not None

                    initial_progress_func("Creating command line...")
                    command_line = self._test_parser.CreateInvokeCommandLine(
                        self._compiler,
                        task_data.context.compiler_context,
                        debug_on_error=False,
                    )

                    dm.WriteLine("Command line: {}\n\n".format(command_line))

                    # Return the number of steps and get the standard progress callback
                    num_executor_steps = self._test_executor.GetNumSteps(self._compiler, task_data.context.compiler_context) or 0
                    num_parser_steps = self._test_parser.GetNumSteps(command_line, self._compiler, task_data.context.compiler_context) or 0

                    steps_per_iteration = len(IterationSteps) + num_executor_steps + num_parser_steps

                    num_steps = steps_per_iteration * self._iterations
                    if self._code_coverage_validator:
                        num_steps += len(CodeCoverageSteps)

                    progress_func = yield num_steps

                    if self._iterations == 1:
                        # ----------------------------------------------------------------------
                        def ExecutorSingleProgressAdapter(
                            iteration: int,  # pylint: disable=unused-argument
                            step: int,
                            status: str,
                        ) -> bool:
                            return progress_func(step + 1, status)

                        # ----------------------------------------------------------------------
                        def ParserSingleProgressAdapter(
                            iteration: int,  # pylint: disable=unused-argument
                            step: int,
                            status: str,
                        ) -> bool:
                            return progress_func(len(IterationSteps) + num_executor_steps + step + 1, status)

                        # ----------------------------------------------------------------------

                        executor_progress_func = ExecutorSingleProgressAdapter
                        parser_progress_func = ParserSingleProgressAdapter

                    else:
                        # ----------------------------------------------------------------------
                        def ExecutorMultipleProgressAdapter(
                            iteration: int,
                            step: int,
                            status: str,
                        ) -> bool:
                            return progress_func(
                                iteration * steps_per_iteration + step + 1,
                                "Iteration #{}: {}".format(iteration + 1, status),
                            )

                        # ----------------------------------------------------------------------
                        def ParserMultipleProgressAdapter(
                            iteration: int,
                            step: int,
                            status: str,
                        ) -> bool:
                            return progress_func(
                                iteration * steps_per_iteration + len(IterationSteps) + num_executor_steps + step + 1,
                                "Iteration #{}: {}".format(iteration + 1, status),
                            )

                        # ----------------------------------------------------------------------

                        executor_progress_func = ExecutorMultipleProgressAdapter
                        parser_progress_func = ParserMultipleProgressAdapter

                    # Run the tests
                    total_test_execution_start_time = time.perf_counter()

                    test_iteration_results: List[TestIterationResult] = []

                    for iteration in range(self._iterations):
                        # Execute the test
                        executor_progress_func(iteration, IterationSteps.Executing.value, "Testing...")

                        execute_result, execute_output = self._test_executor.Execute(
                            dm,
                            self._compiler,
                            task_data.context.compiler_context,
                            command_line,
                            lambda step, status: executor_progress_func(iteration, step, status),
                        )

                        # Remove temporary artifacts
                        executor_progress_func(iteration, IterationSteps.RemovingTemporaryArtifacts.value, "Removing temporary artifacts...")
                        self._test_parser.RemoveTemporaryArtifacts(task_data.context.compiler_context)

                        # Process the execution results
                        execute_log_filename = task_data.context.GetTestIterationExecutionLogFilename(
                            iteration,
                            self._iterations,
                        )

                        with execute_log_filename.open("w") as f:
                            f.write(execute_output)

                        execute_result = ExecuteResult(
                            execute_result.result,
                            execute_result.execution_time,
                            "{}: {}".format(self._test_executor.name, execute_result.short_desc) if execute_result.short_desc else self._test_executor.name,
                            execute_result.coverage_result,
                            execute_log_filename,
                        )

                        dm.WriteLine(
                            "Test execution for iteration #{iteration}:  {result:> 5} ({short_desc}) -> {log_filename}\n".format(
                                iteration=iteration + 1,
                                result=execute_result.result,
                                short_desc=execute_result.short_desc,
                                log_filename=execute_log_filename,
                            ),
                        )

                        # Parse the results
                        executor_progress_func(iteration, IterationSteps.ParsingResults.value, "Parsing results...")

                        parse_result = self._test_parser.Parse(
                            self._compiler,
                            task_data.context.compiler_context,
                            execute_output,
                            lambda step, status: parser_progress_func(iteration, step, status),
                        )

                        object.__setattr__(
                            parse_result,
                            "short_desc",
                            "{}: {}".format(self._test_parser.name, parse_result.short_desc)
                                if parse_result.short_desc else self._test_parser.name
                            ,
                        )

                        # Process the parse results
                        dm.WriteLine(
                            "Test extraction for iteration #{iteration}: {result:> 5} ({short_desc})\n\n".format(
                                iteration=iteration + 1,
                                result=parse_result.result,
                                short_desc=parse_result.short_desc,
                            ),
                        )

                        # Create the iteration information
                        test_iteration_results.append(
                            TestIterationResult(execute_result, parse_result),
                        )

                        if test_iteration_results[-1].result < 0:
                            if self._continue_iterations_on_error:
                                continue

                            break

                    # Commit the test results
                    total_test_execution_time = timedelta(seconds=time.perf_counter() - total_test_execution_start_time)

                    task_data.context.test_result = TestResult(
                        total_test_execution_time,
                        test_log_filename,
                        test_iteration_results,
                        has_multiple_iterations=self._iterations != 1,
                    )

                    # Validate code coverage (if necessary)
                    assert isinstance(task_data.context.build_result, BuildResult), task_data.context.build_result
                    assert task_data.context.build_result.result == 0, task_data.context.build_result
                    assert test_iteration_results

                    if (
                        test_iteration_results[0].execute_result.coverage_result is not None
                        and test_iteration_results[0].execute_result.coverage_result.coverage_percentage is not None
                        and self._code_coverage_validator is not None
                        and task_data.context.build_result.binary is not None
                    ):
                        progress_func(
                            steps_per_iteration * self._iterations + CodeCoverageSteps.ValidatingCodeCoverage.value + 1,
                            "Validating Code Coverage...",
                        )

                        code_coverage_result = self._code_coverage_validator.Validate(
                            dm,
                            task_data.context.build_result.binary,
                            test_iteration_results[0].execute_result.coverage_result.coverage_percentage,
                        )

                        object.__setattr__(
                            code_coverage_result,
                            "short_desc",
                            "{}: {}".format(self._code_coverage_validator.name, code_coverage_result.short_desc)
                                if code_coverage_result.short_desc else self._code_coverage_validator.name
                            ,
                        )

                        # Commit the coverage results
                        task_data.context.coverage_result = code_coverage_result

                    # Return the final data
                    if (
                        task_data.context.coverage_result is None
                        or task_data.context.test_result.result < 0
                        or (
                            task_data.context.test_result.result > 0
                            and task_data.context.coverage_result.result == 0
                        )
                    ):
                        yield (
                            task_data.context.test_result.result,
                            task_data.context.test_result.short_desc,
                        )
                    else:
                        yield (
                            task_data.context.coverage_result.result,
                            task_data.context.coverage_result.short_desc,
                        )

        # ----------------------------------------------------------------------
        def OnErrorResult(
            task_data: ExecuteTests._TaskData,
            result: ErrorResult,
        ) -> None:
            if task_data.context.test_result is None:
                task_data.context.test_result = result
            elif task_data.context.coverage_result is None:
                task_data.context.coverage_result = result
            else:
                assert False, task_data  # pragma: no cover

        # ----------------------------------------------------------------------

        self._ExecuteTasks(
            "Testing",
            TaskDance,
            OnErrorResult,
            max_num_threads=None if self._parallel_tests else 1,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def _CreateBenchmarks(
        dm: DoneManager,
        filename: Path,
        all_results: List[Result],
        common_path: Optional[Path]
    ) -> None:
        with dm.Nested("Creating Benchmarks at '{}'...".format(filename)):
            if common_path:
                len_common_path_parts = len(common_path.parts)
            else:
                len_common_path_parts = 0

            benchmarks: Dict[str, Dict[str, List[BenchmarkStat]]] = {}

            for result in all_results:
                configuration_benchmarks: Dict[str, List[BenchmarkStat]] = {}

                for configuration, results in [
                    ("Debug", result.debug),
                    ("Release", result.release),
                ]:
                    if results is None or not isinstance(results.test_result, TestResult):
                        continue

                    assert results.test_result.test_results
                    parse_result = results.test_result.test_results[0].parse_result

                    if parse_result.benchmarks:
                        configuration_benchmarks[configuration] = parse_result.benchmarks

                if configuration_benchmarks:
                    assert len(result.test_item.parts) > len_common_path_parts
                    benchmarks[Path(*result.test_item.parts[len_common_path_parts:]).as_posix()] = configuration_benchmarks

            with filename.open("w") as f:
                JsonEx.Dump(benchmarks, f)

    # ----------------------------------------------------------------------
    @staticmethod
    def _CreateJunitResults(
        dm: DoneManager,
        junit_xml_output_filename: Path,
        all_results: List[Result],
        common_path: Optional[Path],
    ) -> None:
        with dm.Nested("Creating JUnit output at '{}'...".format(junit_xml_output_filename)):
            if common_path:
                len_common_path_parts = len(common_path.parts)
            else:
                len_common_path_parts = 0

            hostname = socket.gethostname()
            timestamp = datetime.now().isoformat()

            root = ET.Element("testsuites")

            for index, result in enumerate(all_results):
                suite = ET.Element("testsuite")

                suite.set("id", str(index))
                suite.set("hostname", hostname)
                suite.set("timestamp", timestamp)

                assert len(result.test_item.parts) > len_common_path_parts, (result.test_item, common_path)
                suite.set("name", Path(*result.test_item.parts[len_common_path_parts:]).as_posix())

                for configuration, results in [
                    ("Debug", result.debug),
                    ("Release", result.release),
                ]:
                    if results is None or not isinstance(results.test_result, TestResult):
                        continue

                    testcase = ET.Element("testcase")

                    testcase.set("name", configuration)
                    testcase.set("time", str(results.execution_time.total_seconds()))

                    assert results.test_result.test_results
                    parse_result = results.test_result.test_results[0].parse_result

                    for test_name, subtest_result in (parse_result.subtest_results or {}).items():
                        if subtest_result.result == 0:
                            continue

                        failure = ET.Element("failure")

                        failure.text = "{} ({}, {})".format(
                            test_name,
                            subtest_result.result,
                            subtest_result.execution_time,
                        )

                        failure.set("message", failure.text)
                        failure.set("type", "Subtest failure")

                        testcase.append(failure)

                    suite.append(testcase)

                root.append(suite)

            with junit_xml_output_filename.open("w") as f:
                f.write(
                    ET.tostring(
                        root,
                        encoding="unicode",
                    ),
                )

    # ----------------------------------------------------------------------
    def _ExecuteTasks(
        self,
        desc: str,
        execution_task_func: Callable[      # The intricate dance between the task func and custom implementation
            [
                "ExecuteTests._TaskData",
            ],
            Generator[
                Union[
                    Path,                               # 1) Yield a path to the log file
                    int,                                # 2b) Yield the number of steps
                    Tuple[int, Optional[str]],          # 3b) Yield the final result and short desc
                ],
                Union[
                    Callable[[str], None],  # 2a) Caller sends a progress callback
                    Callable[               # 3a) Caller sends a step-based progress callback
                        [
                            int,    # Step
                            str,    # Status
                        ],
                        bool,       # True to continue, False to terminate
                    ],
                ],
                None,
            ],
        ],
        on_error_result_func: Callable[["ExecuteTests._TaskData", ErrorResult], None],
        *,
        max_num_threads: Optional[int]=None,
    ) -> None:
        tasks = self._CreateTasks()
        if not tasks:
            return

        error_count = 0
        warning_count = 0
        success_count = 0

        count_lock = threading.Lock()

        with self._dm.Nested(
            "{} {}...".format(desc, inflect.no("test item", len(tasks))),
            [
                lambda: "{} succeeded".format(inflect.no("test item", success_count)),
                lambda: "{} with failures".format(inflect.no("test item", error_count)),
                lambda: "{} with warnings".format(inflect.no("test item", warning_count)),
            ],
            suffix="\n" if (error_count or warning_count) and not self._quiet else "",
        ) as execute_dm:
            with execute_dm.YieldStdout() as stdout_context:
                with Progress(
                    *Progress.get_default_columns(),
                    "{task.fields[status]}",
                    transient=True,
                ) as progress:
                    total_progress_id = progress.add_task(
                        "{}Total Progress".format(stdout_context.line_prefix),
                        total=len(tasks),
                        status="",
                    )

                    num_threads = 1 if self._single_threaded else min(len(tasks), multiprocessing.cpu_count())
                    if max_num_threads is not None:
                        num_threads = min(num_threads, max_num_threads)

                    with ThreadPoolExecutor(num_threads) as executor:
                        # ----------------------------------------------------------------------
                        def Impl(
                            task_id: TaskID,
                            task_data: ExecuteTests._TaskData,
                        ) -> None:
                            if not self._quiet:
                                progress.update(task_id, visible=True)

                            start_time = time.perf_counter()
                            log_filename: Optional[Path] = None
                            result = 0
                            short_desc: Optional[str] = None

                            try:
                                # ----------------------------------------------------------------------
                                def OnExit():
                                    nonlocal success_count
                                    nonlocal error_count
                                    nonlocal warning_count

                                    assert log_filename is not None

                                    progress.update(task_id, completed=True, visible=False)

                                    if result < 0 and not self._quiet:
                                        progress.print(
                                            r"{prefix}[bold red]ERROR:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                                prefix=stdout_context.line_prefix,
                                                name=task_data.context.display_name,
                                                result=result,
                                                short_desc=" ({})".format(short_desc) if short_desc else "",
                                                suffix=str(log_filename) if execute_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
                                                    log_filename.as_posix(),
                                                ),
                                            ),
                                            highlight=False,
                                        )

                                        stdout_context.persist_content = True

                                    if result > 0 and not self._quiet:
                                        progress.print(
                                            r"{prefix}[bold yellow]WARNING:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                                prefix=stdout_context.line_prefix,
                                                name=task_data.context.display_name,
                                                result=result,
                                                short_desc=" ({})".format(short_desc) if short_desc else "",
                                                suffix=str(log_filename) if execute_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
                                                    log_filename.as_posix(),
                                                ),
                                            ),
                                            highlight=False,
                                        )

                                        stdout_context.persist_content = True

                                    with count_lock:
                                        if result < 0:
                                            error_count += 1
                                        elif result > 0:
                                            warning_count += 1
                                        else:
                                            success_count += 1

                                        successes = success_count
                                        errors = error_count
                                        warnings = warning_count

                                    progress.update(
                                        total_progress_id,
                                        advance=1,
                                        status=TextwrapEx.CreateStatusText(successes, errors, warnings),
                                    )

                                # ----------------------------------------------------------------------

                                with ExitStack(OnExit):
                                    # Get the log filename name
                                    task_dance_iter = execution_task_func(task_data)

                                    log_filename = cast(Path, next(task_dance_iter))

                                    # Send the progress and wait for the number of steps
                                    num_steps = cast(int, task_dance_iter.send(lambda status: progress.update(task_id, status=status)))

                                    # Wait for our turn
                                    progress.update(task_id, status="Waiting...")

                                    with task_data.working_data.execution_lock:
                                        # Update the progress bar
                                        progress.update(task_id, total=num_steps)

                                        current_step = 0

                                        # ----------------------------------------------------------------------
                                        def OnProgress(
                                            step: int,
                                            status: str,
                                        ) -> bool:
                                            nonlocal current_step

                                            advance = step - 1 - current_step
                                            current_step = step - 1

                                            progress.update(
                                                task_id,
                                                advance=advance,
                                                status="({} of {}) {}".format(
                                                    current_step + 1,
                                                    num_steps,
                                                    status,
                                                ),
                                            )

                                            return True

                                        # ----------------------------------------------------------------------

                                        # Send the progress func and wait for completion
                                        result, short_desc = cast(Tuple[int, Optional[str]], task_dance_iter.send(OnProgress))

                            except StopIteration:
                                pass

                            except KeyboardInterrupt:  # pylint: disable=try-except-raise
                                raise

                            except Exception as ex:
                                if self._dm.is_debug:
                                    error = traceback.format_exc()
                                else:
                                    error = str(ex)

                                error = error.strip()

                                if log_filename is None:
                                    # If here, this error has happened before we have received
                                    # anything from the callback. Create a log file and write
                                    # the exception information.
                                    log_filename = CurrentShell.CreateTempFilename()
                                    assert log_filename is not None

                                    with log_filename.open("w") as f:
                                        f.write(error)

                                else:
                                    with log_filename.open("a+") as f:
                                        f.write("\n\n{}".format(error))

                                assert log_filename is not None

                                # Commit the result
                                on_error_result_func(
                                    task_data,
                                    ErrorResult(
                                        self.__class__.CATASTROPHIC_TASK_FAILURE_RESULT,
                                        timedelta(seconds=time.perf_counter() - start_time),
                                        log_filename,
                                        "{} failed spectacularly".format(desc),
                                    ),
                                )

                        # ----------------------------------------------------------------------

                        futures = [
                            executor.submit(
                                Impl,
                                progress.add_task(
                                    "{}  {}".format(stdout_context.line_prefix, task.context.display_name),
                                    status="",
                                    total=None,
                                    visible=False,
                                ),
                                task,
                            )
                            for task in tasks
                        ]

                        for future in futures:
                            future.result()

            if error_count:
                execute_dm.result = -1
            elif warning_count and execute_dm.result == 0:
                execute_dm.result = 1
