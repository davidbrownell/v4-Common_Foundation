# ----------------------------------------------------------------------
# |
# |  ExecuteTests.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-04 08:08:47
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------

import datetime
import socket
import textwrap
import time
import threading
import traceback

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union
from xml.etree import ElementTree as ET

from Common_Foundation import JsonEx
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx

from Common_FoundationEx.CompilerImpl.Compiler import Compiler
from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl
from Common_FoundationEx.CompilerImpl.Verifier import Verifier
from Common_FoundationEx import ExecuteTasksEx
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageValidatorImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import TestExecutorImpl
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl

from Results import BenchmarkStat, BuildResult, CodeCoverageResult, ConfigurationResult, ExecuteResult, ParseResult, Result, TestIterationResult, TestResult


# ----------------------------------------------------------------------
class ExecuteTests(object):
    """Contains for the parameters so we don't need to continually pass them around."""

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
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
        parallel_tests: bool,
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
        # Ensure that the plugins are valid in this environment
        for plugin, desc in [
            (compiler, "compiler"),
            (test_executor, "test executor"),
            (test_parser, "test parser"),
            (code_coverage_validator, "code coverage validator"),
        ]:
            if plugin is None:
                continue

            result = plugin.ValidateEnvironment()
            if result is not None:
                raise Exception(
                    textwrap.dedent(
                        """\
                        The {} '{}' does not support the current environment.

                        {}
                        """,
                    ).format(
                        desc,
                        plugin.name,
                        TextwrapEx.Indent(result.strip(), 4),
                    ),
                )

        # Check for compatible plugins
        for plugin, desc in [
            (test_executor, "test executor"),
            (test_parser, "test parser"),
        ]:
            if not plugin.IsSupportedCompiler(compiler):
                raise Exception(
                    "The {} '{}' is not compatible with the compiler '{}'.".format(
                        desc,
                        plugin.name,
                        compiler.name,
                    ),
                )

        # Check for valid args
        if skip_build and not isinstance(compiler, Verifier):
            raise Exception("The build can only be skipped for compilers that act as verifiers.")

        if debug_only and release_only:
            raise Exception("Debug-only and Release-only are mutually exclusive options.")

        # Update flags for code coverage builds
        if code_coverage_validator is not None:
            parallel_tests = False
            iterations = 1

            if isinstance(compiler, Compiler):
                debug_only = True
                release_only = False

        # Prepare the working data
        test_item_data_items: List[ExecuteTests._TestItemData] = []

        with dm.Nested(
            "Preparing data...",
            lambda: "{} to process".format(inflect.no("configuration", len(test_item_data_items))),
        ) as prep_dm:
            output_dir.mkdir(parents=True, exist_ok=True)

            common_path = PathEx.GetCommonPath(*test_items)
            len_common_path_parts = 0 if common_path is None else len(common_path.parts)

            for test_item in test_items:
                # Determine if the test item is supported
                is_supported = True

                for plugin, plugin_desc, item_desc, func in [
                    (compiler, "compiler", "item", lambda: compiler.IsSupported(test_item)),
                    (compiler, "compiler", "test item", lambda: compiler.IsSupportedTestItem(test_item)),
                    (test_executor, "test executor", "test item", lambda: test_executor.IsSupportedTestItem(test_item)),
                    (test_parser, "test parser", "test item", lambda: test_parser.IsSupportedTestItem(test_item)),
                ]:
                    if not func():
                        prep_dm.WriteVerbose(
                            "'{}' is not a supported {} with the {} '{}'.\n".format(
                                test_item,
                                item_desc,
                                plugin_desc,
                                plugin.name,
                            ),
                        )

                        is_supported = False
                        break

                if not is_supported:
                    continue

                # Prepare the configuration data
                assert len(test_item.parts) > len_common_path_parts
                display_name_template = "{} ({{}})".format(Path(*test_item.parts[len_common_path_parts:]))

                # Create a suitable output dir
                this_output_dir = output_dir / CurrentShell.ScrubFilename(
                    "_".join(test_item.parts[len_common_path_parts:]),
                    replace_char="-",
                )

                debug: Optional[ExecuteTests._ConfigurationData] = None
                release: Optional[ExecuteTests._ConfigurationData] = None

                if isinstance(compiler, Compiler):
                    if release_only:
                        prep_dm.WriteVerbose(
                            "The Debug configuration for '{}' will not be processed because Release-only has been specified.\n".format(
                                test_item,
                            ),
                        )
                    else:
                        debug = cls._ConfigurationData(
                            display_name_template.format("Debug"),
                            test_item,
                            this_output_dir / "Debug",
                            is_debug_configuration=True,
                        )

                    if debug_only:
                        prep_dm.WriteVerbose(
                            "The Release configuration for '{}' will not be processed because Debug-only has been specified.\n".format(
                                test_item,
                            ),
                        )
                    else:
                        release = cls._ConfigurationData(
                            display_name_template.format("Release"),
                            test_item,
                            this_output_dir / "Release",
                            is_debug_configuration=False,
                        )
                else:
                    debug = cls._ConfigurationData(
                        display_name_template.format("Debug"),
                        test_item,
                        this_output_dir / "Debug",
                        is_debug_configuration=True,
                    )

                assert debug is not None or release is not None

                test_item_data_items.append(
                    cls._TestItemData(test_item, this_output_dir, debug, release),
                )

        if not test_item_data_items:
            return []

        tester = cls(
            dm,
            common_path,
            test_item_data_items,
            compiler,
            test_executor,
            test_parser,
            code_coverage_validator,
            metadata,
            parallel_tests=parallel_tests,
            single_threaded=single_threaded,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            quiet=quiet,
        )

        # Prepare the output dirs
        for task_data in tester._CreateTasks():
            if task_data.context.output_dir.is_dir():
                PathEx.RemoveTree(task_data.context.output_dir)

            task_data.context.output_dir.mkdir(parents=True)

        # Return the build and tests
        if not skip_build:
            tester._Build()

        if not build_only:
            tester._Test()

        # Collect the results
        all_results: List[Result] = [
            Result(
                test_item_data.test_item,
                test_item_data.output_dir,
                None if test_item_data.debug is None else test_item_data.debug.ToConfigurationResult(
                    compiler.name,
                    test_executor.name,
                    test_parser.name,
                    code_coverage_validator.name if code_coverage_validator else None,
                    "Debug",
                    has_multiple_iterations=iterations != 1,
                ),
                None if test_item_data.release is None else test_item_data.release.ToConfigurationResult(
                    compiler.name,
                    test_executor.name,
                    test_parser.name,
                    code_coverage_validator.name if code_coverage_validator else None,
                    "Release",
                    has_multiple_iterations=iterations != 1,
                ),
            )
            for test_item_data in test_item_data_items
        ]

        if all(result.result == 0 for result in all_results):
            tester._CreateBenchmarks(
                output_dir / "Benchmarks.json",
                all_results,
                len_common_path_parts,
            )

        if junit_xml_output_filename:
            tester._CreateJUnitResults(
                output_dir / junit_xml_output_filename,
                all_results,
                len_common_path_parts,
            )

        dm.WriteLine("")

        return all_results

    # ----------------------------------------------------------------------
    def __init__(
        self,
        dm: DoneManager,
        common_path: Optional[Path],
        test_item_data_items: List["ExecuteTests._TestItemData"],
        compiler: CompilerImpl,
        test_executor: TestExecutorImpl,
        test_parser: TestParserImpl,
        code_coverage_validator: Optional[CodeCoverageValidatorImpl],
        metadata: Dict[str, Any],
        *,
        parallel_tests: bool,
        single_threaded: bool,
        iterations: int,
        continue_iterations_on_error: bool,
        quiet: bool,
    ):
        self._dm                            = dm
        self._common_path                   = common_path
        self._test_item_data_items          = test_item_data_items
        self._compiler                      = compiler
        self._test_executor                 = test_executor
        self._test_parser                   = test_parser
        self._code_coverage_validator       = code_coverage_validator
        self._metadata                      = metadata
        self._parallel_tests                = parallel_tests
        self._single_threaded               = single_threaded
        self._iterations                    = iterations
        self._continue_iterations_on_error  = continue_iterations_on_error
        self._quiet                         = quiet

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    @dataclass
    class _TestItemData(object):
        # ----------------------------------------------------------------------
        test_item: Path
        output_dir: Path

        debug: Optional["ExecuteTests._ConfigurationData"]
        release: Optional["ExecuteTests._ConfigurationData"]

        execution_lock: threading.Lock      = field(init=False, default_factory=threading.Lock)

    # ----------------------------------------------------------------------
    @dataclass
    class _ConfigurationData(object):
        # ----------------------------------------------------------------------
        display_name: str

        test_item: Path
        output_dir: Path

        is_debug_configuration: bool                                        = field(kw_only=True)

        was_skipped: bool                                                   = field(init=False, default=False)

        compiler_context: Optional[Dict[str, Any]]                          = field(init=False, default=None)

        build_result: Union[None, BuildResult]                              = field(init=False, default=None)
        test_result: Union[None, TestResult]                                = field(init=False, default=None)
        coverage_result: Union[None, CodeCoverageResult]                    = field(init=False, default=None)

        # ----------------------------------------------------------------------
        @property
        def has_errors(self) -> bool:
            return self.GetResult()[0] != 0

        # ----------------------------------------------------------------------
        def GetLogFilename(self) -> Path:
            return self.output_dir / "tester.log"

        # ----------------------------------------------------------------------
        def GetResult(self) -> Tuple[int, Optional[str]]:
            short_desc: Optional[str] = None

            for result in [
                self.build_result,
                self.test_result,
                self.coverage_result,
            ]:
                if result is None:
                    continue

                if result.result != 0:
                    return result.result, result.short_desc

                if result.short_desc:
                    short_desc = result.short_desc

            return 0, short_desc

        # ----------------------------------------------------------------------
        def ToConfigurationResult(
            self,
            compiler_name: str,
            test_execution_name: str,
            test_parser_name: str,
            code_coverage_validator_name: Optional[str],
            configuration: str,
            *,
            has_multiple_iterations: bool,
        ) -> ConfigurationResult:
            assert self.build_result is not None
            assert self.test_result is None or (self.build_result and self.build_result.result == 0)
            assert self.coverage_result is None or (self.build_result and self.build_result.result == 0)

            return ConfigurationResult(
                configuration,
                self.output_dir,
                self.GetLogFilename(),
                compiler_name,
                test_execution_name,
                test_parser_name,
                code_coverage_validator_name,
                self.build_result,
                self.test_result,
                self.coverage_result,
                has_multiple_iterations,
            )

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _CreateTasks(self) -> List[ExecuteTasksEx.TaskData]:
        debug_tasks: List[ExecuteTasksEx.TaskData] = []
        release_tasks: List[ExecuteTasksEx.TaskData] = []

        for test_item_data in self._test_item_data_items:
            if (
                test_item_data.debug is not None
                and not test_item_data.debug.has_errors
                and not test_item_data.debug.was_skipped
            ):
                debug_tasks.append(
                    ExecuteTasksEx.TaskData(
                        test_item_data.debug.display_name,
                        test_item_data.debug,
                        test_item_data.execution_lock,
                    ),
                )

            if (
                test_item_data.release is not None
                and not test_item_data.release.has_errors
                and not test_item_data.release.was_skipped
            ):
                release_tasks.append(
                    ExecuteTasksEx.TaskData(
                        test_item_data.release.display_name,
                        test_item_data.release,
                        test_item_data.execution_lock,
                    ),
                )

        return debug_tasks + release_tasks

    # ----------------------------------------------------------------------
    def _Build(self) -> None:
        # ----------------------------------------------------------------------
        def Step1(
            context: ExecuteTests._ConfigurationData,
        ) -> Tuple[Path, ExecuteTasksEx.ExecuteTasksStep2FuncType]:
            config_data = context

            total_start_time = time.perf_counter()
            log_filename = config_data.GetLogFilename()

            # Create the name of the binary file that may be generated; some
            # plugins use this information to calculate outputs (even if the
            # file itself doesn't exist).
            if isinstance(self._compiler, Verifier):
                binary_filename = config_data.test_item
            else:
                binary_filename = config_data.output_dir / "test_artifact"

                ext = getattr(self._compiler, "binary_extension", None)
                if ext:
                    binary_filename += ext

            # ----------------------------------------------------------------------
            @contextmanager
            def YieldLogDM() -> Iterator[DoneManager]:
                with log_filename.open("a+") as f:
                    with DoneManager.Create(
                        f,
                        "",
                        line_prefix="",
                        display=False,
                        output_flags=DoneManagerFlags.Create(debug=True),
                    ) as dm:
                        yield dm

            # ----------------------------------------------------------------------

            with YieldLogDM() as dm:
                dm.WriteLine(
                    textwrap.dedent(
                        """\
                        # ----------------------------------------------------------------------
                        # |
                        # | Build Info
                        # |
                        # ----------------------------------------------------------------------
                        Compiler:                     {}
                        Binary Filename:              {}

                        """,
                    ).format(self._compiler.name, binary_filename),
                )

            # ----------------------------------------------------------------------
            def Step2(
                on_simple_status_func: Callable[[str], None],
            ) -> Tuple[Optional[int], ExecuteTasksEx.ExecuteTasksStep3FuncType]:
                on_simple_status_func("Configuring...")

                with YieldLogDM() as log_dm:
                    # Create the metadata used to create the compiler context
                    metadata: Dict[str, Any] = {
                        **self._metadata,
                        **{
                            "debug_build": config_data.is_debug_configuration,
                            "profile_build": bool(self._code_coverage_validator),
                            "output_filename": binary_filename,
                            "output_dir": config_data.output_dir,
                            "force": True,
                        },
                    }

                    compiler_context = self._compiler.GetSingleContextItem(
                        log_dm,
                        config_data.test_item,
                        metadata,
                    )

                    if log_dm.result != 0:
                        raise Exception("Compiler context generation failed.")

                    config_data.compiler_context = compiler_context

                    if compiler_context is None:
                        num_steps = 0
                    else:
                        num_steps = self._compiler.GetNumSteps(compiler_context)

                # ----------------------------------------------------------------------
                def Step3(
                    status: ExecuteTasksEx.Status,
                ) -> Tuple[int, Optional[str]]:
                    with YieldLogDM() as log_dm:
                        build_start_time = time.perf_counter()

                        if compiler_context is None:
                            log_dm.WriteLine("The compiler return empty context.\n")

                            result = 0
                            short_desc = "Skipped by the compiler"

                            config_data.was_skipped = True

                        else:
                            with log_dm.Nested("Building...") as building_dm:
                                with building_dm.YieldStream() as stream:
                                    result = getattr(self._compiler, self._compiler.invocation_method_name)(
                                        compiler_context,
                                        stream,
                                        lambda step, value: status.OnProgress(step + 1, value),
                                        verbose=True,
                                    )

                                    if isinstance(result, tuple):
                                        result, short_desc = result
                                    else:
                                        short_desc = None

                                # Remove temporary artifacts
                                self._compiler.RemoveTemporaryArtifacts(compiler_context)

                        current_time = time.perf_counter()

                        config_data.build_result = BuildResult(
                            result,
                            datetime.timedelta(seconds=current_time - total_start_time),
                            log_filename,
                            "{}: {}".format(self._compiler.name, short_desc) if short_desc else "",
                            datetime.timedelta(seconds=current_time - build_start_time),
                            config_data.output_dir,
                            binary_filename,
                        )

                    return result, short_desc

                # ----------------------------------------------------------------------

                return num_steps, Step3

            # ----------------------------------------------------------------------

            return log_filename, Step2

        # ----------------------------------------------------------------------

        tasks = self._CreateTasks()
        if not tasks:
            return

        ExecuteTasksEx.ExecuteTasks(
            self._dm,
            "Building",
            tasks,
            Step1,
            quiet=self._quiet,
            max_num_threads=1 if self._single_threaded else None,
        )

    # ----------------------------------------------------------------------
    def _Test(self) -> None:
        # ----------------------------------------------------------------------
        class IterationSteps(Enum):
            Executing                       = 0
            RemovingTemporaryArtifacts      = auto()
            ParsingResults                  = auto()

        # ----------------------------------------------------------------------
        class CodeCoverageSteps(Enum):
            Validating                      = 0

        # ----------------------------------------------------------------------
        def Step1(
            context: ExecuteTests._ConfigurationData,
        ) -> Tuple[Path, ExecuteTasksEx.ExecuteTasksStep2FuncType]:
            config_data = context

            log_filename = config_data.GetLogFilename()

            # ----------------------------------------------------------------------
            @contextmanager
            def YieldLogDM() -> Iterator[DoneManager]:
                with log_filename.open("a+") as f:
                    with DoneManager.Create(
                        f,
                        "",
                        line_prefix="",
                        display=False,
                        output_flags=DoneManagerFlags.Create(debug=True),
                    ) as dm:
                        yield dm

            # ----------------------------------------------------------------------

            with YieldLogDM() as dm:
                dm.WriteLine(
                    textwrap.dedent(
                        """\

                        # ----------------------------------------------------------------------
                        # |
                        # | Test Info
                        # |
                        # ----------------------------------------------------------------------
                        Test Executor:                {}
                        Test Parser:                  {}
                        Num Iterations:               {}
                        """,
                    ).format(
                        self._test_executor.name,
                        self._test_parser.name,
                        self._iterations,
                    ),
                )

            # ----------------------------------------------------------------------
            def Step2(
                on_simple_status_func: Callable[[str], None],
            ) -> Tuple[int, ExecuteTasksEx.ExecuteTasksStep3FuncType]:
                assert config_data.compiler_context is not None

                with YieldLogDM() as log_dm:
                    on_simple_status_func("Creating command line...")

                    command_line = self._test_parser.CreateInvokeCommandLine(
                        self._compiler,
                        config_data.compiler_context,
                        debug_on_error=False,
                    )

                    log_dm.WriteLine("Test Execution Command Line:  {}\n\n".format(command_line))

                    # Calculate the number of steps
                    num_executor_steps = self._test_executor.GetNumSteps(self._compiler, config_data.compiler_context) or 0
                    num_parser_steps = self._test_parser.GetNumSteps(command_line, self._compiler, config_data.compiler_context) or 0

                    steps_per_iteration = len(IterationSteps) + num_executor_steps + num_parser_steps

                    num_steps = steps_per_iteration * self._iterations
                    if self._code_coverage_validator:
                        num_steps += len(CodeCoverageSteps)

                # ----------------------------------------------------------------------
                def Step3(
                    status: ExecuteTasksEx.Status,
                ) -> Tuple[int, Optional[str]]:
                    assert config_data.compiler_context is not None

                    with YieldLogDM() as log_dm:
                        if self._iterations == 1:
                            # ----------------------------------------------------------------------
                            def SingleExecutorProgressAdapter(
                                iteration: int,  # pylint: disable=unused-argument
                                step: int,
                                value: str,
                            ) -> bool:
                                return status.OnProgress(step + 1, value)

                            # ----------------------------------------------------------------------
                            def SingleParserProgressAdapter(
                                iteration: int,  # pylint: disable=unused-argument
                                step: int,
                                value: str,
                            ) -> bool:
                                return status.OnProgress(len(IterationSteps) + num_executor_steps + step + 1, value)

                            # ----------------------------------------------------------------------

                            executor_progress_func = SingleExecutorProgressAdapter
                            parser_progress_func = SingleParserProgressAdapter

                        else:
                            # ----------------------------------------------------------------------
                            def MultipleExecutorProgressAdapter(
                                iteration: int,
                                step: int,
                                value: str,
                            ) -> bool:
                                return status.OnProgress(
                                    iteration * steps_per_iteration + step + 1,
                                    "Iteration #{}: {}".format(iteration + 1, value),
                                )

                            # ----------------------------------------------------------------------
                            def MultipleParserProgressAdapter(
                                iteration: int,
                                step: int,
                                value: str,
                            ) -> bool:
                                return status.OnProgress(
                                    iteration * steps_per_iteration + len(IterationSteps) + num_executor_steps + step + 1,
                                    "Iteration #{}: {}".format(iteration + 1, value),
                                )

                            # ----------------------------------------------------------------------

                            executor_progress_func = MultipleExecutorProgressAdapter
                            parser_progress_func = MultipleParserProgressAdapter

                        # Run the tests
                        total_test_start_time = time.perf_counter()

                        test_iteration_results: List[TestIterationResult] = []

                        for iteration in range(self._iterations):
                            with log_dm.Nested(
                                "Iteration #{}...".format(iteration + 1),
                                suffix="\n",
                            ) as iteration_dm:
                                with iteration_dm.Nested(
                                    "Test Execution...",
                                    suffix="\n",
                                ) as test_execution_dm:
                                    # Execute the test
                                    executor_progress_func(iteration, IterationSteps.Executing.value, "Testing...")

                                    execute_start_time = time.perf_counter()

                                    try:
                                        execute_result, execute_output = self._test_executor.Execute(
                                            test_execution_dm,
                                            self._compiler,
                                            config_data.compiler_context,
                                            command_line,
                                            lambda step, status: executor_progress_func(iteration, step, status),  # pylint: disable=cell-var-from-loop
                                        )

                                        executor_progress_func(iteration, IterationSteps.RemovingTemporaryArtifacts.value, "Removing temporary artifacts...")
                                        self._test_parser.RemoveTemporaryArtifacts(config_data.compiler_context)

                                    except:  # pylint: disable=bare-except
                                        execute_result = ExecuteResult(
                                            ExecuteTasksEx.CATASTROPHIC_TASK_FAILURE_RESULT,
                                            datetime.timedelta(seconds=time.perf_counter() - execute_start_time),
                                            "The test executor failed spectacularly",
                                            None,
                                        )

                                        execute_output = ""

                                        test_execution_dm.WriteError(traceback.format_exc())

                                    test_execution_dm.result = execute_result.result
                                    test_execution_dm.WriteInfo("\n{}\n".format(execute_output.strip()))

                                    test_execution_dm.WriteLine(
                                        textwrap.dedent(
                                            """\

                                            Execute Result:         {}
                                            Execute Time:           {}
                                            Execute Short Desc:     {}

                                            """,
                                        ).format(
                                            execute_result.result,
                                            execute_result.execution_time,
                                            execute_result.short_desc or "<None>",
                                        ),
                                    )

                                    if execute_result.short_desc:
                                        object.__setattr__(
                                            execute_result,
                                            "short_desc",
                                            "{}: {}".format(self._test_executor.name, execute_result.short_desc),
                                        )

                                with iteration_dm.Nested(
                                    "Test Parser...",
                                    suffix="\n",
                                ) as test_parser_dm:
                                    # Parse the results
                                    executor_progress_func(iteration, IterationSteps.ParsingResults.value, "Parsing Results...")

                                    parse_start_time = time.perf_counter()

                                    try:
                                        parse_result = self._test_parser.Parse(
                                            self._compiler,
                                            config_data.compiler_context,
                                            execute_output,
                                            lambda step, status: parser_progress_func(iteration, step, status),
                                        )

                                    except Exception:  # pylint: disable=bare-except
                                        parse_result = ParseResult(
                                            ExecuteTasksEx.CATASTROPHIC_TASK_FAILURE_RESULT,
                                            datetime.timedelta(seconds=time.perf_counter() - parse_start_time),
                                            "The test parser failed spectacularly",
                                            None,
                                            None,
                                        )

                                        test_parser_dm.WriteError(traceback.format_exc())

                                    test_parser_dm.WriteLine(
                                        textwrap.dedent(
                                            """\
                                            Parse Result:           {}
                                            Parse Time:             {}
                                            Parse Short Desc:       {}

                                            """,
                                        ).format(
                                            parse_result.result,
                                            parse_result.execution_time,
                                            parse_result.short_desc or "<None>",
                                        ),
                                    )

                                    if parse_result.short_desc:
                                        object.__setattr__(
                                            parse_result,
                                            "short_desc",
                                            "{}: {}".format(self._test_parser.name, parse_result.short_desc),
                                        )

                                    test_iteration_results.append(TestIterationResult(execute_result, parse_result))

                                    if test_iteration_results[-1].result < 0:
                                        if self._continue_iterations_on_error:
                                            continue

                                        break

                        assert test_iteration_results

                        # Commit the test results
                        config_data.test_result = TestResult(
                            datetime.timedelta(seconds=time.perf_counter() - total_test_start_time),
                            test_iteration_results,
                            has_multiple_iterations=self._iterations != 1,
                        )

                        # Validate code coverage (if necessary)
                        if (
                            self._code_coverage_validator is not None
                            and config_data.build_result is not None
                            and test_iteration_results[-1].execute_result.coverage_result is not None
                            and test_iteration_results[-1].execute_result.coverage_result.coverage_percentage is not None
                        ):
                            log_dm.WriteLine(
                                textwrap.dedent(
                                    """\
                                    # ----------------------------------------------------------------------
                                    # |
                                    # | Coverage Info
                                    # |
                                    # ----------------------------------------------------------------------
                                    Code Coverage Validator:      {}
                                    """,
                                ).format(self._code_coverage_validator.name),
                            )
                            status.OnProgress(
                                steps_per_iteration * self._iterations + CodeCoverageSteps.Validating.value + 1,
                                "Validating Code Coverage...",
                            )

                            try:
                                code_coverage_result = self._code_coverage_validator.Validate(
                                    log_dm,
                                    config_data.build_result.binary,
                                    test_iteration_results[-1].execute_result.coverage_result.coverage_percentage,
                                )

                                log_dm.WriteLine(
                                    textwrap.dedent(
                                        """\
                                        Code Coverage Result:         {}
                                        Code Coverage Time:           {}
                                        Code Coverage Short Desc:     {}

                                        """,
                                    ).format(
                                        code_coverage_result.result,
                                        code_coverage_result.execution_time,
                                        code_coverage_result.short_desc or "<None>",
                                    ),
                                )

                                if code_coverage_result.short_desc:
                                    object.__setattr__(
                                        code_coverage_result,
                                        "short_desc",
                                        "{}: {}".format(self._code_coverage_validator.name, code_coverage_result.short_desc),
                                    )

                                for name, coverage_data in (test_iteration_results[-1].execute_result.coverage_result.coverage_percentages or {}).items():
                                    log_dm.WriteLine(
                                        "    {:<30} {:.2f}%{}".format(
                                            "{}:".format(name),
                                            (coverage_data[0] if isinstance(coverage_data, tuple) else coverage_data) * 100.0,
                                            "" if not isinstance(coverage_data, tuple) else " ({})".format(coverage_data[1]),
                                        ),
                                    )

                                # Commit the coverage results
                                config_data.coverage_result = code_coverage_result

                            except:  # pylint: disable=bare-except
                                log_dm.WriteError(traceback.format_exc())

                    return config_data.GetResult()

                # ----------------------------------------------------------------------

                return num_steps, Step3

            # ----------------------------------------------------------------------

            return log_filename, Step2

        # ----------------------------------------------------------------------

        tasks = self._CreateTasks()
        if not tasks:
            return

        ExecuteTasksEx.ExecuteTasks(
            self._dm,
            "Testing",
            tasks,
            Step1,
            quiet=self._quiet,
            max_num_threads=1 if self._single_threaded or not self._parallel_tests else None,
        )

    # ----------------------------------------------------------------------
    def _CreateBenchmarks(
        self,
        output_filename: Path,
        all_results: List[Result],
        len_common_path_parts: int,
    ) -> None:
        with self._dm.Nested("Creating benchmarks at '{}'...".format(output_filename)):
            benchmarks: Dict[str, Dict[str, Dict[str, List[BenchmarkStat]]]] = {}

            for result in all_results:
                configuration_benchmarks: Dict[str, Dict[str, List[BenchmarkStat]]] = {}

                for configuration, configuration_result in [
                    ("Debug", result.debug),
                    ("Release", result.release),
                ]:
                    if configuration_result is None or configuration_result.test_result is None:
                        continue

                    assert configuration_result.test_result.test_results
                    parse_result = configuration_result.test_result.test_results[0].parse_result

                    if parse_result.benchmarks:
                        configuration_benchmarks[configuration] = parse_result.benchmarks

                if configuration_benchmarks:
                    assert len_common_path_parts < len(result.test_item.parts)
                    benchmarks[Path(*result.test_item.parts[len_common_path_parts:]).as_posix()] = configuration_benchmarks

            with output_filename.open("w") as f:
                JsonEx.Dump(benchmarks, f)

    # ----------------------------------------------------------------------
    def _CreateJUnitResults(
        self,
        output_filename: Path,
        all_results: List[Result],
        len_common_path_parts: int,
    ) -> None:
        with self._dm.Nested("Creating JUnit output at '{}'...".format(output_filename)):
            hostname = socket.gethostname()
            timestamp = datetime.datetime.now().isoformat()

            root = ET.Element("testsuites")

            for index, result in enumerate(all_results):
                suite = ET.Element("testsuite")

                suite.set("id", str(index))
                suite.set("hostname", hostname)
                suite.set("timestamp", timestamp)

                assert len_common_path_parts < len(result.test_item.parts)
                suite.set("name", Path(*result.test_item.parts[len_common_path_parts:]).as_posix())

                for configuration, result in [
                    ("Debug", result.debug),
                    ("Release", result.release),
                ]:
                    if result is None or result.test_result is None:
                        continue

                    testcase = ET.Element("testcase")

                    testcase.set("name", configuration)
                    testcase.set("time", str(result.execution_time.total_seconds()))

                    assert result.test_result.test_results
                    parse_result = result.test_result.test_results[0].parse_result

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

            with output_filename.open("w") as f:
                f.write(
                    ET.tostring(
                        root,
                        encoding="unicode",
                    ),
                )
