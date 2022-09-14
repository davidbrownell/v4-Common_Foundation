# ----------------------------------------------------------------------
# |
# |  GitSourceControlManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 08:56:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the GitSourceControlManager object"""

import re

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Generator, Optional, Union

from .SourceControlManager import DistributedRepository as DistributedRepositoryBase, SourceControlManager, UpdateMergeArgs

from ..ContextlibEx import ExitStack
from .. import RegularExpression
from ..Shell.All import CurrentShell


# ----------------------------------------------------------------------
class GitSourceControlManager(SourceControlManager):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(GitSourceControlManager, self).__init__()

        self._is_available: Optional[bool]  = None

    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Git"

    @property
    def default_branch_name(self) -> str:
        return "master"

    @property
    def release_branch_name(self) -> str:
        return "release"

    @property
    def tip(self) -> str:
        return "head"

    @property
    def working_directories(self) -> Optional[List[str]]:
        return [".git", ]

    @property
    def ignore_filename(self) -> Optional[str]:
        return ".gitignore"

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def IsAvailable(self) -> bool:
        if self._is_available is None:
            result = self._Execute("git")
            self._is_available = "usage: git" in result.output

        assert self._is_available is not None
        return self._is_available

    # ----------------------------------------------------------------------
    def IsActive(
        self,
        directory: Path,
        *,
        traverse_ancestors: bool=False,
    ) -> Optional[Path]:
        if not self.IsAvailable():
            return None

        # hg automatically traverses ancestors, so we don't need to do anything special to
        # implement that functionality.

        result = self._Execute('git -C "{}" rev-parse --show-toplevel'.format(str(directory)), strip=True)

        if result.returncode == 0:
            result = Path(result.output)
            assert result.is_dir(), result
        else:
            result = None

        return result

    # ----------------------------------------------------------------------
    def Create(
        self,
        output_dir: Path,
    ) -> "Repository":
        output_dir.mkdir(parents=True, exist_ok=True)

        result = self._Execute('git init "{}"'.format(str(output_dir)))

        if result.returncode != 0:
            raise Exception(result.output)

        return Repository(self, output_dir)

    # ----------------------------------------------------------------------
    def Clone(
        self,
        uri: str,
        output_dir: Path,
        branch: Optional[str]=None,
    ) -> "Repository":
        if output_dir.is_dir():
            raise Exception("The directory '{}' already exists and will not be overwritten.".format(str(output_dir)))

        output_dir.parent.mkdir(parents=True, exist_ok=True)

        temp_clone_dir = Path("{}.tmp".format(output_dir))

        result = self._Execute(
            'git -C "{dir}" clone{branch} "{uri}" "{name}"'.format(
                dir=str(output_dir.parent),
                branch= ' --branch "{}"'.format(branch) if branch is not None else "",
                uri=uri,
                name=temp_clone_dir.name,
            ),
        )

        if result.returncode != 0:
            raise Exception(result.output)

        temp_clone_dir.rename(output_dir)

        return Repository(self, output_dir)

    # ----------------------------------------------------------------------
    def Open(
        self,
        path: Path,
    ) -> "Repository":
        if self.IsRoot(path):
            realized_root = path
        else:
            realized_root = self.IsActive(path)

        if realized_root is None:
            raise Exception("'{}' is not a valid git repository.".format(str(path)))

        return Repository(self, realized_root)


