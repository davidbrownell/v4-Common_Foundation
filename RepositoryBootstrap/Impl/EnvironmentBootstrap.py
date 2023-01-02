# ----------------------------------------------------------------------
# |
# |  EnvironmentBootstrap.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-09 17:04:15
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the EnvironmentBootstrap object"""

import json
import os
import textwrap
import uuid

from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Dict, Optional

from Common_Foundation import JsonEx  # type: ignore
from Common_Foundation import PathEx  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore

from ..Configuration import Configuration
from .. import Constants


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EnvironmentBootstrap(object):
    """\
    Object that persists environment bootstrap data. This data is created during setup
    and used as a part of environment activation.
    """

    # ----------------------------------------------------------------------
    foundation_repo: Path
    configurations: Dict[Optional[str], Configuration]

    fingerprints: Dict[Optional[str], Dict[Path, str]]
    dependencies: Dict[uuid.UUID, Path]

    is_mixin_repo: bool                     = field(kw_only=True)
    is_configurable: bool                   = field(kw_only=True)

    # ----------------------------------------------------------------------
    def ToJson(
        self,
        repo_root: Path,
    ) -> Dict[str, Any]:
        return {
            "foundation_repo": PathEx.CreateRelativePath(repo_root, self.foundation_repo).as_posix(),
            "configurations": {
                configuration_name: configuration.ToJson()
                for configuration_name, configuration in self.configurations.items()
            },
            "fingerprints": {
                config_name: {
                    PathEx.CreateRelativePath(repo_root, path).as_posix(): fingerprint
                    for path, fingerprint in fingerprints.items()
                }
                for config_name, fingerprints in self.fingerprints.items()
            },
            "dependencies": {
                str(key): PathEx.CreateRelativePath(repo_root, value).as_posix()
                for key, value in self.dependencies.items()
            },
            "is_mixin_repo": self.is_mixin_repo,
            "is_configurable": self.is_configurable,
        }

    # ----------------------------------------------------------------------
    @staticmethod
    def FromJson(
        repo_root: Path,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        # ----------------------------------------------------------------------
        def RestoreRelativePath(
            value: str,
        ) -> Path:
            fullpath = (repo_root / PurePath(value)).resolve()

            if not fullpath.is_dir():
                raise Exception(
                    textwrap.dedent(
                        """\
                        '{}' does not exist.

                        This is usually an indication that something fundamental has changed
                        or the repository has moved on the file system. To address either issue,
                        please run setup again for this repository:

                            {}{}

                        """,
                    ).format(
                        fullpath,
                        Constants.SETUP_ENVIRONMENT_NAME,
                        CurrentShell.script_extensions[0],
                    ),
                )

            return fullpath

        # ----------------------------------------------------------------------

        data["foundation_repo"] = RestoreRelativePath(data["foundation_repo"])

        data["configurations"] = {
            JsonEx.JsonToOptional(config_name): config_data
            for config_name, config_data in data["configurations"].items()
        }

        data["fingerprints"] = {
            JsonEx.JsonToOptional(config_name): {
                RestoreRelativePath(path): fingerprint
                for path, fingerprint in fingerprints.items()
            }
            for config_name, fingerprints in data["fingerprints"].items()
        }

        data["dependencies"] = {
            uuid.UUID(key): RestoreRelativePath(value)
            for key, value in data["dependencies"].items()
        }

        return data

    # ----------------------------------------------------------------------
    @classmethod
    def CreateFromJson(
        cls,
        repo_root: Path,
        data: Dict[str, Any],
    ) -> "EnvironmentBootstrap":
        data = cls.FromJson(repo_root, data)

        return cls(
            **{
                **data,
                **{
                    "configurations": {
                        config_name: Configuration.CreateFromJson(config_data)
                        for config_name, config_data in data["configurations"].items()
                    },
                },
            },
        )

    # ----------------------------------------------------------------------
    def Save(
        self,
        repo_root: Path,
    ) -> None:
        data = self.ToJson(repo_root)

        # Write the output files. We are writing multiple files:
        #     - A json file that is generally useful
        #     - A line-delimited file that can be easily consumed by shell scripts

        output_dir = self.GetEnvironmentPath(repo_root)

        output_dir.mkdir(parents=True, exist_ok=True)
        CurrentShell.UpdateOwnership(output_dir)

        # Write the json file
        output_filename = output_dir / Constants.GENERATED_BOOTSTRAP_JSON_FILENAME

        with output_filename.open("w") as f:
            JsonEx.Dump(data, f)

        CurrentShell.UpdateOwnership(output_filename)

        # Write the line-delimited file
        output_filename = output_dir / Constants.GENERATED_BOOTSTRAP_DATA_FILENAME

        with output_filename.open("w") as f:
            f.write(
                textwrap.dedent(
                    """\
                    foundation_repo={foundation_repo}
                    is_mixin_repo={is_mixin_repo}
                    is_configurable={is_configurable}
                    """,
                ).format(
                    foundation_repo=data["foundation_repo"],
                    is_mixin_repo="1" if self.is_mixin_repo else "0",
                    is_configurable="1" if self.is_configurable else "0",
                ),
            )

        CurrentShell.UpdateOwnership(output_filename)

    # ----------------------------------------------------------------------
    @classmethod
    def Load(
        cls,
        repo_root: Path,
    ) -> "EnvironmentBootstrap":
        input_filename = cls.GetEnvironmentPath(repo_root) / Constants.GENERATED_BOOTSTRAP_JSON_FILENAME
        if not input_filename.is_file():
            raise Exception("'{}' does not exist; please setup this repository.".format(input_filename))

        with input_filename.open() as f:
            data = json.load(f)

        return cls.CreateFromJson(repo_root, data)

    # ----------------------------------------------------------------------
    @staticmethod
    def GetEnvironmentPath(repository_root: Path) -> Path:
        repository_root /= Constants.GENERATED_DIRECTORY_NAME
        repository_root /= CurrentShell.family_name
        repository_root /= os.getenv(Constants.DE_ENVIRONMENT_NAME) or Constants.DEFAULT_ENVIRONMENT_NAME

        return repository_root
