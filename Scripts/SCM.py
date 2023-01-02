# ----------------------------------------------------------------------
# |
# |  SCM.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 19:41:55
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Executes Source Code Manager commands."""

import io
import multiprocessing
import os
import sys
import textwrap
import types

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, cast, Generator, List, Optional, TextIO, Tuple, Union

try:
    import typer

    from click.exceptions import UsageError
    from rich.progress import Progress, TaskID
    from typer.core import TyperGroup

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.SourceControlManager import DistributedRepository, Repository, SourceControlManager
from Common_Foundation.SourceControlManagers import UpdateMergeArgs
from Common_Foundation.Streams.Capabilities import Capabilities
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
Scm                                         = Types.StringsToEnum("Scm", (scm.name for scm in ALL_SCMS))


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


# ----------------------------------------------------------------------
_path_required_argument                     = typer.Argument(Path.cwd(), exists=False, file_okay=False, resolve_path=True, help="The directory path associated with a repository.")
_path_optional_option                       = typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The directory path associated with a repository.")

_scm_required_argument                      = typer.Argument(..., case_sensitive=False, help="Name of the Source Control Manager (SCM) to use.")
_scm_optional_option                        = typer.Option(None, case_sensitive=False, help="Name of the Source Control Manager (SCM) to use; the SCM will be auto-detected if the name is not provided.")

_branch_optional_option                     = typer.Option(None, help="Name of a branch in the repository.")
_date_optional_option                       = typer.Option(None, help="Date near changes in the repository.")

_change_required_argument                   = typer.Argument(..., help="Change id in the repository.")
_change_optional_option                     = typer.Option(None, help="Change id in the repository.")

_verbose_option                             = typer.Option(False, "--verbose", help="Write verbose information to the terminal.")

_no_prompt_option                           = typer.Option(False, "--no-prompt", help="Do not prompt for confirmation before invoking the functionality.")

_group_commands_root_argument               = typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Root directory used when recursively searching for repositories.")


# ----------------------------------------------------------------------
# |
# |  General Commands
# |
# ----------------------------------------------------------------------
@app.command("Info", rich_help_panel="General Commands")
def Info(
    path: Path=_path_optional_option,
):
    """Returns information about all known SCMs and the specified directory"""

    with DoneManager.CreateCommandLine() as dm:
        rows: List[List[str]] = []

        with dm.Nested(
            "Calculating",
            suffix="\n\n",
        ):
            rows+= [
                [
                    scm.name,
                    "Yes" if scm.IsAvailable() else "No",
                    "Yes" if scm.IsActive(path) else "No",
                ]
                for scm in ALL_SCMS
            ]

        if Capabilities.Get(sys.stdout).supports_colors:
            # This script may be called early within the development cycle, so not using colorama
            col_header_color_on = TextwrapEx.BRIGHT_WHITE_COLOR_ON
            yes_color_on = TextwrapEx.BRIGHT_GREEN_COLOR_ON
            color_off = TextwrapEx.COLOR_OFF
        else:
            col_header_color_on = ""
            yes_color_on = ""
            color_off = ""

        # ----------------------------------------------------------------------
        def DecorateRow(
            row_index: int,
            cols: List[str],
        ) -> List[str]:
            cols[0] = "{}{}{}".format(col_header_color_on, cols[0], color_off)

            if row_index >= 0:
                if "Yes" in cols[1]:
                    cols[1] = "{}{}{}".format(yes_color_on, cols[1], color_off)

                if "Yes" in cols[2]:
                    cols[2] = "{}{}{}".format(yes_color_on, cols[2], color_off)

            return cols

        # ----------------------------------------------------------------------

        with dm.YieldStream() as stream:
            stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Name",
                        "Is Available",
                        "Is Active",
                    ],
                    rows,
                    [
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                    ],
                    decorate_values_func=DecorateRow,
                    decorate_headers=True,
                ),
            )

            stream.write("\n")


# ----------------------------------------------------------------------
@app.command("Create", rich_help_panel="General Commands", help=SourceControlManager.Create.__doc__, no_args_is_help=True)
def Create(
    scm_name: Scm=_scm_required_argument,  # type: ignore
    output_dir: Path=_path_required_argument,
):
    with DoneManager.CreateCommandLine() as dm:
        scm = _GetSCM(None, scm_name)

        with dm.Nested(
            "Creating a new repository in '{}' using '{}'...".format(str(output_dir), scm.name),
        ):
            scm.Create(output_dir)


# ----------------------------------------------------------------------
@app.command("Clone", rich_help_panel="General Commands", help=SourceControlManager.Clone.__doc__, no_args_is_help=True)
def Clone(
    scm_name: Scm=_scm_required_argument,  # type: ignore
    uri: str=typer.Argument(..., help="Uri to clone from"),
    output_dir: Path=_path_required_argument,
    branch: Optional[str]=_branch_optional_option,
):
    with DoneManager.CreateCommandLine() as dm:
        scm = _GetSCM(None, scm_name)

        with dm.Nested(
            "Cloning '{}' in '{}' using '{}'...".format(uri, str(output_dir), scm.name),
        ):
            scm.Clone(uri, output_dir, branch)


# ----------------------------------------------------------------------
# |
# |  Repository Commands
# |
# ----------------------------------------------------------------------
@app.command("GetUniqueName", rich_help_panel="Repository Commands", help=Repository.GetUniqueName.__doc__)
def GetUniqueName(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetUniqueName",
        lambda repo: repo.GetGetUniqueNameCommandLine(),
        lambda repo: repo.GetUniqueName(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("Who", rich_help_panel="Repository Commands", help=Repository.Who.__doc__)
def Who(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore

):
    return _Wrap(
        "Who",
        lambda repo: repo.GetWhoCommandLine(),
        lambda repo: repo.Who(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("Clean", rich_help_panel="Repository Commands", help=Repository.Clean.__doc__)
def Clean(
    no_prompt: bool=_no_prompt_option,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "Clean",
        lambda repo: repo.GetCleanCommandLine(),
        lambda repo: repo.Clean(no_prompt=no_prompt),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumBranches", rich_help_panel="Repository Commands", help=Repository.EnumBranches.__doc__)
def EnumBranches(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumBranches",
        lambda repo: repo.GetEnumBranchesCommandLine(),
        lambda repo: repo.EnumBranches(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetCurrentBranch", rich_help_panel="Repository Commands", help=Repository.GetCurrentBranch.__doc__)
def GetCurrentBranch(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetCurrentBranch",
        lambda repo: repo.GetGetCurrentBranchCommandLine(),
        lambda repo: repo.GetCurrentBranch(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetCurrentNormalizedBranch", rich_help_panel="Repository Commands", help=Repository.GetCurrentNormalizedBranch.__doc__)
def GetCurrentNormalizedBranch(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetCurrentNormalizedBranch",
        lambda repo: repo.GetGetCurrentNormalizedBranchCommandLine(),
        lambda repo: repo.GetCurrentNormalizedBranch(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetMostRecentBranch", rich_help_panel="Repository Commands", help=Repository.GetMostRecentBranch.__doc__)
def GetMostRecentBranch(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetMostRecentBranch",
        lambda repo: repo.GetGetMostRecentBranchCommandLine(),
        lambda repo: repo.GetMostRecentBranch(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("CreateBranch", rich_help_panel="Repository Commands", help=Repository.CreateBranch.__doc__, no_args_is_help=True)
def CreateBranch(
    branch_name: str,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "CreateBranch",
        lambda repo: repo.GetCreateBranchCommandLine(branch_name),
        lambda repo: repo.CreateBranch(branch_name),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("SetBranch", rich_help_panel="Repository Commands", help=Repository.SetBranch.__doc__, no_args_is_help=True)
def SetBranch(
    branch_name: str,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "SetBranch",
        lambda repo: repo.GetSetBranchCommandLine(branch_name),
        lambda repo: repo.SetBranch(branch_name),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("SetBranchOrDefault", rich_help_panel="Repository Commands", help=Repository.SetBranchOrDefault.__doc__, no_args_is_help=True)
def SetBranchOrDefault(
    branch_name: str,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "SetBranchOrDefault",
        lambda repo: repo.GetSetBranchOrDefaultCommandLine(branch_name),
        lambda repo: repo.SetBranchOrDefault(branch_name),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetExecutePermission", rich_help_panel="Repository Commands", help=Repository.GetExecutePermission.__doc__, no_args_is_help=True)
def GetExecutePermission(
    filename: Path=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True, help="Filename to query"),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetExecutePermission",
        lambda repo: repo.GetGetExecutePermissionCommandLine(filename),
        lambda repo: repo.GetExecutePermission(filename),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("SetExecutePermission", rich_help_panel="Repository Commands", help=Repository.SetExecutePermission.__doc__, no_args_is_help=True)
def SetExecutePermission(
    filename: Path=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True, help="Filename to set."),
    is_executable: bool=typer.Argument(..., help="True if the execute permission should be set, False if it should be removed."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "SetExecutePermission",
        lambda repo: repo.GetSetExecutePermissionCommandLine(filename, is_executable),
        lambda repo: repo.SetExecutePermission(filename, is_executable),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("HasUntrackedWorkingChanges", rich_help_panel="Repository Commands", help=Repository.HasUntrackedWorkingChanges.__doc__)
def HasUntrackedWorkingChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "HasUntrackedWorkingChanges",
        lambda repo: repo.GetHasUntrackedWorkingChangesCommandLine(),
        lambda repo: repo.HasUntrackedWorkingChanges(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumUntrackedWorkingChanges", rich_help_panel="Repository Commands", help=Repository.EnumUntrackedWorkingChanges.__doc__)
def EnumUntrackedWorkingChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumUntrackedWorkingChanges",
        lambda repo: repo.GetEnumUntrackedWorkingChangesCommandLine(),
        lambda repo: repo.EnumUntrackedWorkingChanges(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("HasWorkingChanges", rich_help_panel="Repository Commands", help=Repository.HasWorkingChanges.__doc__)
def HasWorkingChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "HasWorkingChanges",
        lambda repo: repo.GetHasWorkingChangesCommandLine(),
        lambda repo: repo.HasWorkingChanges(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumWorkingChanges", rich_help_panel="Repository Commands", help=Repository.EnumWorkingChanges.__doc__)
def EnumWorkingChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumWorkingChanges",
        lambda repo: repo.GetEnumWorkingChangesCommandLine(),
        lambda repo: repo.EnumWorkingChanges(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetChangeStatus", rich_help_panel="Repository Commands", help=Repository.GetChangeStatus.__doc__)
def GetChangeStatus(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetChangeStatus",
        lambda repo: repo.GetGetChangeStatusCommandLine(),
        lambda repo: repo.GetChangeStatus(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("GetChangeInfo", rich_help_panel="Repository Commands", help=Repository.GetChangeInfo.__doc__, no_args_is_help=True)
def GetChangeInfo(
    change: str=_change_required_argument,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetChangeInfo",
        lambda repo: repo.GetGetChangeInfoCommandLine(change),
        lambda repo: repo.GetChangeInfo(change),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("AddFiles", rich_help_panel="Repository Commands", help=Repository.AddFiles.__doc__, no_args_is_help=True)
def AddFiles(
    filenames: List[Path]=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True, help="Filenames to add."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "AddFiles",
        lambda repo: repo.GetAddFilesCommandLine(filenames),
        lambda repo: repo.AddFiles(filenames),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("Commit", rich_help_panel="Repository Commands", help=Repository.Commit.__doc__, no_args_is_help=True)
def Commit(
    description: str,
    username: Optional[str]=None,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "Commit",
        lambda repo: repo.GetCommitCommandLine(description, username),
        lambda repo: repo.Commit(description, username),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("Update", rich_help_panel="Repository Commands", help=Repository.Update.__doc__)
def Update(
    change: Optional[str]=_change_optional_option,
    branch: Optional[str]=_branch_optional_option,
    date: Optional[datetime]=_date_optional_option,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    arg = _CreateUpdateMergeArg(change, branch, date)

    return _Wrap(
        "Update",
        lambda repo: repo.GetUpdateCommandLine(arg),
        lambda repo: repo.Update(arg),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("Merge", rich_help_panel="Repository Commands", help=Repository.Merge.__doc__)
def Merge(
    change: Optional[str]=_change_optional_option,
    branch: Optional[str]=_branch_optional_option,
    date: Optional[datetime]=_date_optional_option,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    arg = _CreateUpdateMergeArg(change, branch, date)

    if arg is None:
        raise typer.BadParameter("A change, branch, or date must be provided")

    return _Wrap(
        "Merge",
        lambda repo: repo.GetMergeCommandLine(arg),
        lambda repo: repo.Merge(arg),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumChangesSinceMerge", rich_help_panel="Repository Commands", help=Repository.EnumChangesSinceMerge.__doc__, no_args_is_help=True)
def EnumChangesSinceMerge(
    dest_branch: str=typer.Argument(..., help="Destination branch name."),
    change: Optional[str]=_change_optional_option,
    branch: Optional[str]=_branch_optional_option,
    date: Optional[datetime]=_date_optional_option,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    arg = _CreateUpdateMergeArg(change, branch, date)

    return _Wrap(
        "EnumChangesSinceMerge",
        lambda repo: repo.GetEnumChangesSinceMergeCommandLine(dest_branch, arg),
        lambda repo: repo.EnumChangesSinceMerge(dest_branch, arg),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumChangedFiles", rich_help_panel="Repository Commands", help=Repository.EnumChangedFiles.__doc__, no_args_is_help=True)
def EnumChangedFiles(
    change: str,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumChangedFiles",
        lambda repo: repo.GetEnumChangedFilesCommandLine(change),
        lambda repo: repo.EnumChangedFiles(change),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumBlameInfo", rich_help_panel="Repository Commands", help=Repository.EnumBlameInfo.__doc__, no_args_is_help=True)
def EnumBlameInfo(
    filename: Path=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True, help="Filename to enumerate."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumBlameInfo",
        lambda repo: repo.GetEnumBlameInfoCommandLine(filename),
        lambda repo: repo.EnumBlameInfo(filename),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("EnumTrackedFiles", rich_help_panel="Repository Commands", help=Repository.EnumTrackedFiles.__doc__)
def EnumTrackedFiles(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumTrackedFiles",
        lambda repo: repo.GetEnumTrackedFilesCommandLine(),
        lambda repo: repo.EnumTrackedFiles(),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("CreatePatch", rich_help_panel="Repository Commands", help=Repository.CreatePatch.__doc__, no_args_is_help=True)
def CreatePatch(
    output_filename: Path=typer.Argument(..., exists=False, help="Output filename for the created patch."),
    start_change: Optional[str]=_change_optional_option,
    end_change: Optional[str]=_change_optional_option,
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "CreatePatch",
        lambda repo: repo.GetCreatePatchCommandLine(output_filename, start_change, end_change),
        lambda repo: repo.CreatePatch(output_filename, start_change, end_change),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
@app.command("ApplyPatch", rich_help_panel="Repository Commands", help=Repository.ApplyPatch.__doc__, no_args_is_help=True)
def ApplyPatch(
    patch_filename: Path=typer.Argument(..., exists=True, dir_okay=False, resolve_path=True, help="Filename of a patch previously created."),
    commit: bool=typer.Option(False, "--commit", help="Apply to automatically commit any changes based on the applied patch."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "ApplyPatch",
        lambda repo: repo.GetApplyPatchCommandLine(patch_filename, commit),
        lambda repo: repo.ApplyPatch(patch_filename, commit),
        repo_root,
        scm_name,
    )


# ----------------------------------------------------------------------
# |
# |  Distributed Repository Commands
# |
# ----------------------------------------------------------------------
@app.command("Reset", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.Reset.__doc__)
def Reset(
    no_prompt: bool=_no_prompt_option,
    no_backup: bool=typer.Option(False, "--no-backup", help="Do not backup changes before resetting."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "Reset",
        lambda repo: cast(DistributedRepository, repo).GetResetCommandLine(no_backup),
        lambda repo: cast(DistributedRepository, repo).Reset(no_prompt, no_backup),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("HasUpdateChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.HasUpdateChanges.__doc__)
def HasUpdateChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "HasUpdateChanges",
        lambda repo: cast(DistributedRepository, repo).GetHasUpdateChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).HasUpdateChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("EnumUpdateChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.EnumUpdateChanges.__doc__)
def EnumUpdateChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumUpdateChanges",
        lambda repo: cast(DistributedRepository, repo).GetEnumUpdateChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).EnumUpdateChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("HasLocalChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.HasLocalChanges.__doc__)
def HasLocalChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "HasLocalChanges",
        lambda repo: cast(DistributedRepository, repo).GetHasLocalChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).HasLocalChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("EnumLocalChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.EnumLocalChanges.__doc__)
def EnumLocalChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumLocalChanges",
        lambda repo: cast(DistributedRepository, repo).GetEnumLocalChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).EnumLocalChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("HasRemoteChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.HasRemoteChanges.__doc__)
def HasRemoteChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "HasRemoteChanges",
        lambda repo: cast(DistributedRepository, repo).GetHasRemoteChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).HasRemoteChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("EnumRemoteChanges", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.EnumRemoteChanges.__doc__)
def EnumRemoteChanges(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "EnumRemoteChanges",
        lambda repo: cast(DistributedRepository, repo).GetEnumRemoteChangesCommandLine(),
        lambda repo: cast(DistributedRepository, repo).EnumRemoteChanges(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("GetDistributedChangeStatus", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.GetDistributedChangeStatus.__doc__)
def GetDistributedChangeStatus(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "GetDistributedChangeStatus",
        lambda repo: cast(DistributedRepository, repo).GetGetDistributedChangeStatusCommandLine(),
        lambda repo: cast(DistributedRepository, repo).GetDistributedChangeStatus(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("Push", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.Push.__doc__)
def Push(
    create_remote_branch: bool=typer.Option(False, "--create-remote-branch", help="Create any new branches on the remote (if necessary) as part of the push."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "Push",
        lambda repo: cast(DistributedRepository, repo).GetPushCommandLine(create_remote_branch),
        lambda repo: cast(DistributedRepository, repo).Push(create_remote_branch),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("Pull", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.Pull.__doc__)
def Pull(
    branches: Optional[List[str]]=typer.Option(None, "--branch", help="Explicit branch names to pull."),
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    branches = Types.EnsurePopulatedList(branches)

    return _Wrap(
        "Pull",
        lambda repo: cast(DistributedRepository, repo).GetPullCommandLine(branches),
        lambda repo: cast(DistributedRepository, repo).Pull(branches),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("PullAndUpdate", rich_help_panel="Distributed Repository Commands", help=DistributedRepository.PullAndUpdate.__doc__)
def PullAndUpdate(
    repo_root: Path=_path_optional_option,
    scm_name: Optional[Scm]=_scm_optional_option,  # type: ignore
):
    return _Wrap(
        "PullAndUpdate",
        lambda repo: cast(DistributedRepository, repo).GetPullAndUpdateCommandLine(),
        lambda repo: cast(DistributedRepository, repo).PullAndUpdate(),
        repo_root,
        scm_name,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
# |
# |  Group Commands
# |
# ----------------------------------------------------------------------
@app.command("AllWorkingChanges", rich_help_panel="Group Commands", no_args_is_help=True)
def AllWorkingChanges(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """List all repositories with working changes."""

    # ----------------------------------------------------------------------
    def GlobalCallback(
        dm: DoneManager,
        repositories: List[Tuple[Repository, Any]],
    ) -> None:
        with dm.YieldStream() as stream:
            stream.write(
                textwrap.dedent(
                    """\
                    {}{} with working changes {} found
                    {}
                    """,
                ).format(
                    "\n" if not verbose else "",
                    inflect.no("repository", len(repositories)),
                    inflect.plural_verb("was", len(repositories)),
                    "\n".join("  - {}".format(directory) for directory in sorted(str(repository.repo_root) for repository, _ in repositories)),
                ),
            )

    # ----------------------------------------------------------------------

    return _WrapAll(
        "Getting working changes...",
        lambda repo: repo.HasWorkingChanges(),
        None,
        None,
        root,
        verbose=verbose,
        requires_distributed_repository=False,
        global_action_callback=GlobalCallback,
    )


# ----------------------------------------------------------------------
@app.command("AllChangeStatus", rich_help_panel="Group Commands", no_args_is_help=True)
def AllChangeStatus(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """List change information for a group of repositories."""

    # ----------------------------------------------------------------------
    def GlobalCallback(
        dm: DoneManager,
        repositories: List[Tuple[Repository, Any]],
    ) -> None:
        if dm.capabilities.supports_colors:
            # This script may be called early within the development cycle, so not using colorama
            col_header_color_on = TextwrapEx.BRIGHT_WHITE_COLOR_ON
            yes_color_on = TextwrapEx.BRIGHT_RED_COLOR_ON
            color_off = TextwrapEx.COLOR_OFF
        else:
            col_header_color_on = ""
            yes_color_on = ""
            color_off = ""

        # ----------------------------------------------------------------------
        def DecorateRow(
            row_index: int,
            cols: List[str],
        ) -> List[str]:
            cols[0] = "{}{}{}".format(col_header_color_on, cols[0], color_off)

            if row_index >= 0:
                if repositories[row_index][1].has_untracked_changes:
                    cols[2] = "{}{}{}".format(yes_color_on, cols[2], color_off)

                if repositories[row_index][1].has_standard_changes:
                    cols[3] = "{}{}{}".format(yes_color_on, cols[3], color_off)

            return cols

        # ----------------------------------------------------------------------

        with dm.YieldStream() as stream:
            stream.write("\n")

            stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Directory (relative to '{}')".format(str(root)),
                        "SCM",
                        "Has Untracked Changes",
                        "Has Local Changes",
                    ],
                    [
                        [
                            "{}{}".format(os.path.sep, str(PathEx.CreateRelativePath(root, repository.repo_root))),
                            repository.scm.name,
                            "Yes" if change_status.has_untracked_changes else "No",
                            "Yes" if change_status.has_standard_changes else "No",
                        ]
                        for repository, change_status in repositories
                    ],
                    [
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                    ],
                    decorate_values_func=DecorateRow,
                    decorate_headers=True,
                ),
            )

            stream.write("\n")

    # ----------------------------------------------------------------------

    return _WrapAll(
        "Getting change statuses...",
        lambda repo: repo.GetChangeStatus(),
        None,
        None,
        root,
        verbose=verbose,
        requires_distributed_repository=False,
        global_action_callback=GlobalCallback,
    )


# ----------------------------------------------------------------------
@app.command("AllDistributedChangeStatus", rich_help_panel="Group Commands", no_args_is_help=True)
def AllDistributedChangeStatus(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """List change status for a group of distributed repositories."""

    # ----------------------------------------------------------------------
    def GetRepoInfo(
        repo: Repository,
    ):
        repo = cast(DistributedRepository, repo)

        return (
            repo.GetDistributedChangeStatus(),
            repo.GetCurrentBranch(),
        )

    # ----------------------------------------------------------------------
    def GlobalCallback(
        dm: DoneManager,
        repositories: List[Tuple[Repository, Any]],
    ) -> None:
        if dm.capabilities.supports_colors:
            # This script may be called early within the development cycle, so not using colorama
            col_header_color_on = TextwrapEx.BRIGHT_WHITE_COLOR_ON
            yes_color_on = TextwrapEx.BRIGHT_RED_COLOR_ON

            release_branch_color_on = TextwrapEx.BRIGHT_GREEN_COLOR_ON
            default_branch_color_on = TextwrapEx.BRIGHT_WHITE_COLOR_ON
            other_branch_color_on = TextwrapEx.BRIGHT_YELLOW_COLOR_ON

            color_off = TextwrapEx.COLOR_OFF
        else:
            col_header_color_on = ""
            yes_color_on = ""

            release_branch_color_on = ""
            default_branch_color_on = ""
            other_branch_color_on = ""

            color_off = ""

        with dm.YieldStream() as stream:
            stream.write("\n")

            # ----------------------------------------------------------------------
            def DecorateBranch(
                repository: Repository,
                branch_name: str,
                justified_value: str,
            ) -> str:
                if branch_name == repository.scm.default_branch_name:
                    color_on = default_branch_color_on
                elif branch_name == repository.scm.release_branch_name:
                    color_on = release_branch_color_on
                else:
                    color_on = other_branch_color_on

                return "{}{}{}".format(color_on, justified_value, color_off)

            # ----------------------------------------------------------------------
            def DecorateRow(
                row_index: int,
                cols: List[str],
            ) -> List[str]:
                cols[0] = "{}{}{}".format(col_header_color_on, cols[0], color_off)

                if row_index >= 0:
                    repository, (change_status, current_branch) = repositories[row_index]

                    cols[2] = DecorateBranch(repository, change_status.most_recent_branch, cols[2])
                    cols[3] = DecorateBranch(repository, current_branch, cols[3])

                    for index, value in [
                        (4, change_status.has_untracked_changes),
                        (5, change_status.has_working_changes),
                        (6, change_status.has_local_changes),
                        (7, change_status.has_remote_changes),
                        (8, change_status.has_update_changes),
                    ]:
                        if value:
                            cols[index] = "{}{}{}".format(yes_color_on, cols[index], color_off)

                return cols

            # ----------------------------------------------------------------------
            def WriteHeader(
                col_sizes: List[int],
            ) -> None:
                whitespace_padding = 2

                first_branch_col = 2
                first_change_col = 4

                branch_width = sum(col_sizes[first_branch_col: first_change_col]) + whitespace_padding * (first_change_col - first_branch_col - 1)
                changes_width = sum(col_sizes[first_change_col:]) + whitespace_padding * (len(col_sizes[first_change_col:]) - 1)

                stream.write(
                    textwrap.dedent(
                        """\
                        {initial_padding}{branch_name}  {change_name}
                        {initial_padding}{branch_decorator}  {change_decorator}

                        """,
                    ).format(
                        initial_padding=" " * (sum(col_sizes[:first_branch_col]) + whitespace_padding * first_branch_col),
                        branch_name="Branches".center(branch_width),
                        change_name="Changes".center(changes_width),
                        branch_decorator="/{}\\".format("-" * (branch_width - 2)),
                        change_decorator="/{}\\".format("-" * (changes_width - 2)),
                    ),
                )

            # ----------------------------------------------------------------------

            stream.write(
                TextwrapEx.CreateTable(
                    [
                        "Directory (relative to '{}')".format(str(root)),
                        "SCM",
                        "Most Recent",
                        "Current",
                        "Untracked",
                        "Working",
                        "Local",
                        "Remote",
                        "Update",
                    ],
                    [
                        [
                            "{}{}".format(os.path.sep, str(PathEx.CreateRelativePath(root, repository.repo_root))),
                            repository.scm.name,
                            change_status.most_recent_branch,
                            most_recent_branch,
                            "Yes" if change_status.has_untracked_changes else "No",
                            "Yes" if change_status.has_working_changes else "No",
                            "Yes" if change_status.has_local_changes else "No",
                            "Yes" if change_status.has_remote_changes else "No",
                            "Yes" if change_status.has_update_changes else "No",
                        ]
                        for repository, (change_status, most_recent_branch) in repositories
                    ],
                    [
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Left,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                        TextwrapEx.Justify.Center,
                    ],
                    decorate_values_func=DecorateRow,
                    decorate_headers=True,
                    on_col_sizes_calculated=WriteHeader,
                ),
            )

            stream.write("\n")

    # ----------------------------------------------------------------------

    return _WrapAll(
        "Getting distributed change statuses...",
        GetRepoInfo,
        None,
        None,
        root,
        verbose=verbose,
        requires_distributed_repository=True,
        global_action_callback=GlobalCallback,
    )


# ----------------------------------------------------------------------
@app.command("UpdateAll", rich_help_panel="Group Commands", no_args_is_help=True)
def UpdateAll(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """Execute 'Update' for a group of repositories."""

    return _WrapAll(
        "HasUpdateChanges",
        lambda repo: cast(DistributedRepository, repo).HasUpdateChanges(),
        "Update",
        lambda repo, _: cast(DistributedRepository, repo).Update(None),
        root,
        verbose=verbose,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("PushAll", rich_help_panel="Group Commands", no_args_is_help=True)
def PushAll(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """Execute 'Push' for a group of repositories."""

    return _WrapAll(
        "HasLocalChanges",
        lambda repo: cast(DistributedRepository, repo).HasLocalChanges(),
        "Push",
        lambda repo, _: cast(DistributedRepository, repo).Push(),
        root,
        verbose=verbose,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("PullAll", rich_help_panel="Group Commands", no_args_is_help=True)
def PullAll(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """Execute 'Pull' for a group of repositories."""

    return _WrapAll(
        "HasRemoteChanges",
        lambda repo: cast(DistributedRepository, repo).HasRemoteChanges(),
        "Pull",
        lambda repo, _: cast(DistributedRepository, repo).Pull(),
        root,
        verbose=verbose,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
@app.command("PullAndUpdateAll", rich_help_panel="Group Commands", no_args_is_help=True)
def PullAndUpdateAll(
    root: Path=_group_commands_root_argument,
    verbose: bool=_verbose_option,
):
    """Execute 'PullAndUpdate' for a group of repositories."""

    return _WrapAll(
        "HasRemoteChanges",
        lambda repo: cast(DistributedRepository, repo).HasRemoteChanges(),
        "PullAndUpdate",
        lambda repo, _: cast(DistributedRepository, repo).PullAndUpdate(),
        root,
        verbose=verbose,
        requires_distributed_repository=True,
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _GetSCM(
    repo_root: Optional[Path],
    scm_name: Optional[Scm],  # type: ignore
) -> SourceControlManager:
    assert repo_root is not None or scm_name is not None

    scm: Optional[SourceControlManager] = None

    if scm_name is not None:
        name = scm_name.value

        for potential_scm in ALL_SCMS:
            if potential_scm.name == name:
                scm = potential_scm
                break

        if scm is None:
            raise Exception("'{}' is not a recognized SCM name.".format(name))

    if scm is not None:
        if repo_root is not None and not scm.IsActive(repo_root):
            raise Exception("'{}' is not active in '{}'.".format(scm.name, str(repo_root)))

        return scm

    assert repo_root is not None

    for scm in ALL_SCMS:
        if scm.IsActive(repo_root):
            return scm

    raise UsageError("No SCMs are active in '{}'.".format(str(repo_root)))


# ----------------------------------------------------------------------
def _CreateUpdateMergeArg(
    change: Optional[str],
    branch: Optional[str],
    date: Optional[datetime],
) -> Union[
    None,
    UpdateMergeArgs.Change,
    UpdateMergeArgs.Date,
    UpdateMergeArgs.Branch,
    UpdateMergeArgs.BranchAndDate,
]:
    if change:
        if branch or date:
            raise typer.BadParameter("branch and date are not valid when a change is specified.")

        return UpdateMergeArgs.Change(change)

    if branch and date:
        return UpdateMergeArgs.BranchAndDate(branch, date)

    if branch:
        return UpdateMergeArgs.Branch(branch)

    if date:
        return UpdateMergeArgs.Date(date)

    return None


# ----------------------------------------------------------------------
def _Wrap(
    method_name: str,
    get_command_line_func: Callable[[Repository], str],
    invoke: Callable[[Repository], Any],
    repo_root: Path,
    scm_name: Optional[Scm],  # type: ignore
    *,
    requires_distributed_repository: bool=False,
) -> None:
    with DoneManager.CreateCommandLine() as dm:
        with dm.Nested("Calculating SCM...", suffix="\n"):
            scm = _GetSCM(repo_root, scm_name)

        with dm.Nested("Executing '{}' using '{}'...".format(method_name, scm.name), prefix="\n") as nested_dm:
            repository = scm.Open(repo_root)

            if requires_distributed_repository and not isinstance(repository, DistributedRepository):
                raise Exception("'{}' is not a distributed SCM.".format(scm.name))

            command_line = get_command_line_func(repository)

            with nested_dm.YieldStream() as stream:
                stream.write(
                    textwrap.dedent(
                        """\
                        Command Line:       {}
                        """,
                    ).format(command_line),
                )
                stream.flush()

                result = invoke(repository)

                if isinstance(result, SubprocessEx.RunResult):
                    return_code = result.returncode
                    output = result.output
                else:
                    return_code = 0
                    output = result

                nested_dm.result = return_code

                sink = io.StringIO()
                _DisplayResults(sink, output)
                sink = sink.getvalue()

                stream.write(
                    textwrap.dedent(
                        """\
                        Working Directory:  {}

                        Return Code:        {}
                        Output:
                        {}
                        """,
                    ).format(
                        str(repo_root),
                        nested_dm.result,
                        TextwrapEx.Indent(sink.rstrip(), 4),
                    ),
                )


# ----------------------------------------------------------------------
def _WrapAll(
    query_desc: str,
    query_callback: Callable[[Repository], Any],        # Needs to evaluate to True
    repo_action_desc: Optional[str],
    repo_action_callback: Optional[Callable[[Repository, Any], Any]],
    root: Path,
    *,
    verbose: bool,

    requires_distributed_repository: bool=False,
    global_action_callback: Optional[Callable[[DoneManager, List[Tuple[Repository, Any]]], None]]=None,
) -> None:
    assert (
        (repo_action_desc is None and repo_action_callback is None)
        or (repo_action_desc is not None and repo_action_callback is not None)
    ), (repo_action_desc, repo_action_callback)

    assert (
        (repo_action_callback is None and global_action_callback is None)
        or (repo_action_callback is not None and global_action_callback is None)
        or (repo_action_callback is None and global_action_callback is not None)
    ), (repo_action_callback, global_action_callback)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        # Get the repositories
        repositories: List[Repository] = []

        with dm.Nested(
            "Searching for repositories in '{}'...".format(str(root)),
            lambda: "{} found".format(inflect.no("repository", len(repositories))),
            suffix="\n" if dm.is_verbose else "",
        ) as search_dm:
            for repository in _EnumRepositories(root):
                if requires_distributed_repository and not isinstance(repository, DistributedRepository):
                    continue

                search_dm.WriteVerbose("[{}] {}\n".format(repository.scm.name, str(repository.repo_root)))
                repositories.append(repository)

        if not repositories:
            return

        # Query
        query_repositories: List[Tuple[Repository, Any]] = []

        with dm.Nested(
            query_desc,
            lambda: "{} matched".format(inflect.no("repository", len(query_repositories))),
            suffix="\n" if dm.is_verbose else "",
        ) as query_dm:
            query_results: List[Optional[Any]] = [None for _ in range(len(repositories))]
            exceptions: List[Optional[Exception]] = [None for _ in range(len(repositories))]

            with query_dm.YieldStdout() as context:
                context.persist_content = False

                with Progress(
                    transient=True,
                ) as progress:
                    total_progress_id = progress.add_task("{}Total Progress".format(context.line_prefix), total=len(repositories))

                    with ThreadPoolExecutor(
                        min(len(repositories), multiprocessing.cpu_count()),
                    ) as executor:
                        futures = []

                        # ----------------------------------------------------------------------
                        def QueryFunc(
                            index: int,
                            task_id: TaskID,
                            repository: Repository,
                        ) -> None:
                            progress.update(task_id, visible=True)
                            with ExitStack(
                                lambda: progress.update(task_id, completed=True, visible=False),
                                lambda: progress.advance(total_progress_id, 1),
                            ):
                                try:
                                    query_results[index] = query_callback(repository)
                                except Exception as ex:
                                    exceptions[index] = ex

                        # ----------------------------------------------------------------------

                        for index, repository in enumerate(repositories):
                            futures.append(
                                executor.submit(
                                    QueryFunc,
                                    index,
                                    progress.add_task(
                                        "{}  {}".format(context.line_prefix, str(repository.repo_root)),
                                        total=1,
                                        visible=False,
                                    ),
                                    repository,
                                ),
                            )

                        for future in futures:
                            future.result()

            for query_result, ex, repository in zip(query_results, exceptions, repositories):
                if ex is not None:
                    query_dm.result = -1

                    query_dm.WriteError(
                        textwrap.dedent(
                            """\
                            {}
                            {}

                            """,
                        ).format(
                            str(repository.repo_root),
                            TextwrapEx.Indent(str(ex), 4),
                        ),
                    )

                    continue

                if query_result:
                    query_dm.WriteVerbose("[{}] {}\n".format(repository.scm.name, str(repository.repo_root)))
                    query_repositories.append((repository, query_result))

            if query_dm.result != 0:
                return

        if not query_repositories:
            dm.WriteLine("\nNo repositories to process.\n")
            return

        # Actions
        if global_action_callback:
            global_action_callback(dm, query_repositories)

        elif repo_action_callback:
            assert repo_action_desc is not None

            with dm.Nested(
                repo_action_desc,
                lambda: "{} processed".format(inflect.no("repository", len(query_repositories))),
            ) as action_dm:
                with action_dm.YieldStdout() as context:
                    context.persist_content = False

                    action_results: List[Any] = [None for _ in range(len(query_repositories))]
                    exceptions: List[Optional[Exception]] = [None for _ in range(len(query_repositories))]

                    with Progress(
                        transient=True,
                    ) as progress:
                        total_progress_id = progress.add_task("{}Total Progress".format(context.line_prefix), total=len(query_repositories))

                        with ThreadPoolExecutor(
                            min(len(query_repositories), multiprocessing.cpu_count()),
                        ) as executor:
                            futures = []

                            # ----------------------------------------------------------------------
                            def ActionFunc(
                                index: int,
                                task_id: TaskID,
                                repository: Repository,
                                query_result: Any,
                            ) -> None:
                                progress.update(task_id, visible=True)
                                with ExitStack(
                                    lambda: progress.update(task_id, completed=True, visible=False),
                                    lambda: progress.advance(total_progress_id, 1),
                                ):
                                    try:
                                        action_results[index] = repo_action_callback(repository, query_result)
                                    except Exception as ex:
                                        exceptions[index] = ex

                            # ----------------------------------------------------------------------

                            for index, (repository, query_result) in enumerate(query_repositories):
                                futures.append(
                                    executor.submit(
                                        ActionFunc,
                                        index,
                                        progress.add_task(
                                            "{}  {}:".format(context.line_prefix, str(repository.repo_root)),
                                            total=1,
                                            visible=False,
                                        ),
                                        repository,
                                        query_result,
                                    ),
                                )

                            for future in futures:
                                future.result()

                for action_result, ex, repository in zip(action_results, exceptions, repositories):
                    if ex is not None:
                        action_dm.result = -1

                        action_dm.WriteError(
                            textwrap.dedent(
                                """\
                                {}
                                {}

                                """,
                            ).format(
                                str(repository.repo_root),
                                TextwrapEx.Indent(str(ex), 4),
                            ),
                        )

                        continue

                    sink = io.StringIO()
                    _DisplayResults(sink, action_result)
                    sink = sink.getvalue().rstrip()

                    action_dm.WriteVerbose(
                        textwrap.dedent(
                            """\
                            {}
                            {}

                            """,
                        ).format(
                            str(repository.repo_root),
                            TextwrapEx.Indent(sink, 4),
                        ),
                    )

                if action_dm.result != 0:
                    return


# ----------------------------------------------------------------------
def _EnumRepositories(
    root_dir: Path,
) -> Generator[Repository, None, None]:
    foundation_dir = os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")
    assert foundation_dir is not None

    sys.path.insert(0, foundation_dir)
    with ExitStack(lambda: sys.path.pop(0)):
        from RepositoryBootstrap import Constants as RepositoryBootstrapConstants  # pylint: disable=import-error

    for root, directories, _ in os.walk(root_dir):
        root = Path(root)

        for scm in ALL_SCMS:
            if scm.IsRoot(root):
                yield scm.Open(root)

                # Don't search in subdirs, as there won't be any
                directories[:] = []
                break

        if RepositoryBootstrapConstants.GENERATED_DIRECTORY_NAME in directories:
            # Don't search in generated dirs, as the symlinks will cause recursive enumerations
            directories.remove(RepositoryBootstrapConstants.GENERATED_DIRECTORY_NAME)


# ----------------------------------------------------------------------
def _DisplayResults(
    stream: Union[TextIO, StreamDecorator],
    result: Any,
) -> None:
    if isinstance(result, str):
        stream.write(result)
        stream.write("\n")

    elif isinstance(result, (bool, int, Path)):
        stream.write(str(result))
        stream.write("\n")

    elif isinstance(result, types.GeneratorType):
        for index, value in enumerate(result):
            stream.write("{}) ".format(index))
            _DisplayResults(stream, value)

        stream.write("\n")

    elif isinstance(result, list):
        for index, item in enumerate(result):
            stream.write("{}) ".format(index))
            _DisplayResults(stream, item)

    elif hasattr(result, "__dict__") or isinstance(result, dict):
        d = getattr(result, "__dict__", result)

        max_length = 0

        for key in d.keys():
            max_length = max(max_length, len(key))

        max_length += 1

        for k, v in d.items():
            sink = io.StringIO()

            _DisplayResults(sink, v)
            sink = sink.getvalue().rstrip()

            stream.write(
                "{} {}\n".format(
                    "{}:".format(k).ljust(max_length),
                    TextwrapEx.Indent(sink, max_length + 1, skip_first_line=True),
                ),
            )
    else:
        assert False, (type(result), result)  # pragma: no cover


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
