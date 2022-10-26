# ----------------------------------------------------------------------
# |
# |  GitHooks.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 08:32:31
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality invoked by Git hook scripts"""

import re

from collections import namedtuple
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List

import typer

from typer.core import TyperGroup

from Common_Foundation.SourceControlManagers.GitSourceControlManager import GitSourceControlManager
from Common_Foundation.Streams.Capabilities import Capabilities
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags

from Common_Foundation import SubprocessEx

from . import HookImpl


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command("commit_msg", no_args_is_help=True)
def commit_msg(
    working_dir: Path=typer.Argument(..., file_okay=False, exists=True, resolve_path=True, help="git working directory."),
    name: str=typer.Argument(..., help="git username."),
    email: str=typer.Argument(..., help="git email."),
    commit_message: Path=typer.Argument(..., dir_okay=False, help="File generated by git that contains the commit message."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Functionality invoked before a commit is finalized."""

    git = GitSourceControlManager()

    repository = git.Open(git.GetRoot(working_dir))

    with _YieldCommandLineDoneManager(verbose=verbose, debug=debug) as dm:
        commit_message = working_dir / commit_message
        assert commit_message.is_file(), commit_message

        with dm.Nested("Extracting commit information...") as commit_dm:
            result = SubprocessEx.Run(
                "git status --porcelain=1 --untracked-files=no",
                cwd=repository.repo_root,
            )

            commit_dm.result = result.returncode

            if commit_dm.result != 0:
                commit_dm.WriteError(result.output)
                return

            with commit_dm.YieldVerboseStream() as stream:
                stream.write(result.output)

            pfr = _ProcessFileList(repository.repo_root, result.output)

        HookImpl.Commit(
            dm,
            repository,
            HookImpl.CommitInfo(
                "HEAD",
                "{} <{}>".format(name, email),
                commit_message.open().read(),
                pfr.files_added,
                pfr.files_modified,
                pfr.files_removed,
            ),
        )


# ----------------------------------------------------------------------
@app.command("pre_push", no_args_is_help=True)
def pre_push(
    working_dir: Path=typer.Argument(..., file_okay=False, exists=True, resolve_path=True, help="git working directory."),  # pylint: disable=unused-argument
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Functionality invoked before a set of changes are pushed to the remote repository."""

    with _YieldCommandLineDoneManager(verbose=verbose, debug=debug) as dm:
        dm.WriteError("Not implemented yet")


# ----------------------------------------------------------------------
@app.command("pre_receive", no_args_is_help=True)
def pre_receive(
    working_dir: Path=typer.Argument(..., file_okay=False, exists=True, resolve_path=True, help="git working directory."),  # pylint: disable=unused-argument
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Functionality invoked after a set of changes are received from a remote repository but before they are introduced into the current repository."""

    with _YieldCommandLineDoneManager(verbose=verbose, debug=debug) as dm:
        dm.WriteError("Not implemented yet")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
@contextmanager
def _YieldCommandLineDoneManager(
    *,
    verbose: bool,
    debug: bool,
) -> Iterator[DoneManager]:
    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
        capabilities=Capabilities(
            is_interactive=False,
            is_headless=False,
            supports_colors=True,
        ),
    ) as dm:
        yield dm


# ----------------------------------------------------------------------
_ProcessFileListResult                      = namedtuple(
    "_ProcessFileListResult",
    [
        "files_added",
        "files_modified",
        "files_removed",
    ],
)

def _ProcessFileList(
    repo_root: Path,
    porcelain_output: str,
) -> _ProcessFileListResult:
    added: List[Path] = []
    modified: List[Path] = []
    removed: List[Path] = []

    # See https://git-scm.com/docs/git-status for more information on the porcelain output format
    regex = re.compile(r"(?P<prefix_x>.)(?P<prefix_y>.)\s+(?P<filename>.+)")

    for line in porcelain_output.split("\n"):
        line = line.rstrip()
        if not line:
            continue

        if "trace: " in line:
            continue

        match = regex.match(line)
        assert match, line

        prefix_x = match.group("prefix_x")

        # Not using prefix_y at this time
        # prefix_y = match.group("prefix_y")

        filename = match.group("filename")

        if prefix_x == " ":
            continue

        if prefix_x == "R":
            assert " -> " in filename, filename
            source, dest = filename.split(" -> ", maxsplit=1)

            removed.append(repo_root / source)
            added.append(repo_root / dest)
        elif prefix_x == "A":
            added.append(repo_root / filename)
        elif prefix_x == "D":
            removed.append(repo_root / filename)
        elif prefix_x in [
            "C", # Copied
            "M", # Modified
            "T", # Type changed
            "U", # Updated but unmerged
        ]:
            modified.append(repo_root / filename)
        else:
            assert False, line

    return _ProcessFileListResult(
        added or None,
        modified or None,
        removed or None,
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
