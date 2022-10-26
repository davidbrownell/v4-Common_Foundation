# ----------------------------------------------------------------------
# |
# |  DataTypes.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 10:41:35
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains data types used during the repository setup/activate process"""

import uuid

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from Common_Foundation import JsonEx  # type: ignore

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
@dataclass(frozen=True)
class CommitInfo(object):
    """Information about a commit"""

    # ----------------------------------------------------------------------
    id: str
    author: str
    description: str
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
class PrePushInfo(object):
    """Information about changes to be pushed to a remote repository."""

    # ----------------------------------------------------------------------
    remote_name: str
    changes: List[str]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.changes


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PreIntegrateInfo(object):
    """Information about changes to be integrated from a remote repository."""

    # ----------------------------------------------------------------------
    remote_name: str
    changes: List[str]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.changes
