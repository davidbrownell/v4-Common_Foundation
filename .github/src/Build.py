# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-07 08:53:49
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds github content"""

import os

from pathlib import Path
from typing import Callable, List, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation import PathEx
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="GitHub",
            requires_output_dir=False,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(
        self,
        configuration: Optional[str],
        output_dir: Optional[Path],
        output_stream: TextIO,
        on_progress_update: Callable[
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
        files_to_delete: List[Path] = []

        root_dir = Path(__file__).parent.parent

        for directory in [
            root_dir / "actions",
            root_dir / "workflows",
        ]:
            for root, _, filenames in os.walk(directory):
                root = Path(root)

                for filename in filenames:
                    if filename == "README.md":
                        continue

                    files_to_delete.append(root / filename)

        if not files_to_delete:
            output_stream.write("No files found to delete.\n")
            return 0

        for filename in files_to_delete:
            filename.unlink()

        return 0

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomBuildArgs(self) -> TyperEx.TypeDefinitionsType:
        return {
            "list_variables": (bool, typer.Option(False, "--list-variables", help="Lists all variables in the Jinja2 templates.")),
            "force": (bool, typer.Option(False, "--force", help="Force the generation of content, even when no changes are detected.")),
        }

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Optional[Path],         # pylint: disable=unused-argument
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        list_variables: bool,
        force: bool,
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        root_dir = Path(__file__).parent.parent

        command_line = 'Jinja2CodeGenerator Generate "{input_dir}" "{output_dir}" --variable-start "<<<" --variable-end ">>>" --block-start "<<%" --block-end "%>>" --comment-start "<<#" --comment-end "#>>" --single-task --code-gen-header-line-prefix "#" {debug}{verbose}{list_variables}{force}'.format(
            input_dir=PathEx.EnsureDir(root_dir / "src"),
            output_dir=root_dir,
            debug=" --debug" if is_debug else "",
            verbose=" --verbose" if is_verbose else "",
            list_variables=" --debug-only" if list_variables else "",
            force=" --force" if force else "",
        )

        if is_verbose:
            output_stream.write("Command Line: {}\n\n".format(command_line))

        result = SubprocessEx.Run(
            command_line,
            cwd=root_dir / "src",
        )

        output_stream.write(result.output)

        return result.returncode


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
