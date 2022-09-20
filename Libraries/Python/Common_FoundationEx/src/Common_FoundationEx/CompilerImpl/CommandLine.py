# ----------------------------------------------------------------------
# |
# |  CommandLine.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 14:08:23
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

import io
import os
import textwrap
import traceback

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import typer

from typer.models import OptionInfo

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell                                # pylint: disable=unused-import
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags     # pylint: disable=unused-import
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.ExecuteTasks import ExecuteTasks, TaskData
from Common_FoundationEx.InflectEx import inflect

from .CompilerImpl import CompilerImpl, InputType
from .Mixins.OutputProcessorMixins.NoOutputProcessorMixin import NoOutputProcessorMixin


# ----------------------------------------------------------------------
def CreateInvokeCommandLineFunc(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    custom_parameters = _CustomParameters.Create(compiler)

    if compiler.requires_output_dir:
        output_dir_parameter = textwrap.dedent(
            """\
            output_dir: Path=typer.Argument(
                ...,
                file_okay=False,
                resolve_path=True,
                help="Directory to write output; it will be created if it doesn't already exist.",
            ),
            """,
        )

        output_dir_argument = "output_dir"
    else:
        output_dir_parameter = ""
        output_dir_argument = "CurrentShell.CreateTempDirectory()"

    if compiler.can_execute_in_parallel:
        single_threaded_parameter = 'single_threaded: bool=typer.Option(False, "--single-threaded", help="Only use a single thread when compiling."),'
        single_threaded_argument = "single_threaded=single_threaded"
    else:
        single_threaded_parameter = ""
        single_threaded_argument = "single_threaded=False"

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
            {output_dir_parameter}
            {custom_parameters}
            {single_threaded_parameter}
            quiet: bool=typer.Option(False, "--quiet", help="Write less output to the terminal."),
            verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
            debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
        ) -> None:
            '''Invokes '{name}'.'''

            with DoneManager.CreateCommandLine(
                output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
            ) as dm:
                _InvokeImpl(
                    compiler,
                    dm,
                    inputs,
                    {output_dir_argument},
                    {custom_args},
                    {single_threaded_argument},
                    quiet=quiet,
                )
        """,
    ).format(
        name=compiler.name,
        invocation_method_name=compiler.invocation_method_name,
        file_okay="True" if compiler.input_type == InputType.Files else "False",
        output_dir_parameter=TextwrapEx.Indent(
            output_dir_parameter,
            4,
            skip_first_line=True,
        ),
        custom_parameters=custom_parameters.GetParametersCode(),
        single_threaded_parameter=single_threaded_parameter,
        output_dir_argument=output_dir_argument,
        single_threaded_argument=single_threaded_argument,
        custom_args=custom_parameters.GetArgumentsCode(),
    )

    global_vars = globals()

    global_vars["app"] = app
    global_vars["compiler"] = compiler
    global_vars["custom_parameters"] = custom_parameters

    exec(func, global_vars)  # pylint: disable=exec-used

    return Impl  #  type: ignore  # pylint: disable=undefined-variable


# ----------------------------------------------------------------------
def CreateCleanCommandLineFunc(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    assert compiler.requires_output_dir

    custom_parameters = _CustomParameters.Create(compiler)

    func = textwrap.dedent(
        """\
        # ----------------------------------------------------------------------
        @app.command("Clean", no_args_is_help=True)
        def Impl(
            inputs: List[Path]=typer.Argument(
                ...,
                exists=True,
                file_okay=False,
                dir_okay=True,
                resolve_path=True,
                help="Output directories generated by prior calls to '{invocation_method_name}'.",
            ),
            {custom_parameters}
            verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
            debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
        ) -> None:
            '''Cleans items generated by '{name}' during prior calls to '{invocation_method_name}'.'''

            with DoneManager.CreateCommandLine(
                output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
            ) as dm:
                _CleanImpl(
                    compiler,
                    dm,
                    inputs,
                    {custom_args},
                )
        """,
    ).format(
        name=compiler.name,
        invocation_method_name=compiler.invocation_method_name,
        custom_parameters=custom_parameters.GetParametersCode(),
        custom_args=custom_parameters.GetArgumentsCode(),
    )

    global_vars = globals()

    global_vars["app"] = app
    global_vars["compiler"] = compiler
    global_vars["custom_parameters"] = custom_parameters

    exec(func, global_vars)  # pylint: disable=exec-used

    return Impl  #  type: ignore  # pylint: disable=undefined-variable


# ----------------------------------------------------------------------
def CreateListCommandLineFunc(
    app: typer.Typer,
    compiler: CompilerImpl,
) -> Callable[..., None]:
    custom_parameters = _CustomParameters.Create(compiler)

    func = textwrap.dedent(
        """\
        # ----------------------------------------------------------------------
        @app.command("List", no_args_is_help=True)
        def Impl(
            inputs: List[Path]=typer.Argument(
                ...,
                exists=True,
                file_okay=False,
                dir_okay=True,
                resolve_path=True,
                help="File system inputs.",
            ),
            {custom_parameters}
            verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
            debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
        ) -> None:
            '''Lists items that will be processed by '{name}' during calls to '{invocation_method_name}'.'''

            with DoneManager.CreateCommandLine(
                output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
            ) as dm:
                _ListImpl(
                    compiler,
                    dm,
                    inputs,
                    {custom_args},
                )
        """,
    ).format(
        name=compiler.name,
        invocation_method_name=compiler.invocation_method_name,
        custom_parameters=custom_parameters.GetParametersCode(),
        custom_args=custom_parameters.GetArgumentsCode(),
    )

    global_vars = globals()

    global_vars["app"] = app
    global_vars["compiler"] = compiler
    global_vars["custom_parameters"] = custom_parameters

    exec(func, global_vars)  # pylint: disable=exec-used

    return Impl  #  type: ignore  # pylint: disable=undefined-variable


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _CustomParameters(object):
    # ----------------------------------------------------------------------
    parameters: Dict[str, str]
    types: Dict[str, OptionInfo]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        compiler: CompilerImpl,
        result_var_name: str="custom_parameters",
    ) -> "_CustomParameters":
        parameters: Dict[str, str] = {}
        types: Dict[str, OptionInfo] = {}

        for k, v in compiler.GetCustomCommandLineArgs().items():
            if isinstance(v, tuple):
                annotation, v = v

                if isinstance(v, dict):
                    v = typer.Option(None, **v)

                assert isinstance(v, OptionInfo), v
                types[k] = v

                default = '={}.types["{}"]'.format(result_var_name, k)
            else:
                annotation = v
                default = ""

            parameters[k] = '{name}: {annotation}{default}'.format(
                name=k,
                annotation=annotation.__name__,
                default=default,
            )

        return cls(parameters, types)

    # ----------------------------------------------------------------------
    def GetParametersCode(self) -> str:
        return TextwrapEx.Indent(
            "\n".join("{},".format(parameter) for parameter in self.parameters.values()),
            4,
            skip_first_line=True,
        )

    # ----------------------------------------------------------------------
    def GetArgumentsCode(self) -> str:
        if not self.parameters:
            return "{}"

        return "{{{}}}".format(", ".join('"{k}": {k}'.format(k=k) for k in self.parameters))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _ContextInfo(object):
    # ----------------------------------------------------------------------
    contexts: List[Dict[str, Any]]
    common_path: Optional[Path]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        compiler: CompilerImpl,
        dm: DoneManager,
        inputs: List[Path],
        output_dir: Path,
        custom_params: Dict[str, Any],
    ) -> "_ContextInfo":
        result = compiler.ValidateEnvironment()
        if result is not None:
            dm.WriteError(result)
            return cls([], None)

        if compiler.requires_output_dir:
            custom_params["output_dir"] = output_dir

        contexts: List[Dict[str, Any]] = []

        with dm.Nested(
            "Generating item(s)...",
            lambda: "{} found".format(inflect.no("item", len(contexts))),
            suffix="\n",
        ) as generate_dm:
            try:
                contexts += compiler.GenerateContextItems(generate_dm, inputs, custom_params)
            except Exception as ex:
                if generate_dm.is_debug:
                    error = traceback.format_exc()
                else:
                    error = str(ex)

                generate_dm.WriteError(error.rstrip())

        if generate_dm.result != 0 or not contexts:
            return cls([], None)

        # Create the display names
        display_names: List[str] = [
            compiler.GetDisplayName(context) or "Item Group {}".format(index + 1)
            for index, context in enumerate(contexts)
        ]

        # ----------------------------------------------------------------------
        def UpdateDisplayNames() -> Optional[Path]:
            # Find a common path if all of the display names are paths
            paths: List[Path] = []

            for display_name in display_names:
                path = Path(display_name).resolve()

                if not path.exists():
                    return None

                paths.append(path)

            common_path = PathEx.GetCommonPath(*paths)
            if common_path is None:
                return None

            # We have a common path! Update all of the display names
            len_common_path_parts = len(common_path.parts)

            for index, path in enumerate(paths):
                contexts[index]["display_name"] = os.path.sep.join(path.parts[len_common_path_parts:])

            return common_path

        # ----------------------------------------------------------------------

        common_path = UpdateDisplayNames()

        return cls(contexts, common_path)


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _InvokeImpl(
    compiler: CompilerImpl,
    dm: DoneManager,
    inputs: List[Path],
    output_dir: Path,
    custom_params: Dict[str, Any],
    *,
    single_threaded: bool,
    quiet: bool,
) -> None:
    """Implements invoke functionality for the compiler"""

    context_info = _ContextInfo.Create(compiler, dm, inputs, output_dir, custom_params)

    if not context_info.contexts:
        return

    # Create and execute the tasks
    # ----------------------------------------------------------------------
    @dataclass
    class TaskDataContext(object):
        output_dir: Path
        compiler_context: Dict[str, Any]

    # ----------------------------------------------------------------------
    def GetLogFilename(
        task_data: TaskData,
    ):
        task_data.context.output_dir.mkdir(parents=True, exist_ok=True)

        log_filename = task_data.context.output_dir / "output.log"

        return (
            log_filename,
            lambda progress: GetNumSteps(task_data, log_filename, progress),
        )

    # ----------------------------------------------------------------------
    def GetNumSteps(
        task_data: TaskData,
        log_filename: Path,
        progress_func: Callable[[str], None],  # pylint: disable=unused-argument
    ):
        return (
            compiler.GetNumSteps(task_data.context.compiler_context),
            lambda progress: Execute(task_data, log_filename, progress),
        )

    # ----------------------------------------------------------------------
    def Execute(
        task_data: TaskData,
        log_filename: Path,
        progress_func: Callable[[int, str], bool],
    ):
        with open(log_filename, "w") as f:
            result = getattr(compiler, compiler.invocation_method_name)(
                task_data.context.compiler_context,
                f,
                progress_func,
                verbose=dm.is_verbose,
            )

            compiler.RemoveTemporaryArtifacts(task_data.context.compiler_context)

            if not isinstance(result, tuple):
                result = result, None

            return result

    # ----------------------------------------------------------------------

    tasks: List[TaskData] = [
        TaskData(
            context["display_name"],
            TaskDataContext(
                output_dir / "{:06}".format(index),
                context,
            ),
            None,
        )
        for index, context in enumerate(context_info.contexts)
    ]

    ExecuteTasks(
        dm,
        "Executing",
        tasks,
        GetLogFilename,
        quiet=quiet,
        max_num_threads=1 if single_threaded else None,
    )

    # Prepare the final output
    add_output_column = not isinstance(compiler, NoOutputProcessorMixin)

    rows: List[List[str]] = []

    for task_data in tasks:
        rows.append(
            [
                task_data.context.compiler_context["display_name"],
                "Failed ({})".format(task_data.result) if task_data.result < 0
                    else "Unknown ({})".format(task_data.result) if task_data.result > 0
                        else "Succeeded ({})".format(task_data.result)
                ,
                str(task_data.execution_time),
                "{}{}".format(
                    TextwrapEx.GetSizeDisplay(task_data.log_filename.stat().st_size) if task_data.log_filename.is_file() else "",
                    "" if dm.capabilities.is_headless else " [View Log]",
                ),
            ]
        )

        if add_output_column:
            rows[-1].append(
                "{} [View]".format(
                    str(task_data.context.output_dir) if not dm.capabilities.is_headless else inflect.no(
                        "item",
                        sum(1 for _ in task_data.context.output_dir.iterdir()),
                    ),
                ),
            )

        rows[-1].append(task_data.short_desc or "")

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
        task_data = tasks[index]

        if task_data.result < 0:
            color_on = failure_on
        elif task_data.result > 0:
            color_on = warning_on
        else:
            color_on = success_on

        values[1] = "{}{}{}".format(color_on, values[1], color_off)

        # Attempt to provide a link to the name
        if not dm.capabilities.is_headless:
            if context_info.common_path:
                potential_file = context_info.common_path / context_info.contexts[index]["display_name"]
            else:
                potential_file = Path(context_info.contexts[index]["display_name"])

            if potential_file.is_file():
                values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(potential_file.as_posix()),
                    values[0],
                )

            values[3] = TextwrapEx.CreateAnsiHyperLinkEx(
                "file://{}".format(task_data.log_filename.as_posix()),
                values[3],
            )

            if add_output_column:
                values[4] = TextwrapEx.CreateAnsiHyperLinkEx(
                    "file://{}".format(task_data.context.output_dir.as_posix()),
                    values[4],
                )

        return values

    # ----------------------------------------------------------------------

    with dm.YieldStream() as stream:
        indented_stream = StreamDecorator(stream, "    ")

        indented_stream.write("\n\n")

        if context_info.common_path is not None:
            indented_stream.write(
                textwrap.dedent(
                    """\
                    All items are relative to '{}'.


                    """,
                ).format(
                    context_info.common_path if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                        "file://{}".format(context_info.common_path.as_posix()),
                        str(context_info.common_path),
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

        headers.append("Short Description")

        col_justifications: List[TextwrapEx.Justify] = [
            TextwrapEx.Justify.Left,
            TextwrapEx.Justify.Center,
            TextwrapEx.Justify.Left,
            TextwrapEx.Justify.Right,
        ]

        if add_output_column:
            col_justifications.append(TextwrapEx.Justify.Right)

        col_justifications.append(TextwrapEx.Justify.Left)

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

    for task_data in tasks:
        if task_data.result < 0:
            error_count += 1
        elif task_data.result > 0:
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
            success_percentage=(success_count / len(tasks)) * 100,
            error_prefix=TextwrapEx.CreateErrorPrefix(dm.capabilities),
            error_count=error_count,
            error_percentage=(error_count / len(tasks)) * 100,
            warning_prefix=TextwrapEx.CreateWarningPrefix(dm.capabilities),
            warning_count=warning_count,
            warning_percentage=(warning_count / len(tasks)) * 100,
            total=len(tasks),
        ),
    )


# ----------------------------------------------------------------------
def _CleanImpl(
    compiler: CompilerImpl,
    dm: DoneManager,
    inputs: List[Path],
    output_dir: Path,
    custom_params: Dict[str, Any],
) -> None:
    """Implements clean functionality for the compiler"""

    context_info = _ContextInfo.Create(compiler, dm, inputs, output_dir, custom_params)

    if not context_info.contexts:
        return

    with dm.Nested("Cleaning...") as clean_dm:
        for index, context in enumerate(context_info.contexts):
            with clean_dm.Nested(
                "Processing '{}' ({} of {})...".format(
                    context["display_name"],
                    index + 1,
                    len(context_info.contexts),
                ),
            ) as this_dm:
                sink = io.StringIO()

                compiler.Clean(this_dm, sink, context)

                sink = sink.getvalue()

                if this_dm.result != 0:
                    this_dm.WriteError(sink)
                else:
                    this_dm.WriteVerbose(sink)


# ----------------------------------------------------------------------
def _ListImpl(
    compiler: CompilerImpl,
    dm: DoneManager,
    inputs: List[Path],
    custom_params: Dict[str, Any],
) -> None:
    """Implements list functionality for the compiler"""

    temp_dir = CurrentShell.CreateTempDirectory()
    with ExitStack(lambda: PathEx.RemoveTree(temp_dir)):
        with dm.YieldStream() as stream:
            context_info = _ContextInfo.Create(compiler, dm, inputs, temp_dir, custom_params)

            for index, context in enumerate(context_info.contexts):
                stream.write("\n")

                rows: List[List[str]] = []

                for k, v in context.items():
                    rows.append([k, str(v)])

                prefix = "{}) ".format(index + 1)

                stream.write(
                    "{}{}\n".format(
                        prefix,
                        TextwrapEx.Indent(
                            TextwrapEx.CreateTable(
                                ["Attribute", "Value"],
                                rows,
                            ),
                            len(prefix),
                            skip_first_line=True,
                        ),
                    ),
                )
