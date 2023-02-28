# ----------------------------------------------------------------------
# |
# |  GitSourceControlManager.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 08:56:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the GitSourceControlManager object"""

import re
import textwrap

from dataclasses import dataclass
from datetime import datetime
from enum import auto, Enum
from pathlib import Path
from typing import Any, Dict, List, Generator, Optional, Tuple, Union

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.SourceControlManager import DistributedRepository as DistributedRepositoryBase, SourceControlManager, UpdateMergeArgs
from Common_Foundation import SubprocessEx


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
        return "main"

    @property
    def release_branch_name(self) -> str:
        return "main_stable"

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
    @staticmethod
    def Execute(
        command_line: str,
        *,
        strip: bool=False,
        add_newline: bool=False,
        cwd: Optional[Path]=None,
    ) -> SubprocessEx.RunResult:
        result = SubprocessEx.Run(command_line, cwd=cwd)

        # Sanitize the output
        output: List[str] = []

        for line in result.output.split("\n"):
            stripped_line = line.strip()

            if (
                not stripped_line
                or "trace: " in stripped_line
                or stripped_line.startswith("Auto packing the repository")
                or stripped_line.startswith("Fetching")
                or stripped_line.startswith("Nothing new to pack")
                or stripped_line.startswith("warning: ")
                or stripped_line == 'See "git help gc" for manual housekeeping.'
            ):
                continue

            output.append(line)

        result.output = "\n".join(output)

        if strip:
            result.output = result.output.strip()
        if add_newline:
            result.output += "\n"

        return result

    # ----------------------------------------------------------------------
    def IsAvailable(self) -> bool:
        if self._is_available is None:
            result = self.__class__.Execute("git")
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

        result = self.__class__.Execute('git -C "{}" rev-parse --show-toplevel'.format(str(directory)), strip=True)

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

        result = self.__class__.Execute('git init "{}"'.format(str(output_dir)))

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

        result = self.__class__.Execute(
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
    def GetGetUniqueNameCommandLine(self) -> str:
        return self._GetCommandLine("git remote -v")

    # ----------------------------------------------------------------------
    def GetUniqueName(self) -> str:
        result = GitSourceControlManager.Execute(self.GetGetUniqueNameCommandLine())
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
        result = GitSourceControlManager.Execute(self.GetWhoCommandLine(), strip=True)
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
        result = GitSourceControlManager.Execute(self.GetEnumBranchesCommandLine())
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
        return self._GetCurrentBranchEx()[1]

    # ----------------------------------------------------------------------
    def GetGetMostRecentBranchCommandLine(self) -> str:
        return self._GetCommandLine('git for-each-ref --sort=-committerdate --format="%(refname)"')

    # ----------------------------------------------------------------------
    def GetMostRecentBranch(self) -> str:
        result = GitSourceControlManager.Execute(self.GetGetMostRecentBranchCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            parts = line.split("/")

            assert parts[0] == "refs", parts
            return parts[-1]

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
        result = GitSourceControlManager.Execute(self.GetGetExecutePermissionCommandLine(filename))
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
        result = GitSourceControlManager.Execute(self.GetEnumUntrackedWorkingChangesCommandLine())
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
        result = GitSourceControlManager.Execute(self.GetEnumWorkingChangesCommandLine())
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
        result = GitSourceControlManager.Execute(self.GetGetChangeInfoCommandLine(change))
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
        branch_type, branch_name = self._GetCurrentBranchEx()

        if branch_type == Repository._BranchType.Standard:
            command_suffix = " origin/{}".format(branch_name)
        elif branch_type == Repository._BranchType.Tag:
            command_suffix = " tags/{}".format(branch_name)
        elif branch_type == Repository._BranchType.Commit:
            # Nothing to do here
            return ""
        else:
            assert False, branch_type  # pragma: no cover

        commands: List[str] = [
            'git merge{}'.format(command_suffix),
        ]

        if update_arg is None:
            pass
        elif isinstance(update_arg, UpdateMergeArgs.Branch):
            commands.insert(0, 'git checkout "{}"'.format(update_arg.branch))
        elif isinstance(update_arg, (UpdateMergeArgs.Change, UpdateMergeArgs.BranchAndDate)):
            revision = self._GetUpdateMergeArgCommandLine(update_arg)
            commands.append('git checkout {}'.format(revision))
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
            source_branch = self._GetCurrentBranchEx(detached_is_error=True)[1]

        elif isinstance(source_merge_arg, UpdateMergeArgs.Change):
            source_branch = self._GetBranchAssociatedWithChange(source_merge_arg.change)

        elif isinstance(source_merge_arg, UpdateMergeArgs.Date):
            source_branch = self._GetCurrentBranchEx(detached_is_error=True)[1]

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
        result = GitSourceControlManager.Execute(self.GetEnumChangesSinceMergeCommandLine(dest_branch, source_merge_arg))
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
        result = GitSourceControlManager.Execute(self.GetEnumChangedFilesCommandLine(change))
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
        result = GitSourceControlManager.Execute(self.GetEnumBlameInfoCommandLine(filename))

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

        result = GitSourceControlManager.Execute(
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
    def EnumChanges(self) -> Generator[DistributedRepositoryBase.EnumChangesResult, None, None]:
        # ----------------------------------------------------------------------
        @dataclass(frozen=True)
        class Datum(object):
            name: str
            git_format: str
            regex: str

        # ----------------------------------------------------------------------

        datums: list[Datum] = [
            Datum(
                "commit_id",
                "%H%n",
                r"(?P<commit_id>\S+)\r?\n",
            ),
            Datum(
                "description",
                "%B%n",
                r"(?P<description>.*?\n)?",
            ),
            Datum(
                "tags",
                "%D%n",
                r"(?P<tags>.+?\n)?",
            ),
            Datum(
                "author",
                "%aN <%aE>%n",
                r"(?P<author>[^\n]+)\n",
            ),
            Datum(
                "date",
                "%ai%n",
                r"(?P<date>[^\n]+)\n",
            ),
        ]

        commit_delimiter = "140c4c3011e84e018c296ef729c3f662"
        section_delimiter = "e3882de41b4f430b8ca7740998dc104e"

        file_regex = re.compile(r"^(?P<code>[RADCMTU])\s+(?P<filename>\S.*)$", re.MULTILINE)

        commit_regex = re.compile(
            r"""(?#
            {sections}
            Section Delimiter               ){section_delimiter}_files\r?\n(?#
            File Content                    )(?P<files>.*)(?#
            )""".format(
                sections="".join(
                    textwrap.dedent(
                        r"""
                        Section Delimiter   ){section_delimiter}_{name}\r?\n(?#
                        {name}              ){regex}(?#
                        """,
                    ).format(
                        section_delimiter=section_delimiter,
                        name=datum.name,
                        regex=datum.regex,
                    ).rstrip()
                    for datum in datums
                ),
                section_delimiter=section_delimiter,
            ),
            re.DOTALL | re.MULTILINE,
        )

        git_format = "{commit_delimiter}%n{datums}%n{section_delimiter}_files%n".format(
            commit_delimiter=commit_delimiter,
            datums="".join("{}_{}%n{}".format(section_delimiter, datum.name, datum.git_format) for datum in datums),
            section_delimiter=section_delimiter,
        )

        command_line_template = self._GetCommandLine(
            " ".join(
                [
                    "git",
                    "--no-pager",
                    "log",
                    "HEAD",
                    '"--format={}"'.format(git_format),
                    "-n", "10",
                    "--name-status",
                    "--no-color",
                    "--skip", "{}",
                    "--tags",
                ],
            ),
        )

        # Execute
        split_token = "{}\n".format(commit_delimiter)

        offset = 0

        # Merges will not include files, but tags are often applied to merges.
        # If we detect a merge, don't send it but keep the tags around for the
        # next commit (which will be the parent of the merge).
        prev_tags: list[str] = []

        while True:
            result = self._Execute(
                command_line_template.format(offset),
                add_newline=True,
            )

            if not result.output or result.output.isspace():
                break

            if "does not have any commits yet" in result.output:
                break

            commits = result.output.split(split_token)

            assert commits
            assert not commits[0] or commits[0].isspace(), commits[0]

            for commit in commits[1:]:
                match = commit_regex.match(commit)
                if match is None:
                    raise Exception("Unexpected git output:\n\n**{}**\n".format(commit.rstrip()))

                # Extract the commit data
                tag_content = match.group("tags")
                file_content = match.group("files")

                tags: list[str] = []

                if tag_content:
                    for potential_tag in tag_content.split(","):
                        potential_tag = potential_tag.strip()

                        if potential_tag.startswith("tag: "):
                            tags.append(potential_tag[len("tag: "):])

                if not file_content:
                    # We are looking at a merge commit
                    assert not prev_tags
                    prev_tags = tags

                    continue

                commit_id = match.group("commit_id")
                description = match.group("description")
                author = match.group("author")
                date = datetime.strptime(match.group("date"), "%Y-%m-%d %H:%M:%S %z")

                # Extract the file info
                files_added: list[Path] = []
                files_removed: list[Path] = []
                files_modified: list[Path] = []

                for match in file_regex.finditer(file_content):
                    code = match.group("code")
                    filename = match.group("filename")

                    if code == "R":
                        assert " -> " in filename, filename
                        source, dest = filename.split(" -> ", maxsplit=1)

                        files_removed.append(self.repo_root / source)
                        files_added.append(self.repo_root / dest)
                    elif code == "A":
                        files_added.append(self.repo_root / filename)
                    elif code == "D":
                        files_removed.append(self.repo_root / filename)
                    elif code in [
                        "C", # Copied
                        "M", # Modified
                        "T", # Type changed
                        "U", # Updated but unmerged
                    ]:
                        files_modified.append(self.repo_root / filename)
                    else:
                        assert False, (code, filename)

                yield Repository.EnumChangesResult(
                    commit_id,
                    description,
                    tags + prev_tags,
                    author,
                    date,
                    files_added,
                    files_removed,
                    files_modified,
                )

                prev_tags = []
                offset += 1

    # ----------------------------------------------------------------------
    def GetResetCommandLine(
        self,
        no_backup: bool=False,
    ) -> str:
        commands: List[str] = []

        # See if we are looking at a detached head pseudo branch. If so, extract the actual branch
        # name and switch to that before running other commands.
        branch_type, branch_name = self._GetCurrentBranchEx()

        commands += [
            "git clean -xdf",
            'git reset --hard{}'.format(
                " origin/{}".format(branch_name) if branch_type == Repository._BranchType.Standard else "",
            ),
        ]

        return self._GetCommandLine(" && ".join(commands))

    # ----------------------------------------------------------------------
    def GetHasUpdateChangesCommandLine(self) -> str:
        return self._GetCommandLine('git log -n 1 --pretty=%D')

    # ----------------------------------------------------------------------
    def HasUpdateChanges(self) -> bool:
        result = GitSourceControlManager.Execute(self.GetHasUpdateChangesCommandLine())
        assert result.returncode == 0, result.output

        return "->" not in result.output

    # ----------------------------------------------------------------------
    def GetEnumUpdateChangesCommandLine(self) -> str:
        raise NotImplementedError(
            textwrap.dedent(
                """\
                Git makes this very difficult, as it doesn't associate the detached head with any branch,
                so the calculation to find the changes between the detached head and some branch is
                ambiguous. In theory, we could parse the reflog and make a best guess as
                to which branch is the desired branch, but this guess wouldn't be
                correct in all cases.
                """,
            ),
        )

    # ----------------------------------------------------------------------
    def EnumUpdateChanges(self) -> Generator[str, None, None]:
        result = GitSourceControlManager.Execute(self.GetEnumUpdateChangesCommandLine())
        assert result.returncode == 0, result.output

        for line in result.output.split("\n"):
            line = line.strip()
            if line:
                yield line

    # ----------------------------------------------------------------------
    def GetHasLocalChangesCommandLine(self) -> str:
        return self.GetEnumLocalChangesCommandLine()

    # ----------------------------------------------------------------------
    def HasLocalChanges(self) -> bool:
        try:
            for _ in self.EnumLocalChanges():
                return True
        except NotImplementedError as ex:
            if "Git makes this very difficult" in str(ex):
                return True

            raise

        return False

    # ----------------------------------------------------------------------
    def GetEnumLocalChangesCommandLine(self) -> str:
        return self._GetCommandLine(
            " && ".join(
                [
                    "git remote update origin",
                    'git --no-pager log "origin/{}..HEAD" --format="%H"'.format(
                        self._GetCurrentBranchEx(detached_is_error=True)[1],
                    ),
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def EnumLocalChanges(self) -> Generator[str, None, None]:
        result = GitSourceControlManager.Execute(
            self.GetEnumLocalChangesCommandLine(),
            strip=True,
        )
        if result.returncode != 0 and "unknown revision" in result.output:
            raise NotImplementedError(
                textwrap.dedent(
                    """\
                    Git makes this very difficult, as there doesn't seem to be a way to get a list
                    of changes that have been made on this branch without a ridiculous amount of
                    parsing.

                    If you see this message, know that this is a branch that hasn't yet been pushed
                    to the origin.
                    """,
                ),
            )

        assert result.returncode == 0, result.output

        if result.output:
            for line in result.output.split("\n"):
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
                    "git remote update origin",
                    'git --no-pager log "HEAD..origin/{}" --format="%H"'.format(
                        self._GetCurrentBranchEx(detached_is_error=True)[1],
                    ),
                ],
            ),
        )

    # ----------------------------------------------------------------------
    def EnumRemoteChanges(self) -> Generator[str, None, None]:
        result = GitSourceControlManager.Execute(
            self.GetEnumRemoteChangesCommandLine(),
            strip=True,
        )
        if result.returncode != 0 and "unknown revision" in result.output:
            # There aren't going to be any remote changes on this branch if the remote doesn't
            # know about it.
            result.returncode = 0
            result.output = ""

        assert result.returncode == 0, result.output

        if result.output:
            for line in result.output.split("\n"):
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
            commands[0] += ' --set-upstream origin "{}"'.format(
                self._GetCurrentBranchEx(detached_is_error=True)[1],
            )

        return " && ".join(commands)

    # ----------------------------------------------------------------------
    def GetPullCommandLine(
        self,
        branch_or_branches: Union[None, str, List[str]]=None,
    ) -> str:
        commands: List[str] = [
            # Git cannot fetch content for tags that it doesn't know about, but we don't know if the
            # branches provided (if any) are tags or branches. We erring on the side of correctness
            # here and pull all of the tags before we attempt to fetch content based on what is
            # potentially a tag name. Stupid git.
            "git fetch --all --tags --force",
        ]

        if branch_or_branches:
            if isinstance(branch_or_branches, list):
                branches = branch_or_branches
            else:
                branches = [branch_or_branches, ]

            commands += [
                'git fetch origin {}'.format(branch)
                for branch in branches
            ]

        else:
            commands.append("git fetch --all")

        return self._GetCommandLine(" && ".join(commands))

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    class _BranchType(Enum):
        # Branch is a standard branch
        Standard                            = auto()

        # Branch is based on a tag (in a detached head state)
        Tag                                 = auto()

        # Branch is based on a specific commit (in a detached head state)
        Commit                              = auto()

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    def _Execute(self, *args, **kwargs) -> SubprocessEx.RunResult:
        return GitSourceControlManager.Execute(*args, **kwargs)

    # ----------------------------------------------------------------------
    def _GetCommandLine(
        self,
        command_line: str,
    ) -> str:
        return command_line.replace("git ", 'git -C "{}" '.format(str(self.repo_root)))

    # ----------------------------------------------------------------------
    def _GetCurrentBranchEx(
        self,
        *,
        detached_is_error: bool=False,
        detached_error_template: str="The requested operation is not valid on a branch in a 'DETACHED HEAD' state ({}).",
    ) -> Tuple["Repository._BranchType", str]:
        # Get the branch name
        branch_name: Optional[str] = None

        result = GitSourceControlManager.Execute(self._GetCommandLine("git branch --no-color"))
        assert result.returncode == 0, result.output

        if result.output:
            regex = re.compile(r"\s*\*\s+(?P<name>.+)")

            for line in result.output.split("\n"):
                match = regex.match(line)
                if match:
                    branch_name = match.group("name")
                    break

        if branch_name is None:
            branch_name = self.scm.default_branch_name

        # Get the branch type
        detached_head_match = re.match(
            r"^\(HEAD detached (?:at|from) (?P<value>.+?)\)$",
            branch_name,
        )

        if detached_head_match:
            branch_name = detached_head_match.group("value")

            # If here, we are either looking at a branch based off of a specific commit
            # or a branch based off of a tag. Note that we can't use the -C method to
            # perform the command in a different directory, so we have to change the
            # working directory instead.
            result = GitSourceControlManager.Execute(
                "git tag --points-at HEAD",
                cwd=self.repo_root,
            )

            if result.returncode == 0 and result.output:
                branch_type = Repository._BranchType.Tag
            else:
                branch_type = Repository._BranchType.Commit

            # Note that I wouldn't be surprised if there are other types here that are missed

            if detached_is_error:
                raise Exception(detached_error_template.format(branch_type))

        else:
            branch_type = Repository._BranchType.Standard

        assert branch_name is not None
        return branch_type, branch_name

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
                branches = [
                    self._GetCurrentBranchEx(detached_is_error=True)[1],
                    self.scm.default_branch_name,
                ]

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

                result = GitSourceControlManager.Execute(command_line, strip=True)
                if result.returncode == 0 and result.output:
                    return result.output

            raise Exception("Revision not found.")

        # ----------------------------------------------------------------------

        if update_arg is None:
            return ""

        if isinstance(update_arg, UpdateMergeArgs.Change):
            result = GitSourceControlManager.Execute(
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
        result = GitSourceControlManager.Execute(
            self._GetCommandLine('git branch --contains "{}"'.format(change)),
            strip=True,
        )
        assert result.returncode == 0, result.output

        if result.output.startswith("* "):
            result.output = result.output[len("* "):]

        return result.output
