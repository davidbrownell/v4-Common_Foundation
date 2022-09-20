# ----------------------------------------------------------------------
# |
# |  __main__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-26 11:16:48
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Recursively searches for and invokes build activities for all build files encountered."""

import datetime
import importlib
import itertools
import multiprocessing
import sys
import textwrap
import threading
import time
import traceback

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Tuple, Union

try:
    import typer

    from rich.progress import Progress, TaskID
    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.EnumSource import EnumSource
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from Common_FoundationEx.BuildImpl import BuildInfoBase, Mode
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


# ----------------------------------------------------------------------
_root_dir_argument                          = typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Root directory to search for build files.")

_build_filename_option                      = typer.Option("Build.py", "--build-filename", help="Name of build files.")
_build_filename_ignore_option               = typer.Option("Build.py-ignore", "--build-filename-ignore", help="Name of files placed in the same directory as a corresponding build file to indicate that it should not be processed by this tool.")
_ignore_ignore_filenames_option             = typer.Option(None, "--ignore-ignore-filename", exists=True, dir_okay=False, resolve_path=True, help="Ignore filenames that would normally prevent execution, but should not prevent execution during this invocation. In other words, execute the build even though there is an ignore file present.")

_verbose_option                             = typer.Option(False, "--verbose", help="Write verbose information to the terminal.")
_debug_option                               = typer.Option(False, "--debug", help="Write additional debug information to the terminal.")


# ----------------------------------------------------------------------
@app.command(
    "Build",
    context_settings={
        "allow_extra_args": True,
        "ignore_unknown_options": True,
    },
    no_args_is_help=True,
)
def Build(
    ctx: typer.Context,
    root_dir: Path=_root_dir_argument,
    output_dir: Path=typer.Argument(..., file_okay=False, resolve_path=True, help="Output will be written to this directory; it will be created if it doesn't already exist."),
    modes: List[Mode]=typer.Option(list(Mode), "--mode", case_sensitive=False, help="Names of modes to invoke."),
    debug_only: bool=typer.Option(False, "--debug-only", help="Only invoke configurations associated with debug builds."),
    release_only: bool=typer.Option(False, "--release-only", help="Only invoke configurations associated with release builds."),
    single_threaded: bool=typer.Option(False, "--single-threaded", help="Only use a single thread."),
    continue_on_error: bool=typer.Option(False, "--continue-on-error", help="Continue execution when an error is encountered. By default, execution will stop when an error is encountered."),
    exit_on_warning: bool=typer.Option(False, "--exit-on-warning", help="Terminate execution when a warning is encountered. By default, execution will continue when a warning is encountered."),
    quiet: bool=typer.Option(False, "--quiet", help="Write less output to the terminal."),
    build_filename: str=_build_filename_option,
    build_filename_ignore: str=_build_filename_ignore_option,
    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,
) -> None:
    """Recursively calls Build files with the desired mode(s)"""

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        build_infos = _GetBuildInfos(
            dm,
            root_dir,
            build_filename,
            build_filename_ignore,
            ignore_ignore_filenames,
        )

        if not build_infos:
            dm.WriteLine("No build info files were found.\n")
            return

        if ctx.args:
            if len(build_infos) > 1 or len(next(iter(build_infos.values()))) > 1:
                dm.WriteError("Custom arguments cannot be provided when multiple build files are found.")
            elif len(modes) > 1:
                dm.WriteError("Custom arguments cannot be provided when multiple modes are invoked.")

            if dm.result != 0:
                return

        common_path = PathEx.GetCommonPath(
            *itertools.chain(
                *(grouped_build_infos.keys() for grouped_build_infos in build_infos.values())
            ),
        )

        assert common_path is not None

        # Get the build configurations that apply given the command line parameters
        # ----------------------------------------------------------------------
        @dataclass
        class ConfigurationInfo(object):
            # ----------------------------------------------------------------------
            display: str
            build_info: BuildInfoBase
            configuration: Optional[str]
            output_dir: Path

        # ----------------------------------------------------------------------

        configurations: Dict[int, List[ConfigurationInfo]] = {}

        with dm.Nested(
            "Extracting configuration information",
            lambda: "{} found".format(inflect.no("configuration", sum(len(values) for values in configurations.values()))),
            suffix="\n",
        ):
            # ----------------------------------------------------------------------
            def GetSupportedConfigurations(
                build_info: BuildInfoBase,
            ) -> Generator[Optional[str], None, None]:
                if build_info.configurations is None:
                    if (
                        (not debug_only and not release_only)
                        or (build_info.priority < BuildInfoBase.STANDARD_PRIORITY)  # If these is a dependency, build it as other builds likely require it
                    ):
                        yield None

                    return

                if BuildInfoBase.COMPLETE_CONFIGURATION_NAME in build_info.configurations:
                    yield BuildInfoBase.COMPLETE_CONFIGURATION_NAME
                    return

                if not debug_only and not release_only:
                    yield from build_info.configurations
                    return

                for configuration in build_info.configurations:
                    configuration_lower = configuration.lower()

                    if (
                        (debug_only and configuration_lower == "debug")
                        or (release_only and configuration_lower == "release")
                    ):
                        yield configuration

            # ----------------------------------------------------------------------

            for priority, build_data in build_infos.items():
                these_configurations: List[ConfigurationInfo] = []

                for build_path, build_info in build_data.items():
                    for configuration in GetSupportedConfigurations(build_info):
                        # Create an output dir for this configuration
                        if build_info.suggested_output_dir_location:
                            this_output_dir = output_dir / build_info.suggested_output_dir_location
                        else:
                            this_output_dir = output_dir / PathEx.CreateRelativePath(root_dir, build_path.parent)

                        if configuration is not None:
                            this_output_dir /= CurrentShell.ScrubFilename(configuration)

                        # Create the display name
                        assert PathEx.IsDescendant(build_path, common_path), (build_path, common_path)
                        relative_path = Path(*build_path.parts[len(common_path.parts):])

                        these_configurations.append(
                            ConfigurationInfo(
                                str(relative_path),
                                build_info,
                                configuration,
                                this_output_dir,
                            ),
                        )

                if these_configurations:
                    configurations[priority] = these_configurations

        if not configurations:
            dm.WriteLine("No supported configurations were found.\n")
            return

        # ----------------------------------------------------------------------
        @dataclass
        class FinalInfo(object):
            # ----------------------------------------------------------------------
            output_dir: Path
            log_file: Path

            build_file: Path

            result: int                                 = field(init=False, default=0)
            execution_time: datetime.timedelta          = field(init=False, default_factory=datetime.timedelta)

            short_desc: Optional[str]                   = field(init=False, default=None)

        # ----------------------------------------------------------------------

        final_infos: Dict[str, Dict[Mode, Dict[Optional[str], FinalInfo]]] = {}
        final_infos_lock = threading.Lock()

        should_continue = True

        for mode_index, mode in enumerate(modes):
            if not should_continue:
                break

            if mode == Mode.Clean:
                get_num_steps_func_attribute = "GetNumCleanSteps"
                execute_func_attribute = "Clean"
                get_custom_args_func_attribute = "GetCustomCleanArgs"

            elif mode == Mode.Build:
                get_num_steps_func_attribute = "GetNumBuildSteps"
                execute_func_attribute = "Build"
                get_custom_args_func_attribute = "GetCustomBuildArgs"

            else:
                assert False, mode  # pragma: no cover

            with dm.Nested(
                "{}ing ({} of {})...".format(mode.value, mode_index + 1, len(modes)),
                suffix="\n",
            ) as mode_dm:
                displayed_status = False

                for priority_group_index, (priority, configuration_infos) in enumerate(configurations.items()):
                    if not should_continue:
                        break

                    with mode_dm.Nested(
                        "Priority '{}' ({} of {})...".format(
                            "Standard" if priority == BuildInfoBase.STANDARD_PRIORITY else priority,
                            priority_group_index + 1,
                            len(configurations),
                        ),
                        suffix=lambda: "\n" if displayed_status else None,
                    ) as priority_group_dm:
                        errors: List[Union[None, str, int]] = [None for _ in range(len(configuration_infos))]
                        warnings: List[Union[None, str, int]] = [None for _ in range(len(configuration_infos))]

                        with priority_group_dm.YieldStdout() as stdout_context:
                            with Progress(
                                *Progress.get_default_columns(),
                                "{task.fields[status]}",
                                transient=True,
                            ) as progress:
                                total_progress_id = progress.add_task(
                                    "{}Total Progress".format(stdout_context.line_prefix),
                                    total=len(configuration_infos),
                                    status="",
                                )

                                with ThreadPoolExecutor(
                                    1 if single_threaded else min(len(configuration_infos), multiprocessing.cpu_count()),
                                ) as executor:
                                    succeeded = 0
                                    succeeded_lock = threading.Lock()

                                    futures = []

                                    # ----------------------------------------------------------------------
                                    def Impl(
                                        index: int,
                                        task_id: TaskID,
                                        configuration_info: ConfigurationInfo,
                                    ) -> None:
                                        if not quiet:
                                            progress.update(task_id, status="", visible=True)

                                        this_output_dir = configuration_info.output_dir / mode.value
                                        this_output_dir.mkdir(parents=True, exist_ok=True)

                                        final_info = FinalInfo(
                                            this_output_dir,
                                            this_output_dir / "output.log",
                                            common_path / configuration_info.display,
                                        )

                                        start_time = time.perf_counter()

                                        del this_output_dir

                                        # ----------------------------------------------------------------------
                                        def PersistFinalInfo():
                                            current_time = time.perf_counter()
                                            assert start_time <= current_time, (start_time, current_time)

                                            final_info.execution_time = datetime.timedelta(seconds=current_time - start_time)

                                            with final_infos_lock:
                                                final_infos \
                                                    .setdefault(configuration_info.display,{}) \
                                                    .setdefault(mode, {}) \
                                                        [configuration_info.configuration] = final_info

                                        # ----------------------------------------------------------------------

                                        with ExitStack(PersistFinalInfo):
                                            try:
                                                num_steps = getattr(configuration_info.build_info, get_num_steps_func_attribute)(
                                                    configuration_info.configuration,
                                                )
                                                current_step = 0

                                                progress.update(
                                                    task_id,
                                                    total=num_steps,
                                                )

                                                execute_func = getattr(configuration_info.build_info, execute_func_attribute)
                                                get_custom_args_func = getattr(configuration_info.build_info, get_custom_args_func_attribute)

                                                # ----------------------------------------------------------------------
                                                def UpdateOutput():
                                                    nonlocal succeeded

                                                    progress.update(task_id, completed=True, visible=False)

                                                    succeeded_value: Optional[int] = None

                                                    if final_info.result == 0:
                                                        with succeeded_lock:
                                                            succeeded += 1

                                                            succeeded_value = succeeded

                                                    else:
                                                        if final_info.result < 0:
                                                            assert errors[index] is None
                                                            errors[index] = final_info.result

                                                            if not quiet:
                                                                progress.print(
                                                                    r"{prefix}[bold red]ERROR:[/] {name}{configuration}: {result}{short_desc} \[{suffix}]".format(
                                                                        prefix=stdout_context.line_prefix,
                                                                        name=configuration_info.display,
                                                                        configuration=" ({})".format(configuration_info.configuration) if configuration_info.configuration else "",
                                                                        result=final_info.result,
                                                                        short_desc=" ({})".format(final_info.short_desc) if final_info.short_desc else "",
                                                                        suffix=final_info.log_file if priority_group_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
                                                                            final_info.log_file.as_posix(),
                                                                        ),
                                                                    ),
                                                                    highlight=False,
                                                                )

                                                                stdout_context.persist_content = True

                                                        elif final_info.result > 0:
                                                            assert warnings[index] is None
                                                            warnings[index] = final_info.result

                                                            if not quiet:
                                                                progress.print(
                                                                    r"{prefix}[bold yellow]WARNING:[/] {name}{configuration}: {result}{short_desc} \[{suffix}]".format(
                                                                        prefix=stdout_context.line_prefix,
                                                                        name=configuration_info.display,
                                                                        configuration=" ({})".format(configuration_info.configuration) if configuration_info.configuration else "",
                                                                        result=final_info.result,
                                                                        short_desc=" ({})".format(final_info.short_desc) if final_info.short_desc else "",
                                                                        suffix=final_info.log_file if priority_group_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
                                                                            final_info.log_file.as_posix(),
                                                                        ),
                                                                    ),
                                                                    highlight=False,
                                                                )

                                                                stdout_context.persist_content = True

                                                        with succeeded_lock:
                                                            succeeded_value = succeeded

                                                    assert succeeded_value is not None

                                                    progress.update(
                                                        total_progress_id,
                                                        advance=1,
                                                        status=TextwrapEx.CreateStatusText(
                                                            succeeded_value,
                                                            sum(1 if error else 0 for error in errors),
                                                            sum(1 if warning else 0 for warning in warnings),
                                                        ),
                                                    )

                                                # ----------------------------------------------------------------------
                                                def OnStepProgress(
                                                    step: int,
                                                    status: str,
                                                ) -> bool:
                                                    nonlocal current_step

                                                    advance = step - current_step
                                                    current_step = step

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

                                                with ExitStack(UpdateOutput):
                                                    with open(final_info.log_file, "w") as f:
                                                        result = execute_func(
                                                            configuration_info.configuration,
                                                            output_dir,
                                                            f,
                                                            OnStepProgress,
                                                            **TyperEx.ProcessDynamicArgs(
                                                                ctx,
                                                                get_custom_args_func(),
                                                            ),
                                                        )

                                                        if isinstance(result, tuple):
                                                            result, final_info.short_desc = result

                                                        final_info.result = result or 0

                                            except KeyboardInterrupt:  # pylint: disable=try-except-raise
                                                raise

                                            except Exception as ex:
                                                final_info.result = -1

                                                if priority_group_dm.is_debug:
                                                    error = traceback.format_exc()
                                                else:
                                                    error = str(ex)

                                                errors[index] = textwrap.dedent(
                                                    """\
                                                    {}
                                                    {}
                                                    """,
                                                ).format(
                                                    configuration_info.display,
                                                    TextwrapEx.Indent(error.rstrip(), 4),
                                                )

                                    # ----------------------------------------------------------------------

                                    for index, configuration_info in enumerate(configuration_infos):
                                        futures.append(
                                            executor.submit(
                                                Impl,
                                                index,
                                                progress.add_task(
                                                    "{}  {}{}".format(
                                                        stdout_context.line_prefix,
                                                        configuration_info.display,
                                                        "" if not configuration_info.configuration else " ({})".format(configuration_info.configuration),
                                                    ),
                                                    total=None,
                                                    visible=False,
                                                ),
                                                configuration_info,
                                            ),
                                        )

                                    for future in futures:
                                        future.result()

                        if any(error for error in errors):
                            displayed_status = True

                            error_strings = [error for error in errors if isinstance(error, str)]

                            if error_strings:
                                priority_group_dm.WriteError("{}\n".format("\n".join(error_strings)))

                            priority_group_dm.result = -1

                        if any(warning for warning in warnings):
                            displayed_status = True

                            warning_strings = [warning for warning in warnings if isinstance(warning, str)]

                            if warning_strings:
                                priority_group_dm.WriteWarning("{}\n".format("\n".join(warning_strings)))

                            if priority_group_dm.result == 0:
                                priority_group_dm.result = 1

                        if not continue_on_error and priority_group_dm.result < 0:
                            should_continue = False
                            break

                        if exit_on_warning and priority_group_dm.result > 0:
                            should_continue = False
                            break

        # Display final output
        rows: List[List[str]] = []
        row_final_infos: List[FinalInfo] = []

        for display, mode_content in final_infos.items():
            for mode, config_content in mode_content.items():
                config_names= list(config_content.keys())

                config_names.sort(
                    key=lambda config_name: config_name or "",
                )

                for config_name in config_names:
                    final_info = config_content[config_name]

                    rows.append(
                        [
                            display,
                            mode,
                            config_name or "",
                            "Failed ({})".format(final_info.result) if final_info.result < 0
                                else "Unknown ({})".format(final_info.result) if final_info.result > 0
                                    else "Succeeded ({})".format(final_info.result)
                            ,
                            str(final_info.execution_time),
                            "{}{}".format(
                                TextwrapEx.GetSizeDisplay(final_info.log_file.stat().st_size) if final_info.log_file.is_file() else "",
                                "" if dm.capabilities.is_headless else " [View Log]",
                            ),
                            str(final_info.output_dir) if dm.capabilities.is_headless else "{} [View]".format(
                                inflect.no("item", sum(1 for _ in final_info.output_dir.iterdir())),
                            ),
                            final_info.short_desc or "",
                        ],
                    )

                    row_final_infos.append(final_info)

        if dm.capabilities.supports_colors:
            success_on = TextwrapEx.SUCCESS_COLOR_ON
            failure_on = TextwrapEx.ERROR_COLOR_ON
            warning_on = TextwrapEx.WARNING_COLOR_ON
            color_off = TextwrapEx.COLOR_OFF
        else:
            success_on = ""
            failure_on = ""
            warning_on = ""
            color_off = ""

        # ----------------------------------------------------------------------
        def DecorateRow(
            index: int,
            values: List[str],
        ) -> List[str]:
            final_info = row_final_infos[index]

            if not dm.capabilities.is_headless:
                values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(final_info.build_file.as_posix()),
                    values[0],
                )

            if final_info.result < 0:
                color_on = failure_on
            elif final_info.result > 0:
                color_on = warning_on
            else:
                color_on = success_on

            values[3] = "{}{}{}".format(color_on, values[3], color_off)

            if not dm.capabilities.is_headless:
                values[5] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(final_info.log_file.as_posix()),
                    values[5],
                )

                values[6] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(final_info.output_dir.as_posix()),
                    values[6],
                )

            return values

        # ----------------------------------------------------------------------

        with dm.YieldStream() as stream:
            indented_stream = StreamDecorator(stream, "    ")

            indented_stream.write(
                textwrap.dedent(
                    """\

                    Build files are relative to '{}'.


                    """,
                ).format(
                    common_path if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                        "file://{}".format(common_path.as_posix()),
                        str(common_path),
                    ),
                )
            )

            indented_stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Build File",
                        "Mode",
                        "Configuration",
                        "Result",
                        "Execution Time",
                        "Log File",
                        "Output Directory",
                        "Short Description",
                    ],
                    rows,
                    [
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Right,
                        TextwrapEx.Justify.Left if dm.capabilities.is_headless else TextwrapEx.Justify.Right,
                        TextwrapEx.Justify.Left,
                    ],
                    decorate_values_func=DecorateRow,
                ),
            )

            indented_stream.write("\n")

        # Write final output
        success_count = 0
        warning_count = 0
        error_count = 0

        for final_info in row_final_infos:
            assert final_info is not None

            if final_info.result < 0:
                error_count += 1
            elif final_info.result > 0:
                warning_count += 1
            else:
                success_count += 1

        dm.WriteLine(
            textwrap.dedent(
                """\

                {success_prefix}{success_count:>6} ({success_percentage:>6.2f}%)
                {error_prefix}  {error_count:>6} ({error_percentage:>6.2f}%)
                {warning_prefix}{warning_count:>6} ({warning_percentage:>6.2f}%)
                Total:   {total:>6} (100.00%)

                """,
            ).format(
                success_prefix=TextwrapEx.CreateSuccessPrefix(dm.capabilities),
                success_count=success_count,
                success_percentage=(success_count / len(row_final_infos)) * 100,
                error_prefix=TextwrapEx.CreateErrorPrefix(dm.capabilities),
                error_count=error_count,
                error_percentage=(error_count / len(row_final_infos)) * 100,
                warning_prefix=TextwrapEx.CreateWarningPrefix(dm.capabilities),
                warning_count=warning_count,
                warning_percentage=(warning_count / len(row_final_infos)) * 100,
                total=len(row_final_infos),
            ),
        )

# ----------------------------------------------------------------------
@app.command("List", no_args_is_help=True)
def ListFunc(
    root_dir: Path=_root_dir_argument,
    build_filename: str=_build_filename_option,
    build_filename_ignore: str=_build_filename_ignore_option,
    ignore_ignore_filenames: Optional[List[Path]]=_ignore_ignore_filenames_option,
    verbose: bool=_verbose_option,
    debug: bool=_debug_option,
) -> None:
    """Lists all Build files"""

    ignore_ignore_filenames = Types.EnsurePopulatedList(ignore_ignore_filenames)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        build_infos = _GetBuildInfos(
            dm,
            root_dir,
            build_filename,
            build_filename_ignore,
            ignore_ignore_filenames,
        )

        if not build_infos:
            dm.WriteLine("\nNo build files were found.\n")
            return

        with dm.YieldStream() as stream:
            stream.write("\n")

            indented_stream = StreamDecorator(stream, "    ")

            for index, (priority, group_build_infos) in enumerate(build_infos.items()):
                header = "Priority Group {} (Priority {})".format(index + 1, priority)

                indented_stream.write("{}\n{}\n\n".format(header, "-" * len(header)))

                headers: Optional[List[str]] = None
                all_values: List[List[str]] = []

                for build_path, build_info in group_build_infos.items():
                    table_info = build_info.GetTableInfo()

                    if headers is None:
                        headers = list(table_info.keys())
                        headers.append("Path")

                    # TODO: Add link to path output
                    all_values.append(list(table_info.values()) + [str(build_path), ])

                assert headers is not None

                StreamDecorator(indented_stream, "    ").write(
                    TextwrapEx.CreateTable(
                        headers,
                        all_values,
                        is_vertical=True,
                    ),
                )

                indented_stream.write("\n")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _GetBuildInfos(
    dm: DoneManager,
    root_dir: Path,
    build_filename: str,
    build_filename_ignore: str,
    ignore_ignore_filenames: Optional[List[Path]],
) -> Dict[int, Dict[Path, BuildInfoBase]]:
    ignore_ignore_filenames_set: Set[Path] = set(ignore_ignore_filenames or [])

    # Get the build files
    build_files: List[Path] = []
    ignored_count = 0
    ignore_override_count = 0

    with dm.Nested(
        "Searching for build files under '{}'...".format(root_dir),
        [
            lambda: "{} found".format(inflect.no("build file", len(build_files))),
            lambda: "{} ignored".format(inflect.no("build file", ignored_count)),
            lambda: "{} overridden".format(inflect.no("ignore file", ignore_override_count)),
        ],
        preserve_status=False,
    ) as search_dm:
        for root, _, filenames in EnumSource(root_dir):
            search_dm.WriteStatus(str(root))

            for filename in filenames:
                if filename != build_filename:
                    continue

                fullpath = root / build_filename

                potential_ignore_filename = root / build_filename_ignore
                if potential_ignore_filename.exists():
                    if potential_ignore_filename in ignore_ignore_filenames_set:
                        search_dm.WriteVerbose(
                            "The ignore filename '{}' was explicitly overridden.\n".format(potential_ignore_filename),
                        )

                        ignore_override_count += 1

                    else:
                        ignored_count += 1

                        search_dm.WriteVerbose(
                            "Build file ignored due to '{}'.\n".format(potential_ignore_filename),
                        )

                        continue

                build_files.append(fullpath.resolve())

        if build_files:
            with search_dm.YieldVerboseStream() as stream:
                stream.write(
                    textwrap.dedent(
                        """\
                        Build Files:
                        {}
                        """,
                    ).format("\n".join("  - {}".format(filename) for filename in build_files)),
                )

    if not build_files:
        return {}

    # Extract the build infos sequentially, as importing them will modify the global sys.modules
    build_infos: List[Tuple[Path, BuildInfoBase]] = []

    with dm.Nested(
        "\nExtracting build information for {}...".format(inflect.no("build file", len(build_files))),
    ) as extract_dm:
        errors: List[str] = []

        with extract_dm.YieldStdout() as context:
            with Progress(
                *Progress.get_default_columns(),
                "{task.fields[status]}",
                transient=True,
            ) as progress:
                progress_task_id = progress.add_task(context.line_prefix, total=len(build_files), status="")

                for build_file in build_files:
                    with ExitStack(
                        lambda: progress.update(
                            progress_task_id,
                            advance=1,
                            status=TextwrapEx.CreateStatusText(len(build_infos), len(errors), None),
                        ),
                    ):
                        try:
                            sys.path.insert(0, str(build_file.parent))
                            with ExitStack(lambda: sys.path.pop(0)):
                                mod = importlib.import_module(build_file.stem)
                                with ExitStack(lambda: sys.modules.pop(build_file.stem)):
                                    build_info_class = getattr(mod, "BuildInfo", None)
                                    if build_info_class is None:
                                        raise Exception("'BuildInfo' was not found in '{}'.".format(build_file))

                                    build_info_instance = build_info_class()

                                    build_infos.append((build_file, build_info_instance))

                        except Exception as ex:
                            # Add progress status
                            progress.print(
                                "{}[red]ERROR:[/] '{}'".format(context.line_prefix, build_file),
                                context.line_prefix,
                                highlight=False,
                            )
                            context.persist_content = True

                            # Add the error information
                            if extract_dm.is_debug:
                                error = traceback.format_exc()
                            else:
                                error = str(ex)

                            error = textwrap.dedent(
                                """\
                                {}
                                {}
                                """,
                            ).format(
                                build_file,
                                TextwrapEx.Indent(error.rstrip(), 4),
                            )

                            errors.append(error)

        if errors:
            extract_dm.WriteError("{}\n".format("\n".join(errors)))
            extract_dm.ExitOnError()

    results: Dict[int, Dict[Path, BuildInfoBase]] = {}

    with dm.Nested(
        "Organizing {}...".format(inflect.no("build file", len(build_infos))),
        lambda: "{} found".format(inflect.no("priority group", len(results))),
        suffix="\n",
    ):
        build_infos.sort(
            key=lambda bi: bi[1].priority,
        )

        for path, build_info in build_infos:
            results.setdefault(build_info.priority, {})[path] = build_info

    return results


# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
