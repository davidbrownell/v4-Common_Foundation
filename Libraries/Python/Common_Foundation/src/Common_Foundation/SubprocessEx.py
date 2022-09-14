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

import ctypes
import subprocess
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, TextIO


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

    return RunResult(
        _PostprocessReturnCode(result.returncode),
        result.stdout.decode("utf-8").replace("\r", ""),
    )


# ----------------------------------------------------------------------
def Stream(
    command_line: str,
    stream: TextIO=sys.stdout,
    cwd: Optional[Path]=None,
    env: Optional[Dict[str, str]]=None,
) -> int:
    result = subprocess.run(
        command_line,
        shell=True,
        stdout=stream,
        stderr=subprocess.STDOUT,
        cwd=cwd,
        env=env,
    )

    return _PostprocessReturnCode(result.returncode)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _PostprocessReturnCode(
    value: int,
) -> int:
    # Ensure that the value is signed
    if value <= 255:
        return ctypes.c_byte(value).value

    return ctypes.c_long(value).value
