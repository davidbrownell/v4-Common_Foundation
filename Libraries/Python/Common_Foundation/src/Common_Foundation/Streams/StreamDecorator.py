# ----------------------------------------------------------------------
# |
# |  StreamDecorator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-13 21:37:15
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the StreamDecorator object"""

import sys

from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import auto, Enum
from typing import Callable, Generator, Iterator, List, Optional, TextIO, Union

from .TextWriter import TextWriter


# ----------------------------------------------------------------------
class StreamDecorator(TextWriter):
    """Stream-like object that supports the decoration of prefixes and suffixes to text lines"""

    # ----------------------------------------------------------------------
    # |
    # |  Public Types
    # |
    # ----------------------------------------------------------------------
    PrefixOrSuffixType                      = Union[
        None,
        str,
        Callable[
            [
                int                         # column_offset
            ],
            str,
        ],
    ]

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(
        self,
        stream_or_streams: Union[None, TextIO, TextWriter, List[Union[TextIO, TextWriter]]],
        line_prefix: "StreamDecorator.PrefixOrSuffixType"=None,
        line_suffix: "StreamDecorator.PrefixOrSuffixType"=None,
        prefix: "StreamDecorator.PrefixOrSuffixType"=None,
        suffix: "StreamDecorator.PrefixOrSuffixType"=None,
        *,
        decorate_empty_lines: bool=True,
    ):
        if stream_or_streams is None:
            streams = []
        elif isinstance(stream_or_streams, list):
            streams = stream_or_streams
        else:
            streams = [stream_or_streams, ]

        # ----------------------------------------------------------------------
        def PrefixOrSuffixTypeToCallable(
            value: StreamDecorator.PrefixOrSuffixType,
        ) -> Callable[[int], str]:
            if value is None:
                return lambda _: ""

            if isinstance(value, str):
                return lambda _: value

            if callable(value):
                return value

            assert False, value  # pragma: no cover

        # ----------------------------------------------------------------------

        self._streams                       = streams
        self._line_prefix                   = PrefixOrSuffixTypeToCallable(line_prefix)
        self._line_suffix                   = PrefixOrSuffixTypeToCallable(line_suffix)
        self._prefix                        = PrefixOrSuffixTypeToCallable(prefix)
        self._suffix                        = PrefixOrSuffixTypeToCallable(suffix)
        self._decorate_empty_lines          = decorate_empty_lines

        self._state: StreamDecorator._State = StreamDecorator._State.Prefix

        self._content: List[str]            = []
        self._col_offset                    = 0

        self.has_stdout                     = any(
            stream is sys.stdout or (isinstance(stream, StreamDecorator) and stream.has_stdout)
            for stream in streams
        )

        self._isatty                        = any(getattr(stream, "isatty", lambda: False)() for stream in self._streams)

    # ----------------------------------------------------------------------
    @property
    def col_offset(self) -> int:
        return self._col_offset

    @property
    def has_streams(self) -> bool:
        return bool(self._streams)

    # ----------------------------------------------------------------------
    def EnumStreams(self) -> Generator[Union[TextIO, TextWriter], None, None]:
        yield from self._streams

    # ----------------------------------------------------------------------
    def GetLinePrefix(
        self,
        column: int,
    ) -> str:
        return self._line_prefix(column)

    # ----------------------------------------------------------------------
    def GetCompleteLinePrefix(
        self,
        *,
        include_self: bool=True,
    ) -> str:
        prefixes = []

        self._GetLinePrefixInfo(prefixes, 0, include_self=include_self)

        return "".join(prefixes)

    # ----------------------------------------------------------------------
    def HasPendingContent(self) -> bool:
        return bool(self._content)

    # ----------------------------------------------------------------------
    def isatty(self) -> bool:
        return self._isatty

    # ----------------------------------------------------------------------
    def fileno(self) -> int:
        return next((stream.fileno() for stream in self._streams if hasattr(stream, "fileno")), 0)  #  type: ignore

    # ----------------------------------------------------------------------
    def write(
        self,
        content: str,
    ) -> int:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        chars_written = 0

        if self._state == StreamDecorator._State.Prefix:
            chars_written += self._write_content(self._prefix(self._col_offset))
            self._state = StreamDecorator._State.Writing

        chars_written += self._write_content(content)

        return chars_written

    # ----------------------------------------------------------------------
    def flush(
        self,
    ) -> None:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        self._write_content("", force=True)

        for stream in self._streams:
            stream.flush()

    # ----------------------------------------------------------------------
    def close(self) -> None:
        if self._state == StreamDecorator._State.Closed:
            raise Exception("Instance is closed.")

        self.flush()

        self._state = StreamDecorator._State.Suffix
        self._write_content(self._suffix(self._col_offset))

        for stream in self._streams:
            stream.close()

        self._state = StreamDecorator._State.Closed

    # ----------------------------------------------------------------------
    @dataclass
    class YieldStdoutContext(object):
        stream: Union["StreamDecorator", TextIO]
        line_prefix: str
        persist_content: bool                           = field(kw_only=True)

    @contextmanager
    def YieldStdout(self) -> Iterator[YieldStdoutContext]:
        """Provides access to a stdout in a way that doesn't impact the indentation level maintained by a hierarchy of StreamDecorators"""

        line_prefix = self.GetCompleteLinePrefix()

        if not self.isatty():
            try:
                self.write("\n")
                yield StreamDecorator.YieldStdoutContext(self, line_prefix, persist_content=False)

            finally:
                self.write("\n")

            return

        assert self.has_stdout, "This functionality can only be used with streams that ultimately write to `sys.stdout`"

        context = StreamDecorator.YieldStdoutContext(sys.stdout, line_prefix, persist_content=False)

        try:
            sys.stdout.write("\n")
            yield context

        finally:
            if not context.persist_content:
                # Move the cursor back up to the original line
                sys.stdout.write("\033[1A\r")
                sys.stdout.write(self.GetCompleteLinePrefix(include_self=False))

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _GetLinePrefixInfo(
        self,
        prefixes: List[str],
        column: int,
        *,
        include_self: bool,
    ) -> int:
        if not self._streams:
            return column

        if isinstance(self._streams[0], StreamDecorator):
            column = self._streams[0]._GetLinePrefixInfo(prefixes, column, include_self=True)  # pylint: disable=protected-access

        if include_self:
            prefix = self.GetLinePrefix(column)
            if prefix:
                prefixes.append(prefix)
                column += len(prefix)

        return column

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _State(Enum):
        Prefix                              = auto()
        Writing                             = auto()
        Suffix                              = auto()
        Closed                              = auto()

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _write_content(
        self,
        content: str,
        *,
        force: bool=False,
    ) -> int:
        chars_written = 0

        len_content = len(content)
        index = 0

        # Process the content line-by-line
        first_iteration = True

        while True:
            if index == len_content and not first_iteration:
                break

            if index < len_content and content[index] == "\n":
                is_newline = True
                index += 1

            else:
                is_newline = False

                # Get everything before any newlines
                starting_index = index

                while index < len_content and content[index] != "\n":
                    index += 1

                if index == starting_index:
                    if not force or not first_iteration:
                        break
                else:
                    if starting_index == 0 and index == len_content:
                        this_content = content
                    else:
                        this_content = content[starting_index:index]

                    # Cache this partial content
                    self._content.append(this_content)
                    continue

            first_iteration = False

            this_content: Optional[str] = None

            if self._content:
                this_content = "".join(self._content)
                self._content = []

            if not this_content or this_content.isspace():
                if not is_newline:
                    # Keep the whitespace around, as it might be the start of a line that
                    # eventually has content.
                    if this_content is not None:
                        self._content.append(this_content)

                    break

                # We done care about the whitespace unless we decorate empty lines
                if not self._decorate_empty_lines:
                    this_content = None

            # Write the line prefix if we are at the start of the line and there is non-whitespace
            # content to be written.
            if (
                self._state == StreamDecorator._State.Writing
                and self._col_offset == 0
                and (self._decorate_empty_lines or this_content is not None)
            ):
                chars_written += self._write_raw(self._line_prefix(self._col_offset))

            # Write the content
            if this_content is not None:
                chars_written += self._write_raw(this_content)

            # Write the line suffix
            if (
                self._state == StreamDecorator._State.Writing
                and is_newline
                and (self._decorate_empty_lines or self._col_offset != 0)
            ):
                chars_written += self._write_raw(self._line_suffix(self._col_offset))

            # Write the newline
            if is_newline:
                chars_written += self._write_raw("\n")

        return chars_written

    # ----------------------------------------------------------------------
    def _write_raw(
        self,
        content: str,
    ) -> int:
        if not content:
            return 0

        for stream in self._streams:
            try:
                stream.write(content)
            except UnicodeEncodeError as ex:
                wrote_content = False

                for decode_error_method in [
                    "surrogateescape",
                    "replace",
                    "backslashreplace",
                    "ignore",
                ]:
                    try:
                        content = content.encode("utf-8").decode("ascii", decode_error_method)
                        stream.write(content)

                        wrote_content = True
                        break
                    except UnicodeEncodeError:
                        pass

                if not wrote_content:
                    raise ex

        len_content = len(content)

        if content.endswith("\n"):
            self._col_offset = 0
        else:
            self._col_offset += len_content

        return len_content
