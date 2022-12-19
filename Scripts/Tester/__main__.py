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

import sys
import textwrap

from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

try:
    import typer
    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from Common_FoundationEx.CompilerImpl.CompilerImpl import CompilerImpl, InputType
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx

import CommandLineImpl
import DisplayResults


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
                    for index, config in enumerate(CommandLineImpl.CONFIGURATIONS)
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
                    for index, compiler in enumerate(CommandLineImpl.COMPILERS)
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
                    for index, test_parser in enumerate(CommandLineImpl.TEST_PARSERS)
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
                    for index, test_executor in enumerate(CommandLineImpl.TEST_EXECUTORS)
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
                    for index, code_coverage_validator in enumerate(CommandLineImpl.CODE_COVERAGE_VALIDATORS)
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

_ignore_ignore_filenames_option             = typer.Option(None, "--ignore-ignore-filename", exists=True, dir_okay=False, resolve_path=True, help="Ignore filenames that would normally prevent execution, but should not prevent execution during this invocation. In other words, execute the build even though there is an ignore file present.")

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

    code_coverage_validator: Optional[CommandLineImpl.code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

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
        def GetConfiguration() -> Optional[CommandLineImpl.Configuration]:
            for config in CommandLineImpl.CONFIGURATIONS:
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

        return CommandLineImpl.Execute(
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
            ignore_ignore_filenames=None,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator,
            code_coverage_mismatch_is_error=True,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=None,
        )


# ----------------------------------------------------------------------
@app.command("TestType", rich_help_panel="Testing with Configurations", no_args_is_help=True)
def TestType(
    config_name: CommandLineImpl.configuration_enum=_configuration_argument,  # type: ignore
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

    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    code_coverage_validator: Optional[CommandLineImpl.code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,

    junit_xml_output_filename: Optional[str]=_junit_xml_output_filename_option,
) -> None:
    """Runs all tests associated with the specified test classification and configuration (e.g. run all python unit tests)."""

    configuration = next((config for config in CommandLineImpl.CONFIGURATIONS if config.name == config_name.value), None)
    assert configuration is not None

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        return CommandLineImpl.Execute(
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
            ignore_ignore_filenames=ignore_ignore_filenames,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator,
            code_coverage_mismatch_is_error=True,
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

    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,

    quiet: bool=_quiet_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,

    code_coverage_validator: Optional[CommandLineImpl.code_coverage_validator_enum]=_code_coverage_validator_option,  # type: ignore

    compiler_flags: Optional[List[str]]=_compiler_flags_option,
    test_executor_flags: Optional[List[str]]=_test_executor_flags_option,
    test_parser_flags: Optional[List[str]]=_test_parser_flags_option,
    code_coverage_validator_flags: Optional[List[str]]=_code_coverage_validator_flags_option,

    junit_xml_output_filename: Optional[str]=_junit_xml_output_filename_option,
) -> None:
    """Runs all tests associated with the specified test classification across all configurations (e.g. run all unit tests)."""

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        for config_index, config in enumerate(CommandLineImpl.CONFIGURATIONS):
            with dm.Nested(
                "Testing '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(CommandLineImpl.CONFIGURATIONS),
                ),
                suffix="\n\n",
            ) as nested_dm:
                CommandLineImpl.Execute(
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
                    ignore_ignore_filenames=ignore_ignore_filenames,
                    quiet=quiet,
                    code_coverage_validator_name=code_coverage_validator,
                    code_coverage_mismatch_is_error=False,
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
    compiler: CommandLineImpl.compiler_enum=_compiler_argument,  # type: ignore
    test_type: str=_test_type_argument,
    verbose: bool=_verbose_option,
) -> None:
    """Matches all tests associated with the specified test classification and configuration (e.g. match all python unit tests)."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in CommandLineImpl.COMPILERS if compiler_type.name == compiler.value), None)
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
        for config_index, config in enumerate(CommandLineImpl.CONFIGURATIONS):
            with dm.Nested(
                "Matching '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(CommandLineImpl.CONFIGURATIONS),
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

    compiler: CommandLineImpl.compiler_enum=_compiler_argument,                                                        # type: ignore
    test_executor: CommandLineImpl.optional_test_executor_enum=_test_executor_argument,                                # type: ignore
    test_parser: CommandLineImpl.test_parser_enum=_test_parser_argument,                                               # type: ignore
    code_coverage_validator: CommandLineImpl.optional_code_coverage_validator_enum=_code_coverage_validator_argument,  # type: ignore

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,

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

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in CommandLineImpl.COMPILERS if compiler_type.name == compiler.value), None)
        assert resolved_compiler is not None

        if test_executor.value == "None":
            resolved_test_executor = None
        else:
            resolved_test_executor = next((te_type for te_type in CommandLineImpl.TEST_EXECUTORS if te_type.name == test_executor.value), None)
            assert resolved_test_executor is not None

        resolved_test_parser = next((tp_type for tp_type in CommandLineImpl.TEST_PARSERS if tp_type.name == test_parser.value), None)
        assert resolved_test_parser is not None

        is_valid_code_coverage_validator = code_coverage_validator.value != "None"

        return CommandLineImpl.Execute(
            dm,
            CommandLineImpl.Configuration(
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
            ignore_ignore_filenames=ignore_ignore_filenames,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator if is_valid_code_coverage_validator else None,
            code_coverage_mismatch_is_error=True,
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

    compiler: CommandLineImpl.compiler_enum=_compiler_argument,                                                        # type: ignore
    test_executor: CommandLineImpl.optional_test_executor_enum=_test_executor_argument,                                # type: ignore
    test_parser: CommandLineImpl.test_parser_enum=_test_parser_argument,                                               # type: ignore
    code_coverage_validator: CommandLineImpl.optional_code_coverage_validator_enum=_code_coverage_validator_argument,  # type: ignore

    test_type: str=_test_type_argument,

    parallel_tests: Optional[bool]=_parallel_tests_option,
    single_threaded: bool=_single_threaded_option,

    iterations: int=_iterations_option,
    continue_iterations_on_error: bool=_continue_iterations_on_error_option,

    debug_only: bool=_debug_only_option,
    release_only: bool=_release_only_option,
    build_only: bool=_build_only_option,
    skip_build: bool=_skip_build_option,

    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,

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

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        resolved_compiler = next((compiler_type for compiler_type in CommandLineImpl.COMPILERS if compiler_type.name == compiler.value), None)
        assert resolved_compiler is not None

        if test_executor.value == "None":
            resolved_test_executor = None
        else:
            resolved_test_executor = next((te_type for te_type in CommandLineImpl.TEST_EXECUTORS if te_type.name == test_executor.value), None)
            assert resolved_test_executor is not None

        resolved_test_parser = next((tp_type for tp_type in CommandLineImpl.TEST_PARSERS if tp_type.name == test_parser.value), None)
        assert resolved_test_parser is not None

        is_valid_code_coverage_validator = code_coverage_validator.value != "None"

        return CommandLineImpl.Execute(
            dm,
            CommandLineImpl.Configuration(
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
            ignore_ignore_filenames=ignore_ignore_filenames,
            quiet=quiet,
            code_coverage_validator_name=code_coverage_validator if is_valid_code_coverage_validator else None,
            code_coverage_mismatch_is_error=True,
            compiler_flags=compiler_flags,
            test_executor_flags=test_executor_flags,
            test_parser_flags=test_parser_flags,
            code_coverage_validator_flags=code_coverage_validator_flags,
            junit_xml_output_filename=junit_xml_output_filename,
        )


# ----------------------------------------------------------------------
@app.command("List", rich_help_panel="Test Discovery", no_args_is_help=True)
def ListFunc(
    input_dir: Path=_directory_input_argument,
    all_tests: bool=typer.Option(False, "--all-tests", help="Display all tests, even those that do not match a configuration."),
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,
) -> None:
    """Lists all tests."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        results = CommandLineImpl.Find(
            dm,
            input_dir,
            ignore_ignore_filenames=None,
            include_all_tests=all_tests,
        )

        DisplayResults.DisplayListResults(dm, results)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _MatchTestsImpl(
    dm: DoneManager,
    input_dir: Path,
    compiler: CompilerImpl,
    test_type: str,
) -> None:
    if not compiler.SupportsTestItemMatching():
        dm.WriteInfo("The compiler '{}' does not support test item matching.\n".format(compiler.name))
        return

    tests = CommandLineImpl.Filter(
        dm,
        CommandLineImpl.Find(
            dm,
            input_dir,
            ignore_ignore_filenames=[],
            include_all_tests=True,
        ),
        test_type,
        compiler.name,
        test_parser_name=None,
    )

    if not tests:
        return

    test_mismatches: Dict[Path, Path] = {}
    source_mismatches: Dict[Path, Path] = {}
    processed_source_dirs: Set[Path] = set()

    with dm.Nested(
        "\nOrganizing content...",
        [
            lambda: "{} source {} found".format(len(source_mismatches), inflect.plural("mismatch", len(source_mismatches))),
            lambda: "{} test {} found".format(len(test_mismatches), inflect.plural("mismatch", len(test_mismatches))),
        ],
    ):
        for test in tests:
            # We can only perform this validation for compilers that operate on files
            if test.compiler.input_type != InputType.Files:
                continue

            test_dir = test.path.parent

            source_name = compiler.TestItemToName(test.path)
            if source_name is not None and not source_name.exists():
                test_mismatches[test.path] = source_name

            source_dir = test_dir.parent

            if source_dir in processed_source_dirs:
                continue

            processed_source_dirs.add(source_dir)

            for item in source_dir.iterdir():
                if not item.is_file():
                    continue

                test_name = compiler.ItemToTestName(item, test_type)
                if test_name is not None and not test_name.exists():
                    source_mismatches[item] = test_name

    # ----------------------------------------------------------------------
    def DisplayItems(
        header: str,
        mismatches: Dict[Path, Path],
    ) -> None:
        with dm.YieldStream() as stream:
            stream.write("\n{}\n{}\n\n".format(header, "=" * len(header)))

            indented_stream = StreamDecorator(stream, "    ")

            len_input_dir_parts = len(input_dir.parts)

            rows: List[Tuple[Path, Path]] = list(mismatches.items())

            indented_stream.write(
                "All files are relative to '{}'.\n\n".format(
                    input_dir if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                        "file:///{}".format(input_dir.as_posix()),
                        str(input_dir),
                    ),
                ),
            )

            # ----------------------------------------------------------------------
            def DecorateRowsWithLink(
                index: int,
                values: List[str],
            ) -> List[str]:
                if not dm.capabilities.is_headless:
                    fullpath = rows[index][0]

                    values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                        "file:///{}".format(fullpath.as_posix()),
                        values[0],
                    )

                return values

            # ----------------------------------------------------------------------

            indented_stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Filename",
                        "Expected Match",
                    ],
                    [
                        [
                            str(Path(*cols[0].parts[len_input_dir_parts:])),
                            str(Path(*cols[1].parts[len_input_dir_parts:])),
                        ]
                        for cols in rows
                    ],
                    decorate_values_func=DecorateRowsWithLink,
                ),
            )

            indented_stream.write("\n\n")

        dm.result = -1

    # ----------------------------------------------------------------------

    if source_mismatches:
        DisplayItems("Source Files Unmatched", source_mismatches)

    if test_mismatches:
        DisplayItems("Test Items Unmatched", test_mismatches)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
