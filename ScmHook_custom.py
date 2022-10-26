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
from pathlib import Path
from typing import Dict, Iterator, List, Optional

from rich import get_console
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table

from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import CommitInfo, PreIntegrateInfo, PrePushInfo


# ----------------------------------------------------------------------
DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE  = "No empty message check"
DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR         = "DEVELOPMENT_ENVIRONMENT_NO_EMPTY_MESSAGE_CHECK"

DISABLE_EMOJI_CHECK_COMMIT_MESSAGE          = "No emoji check"
DISABLE_EMOJI_CHECK_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_NO_COMMIT_EMOJI_CHECK"

DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE   = "No title length check"
DISABLE_TITLE_LENGTH_CHECK_ENV_VAR          = "DEVELOPMENT_ENVIRONMENT_NO_TITLE_LENGTH_CHECK"

DISABLE_BANNED_TEXT_COMMIT_MESSAGE          = "Enable banned text"
DISABLE_BANNED_TEXT_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_NO_BANNED_TEXT_CHECK"


# ----------------------------------------------------------------------
def EnsureCommitMessage(
    dm: DoneManager,
    commit_message: str,
) -> None:
    env_disable_value = os.getenv(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping empty message check to to the '{}' environment variable.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR))
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
        regex = re.compile(r"^(?P<emoji>:\S+:)(?P<message>.*)")

        match = regex.match(commit_message)
        if not match:
            table = Table()

            for col_name, justify in [
                ("Emoji", "center"),
                ("Emoji Name", "center"),
                ("Category", "left"),
                ("Description", "left"),
            ]:
                table.add_column(
                    col_name,
                    justify=justify,
                )

            for category, emoji, description in [
                ("Functionality", "tada", "Added feature"),
                ("Functionality", "heavy_minus_sign", "Removed a feature"),

                ("Design", "bulb", "New idea"),
                ("Design", "book", "New storybook"),

                ("Performance & Correctness", "zap", "Improved performance"),
                ("Performance & Correctness", "robot", "Improved automation"),
                ("Performance & Correctness", "white_check_mark", "Added tests"),
                ("Performance & Correctness", "muscle", "Fixed bug"),
                ("Performance & Correctness", "closed_lock_with_key", "Addressed security concern"),
                ("Performance & Correctness", "loudspeaker", "Added logging"),
                ("Performance & Correctness", "mute", "Removed logging"),

                ("Refactor", "triangular_ruler", "Refactored code"),
                ("Refactor", "bookmark", "Added file(s)"),
                ("Refactor", "fire", "Removed file(s)"),
                ("Refactor", "pencil2", "Renamed file(s)/directory(s)"),
                ("Refactor", "arrow_heading_up", "Upgraded dependency(s)"),
                ("Refactor", "arrow_heading_down", "Downgraded dependency(s)"),

                ("Miscellaneous", "memo", "Added documentation"),
                ("Miscellaneous", "construction", "Work in progress"),
            ]:
                table.add_row(":{}:".format(emoji), emoji, category, description)

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
                                table,
                                "",
                                "This table is based on a more complete list available at https://gist.github.com/georgekrax/dfeb283f714c722ca28b4e98ada29d1c.",
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
        dm.WriteVerbose("Skipping empty message check to to the '{}' environment variable.\n".format(DISABLE_TITLE_LENGTH_CHECK_ENV_VAR))
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
        dm.WriteVerbose("Skipping empty message check to to the '{}' environment variable.\n".format(DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR))
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
