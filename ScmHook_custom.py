# ----------------------------------------------------------------------
# |
# |  ScmHook_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 09:53:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Customizations for SCM hooks"""

import itertools
import os
import re
import textwrap

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Iterator, List, Match, Optional

from rich import get_console
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import CommitInfo, PreIntegrateInfo, PrePushInfo


# ----------------------------------------------------------------------
DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE          = "Do not decorate commit message"
DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_NO_COMMIT_MESSAGE_DECORATION"

DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE  = "No empty message check"
DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR         = "DEVELOPMENT_ENVIRONMENT_NO_EMPTY_MESSAGE_CHECK"

DISABLE_EMOJI_CHECK_COMMIT_MESSAGE          = "No emoji check"
DISABLE_EMOJI_CHECK_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_NO_COMMIT_EMOJI_CHECK"

DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE   = "No title length check"
DISABLE_TITLE_LENGTH_CHECK_ENV_VAR          = "DEVELOPMENT_ENVIRONMENT_NO_TITLE_LENGTH_CHECK"

DISABLE_BANNED_TEXT_COMMIT_MESSAGE          = "Enable banned text"
DISABLE_BANNED_TEXT_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_NO_BANNED_TEXT_CHECK"


# ----------------------------------------------------------------------
class EmojiCategory(Enum):
    """Emoji classification"""

    Functionality                           = "Functionality"
    Design                                  = "Design"
    Perf                                    = "Performance & Correctness"
    Refactor                                = "Refactor"
    Misc                                    = "Miscellaneous"

@dataclass
class EmojiInfo(object):
    """Information about an emoji that can be embedded within a commit message"""

    cat: EmojiCategory
    desc: str
    emoji: str
    aliases: List[str]


