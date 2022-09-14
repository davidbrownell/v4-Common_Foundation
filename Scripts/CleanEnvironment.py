# ----------------------------------------------------------------------
# |
# |  CleanEnvironment.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-18 13:50:19
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Utilities to clean the local development environment."""

import datetime
import os
import sys
import textwrap
import time

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:
    import typer

    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.ContextlibEx import ExitStack  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags  # type: ignore
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
foundation_repository_path = Path(__file__).parent / ".."
assert foundation_repository_path.is_dir(), foundation_repository_path

sys.path.insert(0, str(foundation_repository_path))
with ExitStack(lambda: sys.path.pop(0)):
    from RepositoryBootstrap import Constants as RepositoryBootstrapConstants  # type: ignore  # pylint: disable=import-error


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
)


DO_NOT_TRAVERSE_DEFAULT_DIRS: List[str]     = [
    RepositoryBootstrapConstants.GENERATED_DIRECTORY_NAME,  # type: ignore
    os.path.join("Tools", "openssl"),
    os.path.join("Tools", "Python"),
]


# ----------------------------------------------------------------------
@app.command("RemoveEmptyDirs")
def RemoveEmptyDirs(
    root: Path=typer.Argument(os.getcwd(), exists=True, file_okay=False, resolve_path=True, help="Clean this directory and its descendants."),
    do_not_traverse: List[str]=typer.Option(None, help="Name of a directory that should not be traversed when looking for empty content."),
    dry_run: bool=typer.Option(False, "--dry-run", help="Do not actually remove any content."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
):
    """Removes directories that are empty."""

    do_not_traverse += DO_NOT_TRAVERSE_DEFAULT_DIRS

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        dirs_deleted = 0

        with dm.Nested(
            "Processing '{}'...".format(str(root)),
            lambda: "{} deleted".format(inflect.no("directory", dirs_deleted)),
        ) as this_dm:
            # ----------------------------------------------------------------------
            def Impl(
                path: Path,
            ) -> None:
                if path.is_file():
                    if (
                        not dry_run
                        and path.parent.name != "__pycache__"
                        and path.suffix in [".pyc", ".pyo"]
                    ):
                        path.unlink()

                    return

                process_children = True

                if do_not_traverse:
                    str_path = str(path)

                    for item in do_not_traverse:
                        if item in str_path:
                            this_dm.WriteVerbose("Skipping '{}' due to the do not traverse value '{}'.\n".format(str_path, item))
                            process_children = False

                            break

                if process_children:
                    for child in path.iterdir():
                        Impl(child)

                children = list(path.iterdir())

                if (
                    not children
                    or (children[0].name == "__pycache__" and len(children) == 1)
                ):
                    with this_dm.VerboseNested(
                        "Removing '{}'...".format(str(path))
                    ):
                        if not dry_run:
                            CurrentShell.RemoveDir(path)

                        nonlocal dirs_deleted
                        dirs_deleted += 1

            # ----------------------------------------------------------------------

            Impl(root)

        if dry_run:
            dm.WriteInfo("\nNo content was deleted because '--dry-run' was specified.\n")

        return dm.result


# ----------------------------------------------------------------------
@app.command("RemoveEnvironmentFiles")
def RemoveEnvironmentFiles(
    delete_days: int=typer.Option(7, min=0, help="Delete files older than this many days."),
    yes: bool=typer.Option(False, "--yes", "-y", help="Delete without prompting."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
):
    """\
    Removes files that were generated as part of the environment setup and activation process
    but are no longer necessary.
    """

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        # ----------------------------------------------------------------------
        @dataclass(frozen=True)
        class FileInfo(object):
            path: Path
            type: Optional[str]
            age: datetime.timedelta
            size: int

        # ----------------------------------------------------------------------

        now = time.perf_counter()

        file_infos: List[FileInfo] = []

        with dm.Nested(
            "Searching for files...",
            lambda: "{} found".format(inflect.no("file", len(file_infos))),
            suffix="\n",
        ):
            for root, _, filenames in os.walk(CurrentShell.temp_directory):
                root = Path(root)

                for filename in filenames:
                    fullpath = root / filename

                    if not fullpath.is_file():
                        continue

                    if fullpath.suffix == RepositoryBootstrapConstants.TEMPORARY_FILE_EXTENSION:
                        name_parts = fullpath.suffix.split(".")

                        if len(name_parts) == 1:
                            the_type = None
                        else:
                            the_type = name_parts[-1]

                        file_infos.append(
                            FileInfo(
                                fullpath,
                                the_type,
                                datetime.timedelta(seconds=now - fullpath.stat().st_mtime),
                                fullpath.stat().st_size,
                            ),
                        )

        if not file_infos:
            dm.WriteInfo("No files were found.\n")
            return dm.result

        dm.WriteVerbose(
            textwrap.dedent(
                """\
                Files found:
                {}

                """,
            ).format(
                "\n".join(
                    "  - {}".format(str(file_info.path)) for file_info in file_infos
                ),
            ),
        )

        # Trim the list based on age
        delete_before = datetime.timedelta(days=delete_days)
        file_infos = [file_info for file_info in file_infos if file_info.age >= delete_before]

        if not file_infos:
            dm.WriteInfo("No files were found older than {} days.\n".format(delete_days))
            return dm.result

        if not yes:
            total_size = 0
            for file_info in file_infos:
                total_size += file_info.size

            with dm.YieldStream() as stream:
                stream.write(
                    textwrap.dedent(
                        """\
                        Would you like to delete these files:

                            Name                                                                        Type                   Size               Age (days)
                            --------------------------------------------------------------------------  ---------------------  -----------------  ------------------------------
                        {files}

                        ? ({total_size}) [y/N] """,
                    ).format(
                        total_size=TextwrapEx.GetSizeDisplay(total_size),
                        files="\n".join(
                            "    {name:<74}  {type:21}  {size:<17}  {age:<30}".format(
                                name=file_info.path.stem,
                                type=file_info.type or "",
                                size=TextwrapEx.GetSizeDisplay(file_info.size),
                                age=str(file_info.age),
                            )
                            for file_info in file_infos
                        ),
                    ),
                )

                stream.flush()

            value = input().strip()

            if value.lower() not in ["y", "yes", "1"]:
                return dm.result

        with dm.Nested(
            "\nDeleting files...",
            lambda: "{} deleted".format(inflect.no("file", len(file_infos))),
            suffix="\n",
        ) as this_dm:
            for index, file_info in enumerate(file_infos):
                with this_dm.Nested(
                    "Removing '{}' ({} of {})...".format(str(file_info.path), index + 1, len(file_infos)),
                ):
                    file_info.path.unlink()

        return dm.result


# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
