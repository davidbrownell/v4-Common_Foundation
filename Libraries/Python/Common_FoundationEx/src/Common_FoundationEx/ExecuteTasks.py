# ----------------------------------------------------------------------
# |
# |  ExecuteTasks.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-23 09:11:23
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality to execute multiple tasks in parallel."""

import datetime
import multiprocessing
import threading
import time
import traceback

from abc import abstractmethod, ABC
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, List, Optional, Protocol, Tuple, TypeVar

from rich.progress import Progress, TaskID, TimeElapsedColumn

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
CATASTROPHIC_TASK_FAILURE_RESULT            = -123


# ----------------------------------------------------------------------
class TransformException(Exception):
    """Exception raised when the Transform process has errors when processing a task."""
    pass  # pylint: disable=unnecessary-pass


# ----------------------------------------------------------------------
@dataclass
class TaskData(object):
    display: str
    context: Any

    # Set this value if the task needs to be processed exclusively with respect to
    # other `TaskData` objects with the same execution lock.
    execution_lock: Optional[threading.Lock]            = field(default=None)

    # The following values will be populated during task execution
    result: int                             = field(init=False)
    short_desc: Optional[str]               = field(init=False)

    execution_time: datetime.timedelta      = field(init=False)
    log_filename: Path                      = field(init=False)


# ----------------------------------------------------------------------
class Status(ABC):
    # ----------------------------------------------------------------------
    @abstractmethod
    def OnProgress(
        self,
        zero_based_step: Optional[int],
        status: Optional[str],
    ) -> bool:
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnInfo(
        self,
        value: str,
        *,
        verbose: bool=False,
    ) -> None:
        raise Exception("Abstract method")


# ----------------------------------------------------------------------
class ExecuteTasksStep3FuncType(Protocol):
    def __call__(
        self,
        status: Status,
    ) -> Tuple[
        int,                                # Return code
        Optional[str],                      # Final status message
    ]:
        ...


class ExecuteTasksStep2FuncType(Protocol):
    def __call__(
        self,
        on_simple_status_func: Callable[
            [
                str,                        # Status
            ],
            None,
        ],
    ) -> Tuple[
        Optional[int],                      # Number of steps
        ExecuteTasksStep3FuncType,
    ]:
        ...

class ExecuteTasksStep1FuncType(Protocol):
    def __call__(
        self,
        context: Any,                       # TaskData.context
    ) -> Tuple[
        Path,                               # Log filename
        ExecuteTasksStep2FuncType,
    ]:
        ...


def ExecuteTasks(
    dm: DoneManager,
    desc: str,
    tasks: List[TaskData],
    step1_func: ExecuteTasksStep1FuncType,
    *,
    quiet: bool=False,
    max_num_threads: Optional[int]=None,
    refresh_per_second: Optional[float]=None,
) -> None:
    """Executes tasks that output to individual log files"""

    with _GenerateStatusInfo(
        len(tasks),
        dm,
        desc,
        tasks,
        quiet=quiet,
        refresh_per_second=refresh_per_second,
    ) as (status_factories, on_task_complete_func):
        if max_num_threads == 1:
            for task_data, status_factory in zip(tasks, status_factories):
                with ExitStack(status_factory.Stop):
                    _ExecuteTask(
                        desc,
                        task_data,
                        step1_func,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

            return

        with ThreadPoolExecutor(
            max_workers=max_num_threads,
        ) as executor:
            # ----------------------------------------------------------------------
            def Impl(
                task_data: TaskData,
                status_factory: "_StatusFactory",
            ):
                with ExitStack(status_factory.Stop):
                    _ExecuteTask(
                        desc,
                        task_data,
                        step1_func,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

            # ----------------------------------------------------------------------

            futures = [
                executor.submit(Impl, task_data, status_factory)
                for task_data, status_factory in zip(tasks, status_factories)
            ]

            for future in futures:
                future.result()


# ----------------------------------------------------------------------
TransformedType                             = TypeVar("TransformedType", covariant=True)


class TransformStep2FuncType(Protocol[TransformedType]):
    def __call__(
        self,
        status: Status,
    ) -> Tuple[
        TransformedType,
        Optional[str],                      # Final status message
    ]:
        ...


class TransformStep1FuncType(Protocol[TransformedType]):
    def __call__(
        self,
        context: Any,                       # TaskData.context
        on_simple_status_func: Callable[[str], None],
    ) -> Tuple[
        Optional[int],
        TransformStep2FuncType[TransformedType],
    ]:
        ...


def Transform(
    dm: DoneManager,
    desc: str,
    tasks: List[TaskData],
    step1_func: TransformStep1FuncType[TransformedType],
    *,
    quiet: bool=False,
    max_num_threads: Optional[int]=None,
    refresh_per_second: Optional[float]=None,
    no_compress_tasks: bool=False,
) -> List[Optional[TransformedType]]:
    """Executes functions that return values"""

    temp_directory = CurrentShell.CreateTempDirectory()

    # ----------------------------------------------------------------------
    def OnExit():
        # Delete the temp directory if all has worked as expected
        if dm.result == 0:
            PathEx.RemoveTree(temp_directory)
            return

        dm.WriteInfo("The temporary directory '{}' was preserved due to errors during the transformation process.".format(temp_directory))

    # ----------------------------------------------------------------------

    with ExitStack(OnExit):
        cpu_count = multiprocessing.cpu_count()

        num_threads = min(len(tasks), cpu_count)
        if max_num_threads:
            num_threads = min(num_threads, max_num_threads)

        if (
            no_compress_tasks
            or num_threads < cpu_count
            or num_threads == 1
        ):
            impl_func = _TransformStandard
        else:
            impl_func = _TransformCompressed

        return impl_func(
            temp_directory,
            dm,
            desc,
            tasks,
            step1_func,
            quiet=quiet,
            num_threads=num_threads,
            refresh_per_second=refresh_per_second,
        )


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _StatusFactory(object):
    # ----------------------------------------------------------------------
    # |  Public Types
    class StatusImpl(Status):
        # ----------------------------------------------------------------------
        def __init__(
            self,
            factory_self: "_StatusFactory",
        ):
            self._factory_self              = factory_self

            self._num_steps: Optional[int]              = None
            self._current_step: Optional[int]           = None

        # ----------------------------------------------------------------------
        def SetNumSteps(
            self,
            num_steps: int,
        ) -> None:
            assert self._num_steps is None
            assert self._current_step is None

            self._num_steps = num_steps
            self._current_step = 0

            # pylint: disable=protected-access
            self._factory_self._progress_bar.update(
                self._factory_self._task_id,
                completed=self._current_step,
                refresh=False,
                total=self._num_steps,
            )

        # ----------------------------------------------------------------------
        def OnProgress(
            self,
            zero_based_step: Optional[int],
            status: Optional[str],
        ) -> bool:
            # pylint: disable=protected-access

            if zero_based_step is not None:
                assert self._num_steps is not None
                self._current_step = zero_based_step

            status = status or ""

            if self._num_steps is not None:
                status = "({} of {}) {}".format(
                    self._current_step,
                    self._num_steps,
                    status or "",
                )

            self._factory_self._progress_bar.update(
                self._factory_self._task_id,
                completed=self._current_step,
                refresh=False,
                status=status,
            )

            return True

        # ----------------------------------------------------------------------
        def OnInfo(
            self,
            value: str,
            *,
            verbose: bool=False,
        ) -> None:
            # pylint: disable=protected-access
            if verbose:
                if not self._factory_self._is_verbose:
                    return

                prefix = "[bright_black]VERBOSE: [/]"
            else:
                prefix = "[bright_black]INFO: [/]"

            self._factory_self._progress_bar.print(
                "{line_prefix}{prefix}{value}".format(
                    line_prefix=self._factory_self._stdout_context.line_prefix,
                    prefix=prefix,
                    value=value,
                ),
                highlight=False,
            )

            self._factory_self._stdout_context.persist_content = True

    # ----------------------------------------------------------------------
    # |  Public Methods
    def __init__(
        self,
        stdout_context: StreamDecorator.YieldStdoutContext,
        progress_bar: Progress,
        task_id: TaskID,
        *,
        is_verbose: bool,
    ):
        self._stdout_context                = stdout_context
        self._progress_bar                  = progress_bar
        self._task_id                       = task_id
        self._is_verbose                    = is_verbose

    # ----------------------------------------------------------------------
    @contextmanager
    def CreateStatus(
        self,
        display: str,
    ) -> Iterator["_StatusFactory.StatusImpl"]:
        self._progress_bar.update(
            self._task_id,
            completed=0,
            description="{}  {}".format(self._stdout_context.line_prefix, display),
            refresh=False,
            status="",
            total=None,
            visible=True,
        )

        self._progress_bar.start_task(self._task_id)
        with ExitStack(lambda: self._progress_bar.stop_task(self._task_id)):
            yield _StatusFactory.StatusImpl(self)

    # ----------------------------------------------------------------------
    def Stop(self):
        self._progress_bar.update(
            self._task_id,
            refresh=False,
            visible=False,
        )


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
@contextmanager
def _GenerateStatusInfo(
    display_num_tasks: int,
    dm: DoneManager,
    desc: str,
    tasks: List[TaskData],
    *,
    quiet: bool,
    refresh_per_second: Optional[float],
) -> Iterator[
    Tuple[
        List[_StatusFactory],
        Callable[[TaskData], None],         # on_task_complete_func
    ],
]:
    error_count = 0
    warning_count = 0
    success_count = 0

    count_lock = threading.Lock()

    wrote_info = False

    with dm.Nested(
        "{} {}...".format(desc, inflect.no("item", display_num_tasks)),
        [
            lambda: "{} succeeded".format(inflect.no("item", success_count)),
            lambda: "{} with errors".format(inflect.no("item", error_count)),
            lambda: "{} with warnings".format(inflect.no("item", warning_count)),
        ],
        suffix="\n" if wrote_info else "",
    ) as execute_dm:
        with execute_dm.YieldStdout() as stdout_context:
            stdout_context.persist_content = False

            # Create the progress bar
            progress_bar = Progress(
                *Progress.get_default_columns(),
                TimeElapsedColumn(),
                "{task.fields[status]}",
                transient=True,
                refresh_per_second=refresh_per_second or 10,
            )

            total_progress_id = progress_bar.add_task(
                "{}Total Progress".format(stdout_context.line_prefix),
                total=display_num_tasks,
                status="",
            )

            # ----------------------------------------------------------------------
            def OnTaskDataComplete(
                task_data: TaskData,
            ) -> None:
                nonlocal error_count
                nonlocal warning_count
                nonlocal success_count

                if task_data.result < 0 and not quiet:
                    progress_bar.print(
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
                    progress_bar.print(
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

                    error_display = error_count
                    warning_display = warning_count
                    success_display = success_count

                progress_bar.update(
                    total_progress_id,
                    advance=1,
                    refresh=False,
                    status=TextwrapEx.CreateStatusText(
                        success_display,
                        error_display,
                        warning_display,
                    ),
                )

            # ----------------------------------------------------------------------

            # Add the tasks to the progress bar
            status_factories: List[_StatusFactory] = []

            enqueueing_status = "{}Enqueueing tasks...".format(stdout_context.line_prefix)

            stdout_context.stream.write(enqueueing_status)
            stdout_context.stream.flush()

            for task in tasks:
                status_factories.append(
                    _StatusFactory(
                        stdout_context,
                        progress_bar,
                        progress_bar.add_task(
                            "{}  {}".format(stdout_context.line_prefix, task.display),
                            start=False,
                            status="",
                            total=None,
                            visible=False,
                        ),
                        is_verbose=dm.is_verbose,
                    ),
                )

            stdout_context.stream.write("\r{}\r".format(" " * len(enqueueing_status)))
            stdout_context.stream.flush()

            # Start the progress bar
            progress_bar.start()
            with ExitStack(progress_bar.stop):
                yield status_factories, OnTaskDataComplete


# ----------------------------------------------------------------------
def _ExecuteTask(
    desc: str,
    task_data: TaskData,
    step1_func: ExecuteTasksStep1FuncType,
    status_factory: _StatusFactory,
    on_task_complete_func: Callable[[TaskData], None],
    *,
    is_debug: bool,
) -> None:
    with ExitStack(lambda: on_task_complete_func(task_data)):
        start_time = time.perf_counter()

        try:
            with status_factory.CreateStatus(task_data.display) as status:
                task_data.log_filename, step2_func = step1_func(task_data.context)

                # ----------------------------------------------------------------------
                def OnSimpleStatus(
                    value: str,
                ) -> None:
                    status.OnProgress(None, value)

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
                    if num_steps is not None:
                        assert num_steps >= 0, num_steps
                        status.SetNumSteps(num_steps)

                    task_data.result, task_data.short_desc = step3_func(status)

        except KeyboardInterrupt:  # pylint: disable=try-except-raise
            raise

        except Exception as ex:  # pylint: disable=broad-except
            if is_debug:
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
                short_desc = "{} failed".format(task_data.display)
            else:
                result = CATASTROPHIC_TASK_FAILURE_RESULT
                short_desc = "{} failed".format(desc)

            task_data.result = result
            task_data.short_desc = short_desc

        finally:
            assert hasattr(task_data, "result")
            assert hasattr(task_data, "short_desc")
            assert hasattr(task_data, "log_filename")

            task_data.execution_time = datetime.timedelta(seconds=time.perf_counter() - start_time)


# ----------------------------------------------------------------------
def _TransformStandard(
    temp_directory: Path,
    dm: DoneManager,
    desc: str,
    tasks: List[TaskData],
    step1_func: TransformStep1FuncType[TransformedType],
    *,
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
) -> List[Optional[TransformedType]]:
    all_results: List[Optional[TransformedType]] = [None for _ in range(len(tasks))]

    # Update the task context with task index
    for task_index, task in enumerate(tasks):
        task.context = (task_index, task.context)  # type: ignore

    # ----------------------------------------------------------------------
    def RestoreTaskContexts():
        for task in tasks:
            task.context = task.context[1]  # type: ignore

    # ----------------------------------------------------------------------

    with ExitStack(RestoreTaskContexts):
        # ----------------------------------------------------------------------
        def ExecuteTasksStep1(
            context_info: Tuple[int, Any],
        ) -> Tuple[Path, ExecuteTasksStep2FuncType]:
            task_index, context = context_info

            log_filename = temp_directory / "{:06}.log".format(task_index)

            # ----------------------------------------------------------------------
            def ExecuteTasksStep2(
                on_simple_status_func: Callable[[str], None],
            ) -> Tuple[Optional[int], ExecuteTasksStep3FuncType]:
                num_steps, step3_func = step1_func(context, on_simple_status_func)

                # ----------------------------------------------------------------------
                def ExecuteTasksStep3(
                    status: Status,
                ) -> Tuple[int, Optional[str]]:
                    result, short_desc = step3_func(status)

                    all_results[task_index] = result
                    return 0, short_desc

                # ----------------------------------------------------------------------

                return num_steps, ExecuteTasksStep3

            # ----------------------------------------------------------------------

            return log_filename, ExecuteTasksStep2

        # ----------------------------------------------------------------------

        ExecuteTasks(
            dm,
            desc,
            tasks,
            ExecuteTasksStep1,  # type: ignore
            quiet=quiet,
            max_num_threads=num_threads,
            refresh_per_second=refresh_per_second,
        )

    return all_results


# ----------------------------------------------------------------------
def _TransformCompressed(
    temp_directory: Path,
    dm: DoneManager,
    desc: str,
    tasks: List[TaskData],
    step1_func: TransformStep1FuncType[TransformedType],
    *,
    quiet: bool,
    num_threads: int,
    refresh_per_second: Optional[float],
) -> List[Optional[TransformedType]]:
    assert num_threads != 1

    all_results: List[Optional[TransformedType]] = [None for _ in range(len(tasks))]

    with _GenerateStatusInfo(
        len(tasks),
        dm,
        desc,
        [
            TaskData(
                "",
                thread_index,
            )
            for thread_index in range(num_threads)
        ],
        quiet=quiet,
        refresh_per_second=refresh_per_second,
    ) as (status_factories, on_task_complete_func):
        task_index = 0
        task_index_lock = threading.Lock()

        # ----------------------------------------------------------------------
        def Impl(
            thread_index: int,
        ) -> None:
            nonlocal task_index

            log_filename = temp_directory / "{:06}.log".format(thread_index)
            status_factory = status_factories[thread_index]

            with ExitStack(status_factory.Stop):
                while True:
                    with task_index_lock:
                        this_task_index = task_index
                        task_index += 1

                    if this_task_index >= len(tasks):
                        break

                    task_data = tasks[this_task_index]

                    # ----------------------------------------------------------------------
                    def ExecuteTasksStep1(*args, **kwargs) -> Tuple[Path, ExecuteTasksStep2FuncType]:  # pylint: disable=unused-argument
                        return log_filename, ExecuteTasksStep2

                    # ----------------------------------------------------------------------
                    def ExecuteTasksStep2(
                        on_simple_status_func: Callable[[str], None],
                    ) -> Tuple[Optional[int], ExecuteTasksStep3FuncType]:
                        num_steps, step2_func = step1_func(
                            task_data.context,
                            on_simple_status_func,
                        )

                        # ----------------------------------------------------------------------
                        def ExecuteTasksStep3(
                            status: Status,
                        ) -> Tuple[int, Optional[str]]:
                            result, short_desc = step2_func(status)

                            all_results[this_task_index] = result

                            return 0, short_desc

                        # ----------------------------------------------------------------------

                        return num_steps, ExecuteTasksStep3

                    # ----------------------------------------------------------------------

                    _ExecuteTask(
                        desc,
                        task_data,
                        ExecuteTasksStep1,
                        status_factory,
                        on_task_complete_func,
                        is_debug=dm.is_debug,
                    )

        # ----------------------------------------------------------------------

        with ThreadPoolExecutor(
            max_workers=num_threads,
        ) as executor:
            futures = [
                executor.submit(
                    Impl,
                    thread_index,
                )
                for thread_index in range(num_threads)
            ]

            for future in futures:
                future.result()

    return all_results
