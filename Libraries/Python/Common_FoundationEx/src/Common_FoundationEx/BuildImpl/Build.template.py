# pylint: disable=invalid-name
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_FoundationEx.BuildImpl import BuildInfoBase


# ----------------------------------------------------------------------
raise Exception("This is a template file. Customize the values and remove this exception.")
# pylint: disable=unreachable


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="<your build name here>",

            # Like golf scores, lower priority values indicate higher priority. Adjust this value
            # to ensure that it is invoked before other Build.py files in case there are
            # dependencies between the builds.
            #
            # priority=BuildInfoBase.STANDARD_PRIORITY,

            # Configurations to build; can be None if configurations are not required.
            configurations=["Debug", "Release"],
            configuration_is_required_on_clean=True,

            requires_output_dir=True,
            suggested_output_dir_location=None,         # Optional[Path]

            # required_development_environment="Linux",
            # required_development_configurations=[re.compile(r".*Debug"), ],
            # disable_if_dependency_environment=False,
        )

    # ----------------------------------------------------------------------
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
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        raise Exception("Implement me!")

    # ----------------------------------------------------------------------
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
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        raise Exception("Implement me!")


# ----------------------------------------------------------------------
# Custom functions are exposed via Typer on the command line

def Publish(
    output_dir: Path=typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Output directory associated with a prior build."),
    verbose: bool=typer.Argument(False, help="Display additional information."),
    debug: bool=typer.Argument(False, help="Display debug information."),
) -> None:
    """Publishes content previously built."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        with dm.Nested(
            "Publishing content at '{}'...".format(output_dir),
        ) as publish_dm:
            raise Exception("Implement me!")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
