# ----------------------------------------------------------------------
# |
# |  PullRequestValidator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-06 13:35:05
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
from pathlib import Path
from typing import Optional

import typer

from typer.core import TyperGroup

from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import ChangeInfo, SCMPlugin
from RepositoryBootstrap.Impl.Hooks.HookImpl import ExecutePlugins


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
    destination_branch_name: str=typer.Argument(..., help="Name of the destination branch; the default mainline branch name will be used if none is provided."),
    working_directory: Path=typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The working directory used to resolve path arguments."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Validates a pull request."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        repository = _GetRepository(dm, working_directory)

        if repository.HasWorkingChanges():
            dm.WriteError("\nPull request validation cannot be performed on repositories with working changes.")
            return

        changes: list[ChangeInfo] = []

        with dm.Nested(
            "Extracting changes...",
            lambda: "{} found".format(inflect.no("change", len(changes))),
            suffix="\n",
        ):
            changes += [
                ChangeInfo.CreateFromRepositoryChangeInfo(change_info)
                for change_info in repository.EnumChangesSinceMergeEx(
                    destination_branch_name,
                    None,
                )
            ]

            if not changes:
                return

        ExecutePlugins(
            dm,
            repository,
            changes,
            SCMPlugin.Flag.ValidatePullRequest,
            0,  # type: ignore
        )


# ----------------------------------------------------------------------
@app.command("ListPlugins", no_args_is_help=False)
def ListPlugins(
    working_directory: Path=typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The working directory used to resolve path arguments."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Lists all plugins used in the validation of a pull request."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        plugins = GetPlugins(
            dm,
            _GetRepository(dm, working_directory).repo_root,
            SCMPlugin.Flag.ValidatePullRequest,
        )

        with dm.YieldStream() as stream:
            stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Plugin",
                        "Description",
                    ],
                    [
                        [plugin.name, plugin.description]
                        for plugin in plugins
                    ],
                ),
            )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _GetRepository(
    dm: DoneManager,
    working_directory: Path,
) -> Repository:
    repository: Optional[Repository] = None

    with dm.Nested(
        "Calculating source control repository...",
        lambda: "errors were encountered" if repository is None else repository.scm.name,
    ):
        for scm in ALL_SCMS:
            if scm.IsActive(
                working_directory,
                traverse_ancestors=True,
            ):
                repository = scm.Open(working_directory)
                return repository

        raise Exception("A SCM could be be found for '{}'.".format(working_directory))


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
