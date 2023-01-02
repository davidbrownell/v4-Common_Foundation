# ----------------------------------------------------------------------
# |
# |  Configuration.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 16:06:03
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains types used when defining repository configurations"""

import uuid

from dataclasses import dataclass, field, InitVar
from typing import Any, Callable, Dict, List, Optional, Union

import wrapt

from semantic_version import Version as SemVer


# ----------------------------------------------------------------------
@wrapt.decorator
def MixinRepository(
    wrapped,
    instance,  # pylint: disable=unused-argument
    args,
    kwargs,
):
    """
    Signals that a repository is a mixin repository (a repository that
    contains items that help in the development process but doesn't contain
    primitives used by other dependent repositories). Mixin repositories
    must be activated on top of other repositories and make not may any
    assumptions about the state of the repository on which they are activated.
    """
    return wrapped(*args, **kwargs)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class VersionInfo(object):
    """Mapping of a specific tool or library to a specific version"""

    # ----------------------------------------------------------------------
    name: str
    version: Optional[SemVer]               # None to disable the corresponding tool or library

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": None if self.version is None else str(self.version),
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        if data["version"] == "null":
            data["version"] = None
        else:
            data["version"] = SemVer(data["version"])

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "VersionInfo":
        return cls(**cls.FromJson(data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class VersionSpecs(object):
    """Collection of `VersionInfo` objects for a repository, organized by tools and libraries"""

    # ----------------------------------------------------------------------
    tools: List[VersionInfo]
    libraries: Dict[str, List[VersionInfo]]

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "tools": [tool.ToJson() for tool in self.tools],
            "libraries": {
                library_name: [library.ToJson() for library in libraries]
                for library_name, libraries in self.libraries.items()
            },
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "VersionSpecs":
        return cls(
            tools=[VersionInfo.CreateFromJson(tool) for tool in data["tools"]],
            libraries={
                library_name: [VersionInfo.CreateFromJson(library) for library in libraries]
                for library_name, libraries in data["libraries"].items()
            },
        )


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Dependency(object):
    """A dependency on another repository"""

    # ----------------------------------------------------------------------
    CLONE_URI_TYPE                          = Union[
        None,
        str,
        Callable[
            [
                Optional[str]               # Name of the source control management system (e.g. "mercurial", "git", etc.)
            ],
            str,                            # URL to the repository
        ]
    ]

    # ----------------------------------------------------------------------
    repository_id: uuid.UUID
    friendly_name: str
    configuration: Optional[str]
    clone_uri: CLONE_URI_TYPE

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "repository_id": str(self.repository_id),
            "friendly_name": self.friendly_name,
            "configuration": self.configuration,
            "clone_uri": None, # This value is never persisted
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        data["repository_id"] = uuid.UUID(data["repository_id"])

        if data["configuration"] == "null":
            data["configuration"] = None

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "Dependency":
        return cls(**cls.FromJson(data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Configuration(object):
    """\
    A named configuration specified during activation time.

    A repository can have many configurations, where each configuration
    activates different sets of libraries and dependencies.

    An example of different configurations with a repository could be
    "development" and "production" configurations, where the "development"
    configuration uses libraries and repositories useful while writing
    code in the repository, while "production" only includes those
    dependencies that are necessary when running the code.
    """

    # ----------------------------------------------------------------------
    description: str

    dependencies: List[Dependency]

    version_specs_param: InitVar[Optional[VersionSpecs]]                    = None
    version_specs: VersionSpecs                                             = field(init=False)

    # `suppress_conflicted_repositories` is a list of names of repositories that have configuration conflicts
    # that can be safely ignored. In the vast majority of cases, two repositories with different configurations
    # is considered a configuration error. However, in some cases (such as with bootstrap repos that don't
    # actually use the activated repositories), these conflicts can be ignored. In those scenarios, the first
    # configuration encountered will always be the configuration that is activated within the environment.
    suppress_conflicted_repositories: Optional[List[uuid.UUID]]             = field(default=None)

    # `suppress_conflicted_tools` is a list of names of tools that have conflicts that can be safely ignored.
    # In the vast majority of cases, two repos providing or requiring different versions of the same tool is
    # a configuration error. However, in some cases (such as with bootstrap repos that don't actually use the
    # library), these conflicts can be ignored. In those scenarios, the first version encountered will always
    # be the version used within the activated environment.
    suppress_conflicted_tools: Optional[List[str]]                          = field(default=None)

    # `suppress_conflicted_libraries` is a list of names of libraries that have conflicts that can be safely ignored.
    # In the vast majority of cases, two repos providing or requiring different versions of the same library is
    # a configuration error. However, in some cases (such as with bootstrap repos that don't actually use the
    # library), these conflicts can be ignored. In those scenarios, the first version encountered will always
    # be the version used within the activated environment.
    suppress_conflicted_libraries: Optional[Dict[str, List[str]]]           = field(default=None)

    # ----------------------------------------------------------------------
    def __post_init__(self, version_specs_param):
        object.__setattr__(self, "version_specs", version_specs_param or VersionSpecs([], {}))

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "dependencies": [dependency.ToJson() for dependency in self.dependencies],
            "version_specs": self.version_specs.ToJson(),
            "suppress_conflicted_repositories": None if self.suppress_conflicted_repositories is None else [str(value) for value in self.suppress_conflicted_repositories],
            "suppress_conflicted_tools": self.suppress_conflicted_tools,
            "suppress_conflicted_libraries": self.suppress_conflicted_libraries,
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        if data["suppress_conflicted_repositories"] is not None:
            data["suppress_conflicted_repositories"] = [uuid.UUID(value) for value in data["suppress_conflicted_repositories"]]

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        data: Dict[str, Any],
    ) -> "Configuration":
        data = cls.FromJson(data)

        return cls(
            description=data["description"],
            dependencies=[Dependency.CreateFromJson(dependency) for dependency in data["dependencies"]],
            version_specs_param=VersionSpecs.CreateFromJson(data["version_specs"]),
            suppress_conflicted_repositories=data["suppress_conflicted_repositories"],
            suppress_conflicted_tools=data["suppress_conflicted_tools"],
            suppress_conflicted_libraries=data["suppress_conflicted_libraries"],
        )
