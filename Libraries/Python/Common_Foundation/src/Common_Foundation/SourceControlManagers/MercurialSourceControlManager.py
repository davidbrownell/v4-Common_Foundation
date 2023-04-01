# ----------------------------------------------------------------------
# |
# |  MercurialSourceControlManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 08:56:54
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the MercurialSourceControlManager object"""

import re
import textwrap

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Generator, Optional, Union

from .SourceControlManager import DistributedRepository as DistributedRepositoryBase, SourceControlManager, UpdateMergeArgs

from ..ContextlibEx import ExitStack
from .. import PathEx
from ..Shell.All import CurrentShell
from .. import SubprocessEx


# ----------------------------------------------------------------------
class MercurialSourceControlManager(SourceControlManager):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(MercurialSourceControlManager, self).__init__()

        self._is_available: Optional[bool]  = None

    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Mercurial"

    @property
    def default_branch_name(self) -> str:
        return "default"

    @property
    def release_branch_name(self) -> str:
        return "release"

    @property
    def tip(self) -> str:
        return "tip"

    @property
    def working_directories(self) -> Optional[List[str]]:
        return [".hg", ]

    @property
    def ignore_filename(self) -> Optional[str]:
        return ".hgignore"

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def IsAvailable(self) -> bool:
        if self._is_available is None:
            result = self._Execute("hg version")
            self._is_available = result.returncode == 0 and "Mercurial Distributed SCM" in result.output

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

        result = self._Execute('hg --cwd "{}" root'.format(str(directory)), strip=True)

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

        result = self._Execute('hg init "{}"'.format(str(output_dir)))

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
            'hg --cwd "{dir}" clone{branch} "{uri}" "{name}"'.format(
                dir=str(output_dir.parent),
                branch= ' -b "{}"'.format(branch) if branch is not None else "",
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
            raise Exception("'{}' is not a valid Mercurial repository.".format(str(path)))

        return Repository(self, realized_root)


class Repository(DistributedRepositoryBase):
    # ----------------------------------------------------------------------
    def GetGetUniqueNameCommandLine(self) -> str:
        return self._GetCommandLine("hg paths")

    # ----------------------------------------------------------------------
    def GetUniqueName(self) -> str:
        result = self._Execute(self.GetGetUniqueNameCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        regex = re.compile(r"{}\s*=\s*(?P<value>.+)".format(self.scm.default_branch_name))

        for line in result.output.split("\n"):
            match = regex.match(line)
            if match:
                return match.group("value")

        # If here, we didn't find anything. Most of the time, this is an indication that
        # the repo is local (no remote); return the path.
        return str(self.repo_root)

    # ----------------------------------------------------------------------
    def GetWhoCommandLine(self) -> str:
        return self._GetCommandLine("hg showconfig ui.username")

    # ----------------------------------------------------------------------
    def Who(self) -> str:
        result = self._Execute(self.GetWhoCommandLine(), strip=True)
        assert result.returncode == 0, result.output

        return result.output

    # ----------------------------------------------------------------------
    def GetCleanCommandLine(self) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "hg update --clean",
                    "hg purge",
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def GetEnumBranchesCommandLine(self) -> str:
        return self._GetCommandLine(r'hg branches --template "{branch}\n"')

    # ----------------------------------------------------------------------
    def EnumBranches(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumBranchesCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if line:
                yield line

    # ----------------------------------------------------------------------
    def GetGetCurrentBranchCommandLine(self) -> str:
        return self._GetCommandLine("hg branch")

    # ----------------------------------------------------------------------
    def GetCurrentBranch(self) -> str:
        result = self._Execute(self.GetGetCurrentBranchCommandLine(), strip=True)
        assert result.returncode == 0, result.output

        return result.output

    # ----------------------------------------------------------------------
    def GetGetMostRecentBranchCommandLine(self) -> str:
        return self._GetGetBranchAssociatedWithChangeCommandLine()

    # ----------------------------------------------------------------------
    def GetMostRecentBranch(self) -> str:
        result = self._Execute(self.GetGetMostRecentBranchCommandLine(), strip=True)
        assert result.returncode == 0, result.output

        return result.output

    # ----------------------------------------------------------------------
    def GetCreateBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        return self._GetCommandLine('hg branch "{}"'.format(branch_name))

    # ----------------------------------------------------------------------
    def GetSetBranchCommandLine(
        self,
        branch_name: str,
    ) -> str:
        return self._GetCommandLine('hg update "{}"'.format(branch_name))

    # ----------------------------------------------------------------------
    def GetGetExecutePermissionCommandLine(
        self,
        filename: Path,
    ) -> str:
        return self._GetCommandLine("hg manifest --debug")

    # ----------------------------------------------------------------------
    def GetExecutePermission(
        self,
        filename: Path,
    ) -> bool:
        result = self._Execute(self.GetGetExecutePermissionCommandLine(filename))
        assert result.returncode == 0, result.output

        regex = re.compile(
            textwrap.dedent(
                r"""(?#
                Hash                        )^(?P<hash>\S+)\s+(?#
                Permissions                 )(?P<permissions>\d+)\s+(?#
                Star [what is this?]        )(?:\*\s+)?(?#
                Filename                    )(?P<filename>.+?)$(?#
                )""",
            ),
            re.MULTILINE,
        )

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            match = regex.match(line)
            if not match:
                continue

            this_filename = self.repo_root / match.group("filename")

            if this_filename == filename:
                permissions = int(match.group("permissions"))
                assert permissions < 1000, permissions

                # The execute permission is in the hundreds place
                execute_permission = permissions // 100

                if execute_permission == 6:
                    return False
                if execute_permission == 7:
                    return True
                else:
                    assert False, (line, execute_permission)  # pragma: no cover

        raise Exception("'{}' was not found.".format(str(filename)))

    # ----------------------------------------------------------------------
    def GetSetExecutePermissionCommandLine(
        self,
        filename: Path,
        is_executable: bool,
        commit_message: Optional[str]=None,
    ) -> str:
        relative_path = PathEx.CreateRelativePath(self.repo_root, filename)

        if commit_message is None:
            if is_executable:
                commit_message = "Added execute permission for '{}'".format(str(relative_path))
            else:
                commit_message = "Removed execute permission for '{}'".format(str(relative_path))

        return self._GetCommandLine(
            'hg import --bypass -m "{}" "<temp_filename>" && hg update'.format(commit_message),
        )

    # ----------------------------------------------------------------------
    def SetExecutePermission(
        self,
        filename: Path,
        is_executable: bool,
        commit_message: Optional[str]=None,
    ) -> SubprocessEx.RunResult:  # type: ignore
        command_line = self.GetSetExecutePermissionCommandLine(
            filename,
            is_executable,
            commit_message,
        )

        temp_filename = CurrentShell.CreateTempFilename()

        if is_executable:
            old_mode = "644"
            new_mode = "755"
        else:
            old_mode = "755"
            new_mode = "644"

        with temp_filename.open("w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    diff --git a/{filename} b/{filename}
                    old mode 100{old_mode}
                    new mode 100{new_mode}
                    """,
                ).format(
                    filename=PathEx.CreateRelativePath(self.repo_root, filename),
                    old_mode=old_mode,
                    new_mode=new_mode,
                ),
            )

        command_line = command_line.replace("<temp_filename>", str(temp_filename))

        with ExitStack(temp_filename.unlink):
            return self._Execute(command_line)

    # ----------------------------------------------------------------------
    def GetHasUntrackedWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg status")

    # ----------------------------------------------------------------------
    def HasUntrackedWorkingChanges(self) -> bool:
        result = self._Execute(self.GetHasUntrackedWorkingChangesCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            if line.lstrip().startswith("?"):
                return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumUntrackedWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg status")

    # ----------------------------------------------------------------------
    def EnumUntrackedWorkingChanges(self) -> Generator[Path, None, None]:
        result = self._Execute(self.GetEnumUntrackedWorkingChangesCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            assert len(line) > 2 and line[1] == " " and line[2] != " ", line
            if line[0] == "?":
                yield self.repo_root / line[2:]

    # ----------------------------------------------------------------------
    def GetHasWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg status")

    # ----------------------------------------------------------------------
    def HasWorkingChanges(self) -> bool:
        result = self._Execute(self.GetHasWorkingChangesCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.lstrip()

            if line and not line.startswith("?"):
                return True

        return False

    # ----------------------------------------------------------------------
    def GetEnumWorkingChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg status")

    # ----------------------------------------------------------------------
    def EnumWorkingChanges(self) -> Generator[Path, None, None]:
        result = self._Execute(self.GetEnumWorkingChangesCommandLine(), add_newline=True)
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            assert len(line) > 2 and line[1] == " " and line[2] != " ", line
            if line[0] != "?":
                yield self.repo_root / line[2:]

    # ----------------------------------------------------------------------
    def GetGetChangeStatusCommandLine(self) -> str:
        return self._GetCommandLine("hg status")

    # ----------------------------------------------------------------------
    def GetChangeStatus(self) -> DistributedRepositoryBase.GetChangeStatusResult:
        result = self._Execute(self.GetGetChangeStatusCommandLine())
        assert result.returncode == 0, result.output

        untracked_changes = False
        working_changes = False

        for line in result.output.split("\n"):
            line = line.strip()
            if not line:
                continue

            assert len(line) > 2 and line[1] == " " and line[2] != " ", line

            if line[0] == "?":
                untracked_changes = True
            else:
                working_changes = True

            if untracked_changes and working_changes:
                break

        return DistributedRepositoryBase.GetChangeStatusResult(untracked_changes, working_changes)

    # ----------------------------------------------------------------------
    def GetGetChangeInfoCommandLine(
        self,
        change: str,
    ) -> str:
        return self._GetCommandLine('hg log --rev "{}"'.format(change))

    # ----------------------------------------------------------------------
    def GetChangeInfo(
        self,
        change: str,
    ) -> Dict[str, Any]:
        result = self._Execute(self.GetGetChangeInfoCommandLine(change), strip=True)
        assert result.returncode == 0, result.output

        user: Optional[str] = None
        date: Optional[str] = None
        summary: Optional[str] = None

        for line in result.output.split("\n"):
            if line.startswith("user"):
                assert user is None
                user = line[len("user") + 1:].strip()
            elif line.startswith("date"):
                assert date is None
                date = line[len("date") + 1:].strip()
            elif line.startswith("summary"):
                assert summary is None
                summary = line[len("summary") + 1:].strip()

        assert user is not None
        assert date is not None
        assert summary is not None

        return {
            "user": user,
            "date": date,
            "summary": summary,
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
            "hg add {}".format(" ".join('"{}"'.format(str(filename)) for filename in filenames))
        )

    # ----------------------------------------------------------------------
    def GetCommitCommandLine(
        self,
        description: str,
        username: Optional[str]=None,
    ) -> str:
        return self._GetCommandLine(
            'hg commit --message "{desc}"{user}'.format(
                desc=description.replace('"', '\\"'),
                user=' --user "{}"'.format(username) if username else "",
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
        return self._GetCommandLine(
            "hg update{}".format(self._GetUpdateMergeArgCommandLine(update_arg)),
        )

    # ----------------------------------------------------------------------
    def GetMergeCommandLine(
        self,
        merge_arg: Union[
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
    ) -> str:
        return self._GetCommandLine(
            "hg merge{}".format(self._GetUpdateMergeArgCommandLine(merge_arg)),
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
        *,
        include_working_changes: bool=False,
    ) -> str:
        # ----------------------------------------------------------------------
        def GetDateOperator(
            greater_than: Optional[bool],
        ) -> str:
            if greater_than is None or greater_than:
                return ">"

            return "<"

        # ----------------------------------------------------------------------

        source_branch: Optional[str] = None
        additional_filters: List[str] = []

        if source_merge_arg is None:
            source_branch = self.GetCurrentBranch()

        elif isinstance(source_merge_arg, UpdateMergeArgs.Change):
            result = self._Execute(
                self._GetGetBranchAssociatedWithChangeCommandLine(source_merge_arg.change),
                strip=True,
            )
            assert result.returncode == 0, result.output

            source_branch = result.output
            additional_filters.append("{}::".format(source_merge_arg.change))

        elif isinstance(source_merge_arg, UpdateMergeArgs.Date):
            source_branch = self.GetCurrentBranch()
            additional_filters.append(
                "date('{}{}')".format(
                    GetDateOperator(source_merge_arg.greater_than),
                    source_merge_arg.date.isoformat(timespec="seconds"),
                ),
            )

        elif isinstance(source_merge_arg, UpdateMergeArgs.Branch):
            source_branch = source_merge_arg.branch

        elif isinstance(source_merge_arg, UpdateMergeArgs.BranchAndDate):
            source_branch = source_merge_arg.branch
            additional_filters.append(
                "date('{}{}')".format(
                    GetDateOperator(source_merge_arg.greater_than),
                    source_merge_arg.date.isoformat(timespec="seconds"),
                ),
            )

        else:
            assert False, source_merge_arg  # pragma: no cover

        assert source_branch is not None

        query_filter = "::{} and not ::{}".format(source_branch, dest_branch)
        if additional_filters:
            query_filter += " and {}".format(" and ".join(additional_filters))

        return self._GetCommandLine(
            r'hg log --branch "{source_branch}" --rev "{filter}" --template "{{rev}}\n"'.format(
                source_branch=source_branch,
                filter=query_filter,
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
        *,
        include_working_changes: bool=False,
    ) -> Generator[str, None, None]:
        result = self._Execute(
            self.GetEnumChangesSinceMergeCommandLine(
                dest_branch,
                source_merge_arg,
                include_working_changes=include_working_changes,
            ),
        )
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if line:
                yield line

    # ----------------------------------------------------------------------
    def GetEnumChangesSinceMergeExCommandLine(
        self,
        dest_branch,
        source_merg_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
        *,
        include_working_changes: bool=False,
        rename_is_modification: bool=False,
    ) -> str:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def EnumChangesSinceMergeEx(
        self,
        dest_branch,
        source_merg_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ],
        *,
        include_working_changes: bool=False,
        rename_is_modification: bool=False,
    ) -> Generator[DistributedRepositoryBase.ChangeInfo, None, None]:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def GetEnumChangedFilesCommandLine(
        self,
        change: str,
    ) -> str:
        return self._GetCommandLine(r'''hg log --rev {} --template "{{files % '{{file}}\n'}}"'''.format(change))

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
        return self._GetCommandLine('hg blame "{}"'.format(str(filename)))

    # ----------------------------------------------------------------------
    def EnumBlameInfo(
        self,
        filename: Path,
    ) -> Generator[DistributedRepositoryBase.EnumBlameInfoResult, None, None]:
        result = self._Execute(self.GetEnumBlameInfoCommandLine(filename))

        if result.returncode != 0:
            # Don't produce an error if we are looking at a file that has been removed/renamed.
            if "no such file in" in result.output:
                return

            assert False, result.output

        regex = re.compile(r"^\s*(?P<change>\d+):\s?(?P<line>.*)$")

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
                match.group("change"),
                "{}\n".format(match.group("line")),
            )

    # ----------------------------------------------------------------------
    def GetEnumTrackedFilesCommandLine(self) -> str:
        return self._GetCommandLine("hg status --no-status --clean --added --modified")

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
            command_line = 'hg diff --git > "{}"'.format(str(output_filename))
        else:
            command_line = 'hg export --git --ref "{start}:{end}" > "{filename}"'.format(
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
        return self._GetCommandLine(
            'hg import{commit} "{filename}"'.format(
                commit="  --no-commit" if not commit else "",
                filename=str(patch_filename),
            ),
        )

    # ----------------------------------------------------------------------
    def GetEnumChangesCommandLine(
        self,
        *,
        include_working_changes: bool=False,
    ) -> str:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def EnumChanges(
        self,
        *,
        include_working_changes: bool=False,
    ) -> Generator[str, None, None]:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def GetEnumChangesExCommandLine(
        self,
        *,
        include_working_changes: bool=False,
        rename_is_modification: bool=False,
    ) -> str:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def EnumChangesEx(
        self,
        *,
        include_working_changes: bool=False,
        rename_is_modification: bool=False,
    ) -> Generator[DistributedRepositoryBase.ChangeInfo, None, None]:
        raise Exception("This functionality is not yet implemented.")

    # ----------------------------------------------------------------------
    def GetResetCommandLine(
        self,
        no_backup: bool=False,
    ) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "hg update --clean",
                    "hg purge",
                    'hg strip{no_backup} "roots(outgoing())"'.format(
                        no_backup=" --no-backup" if no_backup else "",
                    ),
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def Reset(
        self,
        no_prompt: bool=False,
        no_backup: bool=False,
    ) -> SubprocessEx.RunResult:
        result = super(Repository, self).Reset(no_prompt, no_backup)

        empty_revision_set_notice = "abort: empty revision set"

        if result.returncode != 0 and empty_revision_set_notice in result.output:
            result.returncode = 0
            result.output = result.output.replace(empty_revision_set_notice, "")

        result.output = "{}\n".format(result.output.rstrip())

        return result

    # ----------------------------------------------------------------------
    def GetHasUpdateChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg summary")

    # ----------------------------------------------------------------------
    def HasUpdateChanges(self) -> bool:
        result = self._Execute(self.GetHasUpdateChangesCommandLine())
        return result.returncode == 0 and result.output.find("update: (current)") == -1

    # ----------------------------------------------------------------------
    def GetEnumUpdateChangesCommandLine(self) -> str:
        return self._GetCommandLine(r'hg log --rev "descendants(.) and not ." --template "rev:{rev}\n"')

    # ----------------------------------------------------------------------
    def EnumUpdateChanges(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumUpdateChangesCommandLine())
        assert result.returncode == 0 or (result.returncode == 1 and "no changes found" in result.output)

        output_prefix = "rev:"

        for line in result.output.split("\n"):
            line = line.strip()

            if line.startswith(output_prefix):
                yield line[len(output_prefix):]

    # ----------------------------------------------------------------------
    def GetHasLocalChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg outgoing")

    # ----------------------------------------------------------------------
    def HasLocalChanges(self) -> bool:
        result = self._Execute(self.GetHasLocalChangesCommandLine())
        assert result.returncode == 0 or (result.returncode == 1 and "no changes found" in result.output), result

        return result.returncode == 0

    # ----------------------------------------------------------------------
    def GetEnumLocalChangesCommandLine(self) -> str:
        return self._GetCommandLine(r'hg outgoing --template "rev:{rev}\n"')

    # ----------------------------------------------------------------------
    def EnumLocalChanges(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumLocalChangesCommandLine())
        assert result.returncode == 0 or (result.returncode == 1 and "no changes found" in result.output), result.output

        output_prefix = "rev:"

        for line in result.output.split("\n"):
            line = line.strip()

            if line.startswith(output_prefix):
                yield line[len(output_prefix):]

    # ----------------------------------------------------------------------
    def GetHasRemoteChangesCommandLine(self) -> str:
        return self._GetCommandLine("hg incoming")

    # ----------------------------------------------------------------------
    def HasRemoteChanges(self) -> bool:
        result = self._Execute(self.GetHasRemoteChangesCommandLine())
        assert result.returncode == 0 or (result.returncode == 1 and "no changes found" in result.output), result

        return result.returncode == 0

    # ----------------------------------------------------------------------
    def GetEnumRemoteChangesCommandLine(self) -> str:
        return self._GetCommandLine(r'hg incoming --template "rev:{rev}\n"')

    # ----------------------------------------------------------------------
    def EnumRemoteChanges(self) -> Generator[str, None, None]:
        result = self._Execute(self.GetEnumRemoteChangesCommandLine())
        assert result.returncode == 0 or (result.returncode == 1 and "no changes found" in result.output), result.output

        output_prefix = "rev:"

        for line in result.output.split("\n"):
            if line.startswith(output_prefix):
                yield line[len(output_prefix):].strip()

    # ----------------------------------------------------------------------
    def GetPushCommandLine(
        self,
        create_remote_branch: bool=False,
    ) -> str:
        return self._GetCommandLine(
            "hg push{}".format(" --new-branch" if create_remote_branch else ""),
        )

    # ----------------------------------------------------------------------
    def GetPullCommandLine(
        self,
        branch_or_branches: Union[None, str, List[str]]=None,
    ) -> str:
        # In Mercurial, a pull gets all branches; no need to consider branch_or_branches
        return self._GetCommandLine("hg pull")

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _GetCommandLine(
        self,
        command_line: str,
    ) -> str:
        return command_line.replace("hg ", 'hg --cwd "{}" '.format(str(self.repo_root)))

    # ----------------------------------------------------------------------
    def _GetGetBranchAssociatedWithChangeCommandLine(
        self,
        change: Optional[str]=None,
    ) -> str:
        return self._GetCommandLine(
            'hg log {change} --template "{{branch}}"'.format(
                change="--rev {}".format(change) if change else "-l 1",
            ),
        )

    # ----------------------------------------------------------------------
    def _GetUpdateMergeArgCommandLine(
        self,
        update_arg: Union[
            None,
            UpdateMergeArgs.Change,
            UpdateMergeArgs.Date,
            UpdateMergeArgs.Branch,
            UpdateMergeArgs.BranchAndDate,
        ]
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
                operator = "<"
            else:
                operator = ">"

            errors: Dict[str, str] = {}

            for branch in branches:
                command_line = self._GetCommandLine(
                    '''hg log --branch "{branch}" --rev "sort(date('{operator}{date}'), -date)" --limit 1 --template "{{rev}}"'''.format(
                        branch=branch,
                        operator=operator,
                        date=datetime_value.isoformat(timespec="seconds"),
                    ),
                )

                result = self._Execute(command_line, strip=True)

                if result.returncode == 0 and result.output:
                    return " {}".format(result.output)

                errors[command_line] = result.output

            raise Exception(
                "Change not found ({branch}, {date})\n{errors}".format(
                    branch=branch,
                    date=datetime_value.isoformat(timespec="seconds"),
                    errors="\n\n".join("{}\n{}".format(k, v) for k, v in errors.items()),
                ),
            )

        # ----------------------------------------------------------------------

        if update_arg is None:
            return ""

        if isinstance(update_arg, UpdateMergeArgs.Change):
            try:
                value = int(update_arg.change)
                if value >= 0:
                    return " {}".format(update_arg.change)

            except ValueError:
                pass

            result = self._Execute(
                self._GetCommandLine(
                    'hg log --rev "{}" --template "{{rev}}"'.format(update_arg.change),
                ),
                strip=True,
            )

            assert result.returncode == 0, result.output
            return " {}".format(result.output)

        if isinstance(update_arg, UpdateMergeArgs.Date):
            return DateAndBranch(update_arg.date, None, update_arg.greater_than)

        if isinstance(update_arg, UpdateMergeArgs.Branch):
            return DateAndBranch(datetime.now(), update_arg.branch, None)

        if isinstance(update_arg, UpdateMergeArgs.BranchAndDate):
            return DateAndBranch(update_arg.date, update_arg.branch, update_arg.greater_than)

        assert False, update_arg  # pragma: no cover
