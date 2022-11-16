# ----------------------------------------------------------------------
# |
# |  BuildImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-09 09:12:05
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

import importlib
import os
import sys
import textwrap

from pathlib import Path
from typing import Callable, List, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.EnumSource import EnumSource
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
def CreateBuildInfoInstance(
    src_dir: Path,
) -> BuildInfoBase:
    assert src_dir.is_dir(), src_dir

    # ----------------------------------------------------------------------
    class BuildInfo(BuildInfoBase):
        def __init__(self):
            super(BuildInfo, self).__init__(
                name="GitHub",
                requires_output_dir=False,
            )

            self._input_filenames: List[Path]                                   = []

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

            root_dir = src_dir.parent

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
        def GetNumBuildSteps(
            self,
            configuration: Optional[str],
        ) -> int:
            # Get Jinja2CodeGenerator
            result = SubprocessEx.Run(
                "DevEnvScripts{} location Jinja2CodeGenerator".format(
                    CurrentShell.script_extensions[0],
                ),
            )

            assert result.returncode == 0, result
            code_generator_filename = PathEx.EnsureFile(Path(result.output.strip()))

            sys.path.insert(0, str(code_generator_filename.parent))
            with ExitStack(lambda: sys.path.pop(0)):
                code_generator_mod = importlib.import_module(code_generator_filename.stem, None)
                assert code_generator_mod

                code_generator = getattr(code_generator_mod, "CodeGenerator", None)
                assert code_generator is not None

                code_generator = code_generator()

            # Get the input filenames
            assert not self._input_filenames

            input_filenames: List[Path] = []

            for root, _, filenames in EnumSource(src_dir):
                for filename in filenames:
                    fullpath = root / filename

                    if code_generator.IsSupported(fullpath):
                        input_filenames.append(fullpath)

            # Commit
            self._input_filenames = input_filenames

            return max(1, len(self._input_filenames))

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
            if not self._input_filenames:
                return 0, "No input files found"

            with DoneManager.Create(
                output_stream,
                "",
                display_result=False,
                output_flags=DoneManagerFlags.Create(verbose=is_verbose, debug=is_debug),
            ) as dm:
                # We are invoking the code generator from the command line rather than using the code
                # generator instance calculated in `GetNumBuildSteps` to encapsulate the surprisingly
                # subtle logic associated with how a `CodeGenerator` coverts metadata to context.
                command_line_flags: List[str] = [
                    "--variable-start", '"<<<"',
                    "--variable-end", '">>>"',
                    "--block-start", '"<<%"',
                    "--block-end", '"%>>"',
                    "--comment-start", '"<<#"',
                    "--comment-end", '"#>>"',
                    "--code-gen-header-line-prefix", "#",
                    "--code-gen-header-input-filename", "{relative_input_filename}",
                    "--output-data-filename-prefix", "{output_data_prefix}",
                    "--single-task",
                ]

                if is_debug:
                    command_line_flags.append("--debug")
                if is_verbose:
                    command_line_flags.append("--verbose")
                if list_variables:
                    command_line_flags.append("--list-variables")
                if force:
                    command_line_flags.append("--force")

                command_line_template = 'Jinja2CodeGenerator{script_extension} Generate "{{input_filename}}" "{{output_dir}}" {flags}'.format(
                    script_extension=CurrentShell.script_extensions[0],
                    flags=" ".join(command_line_flags),
                )

                input_root = src_dir
                output_dir = input_root.parent

                for input_filename_index, input_filename in enumerate(self._input_filenames):
                    with dm.Nested(
                        "Processing '{}' ({} of {})...".format(
                            input_filename,
                            input_filename_index + 1,
                            len(self._input_filenames),
                        ),
                    ) as file_dm:
                        on_progress_update(input_filename_index, str(input_filename))

                        this_output_dir = output_dir / Path(*input_filename.parent.parts[len(input_root.parts):])

                        command_line = command_line_template.format(
                            input_filename=input_filename,
                            output_dir=this_output_dir,
                            relative_input_filename=PathEx.CreateRelativePath(input_root, input_filename).as_posix(),
                            output_data_prefix=input_filename.stem,
                        )

                        file_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

                        result = SubprocessEx.Run(
                            command_line,
                            supports_colors=file_dm.capabilities.supports_colors,
                        )

                        file_dm.result = result.returncode

                        if file_dm.result != 0:
                            file_dm.WriteError(result.output)
                        else:
                            with file_dm.YieldVerboseStream() as stream:
                                stream.write(result.output)

            return dm.result

    # ----------------------------------------------------------------------

    return BuildInfo()


# ----------------------------------------------------------------------
def CreateTagsImpl(
    *,
    dry_run: bool,
    yes: bool,
    verbose: bool,
    debug: bool,
):
    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        if dry_run:
            yes = True

        if not yes:
            result = input(
                textwrap.dedent(
                    """\
                    This script will create "CI-<version>" tags based on the current commit and push
                    them to github.

                    Are you sure that you want to continue?

                    Type 'yes' to continue or anything else to exit: """,
                ),
            ).strip().lower()

            yes = result in ["yes", "y"]

        if not yes:
            dm.result = 1
            return

        command_line = 'CreateTags{ext} CI_VERSION "🤖 Updated CI Version" --prefix CI --release-type official --push --force --include-latest{dry_run}'.format(
            ext=CurrentShell.script_extensions[0],
            dry_run=" --dry-run" if dry_run else "",
        )

        with dm.YieldStream() as stream:
            dm.result = SubprocessEx.Stream(command_line, stream)