EMOJIS: List[EmojiInfo]                     = [
    EmojiInfo(
        EmojiCategory.Functionality,
        "Added a feature or features",
        "tada",
        ["+feature", "+features", "added_feature", "added_features"],
    ),
    EmojiInfo(
        EmojiCategory.Functionality,
        "Removed a feature or features",
        "heavy_minus_sign",
        ["-feature", "-features", "removed_feature", "removed_features"],
    ),
    EmojiInfo(
        EmojiCategory.Design,
        "New idea or ideas",
        "bulb",
        ["idea", "ideas"],
    ),
    EmojiInfo(
        EmojiCategory.Design,
        "New storybook",
        "book",
        ["story", "stories", "book", "books"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Improved performance",
        "zap",
        ["perf", "performance"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Improved automation",
        "robot",
        ["auto", "automation", "CI"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Added tests",
        "white_check_mark",
        ["test", "tests"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Fixed bug",
        "muscle",
        ["bug", "bugs", "fix", "fixes"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Addressed security concern",
        "closed_lock_with_key",
        ["security"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Added logging",
        "loudspeaker",
        ["+log", "+logs", "+logging", "added_log", "added_logs", "added_logging"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Removed logging",
        "mute",
        ["-log", "-logs", "-logging", "removed_log", "removed_logs", "removed_logging"],
    ),
    EmojiInfo(
        EmojiCategory.Perf,
        "Reverted change",
        "skull",
        ["revert", "-change", "rollback"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Refactored code",
        "triangular_ruler",
        ["refactor"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Added file(s)",
        "bookmark",
        ["+file", "+files", "added_file", "added_files"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Removed file(s)",
        "fire",
        ["-file", "-files", "removed_file", "removed_files"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Renamed file(s)/directory(s)",
        "pencil2",
        ["rename", "renames"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Upgraded dependency(s)",
        "arrow_heading_up",
        ["upgraded_dependency", "upgraded_dependencies"],
    ),
    EmojiInfo(
        EmojiCategory.Refactor,
        "Downgraded dependency(s)",
        "arrow_heading_down",
        ["downgraded_dependency", "downgraded_dependencies"],
    ),
    EmojiInfo(
        EmojiCategory.Misc,
        "Added documentation",
        "memo",
        ["+doc", "+docs", "+documentation", "added_doc", "added_docs", "added_documentation"]
    ),
    EmojiInfo(
        EmojiCategory.Misc,
        "Work in progress",
        "construction",
        ["wip", "work_in_progress"],
    ),
]


# ----------------------------------------------------------------------
def DecorateCommitMessage(
    dm: DoneManager,
    commit_message: str,
) -> str:
    env_disable_value = os.getenv(DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping commit message decoration due to the '{}' environment variable.\n".format(DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR))
        return commit_message

    if DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE.lower() in commit_message.lower():
        dm.WriteVerbose("Skipping commit message decoration due to '{}' in the commit message.\n".format(DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE))
        return commit_message

    replaced_content = False

    with dm.Nested(
        "Decorating the commit message...",
        suffix=lambda: "\n" if replaced_content else "",
    ) as this_dm:
        # Create an alias map
        aliases: Dict[str, str] = {}

        for emoji_info in EMOJIS:
            for alias in emoji_info.aliases:
                assert alias not in aliases, alias
                aliases[alias] = emoji_info.emoji

        # Decorate the message
        # ----------------------------------------------------------------------
        def ReplaceAlias(
            match: Match,
        ) -> str:
            alias = match.group("alias")

            emoji = aliases.get(alias, None)
            if emoji is None:
                return match.group("whole_value")

            return r":{}: [{}]".format(emoji, alias)

        # ----------------------------------------------------------------------

        new_commit_message = re.sub(
            textwrap.dedent(
                r"""(?#
                Whole match [begin]             )(?P<whole_value>(?#
                Prefix                          ):(?#
                Alias                           )(?P<alias>[^:]+)(?#
                Suffix                          ):(?#
                Whole match [end]               ))(?#
                )""",
            ),
            ReplaceAlias,
            commit_message,
        )

        if new_commit_message != commit_message:
            with _YieldRichConsole(this_dm) as console:
                console.print(
                    Group(
                        Panel(
                            Group(
                                "The commit message has been changed from:",
                                "",
                                TextwrapEx.Indent(commit_message, 4).replace("[", "\\["),
                                "\nto:\n",
                                TextwrapEx.Indent(new_commit_message, 4).replace("[", "\\["),
                            ),
                            padding=(1, 2),
                            title="[bold white]INFO[/]",
                            title_align="left",
                        ),
                        Panel(
                            Group(
                                "To disable this decoration, include the text '{}' in the commit message.".format(DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE),
                                "",
                                "To permanently disable this decoration for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR),
                            ),
                            padding=(1, 2),
                            title="[bold yellow]Disabling this Check[/]",
                            title_align="left",
                        ),
                    ),
                )

            commit_message = new_commit_message
            replaced_content = True

        return commit_message


# ----------------------------------------------------------------------
def EnsureCommitMessage(
    dm: DoneManager,
    commit_message: str,
) -> None:
    env_disable_value = os.getenv(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping empty message check due to the '{}' environment variable.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR))
        return

    if DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE.lower() in commit_message.lower():
        dm.WriteVerbose("Skipping empty message check due to '{}' in the commit message.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE))
        return

    with dm.Nested(
        "Checking for a valid commit message...",
        suffix=lambda: "\n" if dm.result != 0 else "",
    ) as this_dm:
        _EnsureCommitMessageImpl(this_dm, commit_message)


# ----------------------------------------------------------------------
def CreateEmojiTable() -> Group:
    """Creates a `rich` `Table` instance of all emojis suitable for display."""

    table = Table(
        show_footer=True,
    )

    for col_name, justify, footer in [
        ("Emoji", "center", None),
        (
            "Emoji Name",
            "center",
            Text(
                'add ":<name>:" to the commit message (e.g. ":tada:")',
                style="italic",
            ),
        ),
        ("Category", "left", None),
        ("Description", "left", None),
        (
            "Aliases",
            "left",
            Text(
                'add ":<name>:" to the commit message (e.g. ":+feature:")',
                style="italic",
            ),
        ),
    ]:
        table.add_column(
            col_name,
            footer or "",
            justify=justify,
        )

    for info in EMOJIS:
        table.add_row(
            ":{}:".format(info.emoji),
            info.emoji,
            info.cat.value,
            info.desc,
            ", ".join(info.aliases),
        )

    return Group(
        table,
        "",
        "This table is based on a more complete list available at https://gist.github.com/georgekrax/dfeb283f714c722ca28b4e98ada29d1c.",
    )


# ----------------------------------------------------------------------
def EnsureCommitEmoji(
    dm: DoneManager,
    commit_message: str,
) -> None:
    env_disable_value = os.getenv(DISABLE_EMOJI_CHECK_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping emoji check due to the '{}' environment variable.\n".format(DISABLE_EMOJI_CHECK_ENV_VAR))
        return

    if DISABLE_EMOJI_CHECK_COMMIT_MESSAGE.lower() in commit_message.lower():
        dm.WriteVerbose("Skipping emoji check due to '{}' in the commit message.\n".format(DISABLE_EMOJI_CHECK_COMMIT_MESSAGE))
        return

    with dm.Nested(
        "Checking for a commit message that begins with an emoji...",
        suffix=lambda: "\n" if dm.result != 0 else "",
    ) as this_dm:
        # Validate that the commit message starts with an emoji
        regex = re.compile(r"^(?P<emoji>:\S+:)(?P<message>.*)")

        match = regex.match(commit_message)
        if not match:
            # Write this error with rich so that we display inline emojis
            with _YieldRichConsole(this_dm) as console:
                console.print(
                    Group(
                        Panel(
                            Group(
                                "The commit message did not start with an emoji in the form `:<emoji_name>:`.",
                                "",
                                "Emojis make it much easier to determine the intent of a change when scanning a repository and should be used unless there is a compelling reason not to do so.",
                            ),
                            padding=(1, 2),
                            title="[bold red]ERROR[/]",
                            title_align="left",
                        ),
                        Panel(
                            Group(
                                "If this change is a change within a working branch that will be squashed when merged into the mainline branch, consider using the 'construction' (:construction:) emoji value.",
                                "",
                                CreateEmojiTable(),
                            ),
                            padding=(1, 2),
                            title="[bold white]Consider[/]",
                            title_align="left",
                        ),
                        Panel(
                            Group(
                                "To force this commit without an emoji, include the text '{}' in the commit message.".format(DISABLE_EMOJI_CHECK_COMMIT_MESSAGE),
                                "",
                                "To permanently disable this check for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(DISABLE_EMOJI_CHECK_ENV_VAR),
                            ),
                            padding=(1, 2),
                            title="[bold yellow]Disabling this Check[/]",
                            title_align="left",
                        ),
                    ),
                )

            this_dm.result = -1

            return

        emoji = match.group("emoji")
        message = match.group("message")

        _EnsureCommitMessageImpl(this_dm, message)


# ----------------------------------------------------------------------
def EnsureCommitTitleLength(
    dm: DoneManager,
    commit_message: str,
) -> None:
    env_disable_value = os.getenv(DISABLE_TITLE_LENGTH_CHECK_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping empty message check due to the '{}' environment variable.\n".format(DISABLE_TITLE_LENGTH_CHECK_ENV_VAR))
        return

    if DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE.lower() in commit_message.lower():
        dm.WriteVerbose("Skipping empty message check due to '{}' in the commit message.\n".format(DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE))
        return

    with dm.Nested(
        "Checking for a valid commit title...",
        suffix=lambda: "\n" if dm.result != 0 else "",
    ) as this_dm:
        title = commit_message.split("\n")[0]

        massaged_title = re.sub(
            r":[^:]+:",
            "_",
            title,
        )

        # Longest title length that can be displayed on GitHub.com without introducing an ellipsis
        # (rounded down to a slightly-less specific value that is hopefully easy to remember).
        max_title_length = 65

        massaged_title_len = len(massaged_title)

        if massaged_title_len > max_title_length:
            with _YieldRichConsole(this_dm) as console:
                console.print(
                    Group(
                        Panel(
                        """The commit title "{}" is too long ('{}' characters encountered; '{}' characters allowed).""".format(
                            title,
                            massaged_title_len,
                            max_title_length,
                        ),
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    Panel(
                        Group(
                            "To force this commit with the current title, include the text '{}' in the commit message.".format(DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE),
                            "",
                            "To permanently disable this check for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(DISABLE_TITLE_LENGTH_CHECK_ENV_VAR),
                        ),
                        padding=(1, 2),
                        title="[bold yellow]Disabling this Check[/]",
                        title_align="left",
                    ),
                ),
            )

            dm.result = -1


# ----------------------------------------------------------------------
def CheckBannedText(
    dm: DoneManager,
    commit_message: str,
    repo_root: Path,
    filenames: List[Path],
) -> None:
    if not filenames:
        return

    env_disable_value = os.getenv(DISABLE_BANNED_TEXT_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping empty message check due to the '{}' environment variable.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR))
        return

    if DISABLE_BANNED_TEXT_COMMIT_MESSAGE.lower() in commit_message.lower():
        dm.WriteVerbose("Skipping empty message check due to '{}' in the commit message.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE))
        return

    with dm.Nested(
        "Checking for banned text...",
        suffix=lambda: "\n" if dm.result != 0 else "",
    ) as check_dm:
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
            assert len(repo_root.parts) < len(filename.parts)
            return str(Path(*filename.parts[len(repo_root.parts):]))

        # ----------------------------------------------------------------------

        errors: List[str] = []

        for filename_index, filename in enumerate(filenames):
            display_name = GetDisplayName(filename)
            num_phrases = 0

            with check_dm.Nested(
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
                                str(filename) if check_dm.capabilities.is_headless else "[link=file:///{}]{}[/]".format(
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
            with _YieldRichConsole(check_dm) as console:
                console.print(
                    Group(
                        Panel(
                            Group(
                                "Banned text was found in these files:"
                                "\n",
                                *errors,
                            ),
                            padding=(1, 2),
                            title="[bold red]ERROR[/]",
                            title_align="left",
                        ),
                        Panel(
                            Group(
                                "To force this commit, include the text '{}' in the commit message.".format(DISABLE_BANNED_TEXT_COMMIT_MESSAGE),
                                "",
                                "To permanently disable this check for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(DISABLE_BANNED_TEXT_ENV_VAR),
                            ),
                            padding=(1, 2),
                            title="[bold yellow]Disabling this Check[/]",
                            title_align="left",
                        ),
                    ),
                )

            dm.result = -1


# ----------------------------------------------------------------------
def OnCommit(
    dm: DoneManager,
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,
    commit_info: CommitInfo,
    *,
    first_configuration_in_repo: bool,
) -> Optional[bool]:                        # Return False to prevent the execution of other hooks
    """Called before changes are committed to the local repository."""

    # We don't care about configuration, so bail if we have already performed the validation
    if not first_configuration_in_repo:
        return

    commit_info.description = DecorateCommitMessage(dm, commit_info.description)

    EnsureCommitMessage(dm, commit_info.description)
    EnsureCommitEmoji(dm, commit_info.description)

    EnsureCommitTitleLength(dm, commit_info.description)

    CheckBannedText(
        dm,
        commit_info.description,
        repository.repo_root,
        list(itertools.chain(commit_info.files_added or [], commit_info.files_modified or [])),
    )


# ----------------------------------------------------------------------
def OnPrePush(
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,                 # pylint: disable=unused-argument
    pre_push_info: PrePushInfo,             # pylint: disable=unused-argument
    *,                                      # pylint: disable=unused-argument
    first_configuration_in_repo: bool,      # pylint: disable=unused-argument
) -> Optional[bool]:
    """Called before changes are pushed to a remote repository."""

    raise Exception("Not implemented yet")


# ----------------------------------------------------------------------
def OnPreIntegrate(
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,                 # pylint: disable=unused-argument
    pre_integrate_info: PreIntegrateInfo,   # pylint: disable=unused-argument
    *,                                      # pylint: disable=unused-argument
    first_configuration_in_repo: bool,      # pylint: disable=unused-argument
) -> Optional[bool]:
    """Called before changes are integrated into the local repository when pushed from a remote repository."""

    raise Exception("Not implemented yet")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _EnsureCommitMessageImpl(
    dm: DoneManager,
    commit_message: str,
) -> None:
    if not commit_message or commit_message.isspace():
        with _YieldRichConsole(dm) as console:
            console.print(
                Group(
                    Panel(
                        "The commit message was empty.",
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    Panel(
                        Group(
                            "To force this commit without an emoji, include the text '{}' in the commit message.".format(DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE),
                            "",
                            "To permanently disable this check for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR),
                        ),
                        padding=(1, 2),
                        title="[bold yellow]Disabling this Check[/]",
                        title_align="left",
                    ),
                ),
            )

        dm.result = -1


# ----------------------------------------------------------------------
@contextmanager
def _YieldRichConsole(
    dm: DoneManager,
) -> Iterator[Console]:
    with dm.YieldStdout() as stdout_context:
        yield Console(
            file=StreamDecorator(
                stdout_context.stream,
                line_prefix=stdout_context.line_prefix,
            ),  # type: ignore
            force_terminal=True,
            legacy_windows=False,
            width=get_console().width - len(stdout_context.line_prefix),
        )
