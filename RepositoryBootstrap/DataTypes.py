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
import uuid

from abc import abstractmethod, ABC
from dataclasses import dataclass, field
from datetime import datetime
from enum import auto, Enum, IntFlag
from functools import cached_property
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from Common_Foundation import JsonEx
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
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
    change_type: "ChangeInfo.ChangeType"    # immutable
    change_info: Repository.ChangeInfo      # immutable

    title: str
    description: Optional[str]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        change_type: "ChangeInfo.ChangeType",
        commit_id: str,
        title: str,
        description: Optional[str],
        author: str,
        author_date: datetime,
        files_added: list[Path],
        files_removed: list[Path],
        files_modified: list[Path],
    ) -> "ChangeInfo":
        if description:
            official_description = "{}\n\n{}".format(title.rstrip(), description.strip())
        else:
            official_description = title.rstrip()

        return cls(
            change_type,
            Repository.ChangeInfo(
                commit_id,
                official_description,
                [],
                author,
                author_date,
                files_added,
                files_removed,
                files_modified,
                [],
            ),
            title,
            description,
        )

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromRepositoryChangeInfo(
        cls,
        change_info: Repository.ChangeInfo,
    ) -> "ChangeInfo":
        match = re.match(
            r"(?P<title>[^\n]+)(?:\n+(?P<description>.+))?",
            change_info.description,
            re.DOTALL | re.MULTILINE,
        )

        assert match is not None, change_info.description

        title = match.group("title")
        description = match.group("description") or None

        return cls(
            ChangeInfo.ChangeType.Standard,
            change_info,
            title,
            description,
        )


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

        ExecuteInBatch                      = auto()

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
        value = self.name.replace(" ", "")

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
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,
        change: ChangeInfo,
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @extensionmethod
    def ExecuteBatch(
        self,
        dm: DoneManager,
        repository: Repository,
        changes: Iterator[tuple[ChangeInfo, DoneManager]],
    ) -> None:
        raise Exception("Abstract method")  # pragma: no cover
