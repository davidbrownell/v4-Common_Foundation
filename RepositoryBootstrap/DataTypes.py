# ----------------------------------------------------------------------
# |
# |  DataTypes.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 10:41:35
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains data types used during the repository setup/activate process"""

import re
import textwrap
import uuid

from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from enum import auto, Enum, IntFlag
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Group
from rich.panel import Panel

from Common_Foundation import JsonEx
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.Capabilities import Capabilities
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation.Types import extensionmethod

from . import Configuration as ConfigurationMod


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------

# ----------------------------------------------------------------------
# |
# |  Setup and Activate Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class RepoData(object):
    # ----------------------------------------------------------------------
    name: str
    id: uuid.UUID

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "id": str(self.id),
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        data["id"] = uuid.UUID(data["id"])

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "RepoData":
        return cls(**cls.FromJson(data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ConfiguredRepoData(RepoData):
    # ----------------------------------------------------------------------
    configuration: Optional[str]

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        data = super(ConfiguredRepoData, self).ToJson()

        data["configuration"] = self.configuration

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def FromJson(
        cls,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = super(ConfiguredRepoData, cls).FromJson(data)

        data["configuration"] = JsonEx.JsonToOptional(data["configuration"])

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "ConfiguredRepoData":
        return cls(**cls.FromJson(data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ConfiguredRepoDataWithPath(ConfiguredRepoData):
    # ----------------------------------------------------------------------
    root: Path
    is_mixin_repo: bool                     = field(kw_only=True)

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        data = super(ConfiguredRepoDataWithPath, self).ToJson()

        data["root"] = self.root.as_posix()
        data["is_mixin_repo"] = self.is_mixin_repo

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def FromJson(
        cls,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        data = super(ConfiguredRepoDataWithPath, cls).FromJson(data)

        data["root"] = Path(data["root"])

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "ConfiguredRepoDataWithPath":
        return cls(**cls.FromJson(data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EnhancedRepoData(RepoData):
    """Information about a repo"""

    # ----------------------------------------------------------------------
    root: Path
    clone_uri: ConfigurationMod.Dependency.CLONE_URI_TYPE

    configurations: Dict[Optional[str], ConfigurationMod.Configuration]

    dependencies: Dict[Optional[str], List[ConfiguredRepoData]]
    dependents: Dict[Optional[str], List[ConfiguredRepoData]]


# ----------------------------------------------------------------------
# |
# |  SCM Hook Types
# |
# ----------------------------------------------------------------------
@dataclass
class ChangeInfo(object):
    """Information about a commit"""

    # ----------------------------------------------------------------------
    class ChangeType(Enum):
        Standard                            = auto()
        Amend                               = auto()
        Squash                              = auto()

    # ----------------------------------------------------------------------
    commit_type: "ChangeInfo.ChangeType"    # immutable
    id: str                                 # immutable
    author: str                             # immutable

    title: str
    description: Optional[str]

    files_added: Optional[List[Path]]
    files_modified: Optional[List[Path]]
    files_removed: Optional[List[Path]]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.files_added is None or self.files_added
        assert self.files_modified is None or self.files_modified
        assert self.files_removed is None or self.files_removed


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PushInfo(object):
    """Information about changes to be pushed to a remote repository."""

    # ----------------------------------------------------------------------
    remote_name: str
    changes: List[ChangeInfo]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.changes


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class MergeInfo(object):
    """Information about changes to be integrated from a remote repository."""

    # ----------------------------------------------------------------------
    remote_name: str
    changes: List[ChangeInfo]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.changes


# ----------------------------------------------------------------------
class SCMPlugin(ABC):
    """\
    Abstract base class for a plugin able to process changes.

    Note that this functionality may be invoked outside of an activate environment,
    so only import from python and Common_Foundation. Other imports will fail.
    """

    # ----------------------------------------------------------------------
    # |
    # |  Public Types
    # |
    # ----------------------------------------------------------------------
    class Flag(IntFlag):
        OnCommit                            = auto()
        OnPush                              = auto()
        OnMerge                             = auto()
        ValidatePullRequest                 = auto()

        OnCommitCanBeDisabled               = auto()
        OnPushCanBeDisabled                 = auto()
        OnMergeCanBeDisabled                = auto()
        ValidatePullRequestCanBeDisabled    = auto()

        # Amalgamations
        CanBeDisabled                       = (
            OnCommitCanBeDisabled
            | ValidatePullRequestCanBeDisabled
        )

    # ----------------------------------------------------------------------
    DEFAULT_PRIORITY                        = 10000

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
    def description(self) -> str:
        raise Exception("Abstract property")  # pragma: no cover

    @property
    def priority(self) -> int:
        return self.__class__.DEFAULT_PRIORITY

    @property
    @abstractmethod
    def flags(self) -> "SCMPlugin.Flag":
        raise Exception("Abstract property")  # pragma: no cover

    @cached_property
    def disable_commit_messages(self) -> list[str]:
        return ["No {}".format(self.name), ]

    @cached_property
    def disable_environment_variable(self) -> str:
        value = self.name

        for regex, sub in [
            (r"(.)([A-Z][a-z]+)", r"\1_\2"),
            (r"([a-z0-9])([A-Z])", r"\1_\2"),
        ]:
            value = re.sub(regex, sub, value)

        return "DEVELOPMENT_ENVIRONMENT_PULL_REQUEST_VALIDATOR_NO_{}".format(value.upper())

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    @extensionmethod
    def OnCommit(
        self,
        dm: DoneManager,
        repository: Repository,
        changes: list[ChangeInfo],
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @extensionmethod
    def OnPush(
        self,
        dm: DoneManager,
        repository: Repository,
        push_info: PushInfo,
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @extensionmethod
    def OnMerge(
        self,
        dm: DoneManager,
        repository: Repository,
        merge_info: MergeInfo,
    ) -> None:
        raise Exception("Abstract method") # pragma: no cover

    # ----------------------------------------------------------------------
    def DisplayError(
        self,
        dm: DoneManager,
        message: str,
        disable_flag: "SCMPlugin.Flag",
        disable_description: str="this validation",
    ) -> None:
        dm.result = -1

        self._DisplayImpl(
            dm,
            message,
            "[bold red]",
            disable_flag,
            disable_description,
        )

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    def _DisplayMessage(
        self,
        dm: DoneManager,
        message: str,
        disable_flag: "SCMPlugin.Flag",
        disable_description: str="this validation",
    ) -> None:
        self._DisplayImpl(
            dm,
            message,
            "[bold white]",
            disable_flag,
            disable_description,
        )

    # ----------------------------------------------------------------------
    def _DisplayImpl(
        self,
        dm: DoneManager,
        message: str,
        style: str,
        disable_flag: "SCMPlugin.Flag",
        disable_description: str="this validation",
    ) -> None:
        with dm.YieldStdout() as stdout_context:
            capabilities = Capabilities.Get(stdout_context.stream)

            console = capabilities.CreateRichConsole(
                StreamDecorator(
                    stdout_context.stream,
                    line_prefix=stdout_context.line_prefix,
                ),  # type: ignore
            )

            console.size = (console.width - len(stdout_context.line_prefix), console.height)

            panels: list[Panel] = [
                Panel(
                    Group(message),
                    padding=(1, 2),
                    title="{}{}[/]".format(style, self.name),
                    title_align="left",
                ),
            ]

            disable_messages: list[str] = [
                "To permanently disable {} for your repository, set the environment variable '{}' to a non-zero value during the repository's activation (this is not recommended).".format(
                    disable_description,
                    self.disable_environment_variable,
                ),
            ]

            if self.flags & disable_flag:
                disable_messages.append("")

                disable_commit_messages = self.disable_commit_messages

                if len(disable_commit_messages) == 1:
                    disable_messages.append(
                        "To disable {}, include the text '{}' in the commit message.".format(
                            disable_description,
                            disable_messages[0],
                        ),
                    )
                else:
                    disable_messages.append(
                        textwrap.dedent(
                            """\
                            To disable {}, include any of these in the commit message:

                            {}
                            """,
                        ).format(
                            disable_description,
                            "\n".join("    - '{}'".format(disable_commit_message) for disable_commit_message in disable_commit_messages),
                        ),
                    )

            panels.append(
                Panel(
                    Group(*disable_messages),
                    padding=(1, 2),
                    title="[bold yellow]Disabling this {}[/]".format(disable_description),
                    title_align="left",
                ),
            )

            console.print(Group(*panels))
