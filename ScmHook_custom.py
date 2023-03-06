# ----------------------------------------------------------------------
# |
# |  ScmHook_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 09:53:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Customizations for SCM hooks"""

import itertools
import re
import textwrap

from functools import cached_property
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import PathEx
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import ChangeInfo, SCMPlugin


# ----------------------------------------------------------------------
def GetPlugins() -> list[SCMPlugin]:
    return [
        _CommitMessageDecorator(),
        _ValidateCommitMessage(),
        _ValidateValidTitleLength(),
        _ValidateGitmoji(),
        _ValidateBannedText(),
    ]


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
class _CommitMessageDecorator(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "CommitMessageDecorator"
    description: ClassVar[str]              = "Transforms commit message using CommitEmojis"

    flags: ClassVar[SCMPlugin.Flag]        = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # This has to happen early in the process as it decorates the title and description
    priority: ClassVar[int]                 = SCMPlugin.DEFAULT_PRIORITY // 2

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,
        changes: list[ChangeInfo],
    ) -> None:
        # We have to get creative in how we invoke CommitEmojis because this script isn't running in a
        # fully activated environment. However, we are guaranteed that the working directory is set
        # to the root of Common_Foundation.
        commit_emojis_dir = PathEx.EnsureDir(Path.cwd() / "Scripts" / "CommitEmojis")

        # ----------------------------------------------------------------------
        def Transform(
            value: Optional[str],
        ) -> Optional[str]:
            if value is None:
                return None

            temp_filename = CurrentShell.CreateTempFilename()

            with temp_filename.open(
                "w",
                encoding="UTF-8",
            ) as f:
                f.write(value)

            with ExitStack(lambda: PathEx.RemoveFile(temp_filename)):
                command_line = 'python {} Transform "{}"'.format(
                    commit_emojis_dir,
                    temp_filename,
                )

                result = SubprocessEx.Run(command_line)
                result.RaiseOnError()

                return result.output

        # ----------------------------------------------------------------------
        def ToText(
            title: str,
            description: Optional[str],
        ) -> str:
            return "{}{}{}".format(
                title,
                "\n\n" if description else "",
                description or "",
            )

        # ----------------------------------------------------------------------

        new_title = Transform(changes[0].title)
        assert new_title is not None

        new_description = Transform(changes[0].description)

        if new_title != changes[0].title or new_description != changes[0].description:
            self._DisplayMessage(
                dm,
                textwrap.dedent(
                    """\
                    The change message has been changed from:

                        {}

                    to:

                        {}
                    """,
                ).format(
                    ToText(changes[0].title, changes[0].description),
                    ToText(new_title, new_description),
                ),
                self.flags.OnCommitCanBeDisabled,
                "this decoration",
            )

            changes[0].title = new_title
            changes[0].description = new_description


# ----------------------------------------------------------------------
class _ValidateCommitMessage(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "ValidateCommitMessage"
    description: ClassVar[str]              = "Validates that a commit message is present."

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=unused-argument
        changes: list[ChangeInfo],
    ) -> None:
        if not changes[0].title:
            raise Exception("The commit message cannot be empty.")

        dm.WriteVerbose("The commit message is present.")


# ----------------------------------------------------------------------
class _ValidateValidTitleLength(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "ValidateCommitTitleLength"
    description: ClassVar[str]              = "Validates that a commit title length is valid."

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=unused-argument
        changes: list[ChangeInfo],
    ) -> None:
        # Longest title length that can be displayed on GitHub.com without introducing an ellipsis
        # (rounded down to a slightly-less specific value that is hopefully easy to remember).
        max_title_length = 65

        if len(changes[0].title) > max_title_length:
            raise Exception(
                textwrap.dedent(
                    """\
                    The commit title '{}' is too long.

                        Maximum length:  {}
                        Current length:  {}
                    """,
                ).format(
                    changes[0].title,
                    max_title_length,
                    len(changes[0].title),
                ),
            )

        dm.WriteVerbose("The commit title length is valid.")


