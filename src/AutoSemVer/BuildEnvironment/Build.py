# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-29 12:57:29
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds AutoSemVer"""

import re

from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

from Common_Foundation import PathEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx

try:
    from Common_PythonDevelopment.BuildPythonExecutable import Build, BuildSteps, Clean

    _working_dir = PathEx.EnsureDir(Path(__file__).parent / "..")
    PathEx.EnsureFile(_working_dir / "setup.py")

    _clean_func = Clean

    _build_func = lambda *args, **kwargs: Build(
        *args,
        **{
            **kwargs,
            **{
                "working_dir": _working_dir,
            },
        },
    )

except ModuleNotFoundError:
    # ----------------------------------------------------------------------
    def CleanImpl(*args, **kwargs):  # pylint: disable=unused-argument
        return 0

    # ----------------------------------------------------------------------
    def BuildImpl(*args, **kwargs):  # pylint: disable=unused-argument
        return 0

    # ----------------------------------------------------------------------

    _clean_func = CleanImpl
    _build_func = BuildImpl

    BuildSteps = []


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="AutoSemVer",
            requires_output_dir=True,
            disable_if_dependency_environment=True,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return _clean_func(
            output_dir,
            output_stream,
            is_verbose=is_verbose,
            is_debug=is_debug,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomBuildArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return argument descriptions for any custom args that can be passed to the Build func on the command line"""

        # No custom args by default
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def GetNumBuildSteps(
        self,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        return len(BuildSteps)

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
        force: bool=False,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return _build_func(
            output_dir,
            output_stream,
            on_progress_update,
            is_verbose=is_verbose,
            is_debug=is_debug,
            force=force,
        )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
