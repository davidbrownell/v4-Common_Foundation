# ----------------------------------------------------------------------
# |
# |  __main__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-04 13:05:40
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Validates changes within a pull request before it is committed."""

from typing import Optional

import typer

from typer.core import TyperGroup

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags


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
@app.command("Validate", no_args_is_help=False)
def Validate(
    destination_branch_name: Optional[str]=typer.Option(None, "--destination-branch-name", help="Name of the destination branch; the default mainline branch name will be used if none is provided."),
    latest_only: bool=typer.Option(False, "--latest-only", help="Only look at the latest change rather than all changes since the last merge to the destination branch."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Validates changes within a pull request."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        pass # TODO


# ----------------------------------------------------------------------
@app.command("ListPlugins", no_args_is_help=False)
def ListPlugins(
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """List the plugins invoked as part of the validation process."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        pass # TODO


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