# ----------------------------------------------------------------------
class _ValidateGitmoji(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "ValidateGitmojiEmoji"
    description: ClassVar[str]              = "Validates gitmoji conventions."

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,
        changes: list[ChangeInfo],
    ) -> None:
        # This won't work in all cases, but consider a 32 bit char an emoji
        assert changes[0].title
        title_bytes = changes[0].title.encode("UTF-8")

        startswith_emoji = (
            (len(title_bytes) >= 2 and (title_bytes[0] >> 5) == 0b110)
            or (len(title_bytes) >= 3 and (title_bytes[0] >> 4) == 0b1110)
            or (len(title_bytes) >= 4 and (title_bytes[0] >> 3) == 0b11110)
        )

        if not startswith_emoji:
            raise Exception(
                textwrap.dedent(
                    """\
                    The commit message '{}' does not adhere to Gitmoji conventions (it does not begin with an emoji).

                    For a list of available Gitmoji values, run `CommitEmojis Display` within an activated environment.

                    Visit https://gitmoji.dev/ for more information about Gitmoji and its benefits.
                    """,
                ).format(changes[0].title),
            )

        dm.WriteVerbose("The commit message begins with an emoji.")


# ----------------------------------------------------------------------
class _ValidateBannedText(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "ValidateBannedText"
    description: ClassVar[str]              = "Ensure that commit contents do not contain banned text."

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # ----------------------------------------------------------------------
    @cached_property
    def disable_commit_messages(self) -> list[str]:
        return super(_ValidateBannedText, self).disable_commit_messages + ["Allow banned text", ]

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,
        changes: list[ChangeInfo],
    ) -> None:
        if not changes[0].files_added and not changes[0].files_modified:
            return

        banned_regex = re.compile(
            r"(?P<phrase>{})".format(
                "|".join(
                    [
                        # Note that these are written in an odd way as to not trigger errors when
                        # changes are made to this file
                        "{}ugBug".format("B"),
                    ],
                ),
            ),
            re.IGNORECASE,
        )

        # ----------------------------------------------------------------------
        def GetDisplayName(
            filename: Path,
        ) -> str:
            return str(PathEx.CreateRelativePath(repository.repo_root, filename))

        # ----------------------------------------------------------------------

        filenames = list(itertools.chain(changes[0].files_added or [], changes[0].files_modified or []))

        errors: List[str] = []

        for filename_index, filename in enumerate(filenames):
            display_name = GetDisplayName(filename)
            num_phrases = 0

            with dm.Nested(
                "Processing '{}' ({} of {})...".format(
                    display_name,
                    filename_index + 1,
                    len(filenames),
                ),
                lambda: "{} found".format(inflect.no("banned phrase", num_phrases)),
            ) as file_dm:
                assert filename.is_file(), filename

                try:
                    with filename.open() as f:
                        filename_content = f.read()
                except UnicodeDecodeError:
                    file_dm.WriteInfo("This appears to be a binary file.\n")
                    continue

                results: Dict[str, int] = {}

                for match in banned_regex.finditer(filename_content):
                    phrase = match.group("phrase")

                    if phrase not in results:
                        results[phrase] = 0

                    results[phrase] += 1
                    num_phrases += 1

                if results:
                    errors.append(
                        TextwrapEx.Indent(
                            textwrap.dedent(
                                """\
                                {}
                                {}
                                """,
                            ).format(
                                str(filename) if file_dm.capabilities.is_headless else "[link=file:///{}]{}[/]".format(
                                    filename.as_posix(),
                                    display_name,
                                ),
                                TextwrapEx.Indent(
                                    "\n".join(
                                        '"{}": {}'.format(phrase, inflect.no("time", num_times))
                                        for phrase, num_times in results.items()
                                    ),
                                    4,
                                ),
                            ),
                            4,
                        ),
                    )

                    file_dm.result = -1

        if errors:
            raise Exception(
                textwrap.dedent(
                    """\
                    Banned test was found in these files:
                    {}
                    """,
                ).format("".join(errors).rstrip()),
            )

        dm.WriteVerbose("\nNo banned text was found.")
