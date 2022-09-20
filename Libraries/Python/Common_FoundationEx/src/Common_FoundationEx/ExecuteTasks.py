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
from pathlib import Path
from typing import Any, Callable, List, Optional, Tuple

from rich.progress import Progress, TaskID

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import TextwrapEx

from .InflectEx import inflect


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
CATASTROPHIC_TASK_FAILURE_RESULT            = 123


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
Step3Type                                   = Callable[
    [
        Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
    ],
    Tuple[int, Optional[str]],              # Return code and short description that provides context about the return code
]

Step2Type                                   = Callable[
    [
        Callable[
            [
                str,                        # Status
            ],
            None,
        ],
    ],
    Tuple[
        int,                                # Number of steps
        Step3Type,
    ],
]

Step1Type                                   = Callable[
    [
        TaskData,
    ],
    Tuple[
        Path,                               # Log filename
        Step2Type
    ],
]


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
    *,
    quiet: bool,
    max_num_threads: Optional[int]=None,
) -> None:
    error_count = 0
    warning_count = 0
    success_count = 0

    count_lock = threading.Lock()

    with dm.Nested(
        "{} {}...".format(task_desc, inflect.no("item", len(tasks))),
        [
            lambda: "{} succeeded".format(inflect.no("item", success_count)),
            lambda: "{} with errors".format(inflect.no("item", error_count)),
            lambda: "{} with warnings".format(inflect.no("item", warning_count)),
        ],
        suffix="\n" if (error_count or warning_count) and not quiet else "",
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
                            progress.update(task_id, visible=True)

                        start_time = time.perf_counter()

                        result = 0
                        short_desc: Optional[str] = None
                        log_filename: Optional[Path] = None

                        try:
                            log_filename, next_callback = step1_func(task_data)

                            # ----------------------------------------------------------------------
                            def OnExit():
                                nonlocal success_count
                                nonlocal error_count
                                nonlocal warning_count

                                assert log_filename is not None

                                progress.update(task_id, completed=True, visible=False)

                                if result < 0 and not quiet:
                                    progress.print(
                                        r"{prefix}[bold red]ERROR:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                            prefix=stdout_context.line_prefix,
                                            name=task_data.display,
                                            result=result,
                                            short_desc=" ({})".format(short_desc) if short_desc else "",
                                            suffix=str(log_filename) if execute_dm.capabilities.is_headless else "[link=file://{}]View Log[/]".format(
                                                log_filename.as_posix(),
                                            ),
                                        ),
                                        highlight=False,
                                    )

                                    stdout_context.persist_content = True

                                if result > 0 and not quiet:
                                    progress.print(
                                        r"{prefix}[bold yellow]WARNING:[/] {name}: {result}{short_desc} \[{suffix}]".format(
                                            prefix=stdout_context.line_prefix,
                                            name=task_data.display,
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
                                # ----------------------------------------------------------------------
                                def OnSimpleStatus(
                                    status: str,
                                ) -> None:
                                    progress.update(task_id, status=status)

                                # ----------------------------------------------------------------------

                                num_steps, next_callback = next_callback(OnSimpleStatus)

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

                                    result, short_desc = next_callback(OnProgress)

                        except KeyboardInterrupt:  # pylint: disable=try-except-raise
                            raise

                        except Exception as ex:
                            if dm.is_debug:
                                error = traceback.format_exc()
                            else:
                                error = str(ex)

                            error = error.rstrip()

                            if log_filename is None:
                                # If here, this error has happened before we have received anything
                                # from the initial callback. Create a log file and write the exception
                                # information.
                                log_filename = CurrentShell.CreateTempFilename()
                                assert log_filename is not None

                                with log_filename.open("w") as f:
                                    f.write(error)

                            else:
                                with log_filename.open("a+") as f:
                                    f.write("\n\n{}\n".format(error))

                            result = CATASTROPHIC_TASK_FAILURE_RESULT
                            short_desc = "{} failed spectacularly".format(task_desc)

                        task_data.result = result
                        task_data.short_desc = short_desc
                        task_data.execution_time = datetime.timedelta(seconds=time.perf_counter() - start_time)
                        task_data.log_filename = log_filename

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
