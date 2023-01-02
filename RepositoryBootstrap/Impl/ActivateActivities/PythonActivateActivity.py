# ----------------------------------------------------------------------
# |
# |  PythonActivateActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-14 21:53:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the PythonActivateActivity object"""

import os
import textwrap
import uuid

from pathlib import Path
from typing import Dict, List, Optional

import inflect as inflect_mod

from Common_Foundation.Shell import Commands    # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore
from Common_Foundation.Types import overridemethod

from ...ActivateActivity import ActivateActivity
from ...Configuration import VersionSpecs
from ... import Constants
from ... import DataTypes


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()


# ----------------------------------------------------------------------
class PythonActivateActivity(ActivateActivity):
    """Activates python and python libraries"""

    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Python"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
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
        # Calculate the external requirements
        pip_version: Optional[str] = None
        setuptools_version: Optional[str] = None
        wheel_version: Optional[str] = None

        versions: Dict[str, str] = {}

        with dm.VerboseNested(
            "Calculating external Python requirements...",
            lambda: "{} found".format(inflect.no("requirement", len(versions))),
            display_exceptions=False,
        ):
            assert self.name in version_specs.libraries
            for version_info in version_specs.libraries[self.name]:
                if version_info.version is None:
                    continue

                requirements_version = "{}.{}.*".format(
                    version_info.version.major,
                    version_info.version.minor,
                )

                if version_info.name == "pip":
                    assert pip_version is None
                    pip_version = requirements_version
                elif version_info.name == "setuptools":
                    assert setuptools_version is None
                    setuptools_version = requirements_version
                elif version_info.name == "wheel":
                    assert wheel_version is None
                    wheel_version = requirements_version
                else:
                    versions[version_info.name] = requirements_version

        assert pip_version is not None
        assert setuptools_version is not None
        assert wheel_version is not None

        requirements_filename = CurrentShell.CreateTempFilename()

        with requirements_filename.open("w") as f:
            f.write("\n".join("{}=={}".format(k, v) for k, v in versions.items()))

        # Calculate the internal libraries
        libraries: List[Path] = []

        with dm.VerboseNested(
            "Calculating internal Python libraries...",
            lambda: "{} found".format(inflect.no("library", len(libraries))),
            display_exceptions=False,
        ):
            if configuration is not None and configuration.endswith("nolibs"):
                # ----------------------------------------------------------------------
                def IsSupportedRepository(
                    repo: DataTypes.ConfiguredRepoDataWithPath,
                ) -> bool:
                    return repo.id == Constants.COMMON_FOUNDATION_REPOSITORY_ID

                # ----------------------------------------------------------------------

                is_supported_repository_func = IsSupportedRepository
            else:
                is_supported_repository_func = lambda _: True

            for repository in repositories:
                python_libraries_path = repository.root / Constants.LIBRARIES_SUBDIR / self.name
                if not python_libraries_path.is_dir():
                    continue

                if not is_supported_repository_func(repository):
                    continue

                libraries += [child_path for child_path in python_libraries_path.iterdir() if child_path.is_dir()]

        libraries_filename = CurrentShell.CreateTempFilename()

        with libraries_filename.open("w") as f:
            f.write("\n".join(str(library.resolve()) for library in libraries))

        # Create the commands
        virtual_env_dir = Path(generated_dir) / self.name

        if CurrentShell.family_name == "Windows":
            activate_filename = virtual_env_dir / "Scripts" / "activate"
        else:
            activate_filename = virtual_env_dir / "bin" / "activate"

        commands: List[Commands.Command] = [
            Commands.Message(""),
        ]

        # In the following code, we are not exiting on error as we are sourcing the script
        # on Linux (meaning existing will cause the window to close).

        if force or not activate_filename.is_file():
            if force and os.getenv(Constants.DE_REPO_ACTIVATED_KEY):
                dm.WriteWarning(
                    textwrap.dedent(
                        """\

                        The python environment can not be force-created within an activated environment (as it is being used to run this script).
                        To force the creation of a new python virtual environment, run the same activation command within a new terminal window.

                        Continuing activation with the existing virtual environment.

                        """,
                    ),
                )

            else:
                commands += [
                    Commands.Execute(
                        'python -m RepositoryBootstrap.Impl.ActivateActivities.Impl.PythonCreateVirtualEnv "{virtual_env_dir}" "{pip_version}" "{setuptools_version}" "{wheel_version}"{verbose}'.format(
                            virtual_env_dir=str(virtual_env_dir),
                            pip_version=pip_version,
                            setuptools_version=setuptools_version,
                            wheel_version=wheel_version,
                            verbose=" --verbose" if dm.is_verbose else "",
                        ),
                        exit_via_return_statement=True,
                    ),
                ]

        commands.append(
            Commands.Call(
                str(activate_filename),
                exit_via_return_statement=True,
            ),
        )

        commands += [
            Commands.Execute(
                'python -m RepositoryBootstrap.Impl.ActivateActivities.Impl.PythonInstallRequirements "{requirements_filename}"{verbose}'.format(
                    requirements_filename=str(requirements_filename),
                    verbose=" --verbose" if dm.is_verbose else "",
                ),
                exit_via_return_statement=True,
            ),
            Commands.Delete(requirements_filename),

            Commands.Execute(
                'python -m RepositoryBootstrap.Impl.ActivateActivities.Impl.PythonInstallLibraries "{libraries_filename}"{debug}{verbose}'.format(
                    libraries_filename=str(libraries_filename),
                    debug=" --debug" if dm.is_debug else "",
                    verbose=" --verbose" if dm.is_verbose else "",
                ),
                exit_via_return_statement=True,
            ),
            Commands.Delete(libraries_filename),
        ]

        return commands
