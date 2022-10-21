# ----------------------------------------------------------------------
# |
# |  ExecuteTasks.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 14:26:02
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality to execute tasks with a nice progress bar display"""

import datetime
import multiprocessing
import threading
import time
import traceback

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union

from rich.progress import Progress, TaskID, TimeElapsedColumn

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import TextwrapEx

from .InflectEx import inflect


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
CATASTROPHIC_TASK_FAILURE_RESULT            = -123


# ----------------------------------------------------------------------
class TransformException(Exception):
    """Exception raised when the Transformation process has errors"""
    pass


# ----------------------------------------------------------------------
@dataclass
class TaskData(object):
    display: str
    context: Any

    execution_lock: Optional[threading.Lock]

    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)

    execution_time: datetime.timedelta      = field(init=False)
    log_filename: Path                      = field(init=False)


# ----------------------------------------------------------------------
class Step3ProgressType(Enum):
    standard                                = auto()
    info                                    = auto()
    verbose                                 = auto()


class Step3ProgressProtocol(Protocol):
    def __call__(
        self,
        zero_based_step: Optional[int],
        status: str,
        progress_type: Step3ProgressType=Step3ProgressType.standard,
    ) -> bool:                              # True to continue, False to terminate
        ...


# ----------------------------------------------------------------------
ExecuteTasksStep3Type                       = Callable[
    [
        Step3ProgressProtocol,
    ],
    Tuple[
        int,                                # Return code
        Optional[str],                      # Status message
    ],
]

ExecuteTasksStep2Type                       = Callable[
    [
        Callable[
            [
                str,                        # Status
            ],
            None,
        ],
    ],
    Tuple[
        Optional[int],                      # Number of steps
        ExecuteTasksStep3Type,
    ],
]

ExecuteTasksStep1Type                       = Callable[
    [
        Any,                                # TaskData.context
    ],
    Tuple[
        Path,                               # Log filename
        ExecuteTasksStep2Type,
    ],
]


# ----------------------------------------------------------------------
TransformStep3Type                          = Callable[
    [
        Step3ProgressProtocol,
    ],
    Tuple[
        Any,                                # Result
        Optional[str],                      # Status message
    ],
]

TransformStep2Type                          = Callable[
    [
        Any,                                # TaskData.context
        Callable[
            [
                str,                        # Status
            ],
            None,
        ],
    ],
    Tuple[
        Optional[int],                      # Number of steps
        TransformStep3Type,
    ],
]


# ----------------------------------------------------------------------
# These values remain for backwards compatibility but should not be used
# in new code.
Step1Type                                   = ExecuteTasksStep1Type
Step2Type                                   = ExecuteTasksStep2Type
Step3Type                                   = ExecuteTasksStep3Type


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def ExecuteTasks(
    dm: DoneManager,
    task_desc: str,
    tasks: List[TaskData],
    step1_func: Step1Type,
    custom_done_func_or_funcs: Union[
        None,
        Callable[[], Optional[str]],
        List[Callable[[], Optional[str]]],
    ]=None,
    *,
    quiet: bool=False,
    max_num_threads: Optional[int]=None,
    refresh_per_second: Optional[float]=None,
) -> None:
    """Executes tasks that output work to individual log files"""

    error_count = 0
    warning_count = 0
    success_count = 0

    count_lock = threading.Lock()

    done_funcs: List[Callable[[], Optional[str]]] = [
        lambda: "{} succeeded".format(inflect.no("item", success_count)),
        lambda: "{} with errors".format(inflect.no("item", error_count)),
        lambda: "{} with warnings".format(inflect.no("item", warning_count)),
    ]

    if custom_done_func_or_funcs is not None:
        if isinstance(custom_done_func_or_funcs, list):
            done_funcs += custom_done_func_or_funcs
        else:
            done_funcs.append(custom_done_func_or_funcs)

    with dm.Nested(
        "{} {}...".format(task_desc, inflect.no("item", len(tasks))),
        done_funcs,
        suffix="\n" if (error_count or warning_count) and not quiet else "",
    ) as execute_dm:
        with execute_dm.YieldStdout() as stdout_context:
            stdout_context.persist_content = False

            progress_args: Dict[str, Any] = {}

            if refresh_per_second is not None:
                progress_args["refresh_per_second"] = refresh_per_second

            with Progress(
                *Progress.get_default_columns(),
                TimeElapsedColumn(),
                "{task.fields[status]}",
                **{
                    **{
                        "transient": True,
                    },
                    **progress_args,
                },
            ) as progress:
                total_progress_id = progress.add_task(
                    "{}Total Progress".format(stdout_context.line_prefix),
                    total=len(tasks),
                    status="",
                )

                num_threads = min(len(tasks), multiprocessing.cpu_count())
                if max_num_threads:
                    num_threads = min(max_num_threads, num_threads)

                with ThreadPoolExecutor(num_threads) as executor:
                    # ----------------------------------------------------------------------
                    def Impl(
                        task_id: TaskID,
                        task_data: TaskData,
                    ) -> None:
                        if not quiet:
                            progress.update(
                                task_id,
                                refresh=False,
                                visible=True,
                            )

                        start_time = time.perf_counter()

                        # ----------------------------------------------------------------------
                        def OnExit():
                            nonlocal success_count
                            nonlocal error_count
                            nonlocal warning_count

                            progress.update(
                                task_id,
                                completed=True,
                                refresh=False,
                                visible=False,
                            )

                            if task_data.result < 0 and not quiet:
                                progress.print(
                                    r"{prefix}[bold red]ERROR:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                        prefix=stdout_context.line_prefix,
                                        name=task_data.display,
                                        result=task_data.result,
                                        short_desc=" ({})".format(task_data.short_desc) if task_data.short_desc else "",
                                        suffix=str(task_data.log_filename) if execute_dm.capabilities.is_headless else "[link=file:///{}]View Log[/]".format(
                                            task_data.log_filename.as_posix(),
                                        ),
                                    ),
                                    highlight=False,
                                )

                                stdout_context.persist_content = True

                            if task_data.result > 0 and not quiet:
                                progress.print(
                                    r"{prefix}[bold yellow]WARNING:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                        prefix=stdout_context.line_prefix,
                                        name=task_data.display,
                                        result=task_data.result,
                                        short_desc=" ({})".format(task_data.short_desc) if task_data.short_desc else "",
                                        suffix=str(task_data.log_filename) if execute_dm.capabilities.is_headless else "[link=file:///{}]View Log[/]".format(
                                            task_data.log_filename.as_posix(),
                                        ),
                                    ),
                                    highlight=False,
                                )

                                stdout_context.persist_content = True

                            with count_lock:
                                if task_data.result < 0:
                                    error_count += 1
                                elif task_data.result > 0:
                                    warning_count += 1
                                else:
                                    success_count += 1

                                successes = success_count
                                errors = error_count
                                warnings = warning_count

                            progress.update(
                                total_progress_id,
                                advance=1,
                                refresh=False,
                                status=TextwrapEx.CreateStatusText(successes, errors, warnings),
                            )

                        # ----------------------------------------------------------------------

                        with ExitStack(OnExit):
                            try:
                                task_data.log_filename, step2_func = step1_func(task_data.context)

                                # ----------------------------------------------------------------------
                                def OnSimpleStatus(
                                    status: str,
                                ) -> None:
                                    progress.update(
                                        task_id,
                                        refresh=False,
                                        status=status,
                                    )

                                # ----------------------------------------------------------------------

                                num_steps, step3_func = step2_func(OnSimpleStatus)

                                # ----------------------------------------------------------------------
                                @contextmanager
                                def AcquireExecutionLock():
                                    if task_data.execution_lock is None:
                                        yield
                                        return

                                    OnSimpleStatus("Waiting...")
                                    with task_data.execution_lock:
                                        yield

                                # ----------------------------------------------------------------------

                                with AcquireExecutionLock():
                                    progress.update(
                                        task_id,
                                        refresh=False,
                                        total=num_steps,
                                    )

                                    current_step = 0

                                    # ----------------------------------------------------------------------
                                    def OnProgress(
                                        zero_based_step: Optional[int],
                                        status: str,
                                        progress_type: Step3ProgressType=Step3ProgressType.standard,
                                    ) -> bool:
                                        if progress_type == Step3ProgressType.standard:
                                            nonlocal current_step

                                            if zero_based_step is not None:
                                                advance = zero_based_step - 1 - current_step
                                                current_step = zero_based_step - 1

                                                status = "({} of {}) {}".format(
                                                    current_step + 1,
                                                    num_steps,
                                                    status,
                                                )

                                            elif num_steps is not None:
                                                advance = None

                                                status = "({} of {}) {}".format(
                                                    current_step + 1,
                                                    num_steps,
                                                    status,
                                                )

                                            else:
                                                advance = None

                                            progress.update(
                                                task_id,
                                                advance=advance,
                                                refresh=False,
                                                status=status,
                                            )

                                            return True

                                        if progress_type == Step3ProgressType.verbose:
                                            if not dm.is_verbose:
                                                return True

                                            prefix = "[bright_black]VERBOSE: [/]"

                                        elif progress_type == Step3ProgressType.info:
                                            prefix = "[bright_black]INFO: [/]"

                                        else:
                                            assert False, progress_type  # pragma: no cover

                                        progress.print(
                                            "{line_prefix}{prefix}{status}".format(
                                                line_prefix=stdout_context.line_prefix,
                                                prefix=prefix,
                                                status=status.rstrip(),
                                            ),
                                            highlight=False,
                                        )

                                        stdout_context.persist_content = True

                                        return True

                                    # ----------------------------------------------------------------------

                                    task_data.result, task_data.short_desc = step3_func(OnProgress)

                            except KeyboardInterrupt:  # pylint: disable=try-except-raise
                                raise

                            except Exception as ex:  # pylint: disable=broad-except
                                if dm.is_debug:
                                    error = traceback.format_exc()
                                else:
                                    error = str(ex)

                                error = error.rstrip()

                                if not hasattr(task_data, "log_filename"):
                                    # If here, this error has happened before we have received anything
                                    # from the initial callback. Create a log file and write the exception
                                    # information.
                                    task_data.log_filename = CurrentShell.CreateTempFilename()
                                    assert task_data.log_filename is not None

                                    with task_data.log_filename.open("w") as f:
                                        f.write(error)

                                else:
                                    with task_data.log_filename.open("a+") as f:
                                        f.write("\n\n{}\n".format(error))

                                if isinstance(ex, TransformException):
                                    result = 1
                                    short_desc = "{} failed".format(task_desc)
                                else:
                                    result = CATASTROPHIC_TASK_FAILURE_RESULT
                                    short_desc = "{} failed spectacularly".format(task_desc)

                                task_data.result = result
                                task_data.short_desc = short_desc

                            task_data.execution_time = datetime.timedelta(seconds=time.perf_counter() - start_time)

                    # ----------------------------------------------------------------------

                    futures = [
                        executor.submit(
                            Impl,
                            progress.add_task(
                                "{}  {}".format(stdout_context.line_prefix, task_data.display),
                                status="",
                                total=None,
                                visible=False,
                            ),
                            task_data,
                        )
                        for task_data in tasks
                    ]

                    for future in futures:
                        future.result()

        if error_count:
            execute_dm.result = -1
        elif warning_count and execute_dm.result == 0:
            execute_dm.result = 1


# ----------------------------------------------------------------------
def Transform(
    dm: DoneManager,
    task_desc: str,
    tasks: List[TaskData],
    step2_func: TransformStep2Type,
    custom_done_func_or_funcs: Union[
        None,
        Callable[[], Optional[str]],
        List[Callable[[], Optional[str]]],
    ]=None,
    *,
    quiet: bool=False,
    max_num_threads: Optional[int]=None,
    refresh_per_second: Optional[float]=None,
) -> List[Any]:
    """Executes tasks that do not output work to log files"""

    temp_directory = CurrentShell.CreateTempDirectory()
    was_successful = False

    # ----------------------------------------------------------------------
    def OnExit():
        if was_successful:
            PathEx.RemoveTree(temp_directory)
            return

        dm.WriteInfo("The temporary directory '{}' was preserved due to errors during the transformation process.".format(temp_directory))

    # ----------------------------------------------------------------------

    with ExitStack(OnExit):
        all_results: List[Any] = [None for _ in range(len(tasks))]

        # ----------------------------------------------------------------------
        def ExecuteTasksStep1Func(
            context_info: Tuple[int, Any],
        ) -> Tuple[Path, ExecuteTasksStep2Type]:
            task_index, context = context_info

            log_filename = temp_directory / "{:06}.log".format(task_index)

            # ----------------------------------------------------------------------
            def ExecuteTasksStep2Func(
                on_simple_status,
            ) -> Tuple[Optional[int], ExecuteTasksStep3Type]:
                num_steps, step3_func = step2_func(context, on_simple_status)

                # ----------------------------------------------------------------------
                def ExecuteTasksStep3Func(
                    on_status: Step3ProgressProtocol,
                ) -> Tuple[int, Optional[str]]:
                    result, status_message = step3_func(on_status)

                    all_results[task_index] = result
                    return 0, status_message

                # ----------------------------------------------------------------------

                return num_steps, ExecuteTasksStep3Func

            # ----------------------------------------------------------------------

            return log_filename, ExecuteTasksStep2Func

        # ----------------------------------------------------------------------

        for task_index, task in enumerate(tasks):
            task.context = (task_index, task.context)

        # ----------------------------------------------------------------------
        def RestoreContexts():
            for task in tasks:
                task.context = task.context[1]

        # ----------------------------------------------------------------------

        with ExitStack(RestoreContexts):
            ExecuteTasks(
                dm,
                task_desc,
                tasks,
                ExecuteTasksStep1Func,
                custom_done_func_or_funcs,
                quiet=quiet,
                max_num_threads=max_num_threads,
                refresh_per_second=refresh_per_second,
            )

        was_successful = dm.result == 0

        return all_results
