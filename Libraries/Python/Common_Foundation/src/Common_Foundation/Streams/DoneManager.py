# ----------------------------------------------------------------------
# |
# |  DoneManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-26 16:20:39
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
import itertools
import sys
import time
import traceback

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Flag
from typing import Any, Callable, Iterator, List, Optional, TextIO, Union

from .Capabilities import Capabilities
from .StreamDecorator import StreamDecorator
from .TextWriter import TextWriter

from ..ContextlibEx import ExitStack
from .. import TextwrapEx


# ----------------------------------------------------------------------
# Optional functionality to use if Typer is installed
try:
    import typer

    from click.exceptions import ClickException

    # ----------------------------------------------------------------------
    def OnExitWithTyper(
        result: int,
    ) -> None:
        raise typer.Exit(result)

    # ----------------------------------------------------------------------
    def ShouldRaiseExceptionWithTyper(
        exception: Exception,
    ) -> bool:
        return isinstance(exception, (typer.Exit, typer.Abort, ClickException))

    # ----------------------------------------------------------------------

    OnExit                                  = OnExitWithTyper
    ShouldRaiseException                     = ShouldRaiseExceptionWithTyper

except ImportError:
    # ----------------------------------------------------------------------
    class ExitException(Exception):
        # ----------------------------------------------------------------------
        def __init__(self,
            result: int,
        ):
            self.result                     = result

            super(ExitException, self).__init__("The process is returning with a result of '{}'.".format(result))

    # ----------------------------------------------------------------------
    def OnExitNoTyper(
        result: int,
    ):
        raise ExitException(result)

    # ----------------------------------------------------------------------
    def ShouldRaiseExceptionNoTyper(
        exception: Exception,  # pylint: disable=unused-argument
    ) -> bool:
        return False

    # ----------------------------------------------------------------------

    OnExit                                  = OnExitNoTyper
    ShouldRaiseException                     = ShouldRaiseExceptionNoTyper


# ----------------------------------------------------------------------
# Optional functionality to use if Rich is installed
try:
    import rich

    # ----------------------------------------------------------------------
    def ShowCursorWithRich(
        show: bool,
    ) -> None:
        rich.get_console().show_cursor(show)

    # ----------------------------------------------------------------------

    ShowCursor                              = ShowCursorWithRich

except ImportError:
    # ----------------------------------------------------------------------
    def ShowCursorNoRich(
        show: bool,  # pylint: disable=unused-argument
    ) -> None:
        pass

    # ----------------------------------------------------------------------

    ShowCursor                              = ShowCursorNoRich


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
class DoneManagerException(Exception):
    """Exception whose call stack is not displayed when caught within an active DoneManager"""
    pass  # pylint: disable=unnecessary-pass


# ----------------------------------------------------------------------
class DoneManagerFlags(Flag):
    VerboseFlag                             = auto()
    DebugFlag                               = auto()

    Standard                                = 0
    Verbose                                 = VerboseFlag
    Debug                                   = VerboseFlag | DebugFlag

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        *,
        verbose: bool=False,
        debug: bool=False,
    ) -> "DoneManagerFlags":
        if debug:
            flag = cls.Debug
        elif verbose:
            flag = cls.Verbose
        else:
            flag = cls.Standard

        return flag


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _CommonArgs(object):
    """Arguments common to creating top-level and nested DoneManagers"""

    # ----------------------------------------------------------------------
    heading: Optional[str]
    done_suffix_or_suffixes: Union[None, Callable[[], Optional[str]], List[Callable[[], Optional[str]]]]    = field(default=None)

    prefix: Union[None, str, Callable[[], Optional[str]]]                   = field(kw_only=True, default=None)
    suffix: Union[None, str, Callable[[], Optional[str]]]                   = field(kw_only=True, default=None)

    line_prefix: StreamDecorator.PrefixOrSuffixType     = field(kw_only=True, default="  ")

    display: bool                                       = field(kw_only=True, default=True)     # Display done information
    display_result: bool                                = field(kw_only=True, default=True)     # Display the result
    display_time: bool                                  = field(kw_only=True, default=True)     # Display the time delta

    display_exceptions: bool                            = field(kw_only=True, default=True)     # Display exceptions
    display_exception_details: bool                     = field(kw_only=True, default=True)     # Display exception details
    suppress_exceptions: bool                           = field(kw_only=True, default=False)    # Do not let exceptions propagate

    preserve_status: bool                               = field(kw_only=True, default=True)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.display_exceptions or not self.suppress_exceptions, "It isn't wise to disable exceptions while also suppressing the propagation"

        if not self.display:
            object.__setattr__(self, "line_prefix", None)

        if (
            self.display
            and self.heading
            and not self.heading.isspace()
            and not self.heading.rstrip().endswith("...")
        ):
            # Remove any trailing newlines
            index = 0

            while self.heading[index - 1] == '\n':
                index -= 1

            object.__setattr__(
                self,
                "heading",
                "{}...{}".format(
                    self.heading if index == 0 else self.heading[:index],
                    "" if index == 0 else self.heading[index:],
                ),
            )


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TopLevelArgs(_CommonArgs):
    """Arguments when creating top-level done managers"""

    # ----------------------------------------------------------------------
    output_flags: DoneManagerFlags          = field(kw_only=True, default=DoneManagerFlags.Standard)
    capabilities: Optional[Capabilities]    = field(kw_only=True, default=None)

    num_cols: int                           = field(kw_only=True, default=160)


