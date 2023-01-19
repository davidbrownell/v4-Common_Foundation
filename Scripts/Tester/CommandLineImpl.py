# ----------------------------------------------------------------------
# |
# |  py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-12-02 09:33:35
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Implements functionality invoked from the command line"""

import os
import re
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import typer

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import EnumSource
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import Types

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl, InputType
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageValidatorImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import TestExecutorImpl
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl
from Common_FoundationEx import TyperEx

import DisplayResults

from ExecuteTests import ExecuteTests
from Results import FindResult
from TestTypes import TYPES as TEST_TYPE_INFOS


# ----------------------------------------------------------------------
sys.path.insert(0, Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from RepositoryBootstrap.SetupAndActivate import DynamicPluginArchitecture  # pylint: disable=import-error


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Configuration(object):
    """Collection of plugins easily described by a single name"""

    name: str
    priority: int

    compiler: CompilerImpl
    test_parser: TestParserImpl

    test_executor: Optional[TestExecutorImpl]
    code_coverage_validator: Optional[CodeCoverageValidatorImpl]

    # ----------------------------------------------------------------------
    def ToString(self) -> str:
        return "{}, {}, {}, {}".format(
            self.compiler.name,
            self.test_parser.name,
            "<None>" if self.test_executor is None else self.test_executor.name,
            "<None>" if self.code_coverage_validator is None else self.code_coverage_validator.name,
        )


# ----------------------------------------------------------------------
VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME         = "TESTER_VERBOSE_PLUGIN_INFO"

IGNORE_FILENAME                             = "Tester-ignore"
DO_NOT_PARSE_FILENAME                       = "Tester-DoNotParse"


# ----------------------------------------------------------------------
# |
# |  Public Data
# |
# ----------------------------------------------------------------------
COMPILERS: List[CompilerImpl]                                               = []
TEST_EXECUTORS: List[TestExecutorImpl]                                      = []
TEST_PARSERS: List[TestParserImpl]                                          = []
CODE_COVERAGE_VALIDATORS: List[CodeCoverageValidatorImpl]                   = []

CONFIGURATIONS: List[Configuration]                                         = []


# ----------------------------------------------------------------------
def InitGlobals():
    with DoneManager.Create(
        sys.stdout,
        "\nCalculating dynamic content...",
        [
            lambda: inflect.no("compiler", len(COMPILERS)),
            lambda: inflect.no("test executor", len(TEST_EXECUTORS)),
            lambda: inflect.no("test parser", len(TEST_PARSERS)),
            lambda: inflect.no("code coverage validator", len(CODE_COVERAGE_VALIDATORS)),
            lambda: inflect.no("configuration", len(CONFIGURATIONS)),
        ],
        display_exception_details=False,
        output_flags=DoneManagerFlags.Create(verbose=bool(os.getenv(VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME))),
    ) as dm:
        # ----------------------------------------------------------------------
        def LoadPlugins() -> None:
            # Load the plugins
            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_COMPILERS"):
                potential_names = ["Compiler", "Verifier", ]

                found = False

                for potential_name in potential_names:
                    compiler = getattr(mod, potential_name, None)
                    if compiler is not None:
                        try:
                            COMPILERS.append(compiler())
                        except:
                            dm.WriteError(mod.__file__ or "")
                            raise

                        found = True
                        break

                if not found:
                    raise Exception(
                        "The names {} were not found in '{}'.\n".format(
                            ", ".join("'{}'".format(name) for name in potential_names),
                            mod.__file__,
                        ),
                    )

            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_TEST_EXECUTORS"):
                executor = getattr(mod, "TestExecutor", None)
                if executor is None:
                    raise Exception("'TestExecutor' was not found in '{}'.".format(mod.__file__))

                try:
                    TEST_EXECUTORS.append(executor())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_TEST_PARSERS"):
                test_parser = getattr(mod, "TestParser", None)
                if test_parser is None:
                    raise Exception("'TestParser was not found in '{}'.".format(mod.__file__))

                try:
                    TEST_PARSERS.append(test_parser())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_CODE_COVERAGE_VALIDATORS"):
                validator = getattr(mod, "CodeCoverageValidator", None)
                if validator is None:
                    raise Exception("'CodeCoverageValidator' was not found in '{}'.".format(mod.__file__))

                try:
                    CODE_COVERAGE_VALIDATORS.append(validator())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

        # ----------------------------------------------------------------------
        def CreateConfigurations() -> None:
            # Create the configurations
            configuration_data: Dict[str, Dict[str, Tuple[str, int]]] = {}

            config_item_regex = re.compile(
                r"""(?#
                Start                               )^(?#
                Config Name                         )(?P<config_name>.+?)(?#
                Sep                                 )\s*-\s*(?#
                Plugin Type                         )(?P<type>(?:compiler|test_parser|coverage_executor|coverage_validator))(?#
                Sep                                 )\s*-\s*(?#
                Plugin Name                         )(?P<plugin_name>.+?)(?#
                Optional Begin                      )(?:(?#
                    Sep                             )\s*-\s*(?#
                    Priority                        )pri\s*=\s*(?P<priority>\d+)(?#
                Optional End                        ))?(?#
                End                                 )$(?#
                )""",
            )

            for var in CurrentShell.EnumEnvironmentVariableValues("DEVELOPMENT_ENVIRONMENT_TESTER_CONFIGURATIONS"):
                match = config_item_regex.match(var)
                if not match:
                    raise Exception("'{}' is not a valid configuration item.".format(var))

                configuration_data.setdefault(match.group("config_name"), {})[match.group("type")] = (
                    match.group("plugin_name"),
                    int(match.group("priority") or 0),
                )

            for config_name, config_data in configuration_data.items():
                # Get the names
                compiler_name, compiler_priority = config_data.get("compiler", (None, 0))
                if compiler_name is None:
                    raise Exception("'compiler' was not found for the configuration '{}'.".format(config_name))

                test_parser_name, test_parser_priority = config_data.get("test_parser", (None, 0))
                if test_parser_name is None:
                    raise Exception("'test_parser' was not found for the configuration '{}'.".format(config_name))

                coverage_executor_name, coverage_executor_priority = config_data.get("coverage_executor", (None, 0))
                coverage_validator_name, coverage_validator_priority = config_data.get("coverage_validator", (None, 0))

                # Get the plugins
                compiler = next((compiler for compiler in COMPILERS if compiler.name == compiler_name), None)
                if compiler is None:
                    raise Exception("The compiler name '{}' in the configuration '{}' is not valid.".format(compiler_name, config_name))

                test_parser = next((test_parser for test_parser in TEST_PARSERS if test_parser.name == test_parser_name), None)
                if test_parser is None:
                    raise Exception("The test parser name '{}' in the configuration '{}' is not valid.".format(test_parser_name, config_name))

                if coverage_executor_name is None:
                    coverage_executor = None
                else:
                    coverage_executor = next((ce for ce in TEST_EXECUTORS if ce.name == coverage_executor_name), None)
                    if coverage_executor is None:
                        raise Exception("The coverage executor name '{}' in the configuration '{}' is not valid.".format(coverage_executor_name, config_name))

                if coverage_validator_name is None:
                    coverage_validator = None
                else:
                    coverage_validator = next((cv for cv in CODE_COVERAGE_VALIDATORS if cv.name == coverage_validator_name), None)
                    if coverage_validator is None:
                        raise Exception("The coverage validator '{}' in the configuration '{}' is not valid.".format(coverage_validator_name, config_name))

                # Save the configuration
                CONFIGURATIONS.append(
                    Configuration(
                        config_name,
                        max(
                            compiler_priority,
                            test_parser_priority,
                            coverage_executor_priority,
                            coverage_validator_priority,
                        ),
                        compiler,
                        test_parser,
                        coverage_executor,
                        coverage_validator,
                    ),
                )

            CONFIGURATIONS.sort(key=lambda value: value.priority)

        # ----------------------------------------------------------------------
        def ValidateConfigurations() -> None:
            disabled_compilers: Set[CompilerImpl] = set()
            disabled_test_executors: Set[TestExecutorImpl] = set()
            disabled_test_parsers: Set[TestParserImpl] = set()
            disabled_code_coverage_validators: Set[CodeCoverageValidatorImpl] = set()

            # Compilers
            index = 0

            while index < len(COMPILERS):
                compiler = COMPILERS[index]

                validate_result = compiler.ValidateEnvironment()
                if validate_result is not None:
                    dm.WriteVerbose("The compiler '{}' is not valid in this environment ({}).\n".format(compiler.name, validate_result))
                    disabled_compilers.add(compiler)

                    del COMPILERS[index]
                    continue

                index += 1

            if not COMPILERS:
                raise Exception("No compilers were found. Set the environment variable '{}' to display more information.".format(VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME))

            # Test Executors
            index = 0

            while index < len(TEST_EXECUTORS):
                test_executor = TEST_EXECUTORS[index]

                validate_result = test_executor.ValidateEnvironment()
                if validate_result is not None:
                    dm.WriteVerbose("The test executor '{}' is not valid in this environment ({}).\n".format(test_executor.name, validate_result))
                    disabled_test_executors.add(test_executor)

                    del TEST_EXECUTORS[index]
                    continue

                index += 1

            if not TEST_EXECUTORS:
                raise Exception("No test executors were found. Set the environment variable '{}' to display more information.".format(VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME))

            # Test Parsers
            index = 0

            while index < len(TEST_PARSERS):
                test_parser = TEST_PARSERS[index]

                validate_result = test_parser.ValidateEnvironment()
                if validate_result is not None:
                    dm.WriteVerbose("The test parser '{}' is not valid in this environment ({}).\n".format(test_parser.name, validate_result))
                    disabled_test_parsers.add(test_parser)

                    del TEST_PARSERS[index]
                    continue

                index += 1

            if not TEST_PARSERS:
                raise Exception("No test parsers were found. Set the environment variable '{}' to display more information.".format(VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME))

            # Code Coverage Validators
            index = 0

            while index < len(CODE_COVERAGE_VALIDATORS):
                code_coverage_validator = CODE_COVERAGE_VALIDATORS[index]

                validate_result = code_coverage_validator.ValidateEnvironment()
                if validate_result is not None:
                    dm.WriteVerbose("The code coverage validator '{}' is not valid in this environment ({}).\n".format(code_coverage_validator.name, validate_result))
                    disabled_code_coverage_validators.add(code_coverage_validator)

                    del CODE_COVERAGE_VALIDATORS[index]
                    continue

                index += 1

            if not CODE_COVERAGE_VALIDATORS:
                raise Exception("No code coverage validators were found. Set the environment variable '{}' to display more information.".format(VERBOSE_PLUGIN_ENVIRONMENT_VAR_NAME))

            # Remove configurations that are no longer valid
            index = 0

            while index < len(CONFIGURATIONS):
                configuration = CONFIGURATIONS[index]

                should_remove = False

                if not should_remove and configuration.compiler in disabled_compilers:
                    dm.WriteVerbose(
                        "The configuration '{}' is not valid in this environment as the compiler '{}' has been disabled.\n".format(
                            configuration.name,
                            configuration.compiler.name,
                        ),
                    )

                    should_remove = True

                if not should_remove and configuration.test_parser in disabled_test_parsers:
                    dm.WriteVerbose(
                        "The configuration '{}' is not valid in this environment as the test parser '{}' has been disabled.\n".format(
                            configuration.name,
                            configuration.test_parser.name,
                        ),
                    )

                    should_remove = True

                if should_remove:
                    if configuration.test_executor in disabled_test_executors:
                        object.__setattr__(configuration, "test_executor", None)
                    if configuration.code_coverage_validator in disabled_code_coverage_validators:
                        object.__setattr__(configuration, "code_coverage_validator", None)

                    del CONFIGURATIONS[index]
                    continue

                index += 1

        # ----------------------------------------------------------------------

        LoadPlugins()
        CreateConfigurations()
        ValidateConfigurations()

    # ----------------------------------------------------------------------

InitGlobals()
del InitGlobals


# ----------------------------------------------------------------------
compiler_enum                               = Types.StringsToEnum("CompilerEnum", [compiler.name for compiler in COMPILERS])
optional_test_executor_enum                 = Types.StringsToEnum("OptionalTestExecutorEnum", ["None", ] + [test_executor.name for test_executor in TEST_EXECUTORS])
test_parser_enum                            = Types.StringsToEnum("TestParserEnum", [test_parser.name for test_parser in TEST_PARSERS])
code_coverage_validator_enum                = Types.StringsToEnum("CodeCoverageValidatorEnum", [code_coverage_validator.name for code_coverage_validator in CODE_COVERAGE_VALIDATORS])
optional_code_coverage_validator_enum       = Types.StringsToEnum("OptionalCodeCoverageValidatorEnum", ["None", ] + [code_coverage_validator.name for code_coverage_validator in CODE_COVERAGE_VALIDATORS])
configuration_enum                          = Types.StringsToEnum("ConfigurationEnum", [configuration.name for configuration in CONFIGURATIONS])


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Execute(
    dm: DoneManager,

    configuration: Configuration,
    filename_or_directory: Path,
    output_dir: Optional[Path],
    test_type: Optional[str],
    *,
    code_coverage: bool,
    parallel_tests: Optional[bool],
    single_threaded: bool,

    iterations: int,
    continue_iterations_on_error: bool,

    debug_only: bool,
    release_only: bool,
    build_only: bool,
    skip_build: bool,

    ignore_ignore_filenames: Optional[List[Path]],

    quiet: bool,

    code_coverage_validator_name: Optional[code_coverage_validator_enum],  # type: ignore
    code_coverage_mismatch_is_error: bool,

    compiler_flags: Optional[List[str]],
    test_executor_flags: Optional[List[str]],
    test_parser_flags: Optional[List[str]],
    code_coverage_validator_flags: Optional[List[str]],

    junit_xml_output_filename: Optional[str],
) -> None:
    if debug_only and release_only:
        raise typer.BadParameter("Debug only and Release only cannot be used together.")

    # Get the test executors
    test_executor: Optional[TestExecutorImpl] = None

    if code_coverage:
        test_executor = configuration.test_executor
        parallel_tests = False

    if test_executor is None:
        test_executor = next((executor for executor in TEST_EXECUTORS if executor.name == "Standard"), None)

    assert test_executor is not None

    if code_coverage and not test_executor.is_code_coverage_executor:
        message = "The test executor '{}' does not support code coverage.".format(test_executor.name)

        if code_coverage_mismatch_is_error:
            raise typer.BadParameter(message)

        dm.WriteInfo(message)
        return

    # Get the code coverage validator
    code_coverage_validator: Optional[CodeCoverageValidatorImpl] = None

    if code_coverage:
        if code_coverage_validator_name:
            code_coverage_validator = next((validator for validator in CODE_COVERAGE_VALIDATORS if validator.name == code_coverage_validator_name.value), None)
            assert code_coverage_validator is not None
        else:
            code_coverage_validator = configuration.code_coverage_validator
            if code_coverage_validator is None:
                code_coverage_validator = next((validator for validator in CODE_COVERAGE_VALIDATORS if validator.name == "Standard"), None)
                assert code_coverage_validator is not None

    # Create the initial set of metadata based on provided flags
    metadata: Dict[str, Any] = {
        **_ResolveFlags("code coverage validator", code_coverage_validator, code_coverage_validator_flags),
        **_ResolveFlags("test parser", configuration.test_parser, test_parser_flags),
        **_ResolveFlags("test executor", test_executor, test_executor_flags),
        **_ResolveFlags("compiler", configuration.compiler, compiler_flags),
    }

    # Invoke
    if (
        filename_or_directory.is_file()
        or (
            filename_or_directory.is_dir()
            and configuration.compiler.IsSupported(filename_or_directory)
            and configuration.compiler.IsSupportedTestItem(filename_or_directory)
        )
    ):
        if quiet and filename_or_directory.is_file():
            raise typer.BadParameter("'quiet' is only used when executing tests via a directory.")

        if junit_xml_output_filename is not None:
            raise typer.BadParameter("JUnit XML output is only used when executing tests via a directory.")

        results = ExecuteTests.Execute(
            dm,
            [filename_or_directory],
            CurrentShell.CreateTempDirectory(),
            configuration.compiler,
            configuration.test_parser,
            test_executor,
            code_coverage_validator,
            metadata,
            parallel_tests=parallel_tests or False,
            single_threaded=single_threaded,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=False,
            junit_xml_output_filename=junit_xml_output_filename,
        )

        if results:
            DisplayResults.Display(dm, results)

        return

    if output_dir is None:
        raise typer.BadParameter("An output directory must be specified when the input is a directory.")

    if test_type is None:
        raise typer.BadParameter("The test type must be specified when the input is a directory.")

    if parallel_tests is None:
        test_type_info = next((test_type_info for test_type_info in TEST_TYPE_INFOS if test_type_info.name == test_type), None)
        if test_type_info is not None:
            parallel_tests = test_type_info.execute_in_parallel
        else:
            parallel_tests = False

    test_items: List[Path] = [
        find_result.path
        for find_result in Filter(
            dm,
            Find(
                dm,
                filename_or_directory,
                ignore_ignore_filenames,
                include_all_tests=True,
            ),
            test_type,
            configuration.compiler.name,
            configuration.test_parser.name,
        )
    ]

    if not test_items:
        dm.WriteLine("No tests found matching '{}'.".format(test_type))
        return

    results = ExecuteTests.Execute(
        dm,
        test_items,
        output_dir,
        configuration.compiler,
        configuration.test_parser,
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
        junit_xml_output_filename=junit_xml_output_filename,
    )

    if results:
        if not quiet:
            DisplayResults.Display(dm, results)

        DisplayResults.DisplayQuiet(dm, results)


# ----------------------------------------------------------------------
def Find(
    dm: DoneManager,
    input_dir: Path,
    ignore_ignore_filenames: Optional[List[Path]],
    *,
    include_all_tests: bool,                # Include all tests, even those that do not match a configuration
) -> List[FindResult]:
    ignore_ignore_filenames = ignore_ignore_filenames or []

    directory_compiler_info: Dict[CompilerImpl, List[TestParserImpl]] = {}
    filename_compiler_info: Dict[CompilerImpl, List[TestParserImpl]] = {}

    for compiler in COMPILERS:
        test_parsers: List[TestParserImpl] = [
            test_parser for test_parser in TEST_PARSERS if test_parser.IsSupportedCompiler(compiler)
        ]

        if test_parsers:
            if compiler.input_type == InputType.Directories:
                directory_compiler_info[compiler] = test_parsers
            elif compiler.input_type == InputType.Files:
                filename_compiler_info[compiler] = test_parsers
            else:
                assert False, compiler.input_type  # pragma: no cover

    if not directory_compiler_info and not filename_compiler_info:
        dm.WriteInfo("No compilers were found.\n")
        return []

    configurations_map: Dict[Tuple[CompilerImpl, TestParserImpl], List[str]] = {}

    for configuration in CONFIGURATIONS:
        configurations_map.setdefault((configuration.compiler, configuration.test_parser), []).append(configuration.name)

    results: List[FindResult] = []
    ignored_count = 0
    ignore_override_count = 0

    with dm.Nested(
        "Searching for tests in '{}'...".format(input_dir),
        [
            lambda: "{} found".format(inflect.no("test item", len(results))),
            lambda: "{} ignored".format(inflect.no("test item", ignored_count)),
            lambda: "{} overridden".format(inflect.no("ignore file", ignore_override_count)),
        ],
        suffix="\n",
    ) as search_dm:
        for root, directories, filenames in EnumSource.EnumSource(input_dir):
            if (root / DO_NOT_PARSE_FILENAME).exists():
                search_dm.WriteInfo("Skipping '{}' and its descendants due to '{}'.\n".format(root, DO_NOT_PARSE_FILENAME))

                directories[:] = []
                continue

            directory_is_enabled = True

            potential_ignore_filename = root / IGNORE_FILENAME
            if potential_ignore_filename.exists():
                if potential_ignore_filename in ignore_ignore_filenames:
                    search_dm.WriteVerbose(
                        "The ignore item '{}' was explicitly overridden.\n".format(
                            potential_ignore_filename,
                        ),
                    )

                    ignore_override_count += 1
                else:
                    search_dm.WriteInfo(
                        "'{}' has been excluded due to the ignore item '{}'.\n".format(
                            root,
                            potential_ignore_filename.name,
                        ),
                    )

                    ignored_count += 1

                    directory_is_enabled = False

            # Process compilers that operate on directories
            for compiler, test_parsers in directory_compiler_info.items():
                if not compiler.IsSupported(root):
                    search_dm.WriteVerbose(
                        "'{}' is not supported by the compiler '{}'.\n".format(root, compiler.name),
                    )
                    continue

                if not compiler.IsSupportedTestItem(root):
                    search_dm.WriteVerbose(
                        "'{}' is not a test item that is supported by the compiler '{}'.\n".format(
                            root,
                            compiler.name,
                        ),
                    )
                    continue

                for test_parser in test_parsers:
                    configurations = configurations_map.get((compiler, test_parser), None)
                    if configurations is None and not include_all_tests:
                        continue

                    if not test_parser.IsSupportedTestItem(root):
                        search_dm.WriteVerbose(
                            "'{}' is not supported by the test parser '{}'.\n".format(
                                root,
                                test_parser.name,
                            ),
                        )
                        continue

                    results.append(
                        FindResult(
                            compiler,
                            test_parser,
                            configurations,
                            root.name,
                            root,
                            is_enabled=directory_is_enabled,
                        ),
                    )

            # Process compilers that operate on filenames
            if filename_compiler_info:
                for filename in filenames:
                    fullpath = root / filename

                    file_is_enabled = True

                    potential_ignore_filename = fullpath.parent / (fullpath.name + "-ignore")
                    if potential_ignore_filename.exists():
                        if potential_ignore_filename in ignore_ignore_filenames:
                            search_dm.WriteVerbose(
                                "The ignore item '{}' was explicitly overridden.\n".format(
                                    potential_ignore_filename,
                                ),
                            )

                            ignore_override_count += 1
                        else:
                            search_dm.WriteInfo(
                                "'{}' has been excluded due to the ignore item '{}'.\n".format(
                                    fullpath,
                                    potential_ignore_filename.name,
                                ),
                            )

                            ignored_count += 1

                            file_is_enabled = False

                    for compiler, test_parsers in filename_compiler_info.items():
                        if not compiler.IsSupported(fullpath):
                            search_dm.WriteVerbose(
                                "'{}' is not supported by the compiler '{}'.\n".format(
                                    fullpath,
                                    compiler.name,
                                ),
                            )
                            continue

                        if not compiler.IsSupportedTestItem(fullpath):
                            search_dm.WriteVerbose(
                                "'{}' is not a test item that is supported by the compiler '{}'.\n".format(
                                    fullpath,
                                    compiler.name,
                                ),
                            )
                            continue

                        for test_parser in test_parsers:
                            configurations = configurations_map.get((compiler, test_parser), None)
                            if configurations is None and not include_all_tests:
                                continue

                            if not test_parser.IsSupportedTestItem(fullpath):
                                search_dm.WriteVerbose(
                                    "'{}' is not supported by the test parser '{}'.\n".format(
                                        fullpath,
                                        test_parser.name,
                                    ),
                                )
                                continue

                            results.append(
                                FindResult(
                                    compiler,
                                    test_parser,
                                    configurations,
                                    root.name,
                                    fullpath,
                                    is_enabled=directory_is_enabled and file_is_enabled,
                                ),
                            )

    return results


# ----------------------------------------------------------------------
def Filter(
    dm: DoneManager,
    original_results: List[FindResult],
    test_type: str,
    compiler_name: str,
    test_parser_name: Optional[str],
) -> List[FindResult]:
    if test_parser_name:
        is_supported_test_item_func = lambda result: result.test_parser.name == test_parser_name
    else:
        is_supported_test_item_func = lambda _: True

    results: List[FindResult] = []

    with dm.Nested(
        "Filtering {}...".format(inflect.no("test result", len(original_results))),
        lambda: "{} left".format(inflect.no("test item", len(results))),
    ):
        results += [
            result for result in original_results
            if (
                result.is_enabled
                and result.compiler.name == compiler_name
                and is_supported_test_item_func(result)
                and result.path.parent.name == test_type
            )
        ]

        return results


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ResolveFlags(
    desc: str,
    plugin: Union[None, CompilerImpl, TestExecutorImpl, TestParserImpl, CodeCoverageValidatorImpl],
    flags: Optional[List[str]],
) -> Dict[str, Any]:
    resolved_flags = TyperEx.PostprocessDictArgument(flags)

    if not plugin:
        if resolved_flags:
            raise typer.BadParameter("{desc} flags are not valid without a {desc}.".format(desc=desc))

        return {}

    return TyperEx.ProcessArguments(plugin.GetCustomCommandLineArgs(), resolved_flags.items())
