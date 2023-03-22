# ----------------------------------------------------------------------
# |
# |  ActivationData.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 13:09:03
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ActivationData objects"""

import os
import json
import textwrap
import traceback
import uuid

from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Dict, List, Optional

from Common_Foundation import JsonEx  # type: ignore
from Common_Foundation import PathEx  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore

from .EnvironmentBootstrap import EnvironmentBootstrap

from . import Utilities

from ..Configuration import VersionInfo, VersionSpecs
from .. import Constants
from .. import DataTypes


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Fingerprints(object):
    # ----------------------------------------------------------------------
    values: Dict[Path, str]

    # ----------------------------------------------------------------------
    def ToJson(
        self,
        root: Path,
    ) -> Dict[str, Any]:
        return {
            PathEx.CreateRelativePath(root, path).as_posix(): fingerprint
            for path, fingerprint in self.values.items()
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        repo_root: Path,
        data: Dict[str, Any],
    ) -> Dict[Path, Any]:
        # ----------------------------------------------------------------------
        def RestoreRelativePath(
            value: str,
        ) -> Path:
            fullpath = (repo_root / PurePath(value)).resolve()

            if not fullpath.is_dir():
                raise Exception("'{}' is not a valid directory.".format(fullpath))

            return fullpath

        # ----------------------------------------------------------------------

        return {
            RestoreRelativePath(path): fingerprint
            for path, fingerprint in data.items()
        }

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        repo_root: Path,
        data: Dict[str, Any],
    ) -> "Fingerprints":
        return cls(cls.FromJson(repo_root, data))


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ActivationData(object):
    # ----------------------------------------------------------------------
    id: uuid.UUID
    root: Path
    configuration: Optional[str]

    fingerprints: Fingerprints

    version_specs: VersionSpecs
    prioritized_repositories: List[DataTypes.ConfiguredRepoDataWithPath]

    is_mixin_repo: bool                     = field(kw_only=True)

    # ----------------------------------------------------------------------
    def GetActivationDir(self) -> Path:
        return self.__class__._GetActivationDir(  # pylint: disable=protected-access
            self.root,
            self.configuration or Constants.DEFAULT_CONFIGURATION_NAME,
        )

    # ----------------------------------------------------------------------
    def ToJson(self) -> Dict[str, Any]:
        return {
            "id": str(self.id),
            "configuration": self.configuration,
            "fingerprints": self.fingerprints.ToJson(self.root),
            "version_specs": self.version_specs.ToJson(),
            "prioritized_repositories": [repo.ToJson() for repo in self.prioritized_repositories],
            "is_mixin_repo": self.is_mixin_repo,
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        repo_root: Path,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        data["id"] = uuid.UUID(data["id"])
        data["configuration"] = JsonEx.JsonToOptional(data["configuration"])
        data["fingerprints"] = Fingerprints.CreateFromJson(repo_root, data["fingerprints"])

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        repo_root: Path,
        data: Dict[str, Any],
    ) -> "ActivationData":
        data = cls.FromJson(repo_root, data)

        return cls(
            **{
                **data,
                **{
                    "root": repo_root,
                    "version_specs": VersionSpecs.CreateFromJson(data["version_specs"]),
                    "prioritized_repositories": [
                        DataTypes.ConfiguredRepoDataWithPath.CreateFromJson(repo)
                        for repo in data["prioritized_repositories"]
                    ],
                },
            },
        )

    # ----------------------------------------------------------------------
    def Save(self) -> None:
        with self._GetActivationFilename(self.root, self.configuration).open("w") as f:
            JsonEx.Dump(self.ToJson(), f)

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        dm: DoneManager,
        repository_root: Path,
        configuration: Optional[str],
        *,
        force: bool=False,
    ) -> "ActivationData":
        result = cls._LoadImpl(
            dm,
            repository_root,
            configuration,
            force=force,
        )

        with dm.Nested(
            "Checking for setup changes in '{}' and its dependencies...".format(str(result.root)),
            display_exceptions=False,
        ):
            # Check the fingerprints
            calculated_fingerprints = Utilities.CalculateFingerprint(
                [repo.root for repo in result.prioritized_repositories if not repo.is_mixin_repo],
            )

            original_fingerprints = result.fingerprints.values

            if calculated_fingerprints != original_fingerprints:
                # Something has changed. Attempt to provide more context.
                lines: List[str] = []
                is_critical_error = True

                if original_fingerprints is not None:
                    # Anything added or removed will be reflected in a modification to a setup file,
                    # so we can safely ignore those. In fact, we will often see mismatches between
                    # the fingerprints calculated at setup time (which will only include the
                    # repository and its direct dependencies) and the fingerprints calculated here,
                    # which will include those dependencies and everything that they depend upon.

                    # Assume that we aren't looking at a critical error until we find something that
                    # is critical.
                    is_critical_error = False

                    line_template = "{0:<80}  :  {1}"

                    for k, v in calculated_fingerprints.items():
                        if k not in original_fingerprints:
                            lines.append(line_template.format(str(k), "Added"))
                        elif v != original_fingerprints[k]:
                            lines.append(line_template.format(str(k), "Modified"))
                            is_critical_error = True
                        else:
                            lines.append(line_template.format(str(k), "<No Change>"))

                    for k in original_fingerprints.keys():
                        if k not in calculated_fingerprints:
                            lines.append(line_template.format(str(k), "Removed"))

                if is_critical_error:
                    raise Exception(
                        textwrap.dedent(
                            """\
                            ****************************************************************************************************
                            {repo_root}
                            ****************************************************************************************************

                            This repository or one of its dependencies have changed.

                            Please run '{setup}' for this repository again.

                            {status}

                            ****************************************************************************************************
                            ****************************************************************************************************
                            """,
                        ).format(
                            repo_root=str(result.root),
                            setup="{}{}".format(Constants.SETUP_ENVIRONMENT_NAME, CurrentShell.script_extensions[0]),
                            status="\n".join("    - {}".format(line) for line in lines),
                        ),
                    )

        return result

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _GetActivationFilename(
        cls,
        repository_root: Path,
        configuration: Optional[str],
    ) -> Path:
        return cls._GetActivationDir(repository_root, configuration) / Constants.GENERATED_ACTIVATION_FILENAME

    # ----------------------------------------------------------------------
    @classmethod
    def _GetActivationDir(
        cls,
        repository_root: Path,
        configuration: Optional[str],
    ) -> Path:
        return EnvironmentBootstrap.GetEnvironmentPath(repository_root) / (configuration or Constants.DEFAULT_CONFIGURATION_NAME)

    # ----------------------------------------------------------------------
    @classmethod
    def _LoadImpl(
        cls,
        dm: DoneManager,
        repository_root: Path,
        configuration: Optional[str],
        *,
        force: bool=False,
    ) -> "ActivationData":
        # If we are operating within an activated environment, use the information in the
        # environment to point to the activation data. Doing this supports the scenario where
        # a mixin repository is activated within an existing environment.
        if not force:
            potential_repository_root = os.getenv(Constants.DE_REPO_ROOT_NAME)
            potential_configuration = os.getenv(Constants.DE_REPO_CONFIGURATION_NAME)

            if potential_repository_root is not None:
                repository_root = Path(potential_repository_root)
                configuration = potential_configuration

        # Attempt to use cached info unless:
        # - force was specified
        # - the cached file doesn't exist
        # - the activation script invoking this functionality has been updated since the cached file was created (this can happen when Setup is run)

        environment_name = os.getenv(Constants.DE_ENVIRONMENT_NAME)
        if environment_name is None:
            environment_name = Constants.DEFAULT_ENVIRONMENT_NAME

        activation_script = repository_root / "{}{}{}".format(
            Constants.ACTIVATE_ENVIRONMENT_NAME,
            ".{}".format(environment_name) if environment_name != Constants.DEFAULT_ENVIRONMENT_NAME else "",
            CurrentShell.script_extensions[0],
        )

        if not activation_script.is_file():
            raise Exception("'{}' is not a valid file name.".format(activation_script))

        data_filename = cls._GetActivationFilename(repository_root, configuration)

        if (
            not force
            and data_filename.is_file()
            and activation_script.stat().st_mtime <= data_filename.stat().st_mtime
        ):
            try:
                with data_filename.open() as f:
                    data = json.load(f)

                return cls.CreateFromJson(repository_root, data)

            except Exception as ex:
                if dm.is_debug:
                    warning = traceback.format_exc()
                else:
                    warning = str(ex)

                dm.WriteWarning(
                    textwrap.dedent(
                        """\
                        An exception was encountered while attempting to load cached activation data; processing will continue without that information.

                        {}
                        """,
                    ).format(warning),
                )

        # If here, we are recreating the information
        assert repository_root.is_dir(), repository_root

        # ----------------------------------------------------------------------
        @dataclass(frozen=True)
        class RepoPOD(object):
            # ----------------------------------------------------------------------
            name: str
            id: uuid.UUID
            configuration: Optional[str]
            root: Path

        # ----------------------------------------------------------------------
        @dataclass
        class WorkingRepositoryData(object):
            pod: RepoPOD
            bootstrap: EnvironmentBootstrap
            referencing_pod: Optional[RepoPOD]
            priority: int

        # ----------------------------------------------------------------------

        all_working_data: Dict[uuid.UUID, WorkingRepositoryData] = {}
        tool_version_info: List[VersionInfo] = []
        library_version_info: Dict[str, List[VersionInfo]] = {}
        version_info_lookup: Dict[VersionInfo, RepoPOD] = {}

        suppress_conflicted_repositories: Optional[List[uuid.UUID]] = None
        suppress_conflicted_tools: Optional[List[str]] = None
        suppress_conflicted_libraries: Optional[Dict[str, List[str]]] = None

        # ----------------------------------------------------------------------
        def Walk(
            referencing_pod: Optional[RepoPOD],
            repo_pod: RepoPOD,
            priority_modifier: int,
        ) -> None:
            working_data = all_working_data.get(repo_pod.id, None)
            if working_data is None:
                working_data = WorkingRepositoryData(
                    repo_pod,
                    EnvironmentBootstrap.Load(repo_pod.root),
                    referencing_pod,
                    0,
                )

                all_working_data[repo_pod.id] = working_data

                # Set the suppression information if we are looking at the root repository
                if repo_pod.root == repository_root:
                    nonlocal suppress_conflicted_repositories
                    nonlocal suppress_conflicted_tools
                    nonlocal suppress_conflicted_libraries

                    assert suppress_conflicted_repositories is None, suppress_conflicted_repositories
                    assert suppress_conflicted_tools is None, suppress_conflicted_tools
                    assert suppress_conflicted_libraries is None, suppress_conflicted_libraries

                    configuration_data = working_data.bootstrap.configurations.get(configuration, None)

                    if configuration_data is None:
                        # This will result in an error down the line, but let this part of the process
                        # continue for now
                        suppress_conflicted_repositories = []
                        suppress_conflicted_tools = []
                        suppress_conflicted_libraries = {}
                    else:
                        suppress_conflicted_repositories = configuration_data.suppress_conflicted_repositories or []
                        suppress_conflicted_tools = configuration_data.suppress_conflicted_tools or []
                        suppress_conflicted_libraries = configuration_data.suppress_conflicted_libraries or {}

            working_data.priority += priority_modifier

            assert suppress_conflicted_repositories is not None
            assert suppress_conflicted_tools is not None
            assert suppress_conflicted_libraries is not None

            # Ensure that the configuration name is valid
            if working_data.bootstrap.is_configurable and not repo_pod.configuration:
                raise Exception(
                    "The repository at '{}' is configurable, but no configuration was provided.".format(
                        repo_pod.root,
                    ),
                )

            if not working_data.bootstrap.is_configurable and repo_pod.configuration:
                raise Exception(
                    "The repository at '{}' is not configurable, but a configuration was provided ('{}').".format(
                        repo_pod.root,
                        repo_pod.configuration,
                    ),
                )

            if repo_pod.configuration not in working_data.bootstrap.configurations:
                raise Exception(
                    textwrap.dedent(
                        """\
                        The configuration '{config}' is not a valid configuration for the repository at '{root}'.

                        Valid configuration values are:
                        {configs}
                        """,
                    ).format(
                        config=repo_pod.configuration,
                        root=repo_pod.root,
                        configs="\n".join(
                            "    - {}".format(config or "<None>")
                            for config in working_data.bootstrap.configurations.keys()
                        ),
                    ),
                )

            # Check for consistent repo locations
            if repo_pod.root != working_data.pod.root:
                assert referencing_pod is not None

                raise Exception(
                    textwrap.dedent(
                        """\
                        There is a mismatch in repository locations.

                        Repository:         {name} <{id}>

                        New Location:       {new_value}
                        Referenced By:      {new_name} <{new_id}> [{new_root}]

                        Original Location:  {original_value}
                        Referenced By:      {original_name} <{original_id}> [{original_root}]
                        """,
                    ).format(
                        name=repo_pod.name,
                        id=repo_pod.id,
                        new_value=repo_pod.root,
                        new_name=referencing_pod.name,
                        new_id=referencing_pod.id,
                        new_root=referencing_pod.root,
                        original_value=working_data.pod.root,
                        original_name=working_data.pod.name,
                        original_id=working_data.pod.id,
                        original_root=working_data.pod.root,
                    ),
                )

            # Check for consistent configurations
            if (
                repo_pod.configuration != working_data.pod.configuration
                and repo_pod.id not in suppress_conflicted_repositories
            ):
                assert referencing_pod is not None

                raise Exception(
                    textwrap.dedent(
                        """\
                        There is a mismatch in repository configurations.

                        Repository:              {name} <{id}>

                        New Configuration:       {new_value}
                        Referenced By:           {new_name} <{new_id}> [{new_root}]

                        Original Configuration:  {original_value}
                        Referenced By:           {original_name} <{original_id}> [{original_root}]
                        """,
                    ).format(
                        name=repo_pod.name,
                        id=repo_pod.id,
                        new_value=repo_pod.configuration,
                        new_name=referencing_pod.name,
                        new_id=referencing_pod.id,
                        new_root=referencing_pod.root,
                        original_value=working_data.pod.configuration,
                        original_name=working_data.pod.name,
                        original_id=working_data.pod.id,
                        original_root=working_data.pod.root,
                    ),
                )

            # Process the version info

            # ----------------------------------------------------------------------
            def OnVersionMismatch(
                description: str,
                version_info: VersionInfo,
                existing_version_info: VersionInfo,
            ) -> None:
                original_repo = version_info_lookup[existing_version_info]

                raise Exception(
                    textwrap.dedent(
                        """\
                        There is a mismatch in version information.

                        Item:               {name} - {description}

                        New Version:        {new_value}
                        Specified By:       {new_name} ({new_config}) <{new_id}> [{new_root}]

                        Original Version:   {original_value}
                        Specified By:       {original_name} ({original_config}) <{original_id}> [{original_root}]
                        """,
                    ).format(
                        name=version_info.name,
                        description=description,
                        new_value=version_info.version,
                        new_name=repo_pod.name,
                        new_config=repo_pod.configuration,
                        new_id=repo_pod.id,
                        new_root=repo_pod.root,
                        original_value=existing_version_info.version,
                        original_name=original_repo.name,
                        original_config=original_repo.configuration,
                        original_id=original_repo.id,
                        original_root=original_repo.root,
                    ),
                )

            # ----------------------------------------------------------------------

            # Tools
            for version_info in working_data.bootstrap.configurations[repo_pod.configuration].version_specs.tools:
                existing_version_info = next(
                    (tvi for tvi in tool_version_info if tvi.name == version_info.name),
                    None,
                )

                if existing_version_info is None:
                    tool_version_info.append(version_info)
                    version_info_lookup[version_info] = repo_pod

                elif (
                    version_info.version != existing_version_info.version
                    and version_info.name not in suppress_conflicted_tools
                ):
                    OnVersionMismatch("Tools", version_info, existing_version_info)

            # Libraries
            for library_name, version_infos in working_data.bootstrap.configurations[repo_pod.configuration].version_specs.libraries.items():
                suppress_conflicted_library_names = suppress_conflicted_libraries.get(library_name, [])

                for version_info in version_infos:
                    existing_version_info = next(
                        (
                            lvi
                            for lvi in library_version_info.get(library_name, [])
                            if lvi.name == version_info.name
                        ),
                        None,
                    )

                    if existing_version_info is None:
                        library_version_info.setdefault(library_name, []).append(version_info)
                        version_info_lookup[version_info] = repo_pod

                    elif (
                        version_info.version != existing_version_info.version
                        and version_info.name not in suppress_conflicted_library_names
                    ):
                        OnVersionMismatch(
                            "{} Libraries".format(library_name),
                            version_info,
                            existing_version_info,
                        )

            # Process the repository's dependencies
            for dependency in working_data.bootstrap.configurations[repo_pod.configuration].dependencies:
                dependency_root = working_data.bootstrap.dependencies[dependency.repository_id]

                Walk(
                    working_data.pod,
                    RepoPOD(
                        dependency.friendly_name,
                        dependency.repository_id,
                        dependency.configuration,
                        dependency_root,
                    ),
                    priority_modifier + 1,
                )

        # ----------------------------------------------------------------------

        root_data = Utilities.GetRepoData(repository_root)
        assert root_data is not None

        root_repo = RepoPOD(
            root_data.name,
            root_data.id,
            configuration,
            repository_root,
        )

        Walk(None, root_repo, 1)

        # Order the results from the most- to least-frequently requested
        priority_values = [
            (id, repo.priority) for id, repo in all_working_data.items()
        ]

        priority_values.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        # Calculate the dependencies
        dependencies: List[DataTypes.ConfiguredRepoDataWithPath] = []

        for dependency_id, _ in priority_values:
            dependency_working_data = all_working_data[dependency_id]

            dependencies.append(
                DataTypes.ConfiguredRepoDataWithPath(
                    dependency_working_data.pod.name,
                    dependency_working_data.pod.id,
                    dependency_working_data.pod.configuration,
                    dependency_working_data.pod.root,
                    is_mixin_repo=dependency_working_data.bootstrap.is_mixin_repo,
                ),
            )

        # Create the object
        this_working_data = all_working_data[root_repo.id]

        return cls(
            root_repo.id,
            root_repo.root,
            configuration,
            Fingerprints(this_working_data.bootstrap.fingerprints[configuration]),
            VersionSpecs(tool_version_info, library_version_info),
            dependencies,
            is_mixin_repo=this_working_data.bootstrap.is_mixin_repo,
        )
