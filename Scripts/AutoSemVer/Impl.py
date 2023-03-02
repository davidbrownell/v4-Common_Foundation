# ----------------------------------------------------------------------
# |
# |  Impl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-01 09:15:06
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality used to generate a semantic version based on recent changes in an active repository."""

import datetime
import itertools
import json
import os
import platform
import re

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast, Optional, Type as PythonType

import rtyaml

from jsonschema import Draft202012Validator, validators
from semantic_version import Version as SemVer

from Common_Foundation import PathEx
from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import Types
from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
DEFAULT_CONFIGURATION_FILENAMES: list[str]  = [
    "AutoSemVer.json",
    "AutoSemVer.yaml",
    "AutoSemVer.yml",
]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Configuration(object):
    """Data used to configure how the semantic version is generated"""

    # ----------------------------------------------------------------------
    filename: Optional[Path]

    version_prefix: Optional[str]

    major_scm_token: str
    minor_scm_token: str

    prerelease_environment_variable_name: str

    initial_version: SemVer
    main_branch_names: list[str]

    include_branch_name_when_necessary: bool            = field(kw_only=True)
    include_timestamp_when_necessary: bool              = field(kw_only=True)
    include_computer_name_when_necessary: bool          = field(kw_only=True)


# ----------------------------------------------------------------------
class GenerateStyle(str, Enum):
    Standard                                = "Standard"
    AllPrerelease                           = "AllPrerelease"
    AllMetadata                             = "AllMetadata"


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class GetSemanticVersionResult(object):
    """Result of GetSemanticVersion"""

    configuration_filename: Optional[Path]
    semantic_version: SemVer
    version: str


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def GetSemanticVersion(
    dm: DoneManager,
    *,
    path: Path=Path.cwd(),
    prerelease_name: Optional[str]=None,
    include_branch_name_when_necessary: bool=True,
    include_timestamp_when_necessary: bool=True,
    include_computer_name_when_necessary: bool=True,
    no_metadata: bool=False,
    configuration_filenames: Optional[list[str]]=None,
    style: GenerateStyle=GenerateStyle.Standard,
) -> GetSemanticVersionResult:
    repository: Optional[Repository] = None

    with dm.Nested(
        "Calculating the Source Control Manager repository...",
        lambda: "'{}' found".format("None" if repository is None else repository.scm.name),
    ):
        for potential_scm in ALL_SCMS:
            if potential_scm.IsActive(path):
                repository = potential_scm.Open(path)
                break

        if repository is None:
            raise Exception("A source control manager could not be found for '{}'.".format(path))

    configuration: Optional[Configuration] = None

    # ----------------------------------------------------------------------
    def DisplayConfiguration() -> str:
        if configuration is None:
            return "configuration errors were encountered"

        if configuration.filename is None:
            return "default configuration info will be used"

        return "configuration info found at '{}'".format(configuration.filename)

    # ----------------------------------------------------------------------

    with dm.Nested(
        "Loading AutoSemVer configuration...",
        DisplayConfiguration,
    ) as configuration_dm:
        configuration = GetConfiguration(
            path,
            repository.repo_root,
            configuration_filenames,
        )

        if configuration.filename is None:
            configuration_dm.WriteVerbose("The default configuration will be used.")
        else:
            configuration_dm.WriteVerbose("Configuration information loaded from '{}'.".format(configuration.filename))

    commits_processed = 0
    commits_applied = 0

    baseline_version: Optional[list[int]] = None

    major_delta = 0
    minor_delta = 0
    patch_delta = 0

    update_minor = True
    update_patch = True

    has_working_changes = False

    with dm.Nested(
        "Enumerating commits...",
        [
            lambda: "{} processed".format(inflect.no("commit", commits_processed)),
            lambda: "{} applied [{:.02f}%]".format(
                inflect.no("commit", commits_applied),
                0 if commits_processed == 0 else ((commits_applied / commits_processed) * 100),
            ),
        ],
    ) as enumerate_dm:
        root_path = configuration.filename.parent if configuration.filename else repository.repo_root
        configuration_filenames = configuration_filenames or DEFAULT_CONFIGURATION_FILENAMES

        # ----------------------------------------------------------------------
        def GetConfigurationPathForFile(
            filename: Path,
        ) -> Path:
            for parent in filename.parents:
                for configuration_filename in configuration_filenames:
                    potential_filename = parent / configuration_filename

                    if potential_filename.is_file():
                        return parent

                if parent == repository.repo_root:
                    break

            return root_path

        # ----------------------------------------------------------------------
        def ShouldProcess(
            commit: Repository.EnumChangesResult,
        ) -> bool:
            for filename in itertools.chain(
                commit.files_added,
                commit.files_modified,
                commit.files_removed,
                commit.working_files
            ):
                if (
                    PathEx.IsDescendant(filename, root_path)
                    and GetConfigurationPathForFile(filename) == root_path
                ):
                    return True

            return False

        # ----------------------------------------------------------------------

        version_regex = r"(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)"

        if configuration.version_prefix:
            version_regex = r"^{}{}{}$".format(
                re.escape(configuration.version_prefix),
                "" if configuration.version_prefix.endswith("v") else "v?",
                version_regex,
            )
        else:
            version_regex = r"^v?{}$".format(version_regex)

        version_regex = re.compile(version_regex)

        # ----------------------------------------------------------------------
        def HasExplicitVersion(
            commit: Repository.EnumChangesResult,
            *,
            process_tags: bool=False,
        ) -> bool:
            nonlocal baseline_version

            queries = commit.tags if process_tags else [commit.description, ]

            for query in queries:
                match = version_regex.search(query)
                if match is None:
                    continue

                baseline_version = [
                    int(match.group("major")),
                    int(match.group("minor")),
                    int(match.group("patch")),
                ]

                enumerate_dm.WriteVerbose(
                    "The explicit version '{}' was found in '{}' ({}).".format(
                        match.group(0),
                        commit.commit,
                        commit.author_date,
                    ),
                )

                return True

            return False

        # ----------------------------------------------------------------------

        for commit in repository.EnumChanges(
            include_working_changes=True,
        ):
            commits_processed += 1

            if HasExplicitVersion(commit, process_tags=True):
                commits_applied += 1
                break

            if not ShouldProcess(commit):
                continue

            commits_applied += 1

            if commit.commit == Repository.EnumChangesResult.WORKING_CHANGES_COMMIT_ID:
                has_working_changes = True

            if HasExplicitVersion(commit):
                break

            elif configuration.major_scm_token in commit.description:
                enumerate_dm.WriteVerbose(
                    "Incrementing major version based on '{}' ({}).".format(
                        commit.commit,
                        commit.author_date,
                    ),
                )

                major_delta += 1

                update_minor = False
                update_patch = False

            elif configuration.minor_scm_token in commit.description:
                if update_minor:
                    enumerate_dm.WriteVerbose(
                        "Incrementing minor version based on '{}' ({}).".format(
                            commit.commit,
                            commit.author_date,
                        ),
                    )

                    minor_delta += 1

                    update_patch = False

            else:
                if update_patch:
                    enumerate_dm.WriteVerbose(
                        "Incrementing patch version based on '{}' ({}).".format(
                            commit.commit,
                            commit.author_date,
                        ),
                    )

                    patch_delta += 1

    semantic_version: Optional[SemVer] = None

    with dm.Nested(
        "Calculating semantic version...",
        lambda: str(semantic_version) if semantic_version is not None else "errors were encountered",
    ):
        if baseline_version is None:
            baseline_version = [
                Types.EnsureValid(configuration.initial_version.major),
                Types.EnsureValid(configuration.initial_version.minor),
                Types.EnsureValid(configuration.initial_version.patch),
            ]

        # If we have seen changes to a significant version number, don't less-significant
        # baseline values impact the resulting version..
        if major_delta:
            baseline_version[1] = 0
            baseline_version[2] = 0
        elif minor_delta:
            baseline_version[2] = 0

        # A version in the form "0.0.x" is not valid, so make sure that there is at least
        # a minor version when the major version is 0.
        if baseline_version[0] == 0 and baseline_version[1] == 0:
            baseline_version[1] = 1

            # If we have altered the minor version, the first version will be "0.1.0", so update
            # patch value to account for this potential modification.
            if baseline_version[2] == 0 and patch_delta > 0:
                patch_delta -= 1

        semantic_version = SemVer(
            major=baseline_version[0] + major_delta,
            minor=baseline_version[1] + minor_delta,
            patch=baseline_version[2] + patch_delta,
        )

    version_string: Optional[str] = None

    with dm.Nested(
        "Calculating version string...",
        lambda: version_string or "errors were encountered",
    ):
        version_parts: list[str] = [
            configuration.version_prefix or "",
            str(semantic_version),
        ]

        # Prerelease components
        prerelease_components: list[str] = []

        if prerelease_name is not None:
            prerelease_components.append(prerelease_name)
        else:
            value = os.getenv(configuration.prerelease_environment_variable_name)  # pylint: disable=invalid-envvar-value
            if value:
                prerelease_components.append(value)

            if configuration.include_branch_name_when_necessary and include_branch_name_when_necessary:
                current_branch = repository.GetCurrentBranch()

                if current_branch not in configuration.main_branch_names:
                    prerelease_components.append(current_branch)

        # Build metadata
        metadata_components: list[str] = []

        if not no_metadata:
            if configuration.include_timestamp_when_necessary and include_timestamp_when_necessary:
                now = datetime.datetime.now()

                metadata_components.append(
                    "{:04d}{:02d}{:02d}{:02d}{:02d}{:02d}".format(
                        now.year,
                        now.month,
                        now.day,
                        now.hour,
                        now.minute,
                        now.second,
                    ),
                )

            if configuration.include_computer_name_when_necessary and include_computer_name_when_necessary:
                metadata_components.append(platform.node())

        if has_working_changes:
            metadata_components.append("working_changes")

        if style == GenerateStyle.Standard:
            # No modifications necessary
            pass
        elif style == GenerateStyle.AllPrerelease:
            prerelease_components += metadata_components
            metadata_components = []
        elif style == GenerateStyle.AllMetadata:
            metadata_components = prerelease_components + metadata_components
            prerelease_components = []
        else:
            assert False, style  # pragma: no cover

        if prerelease_components:
            version_parts.append("-{}".format(".".join(prerelease_components)))

        if metadata_components:
            version_parts.append("+{}".format(".".join(metadata_components)))

        version_string = "".join(version_parts)

    return GetSemanticVersionResult(configuration.filename, semantic_version, version_string)


# ----------------------------------------------------------------------
def GetConfiguration(
    path: Path,
    repository_root: Path,
    configuration_filenames: Optional[list[str]]=None,
) -> Configuration:
    configuration_filenames = configuration_filenames or DEFAULT_CONFIGURATION_FILENAMES

    # Load the configuration data
    configuration_filename: Optional[Path] = None
    configuration_content: dict[str, Any] = {}

    for parent in itertools.chain([path, ], path.parents):
        if parent == repository_root:
            break

        for potential_configuration_filename in configuration_filenames:
            potential_filename = parent / potential_configuration_filename

            if not potential_filename.is_file():
                continue

            configuration_filename = potential_filename

            with potential_filename.open() as f:
                if potential_filename.suffix in [".yaml", ".yml"]:
                    configuration_content = cast(dict[str, Any], rtyaml.load(f))

                elif potential_filename.suffix == ".json":
                    configuration_content = json.load(f)

                else:
                    raise Exception("'{}' is not a recognized configuration file type.".format(potential_filename))

                break

    # Load the schema
    schema_filename = PathEx.EnsureFile(Path(__file__).parent / "Configuration" / "GeneratedCode" / "AutoSemVer.json")

    with schema_filename.open() as f:
        schema_content = json.load(f)

    # Validate the configuration data
    _DefaultValidatingValidator(schema_content).validate(configuration_content)

    # Map the configuration data to a Configuration instance
    return Configuration(
        configuration_filename,
        configuration_content.get("version_prefix", None),
        configuration_content["major_scm_token"],
        configuration_content["minor_scm_token"],
        configuration_content["pre_release_environment_variable_name"],
        SemVer.coerce(configuration_content["initial_version"]),
        configuration_content["main_branch_names"],
        include_branch_name_when_necessary=configuration_content["include_branch_name_when_necessary"],
        include_timestamp_when_necessary=configuration_content["include_timestamp_when_necessary"],
        include_computer_name_when_necessary=configuration_content["include_computer_name_when_necessary"],
    )


# ----------------------------------------------------------------------
# |
# |  Private Types
# |
# ----------------------------------------------------------------------
def _DefaultValidatingValidatorFactory(
    validator_class: PythonType,
) -> PythonType:
    # This code is based on https://python-jsonschema.readthedocs.io/en/latest/faq/
    validate_properties = validator_class.VALIDATORS["properties"]

    # ----------------------------------------------------------------------
    def SetDefaults(validator, properties, instance, schema):
        for prop, sub_schema in properties.items():
            default_schema = sub_schema.get("default", None)
            if default_schema is not None:
                instance.setdefault(prop, default_schema)

            for error in validate_properties(validator, properties, instance, schema):
                yield error

    # ----------------------------------------------------------------------

    return validators.extend(validator_class, {"properties": SetDefaults})


_DefaultValidatingValidator                 = _DefaultValidatingValidatorFactory(Draft202012Validator)

del _DefaultValidatingValidatorFactory