@dataclass(frozen=True)
class NestedArgs(_CommonArgs):
    pass


# ----------------------------------------------------------------------
@dataclass
class DoneManager(object):
    # ----------------------------------------------------------------------
    result: int                             = field(init=False, default=0)

    _stream: StreamDecorator

    output_flags: DoneManagerFlags          = field(kw_only=True)
    capabilities: Capabilities              = field(kw_only=True)
    heading: Optional[str]                  = field(kw_only=True)
    preserve_status: bool                   = field(kw_only=True)

    num_cols: int                           = field(kw_only=True)

    _status_line_prefix: str                = field(init=False)

    _wrote_content: bool                    = field(init=False, default=False)
    _prev_status_content: List[str]         = field(init=False, default_factory=list)

    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def Create(
        cls,
        stream: Union[StreamDecorator, TextIO, TextWriter],
        *top_level_args,                    # See `TopLevelArgs`
        **top_level_kwargs,                 # See `TopLevelArgs`
    ) -> Iterator["DoneManager"]:
        """Creates a standard DoneManager"""

        args = TopLevelArgs(*top_level_args, **top_level_kwargs)

        with cls._CreateImpl(
            stream,
            args,
            output_flags=args.output_flags,
            capabilities=args.capabilities or Capabilities.Create(stream),
            num_cols=args.num_cols,
        ) as dm:
            try:
                yield dm
            finally:
                ShowCursor(True)

    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def CreateCommandLine(
        cls,
        stream: Union[StreamDecorator, TextIO, TextWriter]=sys.stdout,
        *,
        output_flags: DoneManagerFlags=DoneManagerFlags.Standard,
        capabilities: Optional[Capabilities]=None,
    ) -> Iterator["DoneManager"]:
        """Creates a DoneManager suitable for use with a command-line application"""

        with cls.Create(
            stream,
            "\n",
            line_prefix="",
            prefix="\nResults: ",
            suffix="\n",
            output_flags=output_flags,
            capabilities=capabilities,
        ) as dm:
            is_exceptional = False

            try:
                yield dm
            except:
                is_exceptional = True
                raise

            finally:
                if not is_exceptional:
                    OnExit(dm.result)

    # ----------------------------------------------------------------------
    @property
    def is_verbose(self) -> bool:
        return bool(self.output_flags & DoneManagerFlags.VerboseFlag)

    @property
    def is_debug(self) -> bool:
        return bool(self.output_flags & DoneManagerFlags.DebugFlag)

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._stream.isatty()

    # ----------------------------------------------------------------------
    def ExitOnError(self) -> None:
        """Exists if the result is < 0"""

        if self.result < 0:
            OnExit(self.result)

    # ----------------------------------------------------------------------
    def ExitOnWarning(self) -> None:
        """Exits if the result is > 0"""

        if self.result > 0:
            OnExit(self.result)

    # ----------------------------------------------------------------------
    def WriteLine(
        self,
        content: str,
    ) -> None:
        """Writes a line without decoration; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(lambda value, *, capabilities: value, content)

    # ----------------------------------------------------------------------
    def WriteSuccess(
        self,
        content: str,
    ) -> None:
        """Writes a line decorated with a success prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateSuccessText, content)

    # ----------------------------------------------------------------------
    def WriteError(
        self,
        content: str,
        *,
        update_result: bool=True,
    ) -> None:
        """Writes a line decorated with an error prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateErrorText, content)

        if update_result and self.result >= 0:
            self.result = -1

    # ----------------------------------------------------------------------
    def WriteWarning(
        self,
        content: str,
        *,
        update_result: bool=True,
    ) -> None:
        """Writes a line decorated with a warning prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateWarningText, content)

        if update_result and self.result == 0:
            self.result = 1

    # ----------------------------------------------------------------------
    def WriteInfo(
        self,
        content: str,
    ) -> None:
        """Writes a line decorated with an info prefix; status information is preserved or cleared based on the `preserve_status` flag."""

        self._WriteImpl(TextwrapEx.CreateInfoText, content)

    # ----------------------------------------------------------------------
    def WriteVerbose(
        self,
        content: str,
    ) -> None:
        """\
        Writes verbose content if the verbose flag is set. Use this functionality when you want
        only the first line to include the verbose decorator. Use `YieldVerboseStream` when you
        want every line to include the verbose decorator.

        Status information is preserved or cleared based on the `preserve_status` flag.
        """

        if self.is_verbose:
            self._WriteImpl(TextwrapEx.CreateVerboseText, content)

    # ----------------------------------------------------------------------
    def WriteDebug(
        self,
        content: str,
    ) -> None:
        """\
        Writes debug content if the debug flag is set. Use this functionality when you want
        only the first line to include the debug decorator. Use `YieldDebugStream` when you
        want every line to include the debug decorator.

        Status information is preserved or cleared based on the `preserve_status` flag.
        """

        if self.is_debug:
            self._WriteImpl(TextwrapEx.CreateDebugText, content)

    # ----------------------------------------------------------------------
    def WriteStatus(
        self,
        content: str,
    ) -> None:
        """\
        Writes status information; status information is temporal, and is replaced each time new
        status is added.
        """

        self._WriteStatus(content)

    # ----------------------------------------------------------------------
    def ClearStatus(self) -> None:
        """Clears any status information currently displayed"""

        if self._prev_status_content:
            self._WriteStatus("", update_prev_status=False)
            self._prev_status_content = []

    # ----------------------------------------------------------------------
    def PreserveStatus(self) -> None:
        """Persists any status information currently displayed so that it will not be overwritten"""

        if self._prev_status_content:
            # Move the cursor back to where it would be after writing the status messages normally.
            sys.stdout.write("\033[{}B".format(len(self._prev_status_content)))
            sys.stdout.write("\r")

            self._prev_status_content = []

    # ----------------------------------------------------------------------
    @contextmanager
    def Nested(
        self,
        *nested_args,                       # See `NestedArgs`
        **nested_kwargs,                    # See `NestedArgs`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager"""

        with self.YieldStream() as stream:
            with self._CreateNestedImpl(stream, *nested_args, **nested_kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def VerboseNested(
        self,
        *nested_args,                       # See `NestedArgs`
        **nested_kwargs,                    # See `NestedArgs`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager if the verbose flag is set"""

        with self.YieldVerboseStream() as verbose_stream:
            with self._CreateNestedImpl(verbose_stream, *nested_args, **nested_kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def DebugNested(
        self,
        *nested_args,                       # See `NestedArgs`
        **nested_kwargs,                    # See `NestedArgs`
    ) -> Iterator["DoneManager"]:
        """Creates a nested DoneManager if the debug flag is set"""


        with self.YieldDebugStream() as debug_stream:
            with self._CreateNestedImpl(debug_stream, *nested_args, **nested_kwargs) as dm:
                yield dm

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldStream(self) -> Iterator[StreamDecorator]:
        """Provides scoped access to the underlying stream; writing to this stream will include line prefixes"""

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        yield self._stream
        self._stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldVerboseStream(self) -> Iterator[StreamDecorator]:
        """\
        Provides scoped access to a verbose-version of the underlying stream; writing to this
        stream will include verbose line prefixes. Use this functionality when you want all
        lines to have the verbose prefix decorator. Use `WriteVerbose` when you only want the
        first line to include the decorator.
        """

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        if self.is_verbose:
            stream = StreamDecorator(
                self._stream,
                line_prefix=TextwrapEx.CreateVerbosePrefix(self.capabilities),
                decorate_empty_lines=True,
            )
        else:
            stream = StreamDecorator(None)

        yield stream
        stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldDebugStream(self) -> Iterator[StreamDecorator]:
        """\
        Provides scoped access to a debug-version of the underlying stream; writing to this
        stream will include debug line prefixes. Use this functionality when you want all
        lines to have the debug prefix decorator. Use `WriteDebug` when you only want the
        first line to include the decorator.
        """

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        if self.is_debug:
            stream = StreamDecorator(
                self._stream,
                line_prefix=TextwrapEx.CreateDebugPrefix(self.capabilities),
                decorate_empty_lines=True,
            )
        else:
            stream = StreamDecorator(None)

        yield stream
        stream.flush()

    # ----------------------------------------------------------------------
    @contextmanager
    def YieldStdout(self) -> Iterator[StreamDecorator.YieldStdoutContext]:
        """Provides scoped access to `sys.stdout` (if possible); writing to this stream will NOT include line prefixes"""

        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()

        is_stdout = False
        persist_content = False

        try:
            with self._stream.YieldStdout() as context:
                try:
                    yield context
                finally:
                    is_stdout = context.stream is sys.stdout
                    persist_content = context.persist_content

        finally:
            if is_stdout:
                if persist_content:
                    # Persisting status can get the done managers off track when it comes to line
                    # prefixes. Add a newline to get things aligned again.
                    self.WriteLine("\n")

                elif self.heading:
                    sys.stdout.write(self.heading)
                    sys.stdout.flush()

    # ----------------------------------------------------------------------
    def __post_init__(self):
        self._line_prefix = self._stream.GetCompleteLinePrefix(include_self=False)
        self._status_line_prefix = self._line_prefix + self._stream.GetLinePrefix(len(self._line_prefix))

        assert self.num_cols > 0, self.num_cols
        self.num_cols -= len(self._status_line_prefix)
        assert self.num_cols > 0, self.num_cols

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def _CreateImpl(
        cls,
        stream: Union[StreamDecorator, TextIO, TextWriter],
        args: _CommonArgs,
        *,
        output_flags: DoneManagerFlags,
        capabilities: Capabilities,
        num_cols: int,
    ) -> Iterator["DoneManager"]:
        if args.heading:
            stream.write(args.heading)
            stream.flush()

        instance = cls(
            StreamDecorator(
                stream,
                prefix="\n" if args.heading else "",
                line_prefix=args.line_prefix,
                decorate_empty_lines=False,
            ),
            heading=args.heading,
            preserve_status=args.preserve_status,
            output_flags=output_flags,
            capabilities=capabilities,
            num_cols=num_cols,
        )

        if instance.capabilities.supports_colors:
            error_color_on = TextwrapEx.ERROR_COLOR_ON
            success_color_on = TextwrapEx.SUCCESS_COLOR_ON
            warning_color_on = TextwrapEx.WARNING_COLOR_ON
            color_off = TextwrapEx.COLOR_OFF
        else:
            error_color_on = ""
            success_color_on = ""
            warning_color_on = ""
            color_off = ""

        time_delta: Optional[str] = None

        done_suffixes: List[Callable[[], Optional[str]]] = []

        if args.display_result:
            if instance.capabilities.supports_colors:
                # ----------------------------------------------------------------------
                def DisplayResult() -> str:
                    if instance.result < 0:
                        color_on = error_color_on
                    elif instance.result > 0:
                        color_on = warning_color_on
                    else:
                        color_on = success_color_on

                    return "{}{}{}".format(color_on, instance.result, color_off)

                # ----------------------------------------------------------------------

                display_func = DisplayResult
            else:
                display_func = lambda: str(instance.result)

            done_suffixes.append(display_func)

        if args.display_time:
            done_suffixes.append(lambda: str(time_delta))

        if args.done_suffix_or_suffixes is None:
            pass # Nothing to do here
        elif isinstance(args.done_suffix_or_suffixes, list):
            done_suffixes += args.done_suffix_or_suffixes
        else:
            done_suffixes.append(args.done_suffix_or_suffixes)

        start_time = time.perf_counter()

        # ----------------------------------------------------------------------
        def OnExitFunc():
            instance._OnExit()  # pylint: disable=protected-access

            # Get the prefix
            if args.prefix is None:
                prefix_value = None
            elif isinstance(args.prefix, str):
                prefix_value = args.prefix
            elif callable(args.prefix):
                prefix_value = args.prefix()
            else:
                assert False, args.prefix  # pragma: no cover

            if prefix_value:
                stream.write(prefix_value)

            # Display the content
            if args.display:
                suffixes: List[str] = []

                for done_suffix in done_suffixes:
                    result = done_suffix()
                    if result is not None:
                        suffixes.append(result)

                if suffixes:
                    content = "DONE! ({})\n".format(", ".join(suffixes))
                else:
                    content = "DONE!\n"

                stream.write(content)

            # Get the suffix
            if args.suffix is None:
                suffix_value = None
            elif isinstance(args.suffix, str):
                suffix_value = args.suffix
            elif callable(args.suffix):
                suffix_value = args.suffix()
            else:
                assert False, args.suffix  # pragma: no cover

            if suffix_value:
                stream.write(suffix_value)

        # ----------------------------------------------------------------------

        with ExitStack(OnExitFunc):
            try:
                yield instance

            except Exception as ex:
                if ShouldRaiseException(ex):
                    raise

                if instance.result >= 0:
                    instance.result = -1

                if args.display_exceptions:
                    # Do not display exceptions if they have already been displayed
                    if not getattr(ex, "_displayed_exception___", False):
                        object.__setattr__(ex, "_displayed_exception___", True)

                        if args.display_exception_details and not isinstance(ex, DoneManagerException):
                            exception_content = traceback.format_exc()
                        else:
                            exception_content = str(ex)

                        if instance._stream.HasPendingContent() != 0:
                            instance._stream.write("\n")

                        instance._stream.write(
                            TextwrapEx.CreateErrorText(exception_content, capabilities=instance.capabilities),
                        )

                        instance._stream.write("\n")

                if not args.suppress_exceptions:
                    raise

            finally:
                current_time = time.perf_counter()

                assert start_time <= current_time, (start_time, current_time)

                time_delta = str(datetime.timedelta(seconds=current_time - start_time))

    # ----------------------------------------------------------------------
    @contextmanager
    def _CreateNestedImpl(
        self,
        stream: StreamDecorator,
        *nested_args,
        **nested_kwargs,
    ) -> Iterator["DoneManager"]:
        if "preserve_status" not in nested_kwargs:
            nested_kwargs["preserve_status"] = False

        with self.__class__._CreateImpl(  # pylint: disable=protected-access
            stream,
            NestedArgs(*nested_args, **nested_kwargs),
            output_flags=self.output_flags,
            capabilities=self.capabilities,
            num_cols=self.num_cols,
        ) as dm:
            try:
                yield dm
            finally:
                if dm.result < 0:
                    if self.result >= 0:
                        self.result = dm.result
                if dm.result > 0:
                    if self.result == 0:
                        self.result = dm.result

    # ----------------------------------------------------------------------
    def _WriteImpl(
        self,
        create_text_func: Any, # Not sure how to create the type hint for this: Callable[[str, *, capabilities: Capabilities], str],
        content: str,
    ) -> None:
        if self._prev_status_content:
            self._WriteStatus("", update_prev_status=False)

        content = create_text_func(content, capabilities=self.capabilities)
        if not content.endswith("\n"):
            content += "\n"

        self._stream.write(content)
        self._wrote_content = True

        if self._prev_status_content:
            self._WriteStatus(self._prev_status_content, update_prev_status=False)

    # ----------------------------------------------------------------------
    def _WriteStatus(
        self,
        content: Union[str, List[str]],
        *,
        update_prev_status: bool=True,
    ) -> None:
        if not content and (not self._prev_status_content or not self._stream.isatty()):
            return

        if not self._stream.isatty() and isinstance(content, str) and not content.endswith("\n"):
            content += "\n"

        if not self._stream.isatty():
            self._stream.write(
                TextwrapEx.Indent(
                    "STATUS: {}".format(content),
                    len("STATUS: "),
                    skip_first_line=True,
                ),
            )

            return

        ShowCursor(not bool(content))

        # Prepare the content
        blank_lines: List[str] = []

        if isinstance(content, list):
            lines = content
            assert not update_prev_status
        else:
            lines: List[str] = []

            for line in content.split("\n"):
                line = "{}{}".format(self._status_line_prefix, line)

                # Trim if necessary
                overflow_chars = len(line) - self.num_cols
                if overflow_chars > 0:
                    remove_index = len(line) // 2 - overflow_chars // 2

                    line = "{}...{}".format(line[:remove_index], line[remove_index + overflow_chars + 3:])

                lines.append("\r{}\n".format(line.ljust(self.num_cols)))

            if self._stream.isatty() and len(self._prev_status_content) > len(lines):
                blank_lines += ["\r{}\n".format("".ljust(self.num_cols)), ] * (len(self._prev_status_content) - len(lines))

        # Write the content
        if not self._wrote_content:
            # If we haven't written anything yet, we need to write something to get
            # the contained stream's prefix to fire (if any).
            self._stream.write("")
            self._wrote_content = True

        for line in itertools.chain(lines, blank_lines):
            sys.stdout.write(line)

        if self._stream.isatty():
            # Move the cursor up to the position that it would be in if we were writing
            # a standard message
            sys.stdout.write("\033[{}A\r".format(len(lines) + len(blank_lines)))

        if update_prev_status:
            self._prev_status_content = lines

    # ----------------------------------------------------------------------
    def _OnExit(self) -> None:
        if self.preserve_status:
            self.PreserveStatus()
        else:
            self.ClearStatus()
