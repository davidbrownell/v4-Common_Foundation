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

from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import PathEx
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import CommitInfo, PreIntegrateInfo, PrePushInfo


# ----------------------------------------------------------------------
DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE          = "Do not decorate commit message"
DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_HOOKS_NO_COMMIT_MESSAGE_DECORATION"

DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE  = "No empty message check"
DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR         = "DEVELOPMENT_ENVIRONMENT_HOOKS_NO_EMPTY_MESSAGE_CHECK"

DISABLE_EMOJI_CHECK_COMMIT_MESSAGE          = "No emoji check"
DISABLE_EMOJI_CHECK_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_HOOKS_NO_COMMIT_EMOJI_CHECK"

DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE   = "No title length check"
DISABLE_TITLE_LENGTH_CHECK_ENV_VAR          = "DEVELOPMENT_ENVIRONMENT_HOOKS_NO_TITLE_LENGTH_CHECK"

DISABLE_BANNED_TEXT_COMMIT_MESSAGE          = "Allow banned text"
DISABLE_BANNED_TEXT_ENV_VAR                 = "DEVELOPMENT_ENVIRONMENT_HOOKS_NO_BANNED_TEXT_CHECK"


# ----------------------------------------------------------------------
def OnCommit(
    dm: DoneManager,
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,
    commits: List[CommitInfo],
    *,
    first_configuration_in_repo: bool,
) -> Optional[bool]:                        # Return False to prevent the execution of other hooks
    """Called before changes are committed to the local repository."""

    # We don't care about configuration, so bail if we have already performed the validation
    if not first_configuration_in_repo:
        return

    with dm.Nested("Decorating commit message...") as decorate_dm:
        DecorateCommitMessage(decorate_dm, commits[0])

    with dm.Nested(
        "Ensuring commit message...",
        suffix=lambda: "\n" if validate_dm.result != 0 else "",
    ) as validate_dm:
        EnsureCommitMessage(validate_dm, commits[0])

    with dm.Nested(
        "Ensuring valid commit message title...",
        suffix=lambda: "\n" if validate_dm.result != 0 else "",
    ) as validate_dm:
        EnsureValidTitle(validate_dm, commits[0])

    with dm.Nested(
        "Ensuring that the commit message begins with an emoji...",
        suffix=lambda: "\n" if validate_dm.result != 0 else "",
    ) as validate_dm:
        EnsureEmoji(validate_dm, commits[0])

    with dm.Nested(
        "Validating banned text...",
        suffix=lambda: "\n" if validate_dm.result != 0 else "",
    ) as validate_dm:
        ValidateBannedText(validate_dm, repository.repo_root, commits[0])


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
def DecorateCommitMessage(
    dm: DoneManager,
    commit_info: CommitInfo,
) -> None:
    if _IsDisabled(
        dm,
        commit_info,
        "commit message decoration",
        DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR,
        DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE,
    ):
        return

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

        command_line = 'python {} Transform "{}"'.format(commit_emojis_dir, value)
        result = SubprocessEx.Run(command_line)

        assert result.returncode == 0, (result.returncode, result.output)
        return result.output

    # ----------------------------------------------------------------------

    new_title = Transform(commit_info.title)
    assert new_title is not None

    new_description = Transform(commit_info.description)

    if new_title != commit_info.title or new_description != commit_info.description:
        with _YieldRichConsole(dm) as console:
            # ----------------------------------------------------------------------
            def DisplayMessage(
                title: str,
                description: Optional[str],
            ) -> str:
                return TextwrapEx.Indent(
                    textwrap.dedent(
                        """\
                        {}{}
                        """,
                    ).format(
                        title,
                        "" if not description else "\n\n{}".format(description),
                    ).replace("[", "\\["),
                    4,
                )

            # ----------------------------------------------------------------------

            console.print(
                Group(
                    Panel(
                        Group(
                            "The commit message has been changed from:\n",
                            DisplayMessage(commit_info.title, commit_info.description),
                            "to:\n",
                            DisplayMessage(new_title, new_description),
                        ),
                        padding=(1, 2),
                        title="[bold white]INFO[/]",
                        title_align="left",
                    ),
                    _CreateDisablePanel(
                        "this decoration",
                        DISABLE_DECORATE_COMMIT_MESSAGE_ENV_VAR,
                        DISABLE_DECORATE_COMMIT_MESSAGE_COMMIT_MESSAGE,
                    ),
                ),
            )

        commit_info.title = new_title
        commit_info.description = new_description


