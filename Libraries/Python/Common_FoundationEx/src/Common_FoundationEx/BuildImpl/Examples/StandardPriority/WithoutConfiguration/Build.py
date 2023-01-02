# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-29 08:45:14
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

from Common_FoundationEx.BuildImpl import BuildInfoBase


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="Build without Configuration",
            requires_output_dir=True,
        )

    # ----------------------------------------------------------------------
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,                   # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,                   # pylint: disable=unused-argument
        is_debug: bool,                     # pylint: disable=unused-argument
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return 0

    # ----------------------------------------------------------------------
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,                   # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,                   # pylint: disable=unused-argument
        is_debug: bool,                     # pylint: disable=unused-argument
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return 0


# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
