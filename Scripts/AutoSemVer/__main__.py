# ----------------------------------------------------------------------
# |
# |  __main__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-01 08:21:03
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Automatically generates semantic versions based on changes in the active repository."""

import sys

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

try:
    import typer

    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator

from AutoSemVer import GenerateStyle, GetSemanticVersion


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # pylint: disable=missing-class-docstring
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command("Generate", no_args_is_help=False)
def Generate(
    path: Path=typer.Argument(Path.cwd(), file_okay=False, exists=True, resolve_path=True, help="Generate a semantic version based on changes that impact the specified path."),
    style: GenerateStyle=typer.Option(GenerateStyle.Standard, "--style", case_sensitive=False, help="Specifies the way in which the semantic version is generated; this is useful when targets using the generated semantic version do not fully support the semantic version specification."),
    prerelease_name: str=typer.Option(None, "--prerelease-name", help="Create a semantic version string with this prerelease name."),
    no_branch_name: bool=typer.Option(False, "--no-branch-name", help="Do not include the branch name in the prerelease section of the generated semantic version."),
    no_metadata: bool=typer.Option(False, "--no-metadata", help="Do not include the build metadata section of the generated semantic version."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
    quiet: bool=typer.Option(False, "--quiet", help="Do not display any information other than the generated semantic version."),
) -> None:
    """Automatically generates a semantic version based on changes in the active repository."""

    # ----------------------------------------------------------------------
    @contextmanager
    def GenerateDoneManager() -> Iterator[tuple[DoneManager, Callable[[str], Any]]]:
        if quiet:
            if verbose:
                raise typer.BadParameter("The 'verbose' and 'quiet' options are mutually exclusive.")
            if debug:
                raise typer.BadParameter("The 'debug' and 'quiet' options are mutually exclusive.")

            with DoneManager.Create(
                StreamDecorator(None),
                "",
            ) as dm:
                yield dm, sys.stdout.write
        else:
            with DoneManager.CreateCommandLine(
                output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
            ) as dm:
                yield dm, lambda version: dm.WriteLine("\n{}".format(version))

    # ----------------------------------------------------------------------

    with GenerateDoneManager() as (dm, output):
        result = GetSemanticVersion(
            dm,
            path=path,
            prerelease_name=prerelease_name,
            include_branch_name_when_necessary=not no_branch_name,
            no_metadata=no_metadata,
            style=style,
        )

        output(result.version)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
