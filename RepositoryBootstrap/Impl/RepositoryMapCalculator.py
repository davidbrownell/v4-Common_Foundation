# ----------------------------------------------------------------------
# |
# |  RepositoryMapCalculator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-24 08:13:05
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the types and functionality to generate a map of a repository and its dependencies"""

import os
import types
import uuid

from abc import abstractmethod, ABC
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast, Any, Callable, ContextManager, Dict, Generator, Iterator, List, Optional, Tuple, Set, Union

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.DynamicFunctions import GetCustomizationMod as GetCustomizationModImpl
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell

from . import Utilities

from .. import Configuration
from .. import Constants
from .. import DataTypes


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
ENUMERATE_EXCLUDE_DIRS                      = [
    "generated",
    "__pycache__",
]

if CurrentShell.family_name == "Windows":
    for potential_env_name in [
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "WINDIR",
    ]:
        env_value = os.getenv(potential_env_name)
        if env_value is not None:
            ENUMERATE_EXCLUDE_DIRS.append(env_value)


# The following terms are given higher priority during search, as they contain names
# that are more likely to contain repositories.
CODE_DIRECTORY_NAMES                        = [
    "code",
    "coding",

    "development",
    "develop",
    "dev",

    "source",
    "src",
]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PendingRepoData(Configuration.Dependency):
    # ----------------------------------------------------------------------
    source_id: uuid.UUID
    source_configuration: Optional[str]

    dependents: Dict[Optional[str], List[DataTypes.ConfiguredRepoData]]   = field(init=False, default_factory=dict)

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        dependency: Configuration.Dependency,
        source_id: uuid.UUID,
        source_configuration: Optional[str],
    ) -> "PendingRepoData":
        return cls(
            **{
                **dependency.__dict__,
                **{
                    "source_id": source_id,
                    "source_configuration": source_configuration,
                },
            },
        )


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EncounteredRepoData(DataTypes.EnhancedRepoData):
    # ----------------------------------------------------------------------
    are_configurations_filtered: bool       = field(kw_only=True)
    is_mixin_repository: bool               = field(kw_only=True)

    is_referenced: bool                     = field(init=False, default=False)

    has_configurations: bool                = field(init=False)

    # Base type overloads
    dependencies: Dict[Optional[str], List[DataTypes.ConfiguredRepoData]]   = field(init=False, default_factory=dict)
    dependents: Dict[Optional[str], List[DataTypes.ConfiguredRepoData]]     = field(init=False, default_factory=dict)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.root is not None

        object.__setattr__(
            self,
            "has_configurations",
            (
                len(self.configurations) > 1
                or None not in self.configurations
            ),
        )

        if self.is_mixin_repository:
            if self.dependencies:
                raise Exception("A mixin repository cannot have dependencies.")

            if self.has_configurations:
                raise Exception("A mixin repository cannot have configurations.")

            for config_data in self.configurations.values():
                if config_data.version_specs.tools:
                    raise Exception("A mixin repository cannot specify tool versions.")

                if config_data.version_specs.libraries:
                    raise Exception("A mixin repository cannot specify library versions.")

    # ----------------------------------------------------------------------
    # Update the comments in ../Constants.py if this method name changes
    @classmethod
    def Create(
        cls,
        name: str,
        id: uuid.UUID,  # pylint: disable=redefined-builtin
        root: Path,
        customization_mod: types.ModuleType,
        explicit_configurations: Optional[List[str]],
    ) -> "EncounteredRepoData":
        dependencies_func = getattr(
            customization_mod,
            Constants.SETUP_ENVIRONMENT_CONFIGURATIONS_METHOD_NAME,
            None,
        )

        if dependencies_func is None:
            raise Exception(
                "The method '{}' was not found in the setup information for '{}'.".format(
                    Constants.SETUP_ENVIRONMENT_CONFIGURATIONS_METHOD_NAME,
                    root,
                ),
            )

        configurations = dependencies_func()
        if configurations is None:
            raise Exception("No configurations were found for the repository at '{}'.".format(root))

        if not isinstance(configurations, dict):
            configurations = {None: configurations}

        configurations = cast(Dict[Optional[str], Configuration.Configuration], configurations)

        # Mixin repositories are specified via the MixinRepository decorator
        is_mixin_repository = (
            hasattr(dependencies_func, "_self_wrapper")
            and dependencies_func._self_wrapper.__name__ == "MixinRepository"  # pylint: disable=protected-access
        )

        if explicit_configurations:
            for config_name in list(configurations.keys()):
                if config_name not in explicit_configurations:
                    del configurations[config_name]

            if not configurations:
                raise Exception(
                    "No configurations were found matching {}".format(
                        ", ".join(
                            '"{}"'.format(supported_configuration)
                            for supported_configuration in explicit_configurations
                        ),
                    ),
                )

        # Pylint struggles with this definition as we are reordering attributes and providing default
        # values that differ from the base class.
        return cls(  # type: ignore  # pylint: disable=no-value-for-parameter
            name,
            id,
            root,
            clone_uri=None, # We don't need to set the clone uri for this repo since we have it on our system already
            configurations=configurations,
            are_configurations_filtered=bool(explicit_configurations),
            is_mixin_repository=is_mixin_repository,
        )

    # ----------------------------------------------------------------------
    def SetReferenced(self) -> None:
        object.__setattr__(self, "is_referenced", True)


# ----------------------------------------------------------------------
class RepositoryMapCalculator(ABC):
    """Implements a repository map calculator, where events are exposed as abstract methods that must be implemented by derived instances"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        repository_root: Path,
        search_depth: int,
        max_num_searches: Optional[int],
        required_ancestor_dirs: Optional[List[Path]],
        *,
        recurse: bool,
        explicit_configurations: Optional[List[str]]=None,
        additional_search_dirs: Optional[List[Path]],
    ):
        assert repository_root.is_dir(), repository_root
        assert search_depth > 0, search_depth
        assert max_num_searches is None or max_num_searches > 0, max_num_searches
        assert required_ancestor_dirs is None or required_ancestor_dirs, required_ancestor_dirs
        assert explicit_configurations is None or explicit_configurations, explicit_configurations
        assert additional_search_dirs is None or additional_search_dirs, additional_search_dirs

        encountered_repos: Dict[uuid.UUID, EncounteredRepoData] = {}
        pending_repos: Dict[uuid.UUID, PendingRepoData] = {}

        # ----------------------------------------------------------------------
        def Impl() -> bool:
            # Get the root repo data
            raw_root_repo_data = Utilities.GetRepoData(repository_root)
            assert raw_root_repo_data is not None

            # ----------------------------------------------------------------------
            def ReferenceRepo(
                repo_data: EncounteredRepoData,
            ) -> bool:
                if repo_data.is_referenced:
                    return True

                repo_data.SetReferenced()

                # Only process the configuration for this repo if dependency information is required
                if repo_data.id is not raw_root_repo_data.id and not recurse:
                    return True

                for config_name, config_info in repo_data.configurations.items():
                    configuration_dependencies: List[DataTypes.ConfiguredRepoData] = []

                    for dependency in config_info.dependencies:
                        configuration_dependencies.append(
                            DataTypes.ConfiguredRepoData(
                                dependency.friendly_name,
                                dependency.repository_id,
                                dependency.configuration,
                            ),
                        )

                        # ----------------------------------------------------------------------
                        def ProcessDependency() -> Union[PendingRepoData, EncounteredRepoData]:
                            # Have we seen this repository before?
                            encountered_dependency = encountered_repos.get(dependency.repository_id, None)
                            if encountered_dependency is not None:
                                if dependency.friendly_name != encountered_dependency.name:
                                    self._OnDependencyNameMismatch(
                                        encountered_data,
                                        dependency.friendly_name,
                                        repo_data,
                                        repo_data.root,
                                        config_name,
                                    )

                                if not encountered_dependency.is_referenced:
                                    ReferenceRepo(encountered_dependency)

                                return encountered_dependency

                            # Is it already pending?
                            pending_dependency = pending_repos.get(dependency.repository_id, None)
                            if pending_dependency is not None:
                                if dependency.friendly_name != pending_dependency.friendly_name:
                                    original_pending_reference = encountered_repos[pending_dependency.source_id]

                                    self._OnPendingNameMismatch(
                                        pending_dependency,
                                        original_pending_reference.root,
                                        dependency.friendly_name,
                                        repo_data,
                                        repo_data.root,
                                        config_name,
                                    )

                                return pending_dependency

                            # Create a pending
                            pending_dependency = PendingRepoData.Create(dependency, repo_data.id, config_name)

                            pending_repos[dependency.repository_id] = pending_dependency

                            return pending_dependency

                        # ----------------------------------------------------------------------

                        ProcessDependency().dependents.setdefault(
                            dependency.configuration,
                            [],
                        ).append(
                            DataTypes.ConfiguredRepoData(
                                repo_data.name,
                                repo_data.id,
                                config_name,
                            ),
                        )

                    repo_data.dependencies[config_name] = configuration_dependencies

                return True

            # ----------------------------------------------------------------------

            # Create the EncounteredRepoData for the root
            with GetCustomizationMod(repository_root) as customization_mod:
                encountered_repos[raw_root_repo_data.id] = EncounteredRepoData.Create(
                    raw_root_repo_data.name,
                    raw_root_repo_data.id,
                    repository_root,
                    customization_mod,
                    explicit_configurations,
                )

            if not ReferenceRepo(encountered_repos[raw_root_repo_data.id]):
                return False

            # Process any pending repositories
            if pending_repos:
                with self._SearchContext(encountered_repos, pending_repos):
                    was_terminated = False
                    directories_searched = 0

                    pending_search_directories: List[Any] = []

                    # ----------------------------------------------------------------------
                    def OnStatusUpdate(
                        path: Optional[Path],
                    ) -> bool:
                        if not self._OnStatusUpdate(
                            directories_searched,
                            len(pending_search_directories),
                            len(encountered_repos),
                            len(pending_repos),
                            path,
                        ):
                            nonlocal was_terminated
                            was_terminated = True

                        return not was_terminated

                    # ----------------------------------------------------------------------

                    with ExitStack(lambda: OnStatusUpdate(None)):
                        if required_ancestor_dirs is None:
                            is_valid_ancestor_func = lambda _: True
                        else:
                            # ----------------------------------------------------------------------
                            def IsValidAncestor(
                                path: Path,
                            ) -> bool:
                                assert required_ancestor_dirs is not None

                                return any(
                                    PathEx.IsDescendant(path, required_ancestor_dir)
                                    for required_ancestor_dir in required_ancestor_dirs
                                )

                            # ----------------------------------------------------------------------

                            is_valid_ancestor_func = IsValidAncestor

                        # Prepare the search
                        search_dirs: List[Tuple[Path, bool]] = [
                            (repository_root, True),
                        ] + [(additional_search_dir, True) for additional_search_dir in (additional_search_dirs or [])]

                        if CurrentShell.family_name == "Windows":
                            # If here, look at other drive locations
                            import win32api  # type: ignore
                            import win32file  # type: ignore

                            for drive in [
                                drive
                                for drive in win32api.GetLogicalDriveStrings().split("\000")
                                if drive and win32file.GetDriveType(drive) == win32file.DRIVE_FIXED  # type: ignore
                            ]:
                                search_dirs.append((Path(drive), False))  # type: ignore
                        else:
                            search_dirs.append((Path(repository_root.root), False))  # type: ignore

                        # Execute the search
                        searched_dirs: Set[Path] = set()

                        for search_dir, skip_root in search_dirs:
                            # Augment the search depth to account for the search dir
                            this_search_depth = search_depth + len(search_dir.parts)

                            search_dir_str = str(search_dir)

                            # Prepare the items associated with the recursive search under this directory
                            pending_search_directories.clear()

                            # ----------------------------------------------------------------------
                            def FirstNonMatchingChar(
                                path: Path,
                            ) -> int:
                                index = 0

                                for index, c in enumerate(str(path)):
                                    if (
                                        index == len(search_dir_str)
                                        or c != search_dir_str[index]
                                    ):
                                        break

                                return index

                            # ----------------------------------------------------------------------
                            def PushSearchDir(
                                path: Path,
                            ) -> None:
                                # Order the search items in an attempt to search the things that are likely to
                                # yield good results over a standard depth-first search.
                                path = path.resolve()

                                if len(path.parts) > this_search_depth:
                                    return

                                priority = 1
                                for part in path.parts:
                                    if part.lower() in CODE_DIRECTORY_NAMES:
                                        priority = 0
                                        break

                                pending_search_directories.append(
                                    (
                                        -FirstNonMatchingChar(path),                            # Favor items with a common ancestor
                                        priority,                                               # Favor names that look like source code locations
                                        0 if PathEx.IsDescendant(path, Path.home()) else 1,     # Favor things in the home dir
                                        len(path.parts),                                        # Favor locations near the root
                                        str(path).lower(),                                      # Case-insensitive sort
                                        path,                                                   # The unaltered path - this must always be the last value
                                    ),
                                )

                            # ----------------------------------------------------------------------
                            def PopSearchDir() -> Path:
                                assert pending_search_directories
                                return pending_search_directories.pop(0)[-1]

                            # ----------------------------------------------------------------------
                            def SortSearchDirs() -> None:
                                pending_search_directories.sort()

                            # ----------------------------------------------------------------------
                            def EnumerateDirectories() -> Generator[Path, None, None]:
                                while pending_search_directories:
                                    search_dir = PopSearchDir()

                                    # Don't process the dir if it has already been processed
                                    if search_dir in searched_dirs:
                                        continue

                                    searched_dirs.add(search_dir)

                                    # Don't process the dir if it doesn't exist anymore (these searches can take awhile)
                                    if not search_dir.is_dir():
                                        continue

                                    # Don't process if the directory has been explicitly ignored
                                    if (search_dir / Constants.IGNORE_DIRECTORY_AS_BOOTSTRAP_DEPENDENCY_SENTINEL_FILENAME).exists():
                                        continue

                                    nonlocal directories_searched

                                    if not OnStatusUpdate(search_dir):
                                        return

                                    yield search_dir

                                    directories_searched += 1

                                    if max_num_searches is not None and directories_searched > max_num_searches:
                                        break

                                    # Add parents and children to the queue
                                    added = False

                                    # Add the parent
                                    try:
                                        potential_parent = search_dir.parent

                                        if (
                                            potential_parent != search_dir
                                            and is_valid_ancestor_func(potential_parent)
                                            and (
                                                not skip_root
                                                or potential_parent.parent != potential_parent
                                            )
                                        ):
                                            PushSearchDir(potential_parent)
                                            added = True

                                    except (PermissionError, FileNotFoundError, OSError):
                                        pass

                                    # Add the children
                                    try:
                                        for child_path in search_dir.iterdir():
                                            if (
                                                not child_path.is_dir()
                                                or child_path.name.startswith(".")
                                                or child_path.name.startswith("$")
                                                or child_path.name.lower() in ENUMERATE_EXCLUDE_DIRS
                                                or str(child_path) in ENUMERATE_EXCLUDE_DIRS
                                            ):
                                                continue

                                            PushSearchDir(child_path)
                                            added = True

                                    except (PermissionError, FileNotFoundError, OSError):
                                        pass

                                    # Sort the search items if we added something
                                    if added:
                                        SortSearchDirs()

                            # ----------------------------------------------------------------------

                            assert not pending_search_directories
                            PushSearchDir(search_dir)

                            for directory in EnumerateDirectories():
                                potential_repo_data = Utilities.GetRepoData(
                                    directory,
                                    raise_on_error=False,
                                )

                                if potential_repo_data is None:
                                    continue

                                # Note that we may have already encountered this repository. This can
                                # happen when the repo has already been found in a location nearer to the
                                # repository_root and the search has continued to find
                                # it in other locations. If this happens, use the original repo and ignore
                                # this one.
                                if potential_repo_data.id in encountered_repos:
                                    continue

                                try:
                                    with GetCustomizationMod(directory) as customization_mod:
                                        encountered_data = EncounteredRepoData.Create(
                                            potential_repo_data.name,
                                            potential_repo_data.id,
                                            directory,
                                            customization_mod,
                                            None,
                                        )

                                    encountered_repos[encountered_data.id] = encountered_data

                                    potential_pending_data = pending_repos.pop(encountered_data.id, None)
                                    if potential_pending_data is not None:
                                        if potential_pending_data.friendly_name != encountered_data.name:
                                            original_pending_reference = encountered_repos[potential_pending_data.source_id]

                                            self._OnDependencyNameMismatch(
                                                encountered_data,
                                                potential_pending_data.friendly_name,
                                                original_pending_reference,
                                                original_pending_reference.root,
                                                potential_pending_data.source_configuration,
                                            )

                                        # Associate all of the existing dependent info with this new data
                                        for k, v in potential_pending_data.dependents.items():
                                            encountered_data.dependents[k] = v

                                        if not ReferenceRepo(encountered_data):
                                            return False

                                        if not pending_repos:
                                            break

                                except Exception as ex:
                                    if not self._OnModuleError(ex, potential_repo_data, directory):
                                        return False

                            if not pending_repos:
                                break

                    if was_terminated:
                        return False

            return True

        # ----------------------------------------------------------------------

        was_terminated = not Impl()

        self.encountered_repos              = encountered_repos
        self.pending_repos                  = pending_repos

        self.was_terminated                 = was_terminated

    # ----------------------------------------------------------------------
    def Filter(self) -> None:
        """Removes all of the encountered and pending repository info that doesn't apply to the specified repository"""

        for repo_id in list(self.encountered_repos.keys()):
            repo_data = self.encountered_repos[repo_id]
            if not repo_data.is_referenced:
                del self.encountered_repos[repo_id]

    # ----------------------------------------------------------------------
    def EnumDependencyOrder(
        self,
        repository_root_or_id: Union[uuid.UUID, Path],
    ) -> Generator[EncounteredRepoData, None, None]:
        priorities: Dict[uuid.UUID, int] = {k:0 for k in self.encountered_repos}
        priority_modifier: int = 1

        # ----------------------------------------------------------------------
        @contextmanager
        def OnWalkItem(
            item: Union[
                EncounteredRepoData,
                PendingRepoData,
                Optional[str],
            ],
            is_being_used: bool,  # pylint: disable=unused-argument
        ) -> Iterator[None]:
            if isinstance(item, EncounteredRepoData):
                nonlocal priority_modifier

                priorities[item.id] += priority_modifier

                priority_modifier += 1

                # ----------------------------------------------------------------------
                def ReducePriorityModifier():
                    nonlocal priority_modifier

                    assert priority_modifier
                    priority_modifier -= 1

                # ----------------------------------------------------------------------

                with ExitStack(ReducePriorityModifier):
                    yield

            else:
                yield

        # ----------------------------------------------------------------------

        self.Walk(repository_root_or_id, OnWalkItem)

        priority_items: List[Tuple[int, EncounteredRepoData]] = [
            (priority, self.encountered_repos[id])
            for id, priority in priorities.items()
            if priority != 0
        ]

        priority_items.sort(
            key=lambda value: (value[0], value[1].name, value[1].root),
            reverse=True,
        )

        for item in priority_items:
            yield item[-1]

    # ----------------------------------------------------------------------
    def Walk(
        self,
        repository_root_or_id: Union[uuid.UUID, Path],
        on_item: Callable[
            [
                Union[
                    EncounteredRepoData,
                    PendingRepoData,
                    Optional[str],          # Configuration name
                ],
                bool,                       # It item being used
            ],
            ContextManager[None],
        ],
        target_configuration_or_configurations: Union[
            None,
            Optional[str],
            List[Optional[str]],
        ]=None,
        *,
        traverse_all: bool=False,           # Traverse all configurations, even those that aren't being directly used
    ) -> None:
        if isinstance(repository_root_or_id, uuid.UUID):
            repo_data = self.encountered_repos.get(repository_root_or_id, None)
            if repo_data is None:
                raise Exception("'{}' was not found.".format(str(repository_root_or_id)))

        elif isinstance(repository_root_or_id, Path):
            repo_data = next(
                (
                    data for data in self.encountered_repos.values()
                    if data.root == repository_root_or_id
                ),
                None,
            )

            if repo_data is None:
                raise Exception("A repository was not found at '{}'.".format(str(repository_root_or_id)))

        # ----------------------------------------------------------------------
        def Impl(
            data: EncounteredRepoData,
            configurations: Optional[List[Optional[str]]],
            is_being_used: bool,
        ) -> None:
            with on_item(data, is_being_used):
                if configurations is None:
                    should_walk_configuration_func = lambda _: True
                else:
                    should_walk_configuration_func = (
                        lambda config_name:
                            any(
                                configuration == config_name
                                for configuration in configurations  # type: ignore
                            )
                    )

                for config_name, config_data in data.configurations.items():
                    this_config_being_used = is_being_used

                    if not should_walk_configuration_func(config_name):
                        this_config_being_used = False

                        if not traverse_all:
                            with on_item(config_name, this_config_being_used):
                                continue

                    with on_item(config_name, this_config_being_used):
                        for dependency in config_data.dependencies:
                            potential_encountered = self.encountered_repos.get(dependency.repository_id, None)
                            if potential_encountered is None:
                                with on_item(self.pending_repos[dependency.repository_id], is_being_used):
                                    pass
                            else:
                                Impl(
                                    potential_encountered,
                                    [dependency.configuration],
                                    this_config_being_used,
                                )

        # ----------------------------------------------------------------------

        if target_configuration_or_configurations is None:
            configurations = None
        elif isinstance(target_configuration_or_configurations, list):
            configurations = target_configuration_or_configurations
        else:
            configurations = [target_configuration_or_configurations, ]

        Impl(
            repo_data,
            cast(Optional[List[Optional[str]]], configurations),
            True,
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _OnStatusUpdate(
        directories_searched: int,
        directories_pending: int,
        repositories_found: int,
        repositories_pending: int,
        current_path: Optional[Path],
    ) -> bool:
        """Return True to continue, False to terminate"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _OnModuleError(
        ex: Exception,
        repo_data: DataTypes.RepoData,
        repo_path: Path,
    ) -> bool:
        """Return True to continue, False to terminate"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _OnDependencyNameMismatch(
        encountered_data: EncounteredRepoData,
        dependency_name: str,
        requesting_data: DataTypes.RepoData,
        requesting_path: Path,
        requesting_configuration: Optional[str],
    ) -> None:
        """Friendly names don't match"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _OnPendingNameMismatch(
        pending_data: PendingRepoData,
        pending_path: Path,
        dependency_name: str,
        requesting_data: DataTypes.RepoData,
        requesting_path: Path,
        requesting_configuration: Optional[str],
    ) -> None:
        """Friendly names don't match"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    @contextmanager
    def _SearchContext(
        encountered_repos: Dict[uuid.UUID, EncounteredRepoData],
        pending_repos: Dict[uuid.UUID, PendingRepoData],
    ) -> Iterator[None]:
        raise Exception("Abstract method")  # pragma: no cover


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
@contextmanager
def GetCustomizationMod(
    repository_root: Path,
) -> Iterator[types.ModuleType]:
    setup_filename = repository_root / Constants.SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME

    with GetCustomizationModImpl(setup_filename) as custom_mod:
        if custom_mod is None:
            raise Exception("The file '{}' does not exist.".format(setup_filename))

    yield custom_mod
