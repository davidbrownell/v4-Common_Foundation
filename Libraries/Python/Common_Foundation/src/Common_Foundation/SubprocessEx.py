# ----------------------------------------------------------------------
# |
# |  SubprocessEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 17:39:23
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements for the subprocess library"""

import os
import copy
import ctypes
import subprocess


from dataclasses import dataclass
from pathlib import Path
from typing import Callable, cast, Dict, IO, List, Optional, TextIO, Union

from .ContextlibEx import ExitStack
from .Streams.TextWriter import TextWriter


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass
class RunResult(object):
    # ----------------------------------------------------------------------
    returncode: int
    output: str

    # ----------------------------------------------------------------------
    def RaiseOnError(self) -> None:
        if self.returncode != 0:
            raise Exception(self.output)


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Run(
    command_line: str,
    cwd: Optional[Path]=None,
    env: Optional[Dict[str, str]]=None,
) -> RunResult:
    result = subprocess.run(
        command_line,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )

    content = result.stdout.decode("utf-8")

    # Importing here to avoid circular imports
    from .Shell.All import CurrentShell

    if CurrentShell.family_name == "Windows":
        content = content.replace("\r\n", "\n")

    return RunResult(_PostprocessReturnCode(result.returncode), content)


# ----------------------------------------------------------------------
def Stream(
    command_line: str,
    stream: Union[TextWriter, TextIO],
    cwd: Optional[Path]=None,
    env: Optional[Dict[str, str]]=None,
    *,
    stdin: Optional[str]=None,
    convert_newlines: Optional[bool]=None,              # Convert '\r\n' to '\n'
    line_delimited_output: bool=False,                  # Buffer lines
) -> int:
    if env is None:
        env = copy.deepcopy(os.environ)     # type: ignore
        env["PYTHONUNBUFFERED"] = "1"       # type: ignore

    if convert_newlines is None:
        # Importing here to avoid circular imports
        from .Shell.All import CurrentShell

        convert_newlines = CurrentShell.family_name == "Windows"

    output_func = cast(Callable[[str], None], stream.write)
    flush_func = stream.flush

    if convert_newlines:
        newline_original_output_func = output_func

        # ----------------------------------------------------------------------
        def NewlineOutput(
            content: str,
        ) -> None:
            newline_original_output_func(content.replace("\r\n", "\n"))

        # ----------------------------------------------------------------------

        output_func = NewlineOutput

    if line_delimited_output:
        line_delimited_original_output_func = output_func
        line_delimited_original_flush_func = flush_func

        cached_content: List[str] = []

        # ----------------------------------------------------------------------
        def LineDelimitedOutput(
            content: str,
        ) -> None:
            if content.endswith("\n"):
                content = "{}{}".format("".join(cached_content), content)
                cached_content[:] = []

                line_delimited_original_output_func(content)
            else:
                cached_content.append(content)

        # ----------------------------------------------------------------------
        def LineDelimitedFlush() -> None:
            if cached_content:
                content = "".join(cached_content)
                cached_content[:] = []
            else:
                content = ""

            if not content.endswith("\n"):
                content += "\n"

            line_delimited_original_output_func(content)
            line_delimited_original_flush_func()

        # ----------------------------------------------------------------------

        output_func = LineDelimitedOutput
        flush_func = LineDelimitedFlush

    with subprocess.Popen(
        command_line,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.PIPE,
        cwd=cwd,
        env=env,
    ) as result:
        try:
            with ExitStack(flush_func):
                if stdin is not None:
                    assert result.stdin is not None

                    result.stdin.write(stdin.encode("utf-8"))
                    result.stdin.flush()
                    result.stdin.close()

                assert result.stdout is not None
                _ReadStateMachine.Execute(result.stdout, output_func)

                result = result.wait() or 0

        except IOError:
            result = -1

        return _PostprocessReturnCode(result)


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
class _ReadStateMachine(object):
    # ----------------------------------------------------------------------
    @classmethod
    def Execute(
        cls,
        input_stream: IO[bytes],
        output_func: Callable[[str], None],
    ) -> None:
        machine = cls(input_stream)

        while True:
            if machine._buffered_input is not None:
                result = machine._buffered_input
                machine._buffered_input = None
            else:
                result = machine._input_stream.read(1)
                if not result:
                    break

                if isinstance(result, (str, bytes)):
                    result = ord(result)

            result = machine._process_func(result)
            if result is None:
                continue

            output_func(machine._ToString(result))

        if machine._buffered_output:
            output_func(machine._ToString(machine._buffered_output))

    # ----------------------------------------------------------------------
    def __init__(
        self,
        input_stream: IO[bytes],
    ):
        self._input_stream                  = input_stream

        self._process_func: Callable[[int], Optional[List[int]]]            = self._ProcessStandard

        self._buffered_input: Optional[int]             = None
        self._buffered_output: List[int]                = []

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _a                                      = ord("a")
    _z                                      = ord("z")
    _A                                      = ord("A")
    _Z                                      = ord("Z")

    @classmethod
    def _IsAsciiLetter(
        cls,
        value: int,
    ) -> bool:
        return (
            (value >= cls._a and value <= cls._z)
            or (value >= cls._A and value <= cls._Z)
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def _IsNewlineish(
        value: int,
    ) -> bool:
        return value in [
            10, # '\r'
            13, # '\n'
        ]

    # ----------------------------------------------------------------------
    @staticmethod
    def _IsEscape(
        value: int,
    ) -> bool:
        return value == 27

    # ----------------------------------------------------------------------
    @staticmethod
    def _ToString(
        value: List[int],
    ) -> str:
        if len(value) == 1:
            return chr(value[0])

        result = bytearray(value)

        for codec in ["utf-8", "utf-16", "utf-32"]:
            try:
                return result.decode(codec)
            except (UnicodeDecodeError, LookupError):
                pass

        raise Exception("The content '{}' could not be decoded.".format(result))

    # ----------------------------------------------------------------------
    def _ProcessStandard(
        self,
        value: int,
    ) -> Optional[List[int]]:
        assert not self._buffered_output

        if self.__class__._IsEscape(value):  # pylint: disable=protected-access
            self._process_func = self._ProcessEscape
            self._buffered_output.append(value)

            return None

        if self.__class__._IsNewlineish(value):  # pylint: disable=protected-access
            self._process_func = self._ProcessLineReset
            self._buffered_output.append(value)

            return None

        if value >> 6 == 0b11:
            # This is the first char of a multi-byte char
            self._process_func = self._ProcessMultiByte
            self._buffered_output.append(value)

            return None

        return [value]

    # ----------------------------------------------------------------------
    def _ProcessEscape(
        self,
        value: int,
    ) -> Optional[List[int]]:
        assert self._buffered_output
        self._buffered_output.append(value)

        if not self.__class__._IsAsciiLetter(value):  # pylint: disable=protected-access
            return None

        self._process_func = self._ProcessStandard

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _ProcessLineReset(
        self,
        value: int,
    ) -> Optional[List[int]]:
        assert self._buffered_output

        if self.__class__._IsNewlineish(value):  # pylint: disable=protected-access
            self._buffered_output.append(value)
            return None

        self._process_func = self._ProcessStandard

        assert self._buffered_input is None
        self._buffered_input = value

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _ProcessMultiByte(
        self,
        value: int,
    ) -> Optional[List[int]]:
        assert self._buffered_output

        if value >> 6 == 0b10:
            # Continuation char
            self._buffered_output.append(value)
            return None

        self._process_func = self._ProcessStandard

        assert self._buffered_input is None
        self._buffered_input = value

        return self._FlushBufferedOutput()

    # ----------------------------------------------------------------------
    def _FlushBufferedOutput(self) -> Optional[List[int]]:
        assert self._buffered_output

        content = self._buffered_output
        self._buffered_output = []

        return content


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _PostprocessReturnCode(
    value: int,
) -> int:
    # Ensure that the value is signed
    if value <= 255:
        return ctypes.c_byte(value).value

    return ctypes.c_long(value).value
