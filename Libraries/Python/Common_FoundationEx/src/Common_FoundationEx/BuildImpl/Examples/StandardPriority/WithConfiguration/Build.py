# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-29 08:45:14
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

import sys
import textwrap
import time

from pathlib import Path
from typing import Callable, Dict, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation import Types
from Common_FoundationEx.BuildImpl import BuildInfoBase, Mode


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="Build with Configuration",
            configurations=["Debug", "Release"],
            configuration_is_required_on_clean=True,
            requires_output_dir=True,
        )

        self._steps: Dict[Mode, Dict[str, int]] = {
            Mode.Clean: {
                "Debug": 2,
                "Release": 3,
            },
            Mode.Build: {
                "Debug": 4,
                "Release": 6,
            },
        }

    # ----------------------------------------------------------------------
    def GetNumCleanSteps(
        self,
        configuration: Optional[str],
    ) -> int:
        assert configuration is not None
        return self._steps[Mode.Clean][configuration]

    # ----------------------------------------------------------------------
    def GetNumBuildSteps(
        self,
        configuration: Optional[str],
    ) -> int:
        assert configuration is not None
        return self._steps[Mode.Build][configuration]

    # ----------------------------------------------------------------------
    def Clean(
        self,
        configuration: Optional[str],
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        assert configuration is not None
        return self._Impl(output_stream, on_progress_update, self._steps[Mode.Clean][configuration])

    # ----------------------------------------------------------------------
    def Build(
        self,
        configuration: Optional[str],
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        assert configuration is not None
        return self._Impl(output_stream, on_progress_update, self._steps[Mode.Build][configuration])

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _Impl(
        output_stream: TextIO,
        on_progress_update: Callable[[int, str], bool],
        num_steps,
    ) -> Tuple[int, str]:
        for step in range(num_steps):
            output_stream.write("Executing Step #{}...\n".format(step + 1))

            if not on_progress_update(step, "Step #{}".format(step + 1)):
                break

            time.sleep(0.25)

        return 0, "{} steps".format(num_steps)


# ----------------------------------------------------------------------
def CustomFunc1(
    verbose: bool=False,
) -> None:
    "This is custom func #1"

    sys.stdout.write(
        textwrap.dedent(
            """\
            CustomFunc1
            -----------
            Verbose:    {}
            """,
        ).format(verbose),
    )


# ----------------------------------------------------------------------
def CustomFunc2(
    output: Path=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True),
    verbose: bool=typer.Option(False, help="A custom func with custom arguments"),
) -> None:
    sys.stdout.write(
        textwrap.dedent(
            """\
            CustomFunc2
            -----------
            Output:     {}
            Verbose:    {}
            """,
        ).format(output, verbose),
    )


# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
