# ----------------------------------------------------------------------
# |
# |  SourceControlManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-20 18:50:53
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains abstract objects used in the creation of Source Control Managers (SCMs)"""

import sys
import textwrap

from abc import abstractmethod, ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Generator, Optional, Union

from . import UpdateMergeArgs

from .. import SubprocessEx


# ----------------------------------------------------------------------
class SourceControlManager(ABC):
    """Abstract base class for a Source Control Manager (SCM) like git or Mercurial"""

    # ----------------------------------------------------------------------
    # |
    # |  Public Properties
    # |
    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def default_branch_name(self) -> str:
        """\
        Name of the default branch for the system. This name will be used when a specific
        branch is not provided.
        """
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def release_branch_name(self) -> str:
        """Name of the branch typically used to release code"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def tip(self) -> str:
        """Name used in the SCM's command line args to represent the most recent change"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def working_directories(self) -> Optional[List[str]]:
        """Names of directories used by the derived SCM to track changes. Return None if the SCM tracks changes in some other way"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def ignore_filename(self) -> Optional[str]:
        """Name of a file used to track files that should be ignored by the system; this can be None if the system doesn't make use of such a file"""
        raise Exception("Abstract property")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def IsAvailable(self) -> bool:
        """Return True if the SCM is available on this system"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def IsActive(
        self,
        directory: Path,
        *,
        traverse_ancestors: bool=False,
    ) -> Optional[Path]:
        """Return True if the SCM is available and active for the provided root"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def IsRoot(
        self,
        directory: Path,
    ) -> bool:
        return any(
            (directory / working_directory).is_dir()
            for working_directory in (self.working_directories or [])
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def Create(
        self,
        output_dir: Path,
    ) -> "Repository":
        """Creates a repository in the provided output directory."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def Clone(
        self,
        uri: str,
        output_dir: Path,
        branch: Optional[str]=None,
    ) -> "Repository":
        """Clones a repository in the provided output directory; `default_branch_name` will be used if no branch is provided."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def Open(
        self,
        path: Path,
    ) -> "Repository":
        """Opens a repository associated with the provided path."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _Execute(
        self,
        command_line: str,
        *,
        strip: bool=False,
        add_newline: bool=False,
    ) -> SubprocessEx.RunResult:

        result = SubprocessEx.Run(command_line)

        if strip:
            result.output = result.output.strip()
        if add_newline:
            result.output += "\n"

        return result


# ----------------------------------------------------------------------
class Repository(ABC):
    """Abstract base class for a repository associated with a SourceControlManager"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        scm: SourceControlManager,
        repo_root: Path,
    ):
        self.scm                            = scm
        self.repo_root                      = repo_root.resolve()

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetGetUniqueNameCommandLine(self) -> str:
        """Returns the command line used to implement Repository.GetUniqueName"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetUniqueName(self) -> str:
        """Returns a unique name for the repository active at the provided root."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetWhoCommandLine(self) -> str:
        """Returns the command line used to implement Repository.Who"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def Who(self) -> str:
        """Returns the username associated with the specified repo."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCleanCommandLine(self) -> str:
        """Returns the command line used to implement Repository.Clean"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Clean(
        self,
        no_prompt: bool=False,
    ) -> SubprocessEx.RunResult:
        """Reverts any changes in the local working directory."""

        if not no_prompt and not self._AreYouSurePrompt(
            textwrap.dedent(
                """\
                This operation will revert any working changes.

                THIS INCLUDES THE FOLLOWING:
                    - Any working edits
                    - Any files that have been added
                """,
            ),
        ):
            return SubprocessEx.RunResult(0, "<<Skipped>>")

        return self._Execute(self.GetCleanCommandLine())

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumBranchesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.EnumBranches"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumBranches(self) -> Generator[str, None, None]:
        """Enumerates all local branches."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetGetCurrentBranchCommandLine(self) -> str:
        """Returns the command line used to implement Repository.GetCurrentBranch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCurrentBranch(self) -> str:
        """Returns the current branch."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def GetGetCurrentNormalizedBranchCommandLine(self) -> str:
        """Returns the command line used to implement Repository.GetCurrentNormalizedBranch"""
        return self.GetGetCurrentBranchCommandLine()

    # ----------------------------------------------------------------------
    def GetCurrentNormalizedBranch(self) -> str:
        """Returns a branch name that removes any decoration associated with its state relative to its peers (for example, git's decoration for a branch that is in a detached head state)."""

        # Some SCMs (such as Git) need to do wonky things to ensure that branches
        # stay consistent (e.g. to avoid a detached head state), such as decorating
        # branch names. These wonky things may present problems for other programs,
        # so this method will expose standard names that un-decorate the actual
        # branch name.

        return self.GetCurrentBranch()

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetGetMostRecentBranchCommandLine(self) -> str:
        """Returns the command line used to implement Repository.GetMostRecentBranch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetMostRecentBranch(self) -> str:
        """Returns the name of the branch associated with the most recent change."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCreateBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        """Returns the command line used to implement Repository.CreateBranch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def CreateBranch(
        self,
        branch_name: str,
    ) -> SubprocessEx.RunResult:
        """Creates a new branch."""

        return self._Execute(self.GetCreateBranchCommandLine(branch_name))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetSetBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        """Returns the command line used to implement Repository.SetBranch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def SetBranch(
        self,
        branch_name: str,
    ) -> SubprocessEx.RunResult:
        """Updates the working directory to the specified branch."""

        return self._Execute(self.GetSetBranchCommandLine(branch_name))

    # ----------------------------------------------------------------------
    def GetSetBranchOrDefaultCommandLine(
        self,
        branch_name: str,
    ) -> str:
        """Returns the command line used to implement Repository.SetBranchOrDefault"""

        if branch_name in self.EnumBranches():
            return self.GetSetBranchCommandLine(branch_name)

        return self.GetSetBranchCommandLine(self.scm.default_branch_name)

    # ----------------------------------------------------------------------
    def SetBranchOrDefault(
        self,
        branch_name: str,
    ) -> SubprocessEx.RunResult:
        """Updates the working directory to the provided branch or the default branch if the provided branch does not exist."""

        return self.SetBranch(
            branch_name if branch_name in self.EnumBranches() else self.scm.default_branch_name,
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetGetExecutePermissionCommandLine(
        self,
        filename: Path,
    ) -> str:
        """Returns the command line used to implement Repository.GetExecutePermission"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetExecutePermission(
        self,
        filename: Path,
    ) -> bool:
        """Returns the stored execute permission for the provided file."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetSetExecutePermissionCommandLine(
        self,
        filename: Path,
        is_executable: bool,
        commit_message: Optional[str]=None,
    ) -> str:
        """Returns the command line used to implement Repository.SetExecutePermission"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def SetExecutePermission(
        self,
        filename: Path,
        is_executable: bool,
        commit_message: Optional[str]=None,
    ) -> SubprocessEx.RunResult:
        """Sets the stored execute permission fro the provided file (note that this will result in a commit with some SCMs)."""

        return self._Execute(
            self.GetSetExecutePermissionCommandLine(filename, is_executable, commit_message),
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetHasUntrackedWorkingChangesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.HasUntrackedWorkingChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def HasUntrackedWorkingChanges(self) -> bool:
        """Returns True if there are local changes that are not tracked by the repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumUntrackedWorkingChangesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.EnumUntrackedWorkingChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumUntrackedWorkingChanges(self) -> Generator[Path, None, None]:
        """Enumerates the filenames of all files that are not tracked by the repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetHasWorkingChangesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.HasWorkingChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def HasWorkingChanges(self) -> bool:
        """Returns True if there are local changes in files tracked by the repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumWorkingChangesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.EnumWorkingChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumWorkingChanges(self) -> Generator[Path, None, None]:
        """Enumerates the filenames of all files with changes that are tracked by the repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def GetGetChangeStatusCommandLine(
        self,
    ) -> str:
        """Returns the command line used to implement Repository.GetChangeStatus"""
        return " && ".join(
            [
                self.GetHasUntrackedWorkingChangesCommandLine(),
                self.GetHasWorkingChangesCommandLine(),
            ],
        )

    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class GetChangeStatusResult(object):
        has_untracked_changes: bool
        has_standard_changes: bool

    def GetChangeStatus(self) -> "Repository.GetChangeStatusResult":
        """Returns change status information about the repository."""

        return Repository.GetChangeStatusResult(
            self.HasUntrackedWorkingChanges(),
            self.HasWorkingChanges(),
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetGetChangeInfoCommandLine(
        self,
        change: str,
    ) -> str:
        """Returns the command line used to implement Repository.GetChangeInfo"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def GetChangeInfo(
        self,
        change: str,
    ) -> Dict[str, Any]:
        """Returns information about a specific change."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetAddFilesCommandLine(
        self,
        filename_or_filenames: Union[
            Path,
            List[Path],
        ],
    ) -> str:
        """Returns the command line used to implement Repository.AddFiles"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def AddFiles(
        self,
        filename_or_filenames: Union[
            Path,
            List[Path],
        ],
    ) -> SubprocessEx.RunResult:
        """Adds files to the repository."""

        return self._Execute(self.GetAddFilesCommandLine(filename_or_filenames))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCommitCommandLine(
        self,
        description: str,
        username: Optional[str]=None,
    ) -> str:
        """Returns the command line used to implement Repository.Commit"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Commit(
        self,
        description: str,
        username: Optional[str]=None,
    ) -> SubprocessEx.RunResult:
        """Commits changes to the repository."""

        return self._Execute(self.GetCommitCommandLine(description, username))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetUpdateCommandLine(
        self,
        update_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> str:
        """Returns the command line used to implement Repository.Update"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Update(
        self,
        update_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> SubprocessEx.RunResult:
        """Updates the working directory."""

        return self._Execute(self.GetUpdateCommandLine(update_arg))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetMergeCommandLine(
        self,
        merge_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> str:
        """Returns the command line used to implement Repository.Merge"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Merge(
        self,
        merge_arg: Union[
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> SubprocessEx.RunResult:
        """Merges changes."""

        return self._Execute(self.GetMergeCommandLine(merge_arg))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumChangesSinceMergeCommandLine(
        self,
        dest_branch: str,
        source_merge_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> str:
        """Returns the command line used to implement Repository.EnumChangesSinceMerge"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumChangesSinceMerge(
        self,
        dest_branch: str,
        source_merge_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> Generator[str, None, None]:
        """Enumerates changes since the specified merge."""

        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumChangedFilesCommandLine(
        self,
        change: str,
    ) -> str:
        """Returns the command line used to implement Repository.EnumChangedFiles"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumChangedFiles(
        self,
        change: str,
    ) -> Generator[Path, None, None]:
        """Enumerates files modified as a part of the specified change."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumBlameInfoCommandLine(
        self,
        filename: Path,
    ) -> str:
        """Returns the command line used to implement Repository.EnumBlameInfo"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class EnumBlameInfoResult(object):
        change: str
        line: str

    @abstractmethod
    def EnumBlameInfo(
        self,
        filename: Path,
    ) -> Generator["Repository.EnumBlameInfoResult", None, None]:
        """Enumerates blame information for the specified filename."""

        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumTrackedFilesCommandLine(self) -> str:
        """Returns the command line used to implement Repository.EnumTrackedFiles"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumTrackedFiles(self) -> Generator[Path, None, None]:
        """Enumerates files tracked by the repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCreatePatchCommandLine(
        self,
        output_filename: Path,
        start_change: Optional[str]=None,
        end_change: Optional[str]=None,
    ) -> str:
        """Returns the command line used to implement Repository.CreatePatch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def CreatePatch(
        self,
        output_filename: Path,
        start_change: Optional[str]=None,
        end_change: Optional[str]=None,
    ) -> SubprocessEx.RunResult:
        """Creates a patch."""

        return self._Execute(
            self.GetCreatePatchCommandLine(output_filename, start_change, end_change),
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetApplyPatchCommandLine(
        self,
        patch_filename: Path,
        commit: bool=False,
    ) -> str:
        """Returns the command line used to implement Repository.ApplyPatch"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def ApplyPatch(
        self,
        patch_filename: Path,
        commit: bool=False,
    ) -> SubprocessEx.RunResult:
        """Applies a created patch."""

        return self._Execute(self.GetApplyPatchCommandLine(patch_filename, commit))

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _Execute(self, *args, **kwargs) -> SubprocessEx.RunResult:
        return self.scm._Execute(*args, **kwargs)  # pylint: disable=protected-access

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @staticmethod
    def _AreYouSurePrompt(
        prompt: str,
    ) -> bool:
        result = input(
            textwrap.dedent(
                """\
                {}

                Enter 'y' to continue or anything else to exit: """,
            ).format(prompt.rstrip()),
        ).strip() == 'y'
        sys.stdout.write("\n")

        return result


# ----------------------------------------------------------------------
class DistributedRepository(Repository):
    """Abstract base class for a repository associated with a distributed SourceControlManager"""

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetResetCommandLine(
        self,
        no_backup: bool=False,
    ) -> str:
        """Returns the command line used to implement DistributedRepository.Reset"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Reset(
        self,
        no_prompt: bool=False,
        no_backup: bool=False,
    ) -> SubprocessEx.RunResult:
        """Resets the repo to the remote state, erasing any un-pushed (but committed) changes."""

        if not no_prompt and not self._AreYouSurePrompt(
            textwrap.dedent(
                """\
                This operation will revert your local repository to match the state of the remote repository.

                THIS INCLUDES THE FOLLOWING:
                    - Any working edits
                    - Any files that have been added
                    - Any committed changes that have not been pushed to the remote repository
                """,
            ),
        ):
            return SubprocessEx.RunResult(0, "<<Skipped>>")

        return self._Execute(self.GetResetCommandLine(no_backup))


    # ----------------------------------------------------------------------
    @abstractmethod
    def GetHasUpdateChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.HasUpdateChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def HasUpdateChanges(self) -> bool:
        """Returns True if there are changes on the local branch that have not yet been applied to the working directory."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumUpdateChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.EnumUpdateChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumUpdateChanges(self) -> Generator[Path, None, None]:
        """Enumerates filenames associated with changes that have not yet been applied to the working directory."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetHasLocalChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.HasLocalChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def HasLocalChanges(self) -> bool:
        """Returns True if there are changes committed in the local branch that have not yet been pushed to the remote repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumLocalChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.EnumLocalChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumLocalChanges(self) -> Generator[str, None, None]:
        """Enumerates filenames associated with committed changes that have not yet been pushed to the remote repository."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetHasRemoteChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.HasRemoteChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def HasRemoteChanges(self) -> bool:
        """Returns True if there are changes in the remote repository that have not yet been pulled."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetEnumRemoteChangesCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.EnumRemoteChanges"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def EnumRemoteChanges(self) -> Generator[str, None, None]:
        """Enumerates filenames associated with changes at the remote repository that have not yet been pulled."""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def GetGetDistributedChangeStatusCommandLine(self) -> str:
        """Returns the command line used to implement DistributedRepository.GetDistributedChangeStatus"""

        return " && ".join(
            [
                self.GetHasUntrackedWorkingChangesCommandLine(),
                self.GetHasWorkingChangesCommandLine(),
                self.GetHasLocalChangesCommandLine(),
                self.GetHasRemoteChangesCommandLine(),
                self.GetHasUpdateChangesCommandLine(),
                self.GetGetMostRecentBranchCommandLine(),
            ],
        )

    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class GetDistributedChangeStatusResult(object):
        has_untracked_changes: bool
        has_working_changes: bool
        has_local_changes: bool
        has_remote_changes: bool
        has_update_changes: bool
        most_recent_branch: str

    def GetDistributedChangeStatus(self) -> "DistributedRepository.GetDistributedChangeStatusResult":
        """Returns change status information about the distributed repository."""

        return DistributedRepository.GetDistributedChangeStatusResult(
            self.HasUntrackedWorkingChanges(),
            self.HasWorkingChanges(),
            self.HasLocalChanges(),
            self.HasRemoteChanges(),
            self.HasUpdateChanges(),
            self.GetMostRecentBranch(),
        )

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetPushCommandLine(
        self,
        create_remote_branch: bool=False,
    ) -> str:
        """Returns the command line used to implement DistributedRepository.Push"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Push(
        self,
        create_remote_branch: bool=False,
    ) -> SubprocessEx.RunResult:
        """Pushes changes to the remote repository."""

        return self._Execute(self.GetPushCommandLine(create_remote_branch))

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetPullCommandLine(
        self,
        branch_or_branches: Union[None, str, List[str]]=None,
    ) -> str:
        """Returns the command line used to implement DistributedRepository.Pull"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def Pull(
        self,
        branch_or_branches: Union[None, str, List[str]]=None,
    ) -> SubprocessEx.RunResult:
        """Pulls changes from the remote repository."""

        return self._Execute(self.GetPullCommandLine(branch_or_branches))

    # ----------------------------------------------------------------------
    def GetPullAndUpdateCommandLine(self) -> str:
        return "{} && {}".format(self.GetPullCommandLine(None), self.GetUpdateCommandLine(None))

    # ----------------------------------------------------------------------
    def PullAndUpdate(self) -> SubprocessEx.RunResult:
        """Pulls changes from the remote repository and updates the working directory."""

        result = self.Pull(None)
        if result.returncode != 0:
            return result

        update_result = self.Update(None)

        result.returncode = update_result.returncode
        result.output = "{}\n\n{}".format(result.output.rstrip(), update_result.output)

        return result
