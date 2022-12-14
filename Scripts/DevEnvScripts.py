# ----------------------------------------------------------------------
# |
# |  DevEnvScripts.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-14 15:06:24
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Displays all scripts available within the activated repository and its dependencies."""

import json
import os
import sys

from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import typer

from rich import print as rich_print
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import Types


# ----------------------------------------------------------------------
sys.path.insert(0, Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0])

    from RepositoryBootstrap import Constants as RepositoryBootstrapConstants  # pylint: disable=import-error


# ----------------------------------------------------------------------
app                                         = typer.Typer()


# ----------------------------------------------------------------------
class CommandSentinel(str, Enum):
    display                                 = "display"
    location                                = "location"


# ----------------------------------------------------------------------
# Keeping this as a single method so the default behavior is to display the script info when no arguments
# are provided
@app.command("EntryPoint")
def EntryPoint(
    location_sentinel: CommandSentinel=typer.Argument(CommandSentinel.display),
    script_name: Optional[str]=typer.Argument(None),
):
    if location_sentinel == CommandSentinel.display:
        _OnDisplay()
    elif location_sentinel == CommandSentinel.location:
        _OnLocation(script_name)
    else:
        assert False, location_sentinel


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _OnDisplay() -> None:
    with DoneManager.CreateCommandLine() as dm:
        content = _LoadScriptContent(dm)

        # ----------------------------------------------------------------------
        def CreateRepositoryPanel(
            repo_id: str,
            repo_name: str,
            repo_root: Path,
            script_infos: List[Any],
        ) -> Panel:
            headers: List[str] = ["Script", "Description"]

            table = Table.grid(
                padding=(1, 2),
            )

            table.add_column("Script", min_width=40)
            table.add_column("Description", min_width=90)

            if dm.capabilities.is_headless:
                table.add_column("Location")

            for script_info in script_infos:
                row_data: List[str] = [
                    "[bold green]{}[/]".format(
                        (
                            script_info["name"]
                            if dm.capabilities.is_headless
                            else "[link=file:///{}]{}[/]".format(
                                Path(script_info["filename"]).as_posix(),
                                script_info["name"],
                            )
                        ),
                    ),
                    script_info["documentation"] or "",
                ]

                if dm.capabilities.is_headless:
                    row_data.append(str(Path(script_info["filename"])))

                table.add_row(*row_data)

            return Panel(
                table,
                border_style="bold white",
                padding=(1, 2),
                subtitle=repo_id,
                subtitle_align="right",
                title=(
                    "{} ({})".format(repo_name, repo_root)
                    if dm.capabilities.is_headless
                    else "[link=file:///{}]{}[/]".format(
                        Path(repo_root).as_posix(),
                        repo_name,
                    )
                ),
                title_align="left",
            )

        # ----------------------------------------------------------------------

        rich_print(
            Panel(
                Group(
                    *(
                        CreateRepositoryPanel(repo_id, repo_name, Path(repo_root), script_infos)
                        for repo_id, (repo_name, repo_root, script_infos) in content.items()
                    ),

                ),
                border_style="bold blue",
            ),
        )


# ----------------------------------------------------------------------
def _OnLocation(
    script_name: Optional[str],
) -> None:
    if script_name is None:
        raise typer.BadParameter("A script name must be provided when extracting a location")

    sink = StringIO()

    with DoneManager.CreateCommandLine(sink) as dm:
        try:
            content = _LoadScriptContent(dm)

            for _, _, script_infos in content.values():
                for script_info in script_infos:
                    if (
                        script_info["name"] == script_name
                        or os.path.splitext(script_info["name"])[0] == script_name
                    ):
                        sys.stdout.write(script_info["filename"])
                        return

            dm.WriteError("The script '{}' was not found.\n".format(script_name))

        finally:
            if dm.result != 0:
                sys.stdout.write(sink.getvalue())


# ----------------------------------------------------------------------
def _LoadScriptContent(
    dm: DoneManager,
) -> Dict[
    str,                                    # Repo Id
    Tuple[
        str,                                # Repo name
        str,                                # Repo location
        List[Dict[str, str]],               # Script info
    ],
]:
    with dm.Nested(
        "Loading script content...",
        suffix="\n",
    ) as load_dm:
        json_filename = Path(
            Types.EnsureValid(os.getenv(RepositoryBootstrapConstants.DE_REPO_GENERATED_NAME)),
        ) / "Scripts" / RepositoryBootstrapConstants.SCRIPT_DATA_NAME

        if not json_filename.is_file():
            load_dm.WriteError("The file '{}' does not exist.\n".format(json_filename))
            load_dm.ExitOnError()

        with json_filename.open() as f:
            content = json.load(f)

        return content


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