# ----------------------------------------------------------------------
class Repository(DistributedRepositoryBase):
    # ----------------------------------------------------------------------
    DetachedHeadPseudoBranchName            = "__DetachedHeadPseudoBranchName_{index}_{branch_name}__"
    _DetachedHeadPseudoBranchName_regex     = RegularExpression.TemplateStringToRegex(DetachedHeadPseudoBranchName)

    # ----------------------------------------------------------------------
    def GetGetUniqueNameCommandLine(self) -> str:
        return self._GetCommandLine("git remote -v")

    # ----------------------------------------------------------------------
    def GetUniqueName(self) -> str:
        result = self._Execute(self.GetGetUniqueNameCommandLine())
        assert result.returncode == 0, result.output

        regex = re.compile(r"origin\s+(?P<url>.+?)\s+\(fetch\)")

        for line in result.output.split("\n"):
            match = regex.match(line)
            if match:
                return match.group("url")

        # If here, we didn't find anything. Most of the time, this is an indication
        # that the repo is local (no remote). Return the path.
        return str(Path.cwd())

    # ----------------------------------------------------------------------
    def GetWhoCommandLine(self) -> str:
        return self._GetCommandLine(" && ".join(["git config user.name", "git config user.email"]))

    # ----------------------------------------------------------------------
    def Who(self) -> str:
        result = self._Execute(self.GetWhoCommandLine(), strip=True)
        assert result.returncode == 0, result.output

        output = result.output.split("\n")

        assert len(output) == 2, output
        return "{} <{}>".format(output[0], output[1])

    # ----------------------------------------------------------------------
    def GetCleanCommandLine(self) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "git clean -df",
                    "git submodule foreach --recursive git clean -df",
                    "git reset --hard",
                    "git submodule foreach --recursive git reset --hard",
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def GetEnumBranchesCommandLine(self) -> str:
        return self._GetCommandLine("git show-branch --list --all")

    # ----------------------------------------------------------------------
    def EnumBranches(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumBranchesCommandLine())
        assert result.returncode == 0, result.output

        regex = re.compile(r"^\*?\s*\[(origin/)?(?P<name>\S+?)\]\s+.+?")

        for line in result.output.split("\n"):
            match = regex.match(line)
            if match:
                yield match.group("name")

    # ----------------------------------------------------------------------
    def GetGetCurrentBranchCommandLine(self) -> str:
        return self._GetCommandLine("git branch --no-color")

    # ----------------------------------------------------------------------
    def GetCurrentBranch(self) -> str:
        result = self._Execute(self.GetGetCurrentBranchCommandLine())
        assert result.returncode == 0, result.output

        if result.output:
            regex = re.compile(r"\s*\*\s+(?P<name>.+)")

            for line in result.output.split("\n"):
                match = regex.match(line)
                if match:
                    return match.group("name")

        return self.scm.default_branch_name

    # ----------------------------------------------------------------------
    def GetGetMostRecentBranchCommandLine(self) -> str:
        return self._GetCommandLine('git for-each-ref --sort=-committerdate --format="%(refname)"')

    # ----------------------------------------------------------------------
    def GetMostRecentBranch(self) -> str:
        result = self._Execute(self.GetGetMostRecentBranchCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            parts = line.split("/")

            if len(parts) >= 4 and parts[1] == "remotes" and parts[2] == "origin":
                return parts[3]

        assert False, result.output

    # ----------------------------------------------------------------------
    def GetCreateBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        return self._GetCommandLine('git branch "{name}" && git checkout "{name}"'.format(name=branch_name))

    # ----------------------------------------------------------------------
    def GetSetBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        return self._GetCommandLine('git checkout "{}"'.format(branch_name))

    # ----------------------------------------------------------------------
    def GetGetExecutePermissionCommandLine(
        self,
        filename: Path,
    ) -> str:
        return self._GetCommandLine('git ls-files -s "{}"'.format(str(filename)))

    # ----------------------------------------------------------------------
    def GetExecutePermission(
        self,
        filename: Path,
    ) -> bool:
        result = self._Execute(self.GetGetExecutePermissionCommandLine(filename))
        assert result.returncode == 0, result.output

        # The first N chars are digits
        output = result.output.strip()

        index = 0
        while index < len(output) and str.isdigit(output[index]):
            index += 1

        assert index != 0, output

        digits = int(output[:index])

        # The last 3 digits are the permissions
        digits %= 1000

        # The hundreds place is the permission
        digits = int(digits / 100)

        if digits == 6:
            return False
        if digits == 7:
            return True

        assert False, (digits, output)

    # ----------------------------------------------------------------------
    def GetSetExecutePermissionCommandLine(
        self,
        filename: Path,
        is_executable: bool,
        commit_message: Optional[str]=None,
    ) -> str:
        return self._GetCommandLine(
            'git update-index --chmod={sign}x "{filename}"'.format(
                sign="+" if is_executable else "-",
                filename=str(filename),
            ),
        )

    # ----------------------------------------------------------------------
    def GetHasUntrackedWorkingChangesCommandLine(self) -> str:
        return self.GetEnumUntrackedWorkingChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasUntrackedWorkingChanges(self) -> bool:
        for _ in self.EnumUntrackedWorkingChanges():
            return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumUntrackedWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine('git ls-files --others --exclude-standard')

    # ----------------------------------------------------------------------
    def EnumUntrackedWorkingChanges(self) -> Generator[Path, None, None]:
        result = self._Execute(self.GetEnumUntrackedWorkingChangesCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            yield self.repo_root / line

    # ----------------------------------------------------------------------
    def GetHasWorkingChangesCommandLine(self) -> str:
        return self.GetEnumWorkingChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasWorkingChanges(self) -> bool:
        for _ in self.EnumWorkingChanges():
            return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine("git status --short")

    # ----------------------------------------------------------------------
    def EnumWorkingChanges(self) -> Generator[Path, None, None]:
        result = self._Execute(self.GetEnumWorkingChangesCommandLine())
        assert result.returncode == 0, result.output

        regex = re.compile(r"^(?P<type>..)\s+(?P<filename>.+)$")

        for line in result.output.split("\n"):
            match = regex.match(line)
            if match and match.group("type") != "??":
                yield self.repo_root / match.group("filename")

    # ----------------------------------------------------------------------
    def GetGetChangeInfoCommandLine(
        self,
        change: str,
    ) -> str:
        # Note the spaces to work around issues with git
        template = " %aN <%ae> %n %cd %n %s"

        return self._GetCommandLine(
            'git --no-pager show -s --format="{}" "{}"'.format(template, change),
        )

    # ----------------------------------------------------------------------
    def GetChangeInfo(
        self,
        change: str,
    ) -> Dict[str, Any]:
        result = self._Execute(self.GetGetChangeInfoCommandLine(change))
        assert result.returncode == 0, result.output

        lines = result.output.split("\n")
        assert len(lines) >= 3, (len(lines), result.output)

        return {
            "user": lines[0].lstrip(),
            "date": lines[1].lstrip(),
            "summary": lines[2].lstrip(),
            "files": list(self.EnumChangedFiles(change)),
        }

    # ----------------------------------------------------------------------
    def GetAddFilesCommandLine(
        self,
        filename_or_filenames: Union[
            Path,
            List[Path],
        ],
    ) -> str:
        if isinstance(filename_or_filenames, list):
            filenames = filename_or_filenames
        else:
            filenames = [filename_or_filenames, ]

        return self._GetCommandLine(
            "git add {}".format(" ".join('"{}"'.format(str(filename)) for filename in filenames)),
        )

    # ----------------------------------------------------------------------
    def GetCommitCommandLine(
        self,
        description: str,
        username: Optional[str]=None,
    ) -> str:
        # Git is particular about username format; massage it into the right
        # format if necessary.
        if username:
            regex = re.compile(r"(?P<username>.+?)\s+\<(?P<email>.+?)\>")

            match = regex.match(username)
            if not match:
                username = "{} <noreply@Generator.com>".format(username)

        return self._GetCommandLine(
            'git commit -a --allow-empty -m "{desc}"{user}'.format(
                desc=description.replace('"', '\\"'),
                user=' --author="{}"'.format(username) if username else "",
            ),
        )

    # ----------------------------------------------------------------------
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
        branch = self.GetCurrentBranch()

        commands: List[str] = [
            'git merge --ff-only "origin/{}"'.format(branch),
        ]

        if update_arg is None:
            pass
        elif isinstance(update_arg, UpdateMergeArgs.Branch):
            commands.insert(0, 'git checkout "{}"'.format(update_arg.branch))
        elif isinstance(update_arg, (UpdateMergeArgs.Change, UpdateMergeArgs.Branch, UpdateMergeArgs.BranchAndDate)):
            revision = self._GetUpdateMergeArgCommandLine(update_arg)

            # Updating to a specific revision within Git is interesting, as one will find
            # themselves in a "DETACHED HEAD" state. While this makes a lot of sense from
            # a commit perspective, it doesn't make as much sense from a reading perspective
            # (especially in scenarios where it is necessary to derive the branch name from the
            # current state, as will be the case during Reset). To work around this, Update to
            # a new branch that is cleverly named in a way that can be parsed by commands that
            # need this sort of information.
            existing_branch_names = set(self.EnumBranches())

            index = 0
            while True:
                potential_branch_name = self.DetachedHeadPseudoBranchName.format(
                    index=index,
                    branch_name=branch,
                )

                if potential_branch_name not in existing_branch_names:
                    break

                index += 1

            commands.append('git checkout {} -b "{}"'.format(revision, potential_branch_name))
        else:
            assert False, update_arg  # pragma: no cover

        return self._GetCommandLine(" && ".join(commands))

    # ----------------------------------------------------------------------
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
        return self._GetCommandLine(
            "git merge --no-commit -no-ff {}".format(self._GetUpdateMergeArgCommandLine(merge_arg)),
        )

    # ----------------------------------------------------------------------
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
        # Git is really screwed up. After a 30 minute search, I couldn't find a way to
        # specify a branch and beginning revision in a single command. Therefore, I am
        # doing it manually.

        source_branch: Optional[str] = None
        additional_filters: List[str] = []

        # ----------------------------------------------------------------------
        def GetDateOperator(arg):
            if arg is None or arg:
                return "since"

            return "until"

        # ----------------------------------------------------------------------

        if source_merge_arg is None:
            source_branch = self.GetCurrentBranch()

        elif isinstance(source_merge_arg, UpdateMergeArgs.Change):
            source_branch = self._GetBranchAssociatedWithChange(source_merge_arg.change)

        elif isinstance(source_merge_arg, UpdateMergeArgs.Date):
            source_branch = self.GetCurrentBranch()

            additional_filters.append(
                '--{}="{}"'.format(
                    GetDateOperator(source_merge_arg.greater_than),
                    source_merge_arg.date.isoformat(timespec="seconds"),
                ),
            )

        elif isinstance(source_merge_arg, UpdateMergeArgs.Branch):
            source_branch = source_merge_arg.branch

        elif isinstance(source_merge_arg, UpdateMergeArgs.BranchAndDate):
            source_branch = source_merge_arg.branch

            additional_filters.append(
                '--{}="{}"'.format(
                    GetDateOperator(source_merge_arg.greater_than),
                    source_merge_arg.date.isoformat(timespec="seconds"),
                ),
            )

        else:
            assert False, source_merge_arg  # pragma: no cover

        return self._GetCommandLine(
            'git --no-pager log "{source_branch}" --not "{dest_branch}" --format="%H" --no-merges{additional_filters}'.format(
                source_branch=source_branch,
                dest_branch=dest_branch,
                additional_filters=" {}".format(" ".join(additional_filters)) if additional_filters else "",
            ),
        )

    # ----------------------------------------------------------------------
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
        result = self._Execute(self.GetEnumChangesSinceMergeCommandLine(dest_branch, source_merge_arg))
        assert result.returncode == 0, result.output

        changes = [line.strip() for line in result.output.split("\n") if line.strip()]

        if isinstance(source_merge_arg, UpdateMergeArgs.Change):
            starting_index: Optional[int] = None

            for index, change in enumerate(changes):
                if change == source_merge_arg.change:
                    starting_index = index
                    break

            if starting_index is None:
                changes = []
            else:
                changes = changes[starting_index:]

        yield from changes

    # ----------------------------------------------------------------------
    def GetEnumChangedFilesCommandLine(
        self,
        change: str,
    ) -> str:
        return self._GetCommandLine(
            "git diff-tree --no-commit-id --name-only -r {}".format(
                self._GetUpdateMergeArgCommandLine(UpdateMergeArgs.Change(change)),
            ),
        )

    # ----------------------------------------------------------------------
    def EnumChangedFiles(
        self,
        change: str,
    ) -> Generator[Path, None, None]:
        result = self._Execute(self.GetEnumChangedFilesCommandLine(change))
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            yield self.repo_root / line

    # ----------------------------------------------------------------------
    def GetEnumBlameInfoCommandLine(
        self,
        filename: Path,
    ) -> str:
        return self._GetCommandLine('git blame -s "{}"'.format(str(filename)))

    # ----------------------------------------------------------------------
    def EnumBlameInfo(
        self,
        filename: Path,
    ) -> Generator[DistributedRepositoryBase.EnumBlameInfoResult, None, None]:
        result = self._Execute(self.GetEnumBlameInfoCommandLine(filename))

        if result.returncode != 0:
            # Don't produce an error if we are looking at a file that has been removed/renamed.
            if "No such file or directory" in result.output:
                return

            assert False, (result.returncode, result.output)

        regex = re.compile(r"^(?P<revision>\S+)\s+(?P<line_number>\d+)\)(?: (?P<line>.*))?$")

        for line in result.output.split("\n"):
            if not line:
                continue

            match = regex.match(line)
            if not match:
                # Don't produce an error on a failure to enumerate binary files
                if line.endswith("binary file"):
                    return

                assert False, line

            yield DistributedRepositoryBase.EnumBlameInfoResult(
                match.group("revision"),
                match.group("line_number"),
            )

    # ----------------------------------------------------------------------
    def GetEnumTrackedFilesCommandLine(self) -> str:
        return self._GetCommandLine("git ls-files")

    # ----------------------------------------------------------------------
    def EnumTrackedFiles(self) -> Generator[Path, None, None]:
        temp_filename = CurrentShell.CreateTempFilename()

        result = self._Execute(
            '{} > "{}"'.format(self.GetEnumTrackedFilesCommandLine(), str(temp_filename)),
        )
        assert result.returncode == 0, result.output

        assert temp_filename.is_file(), temp_filename

        with ExitStack(temp_filename.unlink):
            with temp_filename.open() as f:
                for line in f.readlines():
                    line = line.strip()
                    if line:
                        yield self.repo_root / line

    # ----------------------------------------------------------------------
    def GetCreatePatchCommandLine(
        self,
        output_filename: Path,
        start_change: Optional[str]=None,
        end_change: Optional[str]=None,
    ) -> str:
        assert (
            (start_change is None and end_change is None)
            or (start_change is not None and end_change is not None)
        ), (start_change, end_change)

        output_filename.parent.mkdir(parents=True, exist_ok=True)

        if not start_change and not end_change:
            command_line = 'git diff -g > "{}"'.format(str(output_filename))
        else:
            command_line = 'git diff -g "{start}" "{end}" > "{filename}"'.format(
                start=start_change,
                end=end_change,
                filename=str(output_filename),
            )

        return self._GetCommandLine(command_line)

    # ----------------------------------------------------------------------
    def GetApplyPatchCommandLine(
        self,
        patch_filename: Path,
        commit: bool=False,
    ) -> str:
        if not commit:
            raise Exception("Git does not support applying a patch without committing.")

        return self._GetCommandLine('git apply "{}"'.format(str(patch_filename)))

    # ----------------------------------------------------------------------
    def GetResetCommandLine(
        self,
        no_backup: bool=False,
    ) -> str:
        commands: List[str] = []

        # See if we are looking at a detached head pseudo branch. If so, extract the actual branch
        # name and switch to that before running other commands.
        branch = self.GetCurrentBranch()

        match = self._DetachedHeadPseudoBranchName_regex.match(branch)
        if match:
            branch = match.group("branch_name")
            commands.append('get checkout "{}"'.format(branch))

        # Remove any of the pseudo branches that have been created
        for potential_delete_branch in self.EnumBranches():
            if self._DetachedHeadPseudoBranchName_regex.match(potential_delete_branch):
                commands.append('git branch -D "{}"'.format(potential_delete_branch))

        commands += [
            "git clean -xdf",
            'git reset --hard "origin/{}"'.format(branch),
        ]

        return self._GetCommandLine(" && ".join(commands))

    # ----------------------------------------------------------------------
    def GetHasUpdateChangesCommandLine(self) -> str:
        return self.GetEnumUpdateChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasUpdateChanges(self) -> bool:
        for _ in self.EnumUpdateChanges():
            return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumUpdateChangesCommandLine(self) -> str:
        raise NotImplementedError("TODO")

    # ----------------------------------------------------------------------
    def EnumUpdateChanges(self) -> Generator[Path, None, None]:
        raise NotImplementedError("TODO")

    # ----------------------------------------------------------------------
    def GetHasLocalChangesCommandLine(self) -> str:
        return self.GetEnumLocalChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasLocalChanges(self) -> bool:
        for _ in self.EnumLocalChanges():
            return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumLocalChangesCommandLine(self) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "git remote update",
                    'git --no-pager log "origin/{}..HEAD" --format="%H"'.format(self.GetCurrentBranch()),
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def EnumLocalChanges(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumLocalChangesCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if line:
                yield line

    # ----------------------------------------------------------------------
    def GetHasRemoteChangesCommandLine(self) -> str:
        return self.GetEnumRemoteChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasRemoteChanges(self) -> bool:
        for _ in self.EnumRemoteChanges():
            return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumRemoteChangesCommandLine(self) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "git remote update",
                    'git --no-pager log "HEAD..origin/{}" --format="%H"'.format(self.GetCurrentBranch()),
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def EnumRemoteChanges(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumRemoteChangesCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if line:
                yield line

    # ----------------------------------------------------------------------
    def GetPushCommandLine(
        self,
        create_remote_branch: bool=False,
    ) -> str:
        commands: List[str] = [
            "git push",
            "git push --tags",
        ]

        if create_remote_branch:
            commands[0] += ' --set-upstream origin "{}"'.format(self.GetCurrentBranch())

        return " && ".join(commands)

    # ----------------------------------------------------------------------
    def GetPullCommandLine(
        self,
        branch_or_branches: Union[None, str, List[str]]=None,
    ) -> str:
        commands: List[str] = []

        if branch_or_branches is not None:
            if isinstance(branch_or_branches, list):
                branches = branch_or_branches
            else:
                branches = [branch_or_branches, ]

            commands += [
                'git checkout -b "{name}" "origin/{name}"'.format(name=branch)
                for branch in branches
            ]

        commands += [
            "git fetch --all",
            "git fetch --all --tags",
        ]

        return self._GetCommandLine(" && ".join(commands))

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _GetCommandLine(
        self,
        command_line: str,
    ) -> str:
        return command_line.replace("git ", 'git -C "{}" '.format(str(self.repo_root)))

    # ----------------------------------------------------------------------
    def _GetUpdateMergeArgCommandLine(
        self,
        update_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> str:
        # ----------------------------------------------------------------------
        def DateAndBranch(
            datetime_value: datetime,
            branch: Optional[str],
            greater_than: Optional[bool],
        ) -> str:
            if branch:
                branches = [branch]
            else:
                branches = [self.GetCurrentBranch(), self.scm.default_branch_name]

            if not greater_than:
                operator = "until"
            else:
                operator = "since"

            for branch in branches:
                command_line = self._GetCommandLine(
                    'git --no-pager long "--branches=*{}" "--{}={}" -n 1 --format="%H"'.format(
                        branch,
                        operator,
                        datetime_value.isoformat(timespec="seconds"),
                    ),
                )

                result = self._Execute(command_line, strip=True)
                if result.returncode == 0 and result.output:
                    return result.output

            raise Exception("Revision not found.")

        # ----------------------------------------------------------------------

        if update_arg is None:
            return ""

        if isinstance(update_arg, UpdateMergeArgs.Change):
            result = self._Execute(
                self._GetCommandLine(
                    'git --no-pager log {} -n 1 --format="%H"'.format(update_arg.change),
                ),
                strip=True,
            )
            assert result.returncode == 0, result.output

            if result.output.startswith("* "):
                result.output = result.output[len("* "):]

            return result.output

        if isinstance(update_arg, UpdateMergeArgs.Date):
            return DateAndBranch(update_arg.date, None, update_arg.greater_than)

        if isinstance(update_arg, UpdateMergeArgs.Branch):
            return update_arg.branch

        if isinstance(update_arg, UpdateMergeArgs.BranchAndDate):
            return DateAndBranch(update_arg.date, update_arg.branch, update_arg.greater_than)

        assert False, update_arg  # pragma: no cover

    # ----------------------------------------------------------------------
    def _GetBranchAssociatedWithChange(
        self,
        change: str,
    ) -> str:
        result = self._Execute(
            self._GetCommandLine('git branch --contains "{}"'.format(change)),
            strip=True,
        )
        assert result.returncode == 0, result.output

        if result.output.startswith("* "):
            result.output = result.output[len("* "):]

        return result.output
