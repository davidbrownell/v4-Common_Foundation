# ----------------------------------------------------------------------
# |
# |  ActivateActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 19:47:04
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ActivateActivity object"""

import os

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from semantic_version import Version as SemVer

from Common_Foundation.DynamicFunctions import CreateInvocationWrapper, GetCustomizationMod  # type: ignore
from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Shell.All import ALL_SHELLS, CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore

from .Configuration import VersionInfo, VersionSpecs
from . import Constants
from . import DataTypes


# ----------------------------------------------------------------------
class ActivateActivity(ABC):
    """\
    Base class for activities that can be performed at any time (during activation or later).
    Derived classes should account for repeated invocations within the same environment.
    """

    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        raise Exception("Abstract property")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Methods
    # |
    # ----------------------------------------------------------------------
    def CreateCommands(
        self,
        dm: DoneManager,
        configuration: Optional[str],
        repositories: List[DataTypes.ConfiguredRepoDataWithPath],
        version_specs: VersionSpecs,
        generated_dir: Path,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        with dm.Nested(
            "Activating '{}'...".format(self.name),
            suffix="\n" if dm.is_verbose else "",
            display_exceptions=False,
        ) as nested_dm:
            return self._CreateCommandsImpl(
                nested_dm,
                configuration,
                repositories,
                version_specs,
                generated_dir,
                force=force,
            )

    # ----------------------------------------------------------------------
    @classmethod
    def GetVersionedDirectory(
        cls,
        path: Path,
        version_infos: List[VersionInfo],
    ) -> Path:
        """Returns the fullpath to the latest versioned directory or the version specified in `version_info`"""
        return cls.GetVersionedDirectoryEx(path, version_infos)[0]

    # ----------------------------------------------------------------------
    @classmethod
    def GetVersionedDirectoryEx(
        cls,
        path: Path,
        version_infos: List[VersionInfo],
    ) -> Tuple[Path, SemVer]:
        """Returns the fullpath to the latest versioned directory or the version specified in `version_info`"""

        explicit_version = next((vi for vi in version_infos if vi.name == path.name), None)
        if explicit_version is not None:
            assert explicit_version.version is not None

            explicit_version_string = str(explicit_version.version)

            versions = {
                explicit_version_string: explicit_version.version,
            }

            for potential_version_prefix in Constants.POTENTIAL_VERSION_PREFIXES:
                versions["{}{}".format(potential_version_prefix, explicit_version_string)] = explicit_version.version

        else:
            versions = cls.SortVersions(
                [
                    item.name
                    for item in path.iterdir()
                    if item.is_dir()
                ],
            )

        # Cache any exceptions associated with fullpath customization and only percolate them if
        # we don't find any valid customizations.
        exceptions: List[Exception] = []

        for version_string, semver in versions.items():
            this_fullpath = path / version_string

            if not this_fullpath.is_dir():
                continue

            try:
                this_fullpath = cls.GetCustomizedFullpath(this_fullpath)
                assert this_fullpath.is_dir(), this_fullpath

                return this_fullpath, semver

            except Exception as ex:
                exceptions.append(ex)

        if not exceptions:
            raise Exception("A versioned directory could not be found for '{}'.".format(path))

        raise Exception("\n".join(str(exception) for exception in exceptions))

    # ----------------------------------------------------------------------
    @staticmethod
    def SortVersions(
        version_strings: List[str],
    ) -> Dict[str, SemVer]:
        if not version_strings:
            return {}

        lookup: Dict[SemVer, str] = {}
        versions: List[SemVer] = []

        for version_string in version_strings:
            if version_string.startswith("."):
                continue

            original_version_string = version_string

            for potential_prefix in Constants.POTENTIAL_VERSION_PREFIXES:
                if version_string.startswith(potential_prefix):
                    version_string = version_string[len(potential_prefix):]
                    break

            try:
                # Remove leading zeros from version string values
                parts: List[str] = []

                for part in version_string.split("."):
                    assert part, version_string

                    part = part.lstrip("0")
                    if part:
                        parts.append(part)
                    else:
                        parts.append("0")

                version = SemVer.coerce(".".join(parts))

                lookup[version] = original_version_string
                versions.append(version)

            except ValueError:
                continue

        if not versions:
            return {}

        versions.sort(
            reverse=True,
        )

        return {lookup[version]: version for version in versions}

    # ----------------------------------------------------------------------
    _is_os_names_path_potential_os_names: Optional[Set[str]]                = None

    @classmethod
    def IsOSNamesPath(
        cls,
        path: Path,
    ) -> bool:
        if cls._is_os_names_path_potential_os_names is None:
            potential_names = set(
                [
                    Constants.AGNOSTIC_OS_NAME,
                    Constants.SRC_OS_NAME,
                    Constants.CUSTOMIZATIONS_OS_NAME,
                ],
            )

            for shell in ALL_SHELLS:
                potential_names.add(shell.name)
                potential_names.add(shell.family_name)

            cls._is_os_names_path_potential_os_names = potential_names

        found_one = False

        for item in path.iterdir():
            if not item.is_dir():
                continue

            if item.name in cls._is_os_names_path_potential_os_names:
                found_one = True
            else:
                return False

        return found_one

    # ----------------------------------------------------------------------
    _is_architecture_potential_architecture_names: Optional[Set[str]]       = None

    @classmethod
    def IsArchitectureNamesPath(
        cls,
        path: Path,
    ) -> bool:
        if cls._is_architecture_potential_architecture_names is None:
            potential_names: Set[str] = set()

            for shell in ALL_SHELLS:
                for architecture in shell.supported_architectures:
                    potential_names.add(architecture)

            cls._is_architecture_potential_architecture_names = potential_names

        found_one = False

        for item in path.iterdir():
            if not item.is_dir():
                continue

            if item.name in cls._is_architecture_potential_architecture_names:
                found_one = True
            else:
                return False

        return found_one

    # ----------------------------------------------------------------------
    @classmethod
    def GetCustomizedFullpath(
        cls,
        path: Path,
    ) -> Path:
        while True:
            if cls.IsOSNamesPath(path):
                potential_path = path / CurrentShell.name
                if potential_path.is_dir():
                    path = potential_path
                    continue

                if CurrentShell.family_name != CurrentShell.name:
                    potential_path = path / CurrentShell.family_name
                    if potential_path.is_dir():
                        path = potential_path
                        continue

                potential_path = path / Constants.AGNOSTIC_OS_NAME
                if potential_path.is_dir():
                    path = potential_path
                    continue

                potential_names: List[str] = [CurrentShell.name]

                if CurrentShell.family_name != CurrentShell.name:
                    potential_names.append(CurrentShell.family_name)

                potential_names.append(Constants.AGNOSTIC_OS_NAME)

                raise Exception(
                    "OS names were found in '{}'; is one of {} missing?".format(
                        path,
                        ", ".join("'{}'".format(potential_name) for potential_name in potential_names),
                    ),
                )

            if cls.IsArchitectureNamesPath(path):
                potential_path = path / CurrentShell.current_architecture
                if potential_path.is_dir():
                    path = potential_path
                    continue

                raise Exception(
                    "Architecture names were found in '{}'; is '{}' missing?".format(
                        path,
                        CurrentShell.current_architecture,
                    ),
                )

            break

        environment_name = os.getenv(Constants.DE_ENVIRONMENT_NAME)
        assert environment_name is not None

        potential_path = path / environment_name
        if potential_path.is_dir():
            path = potential_path

        return path

    # ----------------------------------------------------------------------
    @staticmethod
    def CallCustomMethod(
        path: Path,
        method_name: str,
        kwargs: Any,
        *,
        result_is_list=True,
    ) -> Any:
        """\
        Calls the specified method if it exists with the args that it expects.
        Ensure that the return value is None or a list of items (if indicated).
        """

        with GetCustomizationMod(path) as mod:
            method = getattr(mod, method_name, None)
            if method is None:
                return None

            result = CreateInvocationWrapper(method)(kwargs)

            if result_is_list and not isinstance(result, list):
                result = [result, ]

            return result

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def _CreateCommandsImpl(
        self,
        dm: DoneManager,
        configuration: Optional[str],
        repositories: List[DataTypes.ConfiguredRepoDataWithPath],
        version_specs: VersionSpecs,
        generated_dir: Path,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        """Returns commands that are invoked during activation"""
        raise Exception("Abstract method")  # pragma: no cover
