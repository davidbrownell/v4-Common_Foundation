# ----------------------------------------------------------------------
# |
# |  CommitEmojis.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-27 06:40:09
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Displays emojis that can be used in commit messages."""

import os
import sys

from pathlib import Path

import typer

from rich import print as rich_print
from typer.core import TyperGroup

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import Types

# ----------------------------------------------------------------------
sys.path.insert(0, str(PathEx.EnsureDir(Path(Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION"))))))
with ExitStack(lambda: sys.path.pop(0)):
    from ScmHook_custom import CreateEmojiTable


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command("EntryPoint")
def EntryPoint(
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Displays emojis that can be used in commit messages."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        with dm.YieldStream() as stream:
            rich_print(
                CreateEmojiTable(),
                file=stream,  # type: ignore
            )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