# ----------------------------------------------------------------------
def EnsureCommitMessage(
    dm: DoneManager,
    commit_info: CommitInfo,
) -> None:
    if not commit_info.is_user_authored:
        return

    if _IsDisabled(
        dm,
        commit_info,
        "commit message validation",
        DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR,
        DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE,
    ):
        return

    if not commit_info.title:
        dm.result = -1

        with _YieldRichConsole(dm) as console:
            console.print(
                Group(
                    Panel(
                        "The commit message cannot be empty.",
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    _CreateDisablePanel(
                        "this validation",
                        DISABLE_EMPTY_MESSAGE_CHECK_ENV_VAR,
                        DISABLE_EMPTY_MESSAGE_CHECK_COMMIT_MESSAGE,
                    ),
                ),
            )


# ----------------------------------------------------------------------
def EnsureValidTitle(
    dm: DoneManager,
    commit_info: CommitInfo,
) -> None:
    if not commit_info.is_user_authored:
        return

    if _IsDisabled(
        dm,
        commit_info,
        "title validation",
        DISABLE_TITLE_LENGTH_CHECK_ENV_VAR,
        DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE,
    ):
        return

    # Longest title length that can be displayed on GitHub.com without introducing an ellipsis
    # (rounded down to a slightly-less specific value that is hopefully easy to remember).
    max_title_length = 65

    if len(commit_info.title) > max_title_length:
        dm.result = -1

        with _YieldRichConsole(dm) as console:
            console.print(
                Group(
                    Panel(
                        textwrap.dedent(
                            """\
                            The commit title "{}" is too long.

                                Maximum length:   {}
                                Current length:   {}
                            """,
                        ).format(commit_info.title, max_title_length, len(commit_info.title)),
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    _CreateDisablePanel(
                        "this validation",
                        DISABLE_TITLE_LENGTH_CHECK_ENV_VAR,
                        DISABLE_TITLE_LENGTH_CHECK_COMMIT_MESSAGE,
                    ),
                ),
            )



# ----------------------------------------------------------------------
def EnsureEmoji(
    dm: DoneManager,
    commit_info: CommitInfo,
) -> None:
    if not commit_info.is_user_authored:
        return

    if _IsDisabled(
        dm,
        commit_info,
        "emoji validation",
        DISABLE_EMOJI_CHECK_ENV_VAR,
        DISABLE_EMOJI_CHECK_COMMIT_MESSAGE,
    ):
        return

    # This won't work in all cases, but consider a 32 bit char an emoji
    assert commit_info.title
    title_bytes = commit_info.title.encode("UTF-8")

    startswith_emoji = (
        (len(title_bytes) >= 2 and (title_bytes[0] >> 5) == 0b110)
        or (len(title_bytes) >= 3 and (title_bytes[0] >> 4) == 0b1110)
        or (len(title_bytes) >= 4 and (title_bytes[0] >> 3) == 0b11110)
    )

    if not startswith_emoji:
        dm.result = -1

        with _YieldRichConsole(dm) as console:
            console.print(
                Group(
                    Panel(
                        Group(
                            textwrap.dedent(
                                """\
                                The commit message "{}" does not adhere to Gitmoji conventions (it does not begin with an emoji).

                                For a list of available Gitmoji values, run `CommitEmojis Display` within an activated environment.

                                Visit https://gitmoji.dev/ for more information about Gitmoji and its benefits.
                                """,
                            ).format(commit_info.title),
                        ),
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    _CreateDisablePanel(
                        "this validation",
                        DISABLE_EMOJI_CHECK_ENV_VAR,
                        DISABLE_EMOJI_CHECK_COMMIT_MESSAGE,
                    ),
                ),
            )


# ----------------------------------------------------------------------
def ValidateBannedText(
    dm: DoneManager,
    repository_root: Path,
    commit_info: CommitInfo,
) -> None:
    if not commit_info.files_added and not commit_info.files_modified:
        return

    if _IsDisabled(
        dm,
        commit_info,
        "banned text validation",
        DISABLE_BANNED_TEXT_ENV_VAR,
        DISABLE_BANNED_TEXT_COMMIT_MESSAGE,
    ):
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
        assert len(repository_root.parts) < len(filename.parts)
        return str(Path(*filename.parts[len(repository_root.parts):]))

    # ----------------------------------------------------------------------

    filenames = list(itertools.chain(commit_info.files_added or [], commit_info.files_modified or []))

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
        with _YieldRichConsole(dm) as console:
            console.print(
                Group(
                    Panel(
                        Group(
                            "Banned text was found in these files:\n",
                            *errors,
                        ),
                        padding=(1, 2),
                        title="[bold red]ERROR[/]",
                        title_align="left",
                    ),
                    _CreateDisablePanel(
                        "this validation",
                        DISABLE_BANNED_TEXT_ENV_VAR,
                        DISABLE_BANNED_TEXT_COMMIT_MESSAGE,
                    ),
                ),
            )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _IsDisabled(
    dm: DoneManager,
    commit_info: CommitInfo,
    desc: str,
    disable_env_var: str,
    disable_message: str,
) -> bool:
    env_disable_value = os.getenv(disable_env_var)
    if env_disable_value is not None and env_disable_value != "0":
        dm.WriteVerbose("Skipping {} due to the '{}' environment variable.\n".format(desc, disable_env_var))
        return True

    disable_message_lower = disable_message.lower()

    if (
        disable_message_lower in commit_info.title.lower()
        or (commit_info.description and disable_message_lower in commit_info.description.lower())
    ):
        dm.WriteVerbose("Skipping {} due to '{}' in the commit message.\n".format(desc, disable_message))
        return True

    return False


# ----------------------------------------------------------------------
def _CreateDisablePanel(
    desc: str,
    disable_env_var: str,
    disable_message: str,
) -> Panel:
    return Panel(
        Group(
            "To disable {}, include the text '{}' in the commit message.".format(desc, disable_message),
            "",
            "To permanently disable {} for your repository, set the environment value '{}' to a non-zero value during your repository's activation (this is not recommended).".format(desc, disable_env_var),
        ),
        padding=(1, 2),
        title="[bold yellow]Disabling {}[/]".format(desc),
        title_align="left",
    )


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
