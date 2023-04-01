# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-02-25 09:49:40
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds Configuration information based on ../Configuration.SimpleSchema"""

# pylint: disable=invalid-name
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="AutoSemVer_Configuration",

            # Like golf scores, lower priority values indicate higher priority. Adjust this value
            # to ensure that it is invoked before other Build.py files in case there are
            # dependencies between the builds.
            #
            # priority=BuildInfoBase.STANDARD_PRIORITY,

            # Configurations to build; can be None if configurations are not required.
            configurations=None,
            configuration_is_required_on_clean=None,

            requires_output_dir=False,
            suggested_output_dir_location=None,         # Optional[Path]

            # required_development_environment="Linux",
            # required_development_configurations=[re.compile(r".*Debug"), ],
            # disable_if_dependency_environment=False,
        )

    # ----------------------------------------------------------------------
    # Additional extension methods:
    #   - GetNumCleanSteps
    #   - GetCustomCleanArgs
    #   - GetNumBuildSteps
    #   - GetCustomBuildArgs

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Optional[Path],         # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        output_dir = Path(__file__).parent.parent / "GeneratedCode"

        with DoneManager.Create(
            output_stream,
            "Removing '{}'...".format(output_dir),
            output_flags=DoneManagerFlags.Create(
                verbose=is_verbose,
                debug=is_debug,
            ),
        ) as dm:
            if not output_dir.is_dir():
                dm.WriteInfo("The directory does not exist.")
            else:
                PathEx.RemoveTree(output_dir)

            return 0

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Optional[Path],         # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        with DoneManager.Create(
            output_stream,
            "Building Configuration data...",
            output_flags=DoneManagerFlags.Create(
                verbose=is_verbose,
                debug=is_debug,
            ),
        ) as dm:
            command_line = 'SimpleSchema{script_ext} Generate ../AutoSemVerSchema.SimpleSchema "{output_dir}" --plugin JsonSchema --single-task{debug}{verbose}'.format(
                script_ext=CurrentShell.script_extensions[0],
                output_dir=Path(__file__).parent.parent / "GeneratedCode",
                debug=" --debug" if is_debug else "",
                verbose=" --verbose" if is_verbose else "",
            )

            dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

            result = SubprocessEx.Run(command_line)

            dm.result = result.returncode

            if dm.result != 0:
                dm.WriteError(result.output)
            else:
                with dm.YieldVerboseStream() as verbose_stream:
                    verbose_stream.write(result.output)

            return dm.result


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
