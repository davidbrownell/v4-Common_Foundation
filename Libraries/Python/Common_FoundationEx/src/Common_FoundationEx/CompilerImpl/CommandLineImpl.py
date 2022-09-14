# ----------------------------------------------------------------------
# |
# |  CommandLineImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 11:41:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality that makes it as easy as possible to create command line interfaces for compilers"""

import datetime
import multiprocessing
import os
import threading
import textwrap
import time
import traceback

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import typer

from rich.progress import Progress, TaskID
from typer.models import OptionInfo

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell                                # pylint: disable=unused-import
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags     # pylint: disable=unused-import
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from .CompilerImpl import CompilerImpl, DiagnosticException, InputType


# ----------------------------------------------------------------------
def CreateInvokeCommandLineFunc(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    return CreateInvokeCommandLineFuncImpl(app, compiler)


# ----------------------------------------------------------------------
def CreateCleanCommandLineFunc(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    raise NotImplementedError("TODO: Not implemented yet")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def CreateInvokeCommandLineFuncImpl(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    custom_parameters: Dict[str, str] = {}
    custom_types: Dict[str, OptionInfo] = {}

    for k, v in compiler.GetCustomArgs().items():
        if isinstance(v, tuple):
            annotation, v = v

            if isinstance(v, dict):
                v = typer.Option(None, **v)

            assert isinstance(v, OptionInfo), v
            custom_types[k] = v

            default= '=custom_types["{}"]'.format(k)
        else:
            annotation = v
            default = ""

        custom_parameters[k] = '{name}: {annotation}{default}'.format(
            name=k,
            annotation=annotation.__name__,
            default=default,
        )

    func = textwrap.dedent(
        """\
        # ----------------------------------------------------------------------
        @app.command("{invocation_method_name}", no_args_is_help=True)
        def Impl(
            inputs: List[Path]=typer.Argument(
                ...,
                exists=True,
                file_okay={file_okay},
                dir_okay=True,
                resolve_path=True,
                help="File system inputs.",
            ),
            output_dir: Path=typer.Option(
                CurrentShell.CreateTempDirectory(),
                file_okay=False,
                resolve_path=True,
                help="Directory to write output; it will be created if it doesn't already exist.",
            ),
            {custom_parameters}
            single_threaded: bool=typer.Option(False, "--single-threaded", help="Only use a single thread."),
            quiet: bool=typer.Option(False, "--quiet", help="Write less output to the terminal."),
            verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
            debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
        ) -> None:
            '''Invokes '{name}'.'''

            with DoneManager.CreateCommandLine(
                output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
            ) as dm:
                _ExecuteImpl(
                    compiler,
                    dm,
                    inputs,
                    output_dir,
                    {custom_args},
                    single_threaded=single_threaded,
                    quiet=quiet,
                )
        """,
    ).format(
        name=compiler.name,
        invocation_method_name=compiler.invocation_method_name,
        file_okay="True" if compiler.input_type == InputType.Files else "False",
        custom_parameters=TextwrapEx.Indent(
            "\n".join("{},".format(custom_parameter) for custom_parameter in custom_parameters.values()),
            4,
            skip_first_line=True,
        ),
        custom_args="{}" if not custom_parameters else "{{{}}}".format(", ".join('"{k}": {k}'.format(k=k) for k in custom_parameters)),
    )

    global_vars = globals()

    global_vars["app"] = app
    global_vars["compiler"] = compiler
    global_vars["custom_types"] = custom_types

    exec(func, global_vars)  # pylint: disable=exec-used

    return Impl  #  type: ignore  # pylint: disable=undefined-variable


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ExecuteImpl(
    compiler: CompilerImpl,
    dm: DoneManager,
    inputs: List[Path],
    output_dir: Path,
    custom_params: Dict[str, Any],
    *,
    single_threaded: bool,
    quiet: bool,
) -> None:
    """Implements functionality invoked from the dynamically generated function"""

    result = compiler.ValidateEnvironment()
    if result is not None:
        dm.WriteError(result)
        return

    contexts: List[Dict[str, Any]] = []

    with dm.Nested(
        "Generating items(s)...",
        lambda: "{} found".format(inflect.no("item", len(contexts))),
    ) as generate_dm:
        try:
            contexts += list(compiler.GenerateContextItems(generate_dm, inputs, custom_params))

        except Exception as ex:
            if isinstance(ex, DiagnosticException):
                generate_dm.result = -1
            else:
                if dm.is_debug:
                    error = traceback.format_exc()
                else:
                    error = str(ex)

                generate_dm.WriteError(error.rstrip())

            return

        if not contexts:
            return

    # ----------------------------------------------------------------------
    @dataclass
    class FinalInfo(object):
        output_dir: Path
        log_file: Path

        result: int                             = field(init=False, default=0)
        execution_time: datetime.timedelta      = field(init=False, default_factory=datetime.timedelta)

        short_desc: Optional[str]               = field(init=False, default=None)

    # ----------------------------------------------------------------------

    final_infos: List[Optional[FinalInfo]] = [None for _ in range(len(contexts))]

    context_names: List[str] = [
        compiler.GetDisplayName(context) or "Item Group {}".format(index + 1)
        for index, context in enumerate(contexts)
    ]

    # ----------------------------------------------------------------------
    def UpdateContextNames() -> Optional[Path]:
        # Find a common path if all of the context names are paths

        paths: List[Path] = []

        for context_name in context_names:
            path = Path(context_name).resolve()

            if not path.exists():
                return None

            paths.append(path)

        common_path = PathEx.GetCommonPath(*paths)
        if common_path is None:
            return None

        # We've got one! Update all of the display names
        common_path_parts_len = len(common_path.parts)

        for index, path in enumerate(paths):
            assert len(path.parts) > common_path_parts_len, (len(path.parts), common_path_parts_len)
            context_names[index] = os.path.sep.join(path.parts[common_path_parts_len:])

        return common_path

    # ----------------------------------------------------------------------

    common_path = UpdateContextNames()

    with dm.Nested("Executing...") as execute_dm:
        output_dir.mkdir(parents=True, exist_ok=True)

        errors: List[Union[None, str, int]] = [None for _ in range(len(contexts))]
        warnings: List[Union[None, str, int]] = [None for _ in range(len(contexts))]

        with execute_dm.YieldStdout() as stdout_context:
            with Progress(
                *Progress.get_default_columns(),
                "{task.fields[status]}",
                transient=True,
            ) as progress:
                total_progress_id = progress.add_task(
                    "{}Total Progress".format(stdout_context.line_prefix),
                    total=len(contexts),
                    status="",
                )

                with ThreadPoolExecutor(
                    1 if single_threaded or not compiler.execute_in_parallel else min(len(contexts), multiprocessing.cpu_count()),
                ) as executor:
                    succeeded = 0
                    succeeded_lock = threading.Lock()

                    futures = []

                    # ----------------------------------------------------------------------
                    def Impl(
                        index: int,
                        task_id: TaskID,
                        context: Dict[str, Any],
                    ) -> None:
                        if not quiet:
                            progress.update(task_id, status="", visible=True)

                        this_output_dir = output_dir / "{:06}".format(index)
                        this_output_dir.mkdir(parents=True, exist_ok=True)

                        final_info = FinalInfo(
                            this_output_dir,
                            this_output_dir / "output.log",
                        )

                        start_time = time.perf_counter()

                        del this_output_dir

                        # ----------------------------------------------------------------------
                        def PersistFinalInfo():
                            current_time = time.perf_counter()
                            assert start_time <= current_time, (start_time, current_time)

                            final_info.execution_time = datetime.timedelta(seconds=current_time - start_time)

                            final_infos[index] = final_info

                        # ----------------------------------------------------------------------

                        with ExitStack(PersistFinalInfo):
                            try:
                                num_steps = compiler.GetNumSteps(context)
                                current_step = 0

                                progress.update(task_id, total=num_steps)

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
                                                    r"{prefix}[bold red]ERROR:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                                        prefix=stdout_context.line_prefix,
                                                        name=context_names[index],
                                                        result=final_info.result,
                                                        short_desc=" ({})".format(final_info.short_desc) if final_info.short_desc else "",
                                                        suffix=final_info.log_file if execute_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
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
                                                    r"{prefix}[bold yellow]WARNING:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                                        prefix=stdout_context.line_prefix,
                                                        name=context_names[index],
                                                        result=final_info.result,
                                                        short_desc=" ({})".format(final_info.short_desc) if final_info.short_desc else "",
                                                        suffix=final_info.log_file if execute_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
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
                                        result = getattr(compiler, compiler.invocation_method_name)(
                                            context,
                                            f,
                                            OnStepProgress,
                                            verbose=execute_dm.is_verbose,
                                        )

                                        if isinstance(result, tuple):
                                            result, final_info.short_desc = result

                                        final_info.result = result or 0

                            except KeyboardInterrupt:  # pylint: disable=try-except-raise
                                raise

                            except Exception as ex:
                                final_info.result = -1

                                if execute_dm.is_debug:
                                    error = traceback.format_exc()
                                else:
                                    error = str(ex)

                                errors[index] = textwrap.dedent(
                                    """\
                                    {}
                                    {}
                                    """,
                                ).format(
                                    context_names[index],
                                    TextwrapEx.Indent(error.rstrip(), 4),
                                )


                    # ----------------------------------------------------------------------

                    for index, (context, context_name) in enumerate(zip(contexts, context_names)):
                        futures.append(
                            executor.submit(
                                Impl,
                                index,
                                progress.add_task(
                                    "{}  {}".format(stdout_context.line_prefix, context_name),
                                    total=None,
                                    visible=False,
                                ),
                                context,
                            ),
                        )

                    for future in futures:
                        future.result()

        if any(error for error in errors):
            error_strings = [error for error in errors if isinstance(error, str)]

            if error_strings:
                execute_dm.WriteError("{}\n".format("\n".join(error_strings)))

            execute_dm.result = -1

        if any(warning for warning in warnings):
            warning_strings = [warning for warning in warnings if isinstance(warning, str)]

            if warning_strings:
                execute_dm.WriteWarning("{}\n".format("\n".join(warning_strings)))

            if execute_dm.result == 0:
                execute_dm.result = 1

        # Display final output

        # Importing here to avoid circular dependencies
        from .VerifierBase import VerifierBase
        add_output_column = not isinstance(compiler, VerifierBase)

        has_short_descs = any(final_info and final_info.short_desc for final_info in final_infos)

        rows: List[List[str]] = []

        for final_info, context_name in zip(final_infos, context_names):
            assert final_info is not None

            rows.append(
                [
                    context_name,
                    "Failed ({})".format(final_info.result) if final_info.result < 0
                        else "Unknown ({})".format(final_info.result) if final_info.result > 0
                            else "Succeeded ({})".format(final_info.result)
                    ,
                    str(final_info.execution_time),
                    "{}{}".format(
                        TextwrapEx.GetSizeDisplay(final_info.log_file.stat().st_size) if final_info.log_file.is_file() else "",
                        "" if dm.capabilities.is_headless else " [View Log]",
                    ),
                ],
            )

            if add_output_column:
                rows[1].append(
                    "{} [View]".format(
                        str(final_info.output_dir) if not dm.capabilities.is_headless else inflect.no(
                            "item",
                            sum(1 for _ in final_info.output_dir.iterdir()),
                        ),
                    ),
                )

            if has_short_descs:
                rows[-1].append(final_info.short_desc or "")

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
            final_info = final_infos[index]
            assert final_info is not None

            # Attempt to provide a link to the name
            if common_path:
                potential_file = common_path / context_names[index]
            else:
                potential_file = Path(context_names[index])

            if potential_file.is_file() and not dm.capabilities.is_headless:
                values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(potential_file.as_posix()),
                    values[0],
                )

            if final_info.result < 0:
                color_on = failure_on
            elif final_info.result > 0:
                color_on = warning_on
            else:
                color_on = success_on

            values[1] = "{}{}{}".format(color_on, values[1], color_off)

            if not dm.capabilities.is_headless:
                values[3] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(final_info.log_file.as_posix()),
                    values[3],
                )

                if add_output_column:
                    values[4] = TextwrapEx.CreateAnsiHyperLinkEx(
                        "file://{}".format(final_info.output_dir.as_posix()),
                        values[4],
                    )

            if has_short_descs:
                values[-1] = "{}{}{}".format(color_on, values[-1], color_off)

            return values

        # ----------------------------------------------------------------------

        with dm.YieldStream() as stream:
            indented_stream = StreamDecorator(stream, "    ")

            indented_stream.write("\n\n")

            if common_path is not None:
                indented_stream.write(
                    textwrap.dedent(
                        """\
                        All items are relative to '{}'.


                        """,
                    ).format(
                        common_path if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                            "file://{}".format(common_path),
                            str(common_path),
                        ),
                    ),
                )

            headers: List[str] = [
                "Context Name",
                "Result",
                "Execution Time",
                "Log File",
            ]

            if add_output_column:
                headers.append("Output Directory")

            if has_short_descs:
                headers.append("Short Description")

            col_justifications = [TextwrapEx.Justify.Left for _ in range(len(headers))]
            col_justifications[1] = TextwrapEx.Justify.Center
            col_justifications[3] = TextwrapEx.Justify.Right

            if add_output_column:
                col_justifications[4] = TextwrapEx.Justify.Right

            indented_stream.write(
                TextwrapEx.CreateTable(
                    headers,
                    rows,
                    col_justifications,
                    decorate_values_func=DecorateRow,
                ),
            )

            indented_stream.write("\n")

        # Write final output
        success_count = 0
        warning_count = 0
        error_count = 0

        for final_info in final_infos:
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
                success_percentage=(success_count / len(final_infos)) * 100,
                error_prefix=TextwrapEx.CreateErrorPrefix(dm.capabilities),
                error_count=error_count,
                error_percentage=(error_count / len(final_infos)) * 100,
                warning_prefix=TextwrapEx.CreateWarningPrefix(dm.capabilities),
                warning_count=warning_count,
                warning_percentage=(warning_count / len(final_infos)) * 100,
                total=len(final_infos),
            ),
        )
