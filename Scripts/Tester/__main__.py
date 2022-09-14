# ----------------------------------------------------------------------
# |
# |  __main__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 14:22:50
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""General purpose test executor."""

import os
import re
import sys
import textwrap

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

try:
    import typer
    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import EnumSource
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from Common_FoundationEx.CompilerImpl import CompilerImpl, InputType
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx.TesterPlugins.CodeCoverageValidatorImpl import CodeCoverageValidatorImpl
from Common_FoundationEx.TesterPlugins.TestExecutorImpl import TestExecutorImpl
from Common_FoundationEx.TesterPlugins.TestParserImpl import TestParserImpl
from Common_FoundationEx import TyperEx

import DisplayResults
from ExecuteTests import ExecuteTests
from TestTypes import TYPES as TEST_TYPE_INFOS


# ----------------------------------------------------------------------
sys.path.insert(0, Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from RepositoryBootstrap import DynamicPluginArchitecture  # pylint: disable=import-error


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
_COMPILERS: List[CompilerImpl]                                              = []
_TEST_EXECUTORS: List[TestExecutorImpl]                                     = []
_TEST_PARSERS: List[TestParserImpl]                                         = []
_CODE_COVERAGE_VALIDATORS: List[CodeCoverageValidatorImpl]                  = []

_CONFIGURATIONS: List[Configuration]                                        = []


# ----------------------------------------------------------------------
def InitGlobals():
    with DoneManager.Create(
        sys.stdout,
        "\nCalculating dynamic content...",
        [
            lambda: inflect.no("compiler", len(_COMPILERS)),
            lambda: inflect.no("test executor", len(_TEST_EXECUTORS)),
            lambda: inflect.no("test parser", len(_TEST_PARSERS)),
            lambda: inflect.no("code coverage validator", len(_CODE_COVERAGE_VALIDATORS)),
            lambda: inflect.no("configuration", len(_CONFIGURATIONS)),
        ],
        display_exception_details=False,
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
                            _COMPILERS.append(compiler())
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
                    _TEST_EXECUTORS.append(executor())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_TEST_PARSERS"):
                test_parser = getattr(mod, "TestParser", None)
                if test_parser is None:
                    raise Exception("'TestParser was not found in '{}'.".format(mod.__file__))

                try:
                    _TEST_PARSERS.append(test_parser())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

            for mod in DynamicPluginArchitecture.EnumeratePlugins("DEVELOPMENT_ENVIRONMENT_CODE_COVERAGE_VALIDATORS"):
                validator = getattr(mod, "CodeCoverageValidator", None)
                if validator is None:
                    raise Exception("'CodeCoverageValidator' was not found in '{}'.".format(mod.__file__))

                try:
                    _CODE_COVERAGE_VALIDATORS.append(validator())
                except:
                    dm.WriteError(mod.__file__ or "")
                    raise

            # Validate
            if not _CODE_COVERAGE_VALIDATORS:
                raise Exception("No code coverage validators were found.")
            if not _COMPILERS:
                raise Exception("No compilers were found.")
            if not _TEST_EXECUTORS:
                raise Exception("No test executors were found.")
            if not _TEST_PARSERS:
                raise Exception("No test parsers were found.")

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
                compiler = next((compiler for compiler in _COMPILERS if compiler.name == compiler_name), None)
                if compiler is None:
                    raise Exception("The compiler name '{}' in the configuration '{}' is not valid.".format(compiler_name, config_name))

                test_parser = next((test_parser for test_parser in _TEST_PARSERS if test_parser.name == test_parser_name), None)
                if test_parser is None:
                    raise Exception("The test parser name '{}' in the configuration '{}' is not valid.".format(test_parser_name, config_name))

                if coverage_executor_name is None:
                    coverage_executor = None
                else:
                    coverage_executor = next((ce for ce in _TEST_EXECUTORS if ce.name == coverage_executor_name), None)
                    if coverage_executor is None:
                        raise Exception("The coverage executor name '{}' in the configuration '{}' is not valid.".format(coverage_executor_name, config_name))

                if coverage_validator_name is None:
                    coverage_validator = None
                else:
                    coverage_validator = next((cv for cv in _CODE_COVERAGE_VALIDATORS if cv.name == coverage_validator_name), None)
                    if coverage_validator is None:
                        raise Exception("The coverage validator '{}' in the configuration '{}' is not valid.".format(coverage_validator_name, config_name))

                # Save the configuration
                _CONFIGURATIONS.append(
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

            _CONFIGURATIONS.sort(key=lambda value: value.priority)

        # ----------------------------------------------------------------------

        LoadPlugins()
        CreateConfigurations()

    # ----------------------------------------------------------------------

InitGlobals()
del InitGlobals


# ----------------------------------------------------------------------
_compiler_enum                              = Types.StringsToEnum("CompilerEnum", [compiler.name for compiler in _COMPILERS])
_optional_test_executor_enum                = Types.StringsToEnum("OptionalTestExecutorEnum", ["None", ] + [test_executor.name for test_executor in _TEST_EXECUTORS])
_test_parser_enum                           = Types.StringsToEnum("TestParserEnum", [test_parser.name for test_parser in _TEST_PARSERS])
_code_coverage_validator_enum               = Types.StringsToEnum("CodeCoverageValidatorEnum", [code_coverage_validator.name for code_coverage_validator in _CODE_COVERAGE_VALIDATORS])
_optional_code_coverage_validator_enum      = Types.StringsToEnum("OptionalCodeCoverageValidatorEnum", ["None", ] + [code_coverage_validator.name for code_coverage_validator in _CODE_COVERAGE_VALIDATORS])
_configuration_enum                         = Types.StringsToEnum("ConfigurationEnum", [configuration.name for configuration in _CONFIGURATIONS])


# ----------------------------------------------------------------------
def _HelpEpilog() -> str:
    sections: List[str] = [
        # Configuration
        textwrap.dedent(
            """\
            [bold]Configurations[/]

            A configuration specifies pre-configured values for the compiler, test_parser, test_executor (optional), and code_coverage_validator (optional).

            {}
            """,
        ).format(
            TextwrapEx.CreateTable(
                [
                    "Name",
                    "Compiler",
                    "Test Parser",
                    "Test Executor (optional)",
                    "Code Coverage Validator (optional)",
                ],
                [
                    [
                        "{}) {}".format(index + 1, config.name),
                        config.compiler.name,
                        config.test_parser.name,
                        "<None>" if config.test_executor is None else config.test_executor.name,
                        "<None>" if config.code_coverage_validator is None else config.code_coverage_validator.name,
                    ]
                    for index, config in enumerate(_CONFIGURATIONS)
                ],
            ),
        ),

        # Compilers
        textwrap.dedent(
            """\
            [bold]Compilers[/]

            Compiler have knowledge of specific file types or directories that match an expected format. They detect items that they are able to process and compile or verify that content.

            {}
            """,
        ).format(
            TextwrapEx.CreateTable(
                ["Name", "Description"],
                [
                    ["{}) {}".format(index + 1, compiler.name), compiler.description]
                    for index, compiler in enumerate(_COMPILERS)
                ],
            ),
        ),

        # Test Parsers
        textwrap.dedent(
            """\
            [bold]Test Parsers[/]

            Test parsers analyze test execution output to determine if a test passed or failed.

            {}
            """,
        ).format(
            TextwrapEx.CreateTable(
                ["Name", "Description"],
                [
                    ["{}) {}".format(index + 1, test_parser.name), test_parser.description]
                    for index, test_parser in enumerate(_TEST_PARSERS)
                ],
            ),
        ),

        # Test Executors
        textwrap.dedent(
            """\
            [bold]Test Executors[/]

            Test executors execute tests (for example, ensuring that code coverage information is extracted during a test's execution).

            {}
            """,
        ).format(
            TextwrapEx.CreateTable(
                ["Name", "Description"],
                [
                    ["{}) {}".format(index + 1, test_executor.name), test_executor.description]
                    for index, test_executor in enumerate(_TEST_EXECUTORS)
                ],
            ),
        ),

        # Code Coverage Validators
        textwrap.dedent(
            """\
            [bold]Code Coverage Validators[/]

            When code coverage is enabled, code coverage validators ensure that extracted code coverage information meets the expected standards.

            {}
            """,
        ).format(
            TextwrapEx.CreateTable(
                ["Name", "Description"],
                [
                    ["{}) {}".format(index + 1, code_coverage_validator.name), code_coverage_validator.description]
                    for index, code_coverage_validator in enumerate(_CODE_COVERAGE_VALIDATORS)
                ],
            ),
        ),
    ]

    return "\n".join(sections).replace("\n", "\n\n")


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    """Groups funcs in declaration order"""
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    rich_markup_mode="rich",
    epilog=_HelpEpilog(),
)


# ----------------------------------------------------------------------
_configuration_argument                     = typer.Argument(..., help="Name of configuration to use when building and testing.")
_directory_input_argument                   = typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Input directory used as the root to search for tests.")
_generic_input_argument                     = typer.Argument(..., exists=True, resolve_path=True, help="Input file or directory, where the type required depends on the compiler being used.")
_output_argument                            = typer.Argument(..., file_okay=False, resolve_path=True, help="Name of the directory used to store results.")
_test_type_argument                         = typer.Argument(..., help="Name of test types to process (e.g. 'UnitTests', 'EndToEndTests')")

_compiler_argument                          = typer.Argument(..., help="Name of compiler used to build tests.")
_test_executor_argument                     = typer.Argument(..., help="Name of test executor used to execute tests.")
_test_parser_argument                       = typer.Argument(..., help="Name of test parser used to extract results from test output.")

_code_coverage_option                       = typer.Option(False, "--code-coverage", help="Measure code coverage during tests.")
_parallel_tests_option                      = typer.Option(None, "--parallel-tests", help="Run tests in parallel. If not provided, the correct setting will be set based on the test type specified.")
_single_threaded_option                     = typer.Option(False, "--single-threaded", help="Only use a single thread to build and run tests.")

_iterations_option                          = typer.Option(1, "--iterations", min=1, help="Run the test N times; this functionality can be helpful when testing non-deterministic failures.")
_continue_iterations_on_error_option        = typer.Option(False, "--continue-iterations-on-error", help="Continue processing test iterations, even when errors are encountered.")

_debug_only_option                          = typer.Option(False, "--debug-only", help="Only process debug configurations.")
_release_only_option                        = typer.Option(False, "--release-only", help="Only process release configurations.")
_build_only_option                          = typer.Option(False, "--build-only", help="Build the tests but do not run them.")
_skip_build_option                          = typer.Option(False, "--skip-build", help="Do not build the tests before running them; this option can only be used with compilers that act as Verifiers.")

_quiet_option                               = typer.Option(False, "--quiet", help="Write less output to the terminal.")
_verbose_option                             = typer.Option(False, "--verbose", help="Write verbose information to the terminal.")
_debug_option                               = typer.Option(False, "--debug", help="Write additional debug information to the terminal.")

_code_coverage_validator_argument           = typer.Argument(..., help="Name of the code coverage validator to use.")
_code_coverage_validator_option             = typer.Option(None, help="Name of the code coverage validator to use.")

_junit_xml_output_filename_option           = typer.Option(None, help="Write results in JUnit format to the specified file for interoperability with other tools.")

_compiler_flags_option                      = TyperEx.TypeDictOption(
    None,
    {},
    "--compiler-flag",
    allow_any__=True,
    help="Flag(s) passed to the compiler to customize behavior.",
)

_test_executor_flags_option                 = TyperEx.TypeDictOption(
    None,
    {},
    "--test-executor-flag",
    allow_any__=True,
    help="Flag(s) passed to the test executor to customize behavior.",
)

_test_parser_flags_option                   = TyperEx.TypeDictOption(
    None,
    {},
    "--test-parser-flag",
    allow_any__=True,
    help="Flag(s) passed to the test parser to customize behavior.",
)

_code_coverage_validator_flags_option       = TyperEx.TypeDictOption(
    None,
    {},
    "--code-coverage-flag",
    allow_any__=True,
    help="Flag(s) passed to the code coverage validator to customize behavior.",
)


# ----------------------------------------------------------------------
@app.command("TestItem", rich_help_panel="Testing with Configurations", no_args_is_help=True)
def TestItem(
    filename_or_directory: Path=_generic_input_argument,

    code_coverage: bool=_code_coverage_option,

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    code_coverage_validator: Optional[_code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,
) -> None:
    """Tests a single item; where an "item" can be a file or directory depending on which compiler is used (e.g. run this test)."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        # ----------------------------------------------------------------------
        def GetConfiguration() -> Optional[Configuration]:
            for config in _CONFIGURATIONS:
                if (
                    config.compiler.IsSupported(filename_or_directory)
                    and config.compiler.IsSupportedTestItem(filename_or_directory)
                    and config.test_parser.IsSupportedTestItem(filename_or_directory)
                ):
                    return config

            return None

        # ----------------------------------------------------------------------

        configuration = GetConfiguration()
        if configuration is None:
            raise typer.BadParameter("Unable to find a configuration with a compiler and test parser that supports '{}'.".format(filename_or_directory))

        return _TestImpl(
            dm,
            configuration,
            filename_or_directory,
            output_dir=None,
            test_type=None,
            code_coverage=code_coverage,
            parallel_tests=False,
            single_threaded=True,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=None,
        )


# ----------------------------------------------------------------------
@app.command("TestType", rich_help_panel="Testing with Configurations", no_args_is_help=True)
def TestType(
    config_name: _configuration_enum=_configuration_argument,  # type: ignore
    input_dir: Path=_directory_input_argument,
    output_dir: Path=_output_argument,
    test_type: str=_test_type_argument,

    code_coverage: bool=_code_coverage_option,

    parallel_tests: Optional[bool]=_parallel_tests_option,
    single_threaded: bool=_single_threaded_option,

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    code_coverage_validator: Optional[_code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,

    junit_xml_output_filename: Optional[str]=_junit_xml_output_filename_option,
) -> None:
    """Runs all tests associated with the specified test classification and configuration (e.g. run all python unit tests)."""

    configuration = next((config for config in _CONFIGURATIONS if config.name == config_name.value), None)
    assert configuration is not None

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        return _TestImpl(
            dm,
            configuration,
            input_dir,
            output_dir,
            test_type,
            code_coverage=code_coverage,
            parallel_tests=parallel_tests,
            single_threaded=single_threaded,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=junit_xml_output_filename,
        )


# ----------------------------------------------------------------------
@app.command("TestAll", rich_help_panel="Testing with Configurations", no_args_is_help=True)
def TestAll(
    input_dir: Path=_directory_input_argument,
    output_dir: Path=_output_argument,
    test_type: str=_test_type_argument,

    code_coverage: bool=_code_coverage_option,

    parallel_tests: Optional[bool]=_parallel_tests_option,
    single_threaded: bool=_single_threaded_option,

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    code_coverage_validator: Optional[_code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,

    junit_xml_output_filename: Optional[str]=_junit_xml_output_filename_option,
) -> None:
    """Runs all tests associated with the specified test classification across all configurations (e.g. run all unit tests)."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        for config_index, config in enumerate(_CONFIGURATIONS):
            with dm.Nested(
                "Testing '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(_CONFIGURATIONS),
                ),
                suffix="\n\n",
            ) as nested_dm:
                _TestImpl(
                    nested_dm,
                    config,
                    input_dir,
                    output_dir,
                    test_type,
                    code_coverage=code_coverage,
                    parallel_tests=parallel_tests,
                    single_threaded=single_threaded,
                    iterations=iterations,
                    continue_iterations_on_error=continue_iterations_on_error,
                    debug_only=debug_only,
                    release_only=release_only,
                    build_only=build_only,
                    skip_build=skip_build,
                    quiet=quiet,
                    code_coverage_validator_name=code_coverage_validator,
                    compiler_flags=compiler_flags,
                    test_executor_flags=test_executor_flags,
                    test_parser_flags=test_parser_flags,
                    code_coverage_validator_flags=code_coverage_validator_flags,
                    junit_xml_output_filename=junit_xml_output_filename,
                )


# ----------------------------------------------------------------------
@app.command("MatchTests", rich_help_panel="Test Matching", no_args_is_help=True)
def MatchTests(
    input_dir: Path=_directory_input_argument,
    compiler: _compiler_enum=_compiler_argument,  # type: ignore
    test_type: str=_test_type_argument,
    verbose: bool=_verbose_option,
) -> None:
    """Matches all tests associated with the specified test classification and configuration (e.g. match all python unit tests)."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in _COMPILERS if compiler_type.name == compiler.value), None)
        assert resolved_compiler is not None

        if resolved_compiler.input_type != InputType.Files:
            dm.WriteInfo("Tests can only be matched for compilers that operate on individual files.")
            return

        return _MatchTestsImpl(dm, input_dir, resolved_compiler, test_type)


# ----------------------------------------------------------------------
@app.command("MatchAllTests", rich_help_panel="Test Matching", no_args_is_help=True)
def MatchAllTests(
    input_dir: Path=_directory_input_argument,
    test_type: str=_test_type_argument,
    verbose: bool=_verbose_option,
) -> None:
    """Matches all tests associated with the specified test classification across all configurations (e.g. match all unit tests)."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        for config_index, config in enumerate(_CONFIGURATIONS):
            with dm.Nested(
                "Matching '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(_CONFIGURATIONS),
                ),
                suffix="\n",
            ) as config_dm:
                if config.compiler.input_type != InputType.Files:
                    config_dm.WriteInfo("The compiler does not operate on files and cannot be used to match tests.")
                    continue

                _MatchTestsImpl(config_dm, input_dir, config.compiler, test_type)


# ----------------------------------------------------------------------
@app.command("Execute", rich_help_panel="Testing with Specific Compilers, TestParsers, TestExecutors, and CodeCoverageValidators", no_args_is_help=True)
def Execute(
    filename_or_directory: Path=_generic_input_argument,

    compiler: _compiler_enum=_compiler_argument,                                                        # type: ignore
    test_executor: _optional_test_executor_enum=_test_executor_argument,                                # type: ignore
    test_parser: _test_parser_enum=_test_parser_argument,                                               # type: ignore
    code_coverage_validator: _optional_code_coverage_validator_enum=_code_coverage_validator_argument,  # type: ignore

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,
) -> None:
    """\
    Executes a specific test using a specific compiler, test parser, test executor, and code coverage
    validator. In most cases, it is simpler to invoke a `Test____` method rather than invoking
    this method directly.
    """

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in _COMPILERS if compiler_type.name == compiler.value), None)
        assert resolved_compiler is not None

        if test_executor.value == "None":
            resolved_test_executor = None
        else:
            resolved_test_executor = next((te_type for te_type in _TEST_EXECUTORS if te_type.name == test_executor.value), None)
            assert resolved_test_executor is not None

        resolved_test_parser = next((tp_type for tp_type in _TEST_PARSERS if tp_type.name == test_parser.value), None)
        assert resolved_test_parser is not None

        is_valid_code_coverage_validator = code_coverage_validator.value != "None"

        return _TestImpl(
            dm,
            Configuration(
                "Custom",
                0,
                resolved_compiler,
                resolved_test_parser,
                resolved_test_executor,
                None,
            ),
            filename_or_directory,
            output_dir=None,
            test_type=None,
            code_coverage=is_valid_code_coverage_validator,
            parallel_tests=False,
            single_threaded=True,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator if is_valid_code_coverage_validator else None,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=None,
        )


# ----------------------------------------------------------------------
@app.command("ExecuteTree", rich_help_panel="Testing with Specific Compilers, TestParsers, TestExecutors, and CodeCoverageValidators", no_args_is_help=True)
def ExecuteTree(
    input_dir: Path=_directory_input_argument,
    output_dir: Path=_output_argument,

    compiler: _compiler_enum=_compiler_argument,                                                        # type: ignore
    test_executor: _optional_test_executor_enum=_test_executor_argument,                                # type: ignore
    test_parser: _test_parser_enum=_test_parser_argument,                                               # type: ignore
    code_coverage_validator: _optional_code_coverage_validator_enum=_code_coverage_validator_argument,  # type: ignore

    test_type: str=_test_type_argument,

    parallel_tests: Optional[bool]=_parallel_tests_option,
    single_threaded: bool=_single_threaded_option,

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,

    junit_xml_output_filename: Optional[str]=_junit_xml_output_filename_option,
) -> None:
    """\
    Executes all tests under a root directory using a specific compiler, test parser, test executor,
    and code coverage validator. In most cases, it is simpler to invoke a `Test____` method rather
    than invoking this method directly.
    """

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in _COMPILERS if compiler_type.name == compiler.value), None)
        assert resolved_compiler is not None

        if test_executor.value == "None":
            resolved_test_executor = None
        else:
            resolved_test_executor = next((te_type for te_type in _TEST_EXECUTORS if te_type.name == test_executor.value), None)
            assert resolved_test_executor is not None

        resolved_test_parser = next((tp_type for tp_type in _TEST_PARSERS if tp_type.name == test_parser.value), None)
        assert resolved_test_parser is not None

        is_valid_code_coverage_validator = code_coverage_validator.value != "None"

        return _TestImpl(
            dm,
            Configuration(
                "Custom",
                0,
                resolved_compiler,
                resolved_test_parser,
                resolved_test_executor,
                None,
            ),
            input_dir,
            output_dir,
            test_type,
            code_coverage=is_valid_code_coverage_validator,
            parallel_tests=parallel_tests,
            single_threaded=single_threaded,
            iterations=iterations,
            continue_iterations_on_error=continue_iterations_on_error,
            debug_only=debug_only,
            release_only=release_only,
            build_only=build_only,
            skip_build=skip_build,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator if is_valid_code_coverage_validator else None,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=junit_xml_output_filename,
        )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _TestImpl(
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

    quiet: bool,

    code_coverage_validator_name: Optional[_code_coverage_validator_enum],  # type: ignore

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
        test_executor = next((executor for executor in _TEST_EXECUTORS if executor.name == "Standard"), None)

    assert test_executor is not None

    if code_coverage and not test_executor.is_code_coverage_executor:
        raise typer.BadParameter("The test executor '{}' does not support code coverage.".format(test_executor.name))

    # Get the code coverage validator
    code_coverage_validator: Optional[CodeCoverageValidatorImpl] = None

    if code_coverage:
        if code_coverage_validator_name:
            code_coverage_validator = next((validator for validator in _CODE_COVERAGE_VALIDATORS if validator.name == code_coverage_validator_name.value), None)
            assert code_coverage_validator is not None
        else:
            code_coverage_validator = configuration.code_coverage_validator
            if code_coverage_validator is None:
                code_coverage_validator = next((validator for validator in _CODE_COVERAGE_VALIDATORS if validator.name == "Standard"), None)
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
        or (filename_or_directory.is_dir() and configuration.compiler.IsSupported(filename_or_directory))
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

    test_items = _FindTests(
        dm,
        filename_or_directory,
        test_type,
        configuration.compiler,
        configuration.test_parser,
    )

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
def _FindTests(
    dm: DoneManager,
    directory: Path,
    test_type: str,
    compiler: CompilerImpl,
    test_parser: Optional[TestParserImpl],
) -> List[Path]:
    assert directory.is_dir(), directory

    if test_parser:
        is_supported_test_item_func = lambda path: test_parser.IsSupportedTestItem(path)
        test_parser_name = test_parser.name
    else:
        is_supported_test_item_func = lambda _: True
        test_parser_name = "ignored"

    test_items: List[Path] = []

    with dm.Nested(
        "Finding tests in '{}'...".format(directory),
        lambda: "{} found".format(inflect.no("test item", len(test_items))),
        suffix="\n",
    ) as search_dm:
        if compiler.input_type == InputType.Files:
            # ----------------------------------------------------------------------
            def ProcessFiles(
                root: Path,
                directories: List[str],  # pylint: disable=unused-argument
                filenames: List[str],
            ) -> None:
                for filename in filenames:
                    fullpath = root / filename

                    if not compiler.IsSupported(fullpath) or not compiler.IsSupportedTestItem(fullpath):
                        search_dm.WriteVerbose(
                            "'{}' is not supported by the compiler '{}'.\n".format(
                                fullpath,
                                compiler.name,
                            ),
                        )
                        continue

                    if not is_supported_test_item_func(fullpath):
                        search_dm.WriteVerbose(
                            "'{}' is not supported by the test parser '{}'.\n".format(
                                fullpath,
                                test_parser_name,
                            ),
                        )

                        continue

                    test_items.append(fullpath)

            # ----------------------------------------------------------------------

            process_func = ProcessFiles

        elif compiler.input_type == InputType.Directories:
            # ----------------------------------------------------------------------
            def ProcessDirectories(
                root: Path,
                directories: List[str],
                filename: List[str],        # pylint: disable=unused-argument
            ) -> None:
                if not compiler.IsSupported(root) or not compiler.IsSupportedTestItem(root):
                    search_dm.WriteVerbose(
                        "'{}' is not supported by the compiler '{}'.\n".format(
                            root,
                            compiler.name,
                        ),
                    )

                    return

                if not is_supported_test_item_func(root):
                    search_dm.WriteVerbose(
                        "'{}' is not supported by the test parser '{}'.\n".format(
                            root,
                            test_parser_name,
                        ),
                    )

                    return

                directories[:] = []

                test_items.append(root)

            # ----------------------------------------------------------------------

            process_func = ProcessDirectories

        else:
            assert False, compiler.input_type  # pragma: no cover

        for root, directories, filenames in EnumSource.EnumSource(directory):
            if root.name == test_type:
                process_func(root, directories, filenames)

    return test_items


# ----------------------------------------------------------------------
def _MatchTestsImpl(
    dm: DoneManager,
    input_dir: Path,
    compiler: CompilerImpl,
    test_type: str,
) -> None:
    ignore_dir_funcs: List[Callable[[Path], bool]] = EnumSource.ALL_SKIP_FUNCS

    source_items: List[Path] = []

    with dm.Nested(
        "Parsing '{}'...".format(input_dir),
        lambda: "{} found".format(inflect.no("test file", len(source_items))),
        suffix="\n" if dm.is_verbose else "",
    ) as search_dm:
        for root, _, filenames in EnumSource.EnumSource(input_dir, ignore_dir_funcs):
            for filename in filenames:
                fullpath = root / filename

                if compiler.IsSupported(fullpath):
                    source_items.append(fullpath)
                    search_dm.WriteVerbose(str(fullpath))

    test_items: List[Path] = _FindTests(dm, input_dir, test_type, compiler, None)

    len_test_items = len(test_items)

    with dm.Nested(
        "Removing ignored tests...",
        lambda: "{} removed".format(inflect.no("test file", len_test_items - len(test_items))),
    ) as remove_dm:
        # Remove any test items that correspond to sources that were explicitly removed.
        # We want to run these tests (so they shouldn't be removed from the output of `_FindTests`),
        # but we don't want them to appear in the output of this list.

        # ----------------------------------------------------------------------
        def IsMissingTest(
            filename: Path,
        ) -> bool:
            for parent in filename.parents:
                if any(ignore_dir_funcs(parent) for ignore_dir_funcs in ignore_dir_funcs):
                    remove_dm.WriteVerbose(str(filename))
                    return False

            return True

        # ----------------------------------------------------------------------

        test_items = [test_item for test_item in test_items if IsMissingTest(test_item)]

    # Compare the tests with the source items and report the differences
    matches = 0

    with dm.Nested(
        "Comparing...",
        [
            lambda: "{} matched".format(inflect.no("test", matches)),
            lambda: "{} unmatched".format(inflect.no("source item", len(source_items))),
            lambda: "{} unmatched".format(inflect.no("test item", len(test_items))),
        ],
        suffix="\n" if dm.is_verbose else "",
    ) as compare_dm:
        index = 0
        while index < len(source_items):
            source_item = source_items[index]

            test_item = compiler.ItemToTestName(source_item, test_type)
            if test_item and test_item.is_file():
                compare_dm.WriteVerbose("{} -> {}\n".format(str(source_item).ljust(120), test_item))
                matches += 1

                if test_item in test_items:
                    test_items.remove(test_item)

                del source_items[index]

                continue

            index += 1

    # ----------------------------------------------------------------------
    def DisplayItems(
        header: str,
        items: List[Path],
    ) -> None:
        with dm.YieldStream() as stream:
            indented_stream = StreamDecorator(stream, "    ")

            common_path = PathEx.GetCommonPath(*items)

            if common_path:
                len_common_path_parts = 0 if common_path is None else len(common_path.parts)

                display_info = {
                    str(Path(*source_item.parts[len_common_path_parts:])) : source_item
                    for source_item in source_items
                }

                indented_stream.write(
                    "\n\nAll files are relative to '{}'.\n\n".format(
                        common_path if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                            "file://{}".format(common_path.as_posix()),
                            str(common_path),
                        ),
                    ),
                )

                # ----------------------------------------------------------------------
                def DecorateRowsWithLink(
                    index: int,  # pylint: disable=unused-argument
                    values: List[str],
                ) -> List[str]:
                    if not dm.capabilities.is_headless:
                        fullpath = display_info[values[0].strip()]

                        values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                            "file://{}".format(fullpath.as_posix()),
                            values[0],
                        )

                    return values

                # ----------------------------------------------------------------------

                decorate_rows_func = DecorateRowsWithLink

            else:
                display_info = {str(source_item): source_item for source_item in source_items}

                decorate_rows_func = lambda index, values: values

            indented_stream.write("\n")

            indented_stream.write(
                TextwrapEx.CreateTable(
                    [header],
                    [
                        [display] for display in display_info
                    ],
                    decorate_values_func=decorate_rows_func,
                ),
            )

            indented_stream.write("\n")

        dm.result = -1

    # ----------------------------------------------------------------------

    if source_items:
        DisplayItems("Source Files Unmatched", source_items)

    if test_items:
        DisplayItems("Test Items Unmatched", test_items)


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

    return TyperEx.ProcessArguments(plugin.GetCustomArgs(), resolved_flags.items())


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
