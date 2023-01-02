# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 11:57:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=invalid-name
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

import io
import json
import os
import textwrap

from dataclasses import dataclass, field
from enum import auto, Enum
from pathlib import Path
from typing import Callable, cast, List, Optional, TextIO, Tuple, Union

import typer

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Shell.All import CurrentShell, LinuxShell, WindowsShell
from Common_Foundation.Shell.Shell import Shell
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import SubprocessEx
from Common_Foundation import Types

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ConfigurationInfo(object):
    # ----------------------------------------------------------------------
    name: str
    image_name: str
    shell: Shell

    decorate_base_dockerfile_instructions_func: Optional[Callable[[List[str]], List[str]]]          = field(kw_only=True, default=None)
    decorate_setup_dockerfile_instructions_func: Optional[Callable[[List[str]], List[str]]]         = field(kw_only=True, default=None)
    decorate_activated_dockerfile_instructions_func: Optional[Callable[[List[str]], List[str]]]     = field(kw_only=True, default=None)


# ----------------------------------------------------------------------
_linux_shell                                = LinuxShell()
_windows_shell                              = WindowsShell()


# ----------------------------------------------------------------------
def _UpdateOpenSUSE15BaseInstructions(*args, **kwargs): return __UpdateOpenSUSE15BaseInstructions(*args, **kwargs)      # pylint: disable=multiple-statements
def _UpdateOpenSUSE423BaseInstructions(*args, **kwargs): return __UpdateOpenSUSE423BaseInstructions(*args, **kwargs)    # pylint: disable=multiple-statements
def _UpdateFedora36SetupInstructions(*args, **kwargs): return __UpdateFedora36SetupInstructions(*args, **kwargs)        # pylint: disable=multiple-statements
def _UpdateFedora23BaseInstructions(*args, **kwargs): return __UpdateFedora23BaseInstructions(*args, **kwargs)          # pylint: disable=multiple-statements


# ----------------------------------------------------------------------
def _GetConfigurations() -> List[ConfigurationInfo]:
    if CurrentShell.family_name == "Windows":
        # Get version information to determine if docker is running Windows or Linux containers
        result = SubprocessEx.Run("docker version --format json")

        assert result.returncode == 0
        content = json.loads(result.output)

        content = content.get("Server", None)
        assert content

        content = content.get("Os", None)
        assert content

        if content.lower() == "windows":
            return [
                ConfigurationInfo(          # Released on 9/01/2021
                    "nanoserver:ltsc2022",
                    "mcr.microsoft.com/windows/nanoserver:ltsc2022",
                    _windows_shell,
                ),
            ]

    return [
        ConfigurationInfo(                  # Released on 7/01/2014
            "centos7",
            "centos:centos7",
            _linux_shell,
        ),
        ConfigurationInfo(                  # Released on 7/09/2022
            "debian:11.4-slim",
            "debian:11.4-slim",
            _linux_shell,
        ),
        ConfigurationInfo(                  # Released on 5/05/2022
            "fedora:36",
            "fedora:36",
            _linux_shell,
            decorate_setup_dockerfile_instructions_func=_UpdateFedora36SetupInstructions,
        ),
        ConfigurationInfo(                  # Released on 11/03/2015
            "fedora:23",
            "fedora:23",
            _linux_shell,
            decorate_base_dockerfile_instructions_func=_UpdateFedora23BaseInstructions,
        ),
        ConfigurationInfo(                  # Released on 12/24/2019
            "mint:19.3",
            "linuxmintd/mint19.3-amd64@sha256:23699c2acd7bf5df805375f0d39c7adafa98832749d1c3f43015b0941992d612",
            _linux_shell,
        ),
        ConfigurationInfo(                  # Released on 12/03/2019
            "opensuse_leap:15",
            "opensuse/leap:15",
            _linux_shell,
            decorate_base_dockerfile_instructions_func=_UpdateOpenSUSE15BaseInstructions,
        ),
        ConfigurationInfo(
            "opensuse_leap:42.3",           # Released on 7/27/2017
            "opensuse/leap:42.3",
            _linux_shell,
            decorate_base_dockerfile_instructions_func=_UpdateOpenSUSE423BaseInstructions,
        ),
        ConfigurationInfo(                  # Released on 5/07/2019
            "redhat_ubi:8",
            "redhat/ubi8:8.6-903.1661794351",
            _linux_shell,
        ),
        ConfigurationInfo(                  # Released on 4/21/2022
            "ubuntu:22.04",
            "ubuntu:22.04",
            _linux_shell,
        ),
        ConfigurationInfo(                  # Released on 4/26/2018
            "ubuntu:18.04",
            "ubuntu:18.04",
            _linux_shell,
        ),
    ]


# ----------------------------------------------------------------------
CONFIGURATIONS: List[ConfigurationInfo]     = _GetConfigurations()

del _GetConfigurations


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    class BuildStep(Enum):
        BundlingRepository                  = 0
        CreatingDockerFiles                 = auto()
        BuildingBaseImage                   = auto()
        BuildingSetupImage                  = auto()
        BuildingActivatedImage              = auto()

    # ----------------------------------------------------------------------
    DEFAULT_IMAGE_NAME                      = "common_foundation-playground"
    DEFAULT_MAINTAINER                      = "No Maintainer <no_maintainer@does_not_exist.com>"

    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="Docker Playground",
            configurations=[configuration.name for configuration in CONFIGURATIONS],
            configuration_is_required_on_clean=True,
            requires_output_dir=True,
        )

    # ----------------------------------------------------------------------
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],
        output_dir: Optional[Path],
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,                   # pylint: disable=unused-argument
        is_debug: bool,                     # pylint: disable=unused-argument
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        assert configuration
        assert output_dir
        assert output_dir.is_dir(), output_dir

        output_dir /= CurrentShell.ScrubFilename(configuration)
        assert output_dir

        with DoneManager.Create(
            output_stream,
            "Cleaning '{}'...".format(configuration),
        ) as dm:
            if output_dir.is_dir():
                with dm.Nested("Deleting '{}'...".format(output_dir)):
                    PathEx.RemoveTree(output_dir)
            else:
                dm.WriteInfo("The directory '{}' does not exist.\n".format(output_dir))

        return 0

    # ----------------------------------------------------------------------
    @classmethod
    def GetNumBuildSteps(
        cls,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        return len(cls.BuildStep)

    # ----------------------------------------------------------------------
    @staticmethod
    def GetCustomBuildArgs() -> TyperEx.TypeDefinitionsType:
        return {
            "dev_environment_configuration": (str, typer.Option("python310")),
            "image_name": (str, typer.Option(BuildInfo.DEFAULT_IMAGE_NAME, help="Name of the image to build.")),
            "maintainer": (str, typer.Option(BuildInfo.DEFAULT_MAINTAINER, help="Maintainer name in the generated dockerfile.")),
            "include_working_changes": (bool, typer.Option(False, "--include-working-changes", help="Include working changes in the source repository when building the image.")),
            "force": (bool, typer.Option(False, "--force", help="Do not use cache when building the image.")),
            "no_squash": (bool, typer.Option(False, "--no-squash", help="Do not squash layers in the generated image.")),
        }

    # ----------------------------------------------------------------------
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],
        output_dir: Optional[Path],
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
        dev_environment_configuration: str,
        force: bool,
        image_name: str,
        include_working_changes: bool,
        maintainer: str,
        no_squash: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        assert configuration
        assert output_dir

        if (
            (image_name != BuildInfo.DEFAULT_IMAGE_NAME and maintainer == BuildInfo.DEFAULT_MAINTAINER)
            or (image_name == BuildInfo.DEFAULT_IMAGE_NAME and maintainer != BuildInfo.DEFAULT_MAINTAINER)
        ):
            raise typer.BadParameter("Both image name and maintainer must be customized (or not customized) together.")

        config_info = next((config for config in CONFIGURATIONS if config.name == configuration), None)
        assert config_info is not None
        del configuration

        tag_template = _CreateDockerTagTemplate(image_name, config_info.name)

        with DoneManager.Create(
            output_stream,
            "Building '{}'...".format(config_info.name),
            output_flags=DoneManagerFlags.Create(
                verbose=is_verbose,
                debug=is_debug,
            ),
        ) as dm:
            if not os.getenv("DEVELOPMENT_ENVIRONMENT_DOCKER_DEVELOPMENT_MIXIN_ACTIVE"):
                dm.WriteError(
                    textwrap.dedent(
                        """\
                        This build relies on the repository 'Common_DockerDevelopmentMixin', which does
                        not appear to be activated.

                        This repository is available at: https://github.com/davidbrownell/v4-Common_DockerDevelopmentMixin
                        """,
                    ),
                )

                return dm.result

            output_dir /= CurrentShell.ScrubFilename(config_info.name)
            assert output_dir

            output_dir.mkdir(parents=True, exist_ok=True)

            archive_filename = output_dir / "archive.tgz"

            base_dockerfile = output_dir / "Dockerfile.base"
            setup_dockerfile = output_dir / "Dockerfile.setup"
            activated_dockerfile = output_dir / "Dockerfile.activated"

            base_tag = tag_template.format("base")
            setup_tag = tag_template.format("setup")
            activated_tag = tag_template.format("activated")

            with dm.Nested("Bundling repository...") as bundle_dm:
                on_progress_update(self.__class__.BuildStep.BundlingRepository.value, "Bundling repository")

                command_line = 'DockerDev{ext} BundleRepo "{repo_root}" "{bundle_filename}"{include_working_changes} --verbose --debug'.format(
                    ext=CurrentShell.script_extensions[0],
                    repo_root=Path(Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION"))),
                    bundle_filename=archive_filename,
                    include_working_changes=" --include-working-changes" if include_working_changes else "",
                )

                bundle_dm.WriteVerbose("Command line: {}".format(command_line))

                result = SubprocessEx.Run(command_line)

                bundle_dm.result = result.returncode

                if bundle_dm.result != 0:
                    bundle_dm.WriteError(result.output)
                    return bundle_dm.result

                with bundle_dm.YieldVerboseStream() as stream:
                    stream.write(result.output)

            with dm.Nested("Creating dockerfiles..."):
                on_progress_update(self.__class__.BuildStep.CreatingDockerFiles.value, "Creating dockerfiles")

                if config_info.shell is _linux_shell:
                    base_dockerfile_instructions: List[str] = [
                        "FROM {}".format(config_info.image_name),
                        "RUN mkdir code",
                        "COPY {name} code/{name}".format(name=archive_filename.name),
                        textwrap.dedent(
                            """\
                            RUN cd code \\
                                && tar -xf {name} \\
                                && rm {name} \\
                                && find . -name "*.sh" -exec chmod a+x {{}} +
                            """,
                        ).format(name=archive_filename.name),
                        "WORKDIR /code",
                        'CMD ["bash"]',
                        'LABEL maintainer="{}"'.format(maintainer),
                    ]

                    setup_dockerfile_instructions: List[str] = [
                        "FROM {}".format(base_tag),
                        'RUN bash -c "./Setup.sh --debug"',
                    ]

                    activated_dockerfile_instructions: List[str] = [
                        "FROM {}".format(setup_tag),
                        'RUN bash -c "source ./Activate.sh {} --debug"'.format(dev_environment_configuration),
                        'CMD ["bash", "-c", "source ./Activate.sh {}; bash"]'.format(dev_environment_configuration),
                    ]

                elif config_info.shell is _windows_shell:
                    base_dockerfile_instructions: List[str] = [
                        "FROM {}".format(config_info.image_name),
                        "RUN mkdir code",
                        "COPY {name} .".format(name=archive_filename.name),
                        textwrap.dedent(
                            """\
                            RUN tar -xf {name} -C code \\
                                && del code\\\\{name} \\
                                && del {name}
                            """,
                        ).format(name=archive_filename.name),
                        r"WORKDIR C:\\code",
                        'CMD ["cmd"]',
                        'LABEL maintainer="{}"'.format(maintainer),
                    ]

                    setup_dockerfile_instructions: List[str] = [
                        "FROM {}".format(base_tag),
                        "RUN Setup.cmd --debug",
                    ]

                    activated_dockerfile_instructions: List[str] = [
                        "FROM {}".format(setup_tag),
                        "RUN Activate.cmd {} --debug && rmdir /S /Q pypa && rmdir /S /Q pip".format(dev_environment_configuration),
                        'CMD ["cmd", "/k", "Activate.cmd {}"]'.format(dev_environment_configuration),
                    ]

                else:
                    assert False, config_info.shell  # pragma: no cover

                base_dockerfile_instructions = (config_info.decorate_base_dockerfile_instructions_func or (lambda value: value))(base_dockerfile_instructions)
                setup_dockerfile_instructions = (config_info.decorate_setup_dockerfile_instructions_func or (lambda value: value))(setup_dockerfile_instructions)
                activated_dockerfile_instructions = (config_info.decorate_activated_dockerfile_instructions_func or (lambda value: value))(activated_dockerfile_instructions)

                with base_dockerfile.open("w") as f:
                    f.write("\n".join(base_dockerfile_instructions))

                with setup_dockerfile.open("w") as f:
                    f.write("\n".join(setup_dockerfile_instructions))

                with activated_dockerfile.open("w") as f:
                    f.write("\n".join(activated_dockerfile_instructions))

            with dm.Nested("Building images...") as build_dm:
                build_info = [
                    (self.__class__.BuildStep.BuildingBaseImage, "base image", base_dockerfile, base_tag),
                    (self.__class__.BuildStep.BuildingSetupImage, "setup image", setup_dockerfile, setup_tag),
                    (self.__class__.BuildStep.BuildingActivatedImage, "activated image", activated_dockerfile, activated_tag),
                ]

                for build_index, (build_step, name, dockerfile, tag) in enumerate(build_info):
                    with build_dm.Nested(
                        "Building '{}' ({} of {})'...".format(
                            name,
                            build_index + 1,
                            len(build_info),
                        ),
                    ) as this_build_dm:
                        on_progress_update(build_step.value, "Building '{}'".format(name))

                        command_line = 'docker build --tag {tag}{squash}{force} -f {dockerfile} .'.format(
                            tag=tag,
                            squash="" if no_squash else " --squash",
                            force=" --no-cache" if force else "",
                            dockerfile=dockerfile.name,
                        )

                        this_build_dm.WriteVerbose("Command line: {}".format(command_line))

                        result = SubprocessEx.Run(
                            command_line,
                            cwd=dockerfile.parent,
                        )

                        this_build_dm.result = result.returncode

                        if this_build_dm.result != 0:
                            this_build_dm.WriteError(result.output)
                            return this_build_dm.result

                        with this_build_dm.YieldVerboseStream() as stream:
                            stream.write(result.output)

            return dm.result


# ----------------------------------------------------------------------
_configurations_and_all                     = Types.StringsToEnum(
    "ConfigurationsAndAllEnum",
    ["All", ] + [config.name for config in CONFIGURATIONS],
)


# ----------------------------------------------------------------------
def BuildVerificationTest(
    configuration: _configurations_and_all=typer.Argument(..., help="Docker image configuration to validate."),  # type: ignore
    dev_environment_config: str=typer.Option("python310", help="Development environment configuration specified during Build."),
    image_name: str=typer.Option(BuildInfo.DEFAULT_IMAGE_NAME, help="Docker image name specified during Build."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
) -> None:
    """Verifies basic functionality associated with an image."""

    if configuration.value == "All":
        configurations = CONFIGURATIONS
    else:
        configurations = [
            next((config for config in CONFIGURATIONS if config.name == configuration.value), None),
        ]

        assert configurations[0]

    configurations = cast(List[ConfigurationInfo], configurations)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        for config_index, config in enumerate(configurations):
            with dm.Nested(
                "Processing '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(configurations),
                ),
                suffix="\n" if dm.is_verbose else "",
            ) as config_dm:
                # Create the guest commands
                if isinstance(config.shell, LinuxShell):
                    commands = 'bash -c "{}"'.format(
                        " && ".join(
                            [
                                ". ./Activate.sh {} --debug".format(dev_environment_config),
                                "Tester.sh TestType basic_python_unittest Scripts /tmp/TesterOutput UnitTests --debug",
                                "Builder.sh Build . /tmp/BuilderOutput --debug",
                            ],
                        ),
                    )

                elif isinstance(config.shell, WindowsShell):
                    commands = 'cmd /c "{}"'.format(
                        " && ".join(
                            [
                                "Activate.cmd {} --debug".format(dev_environment_config),
                                r"Tester.cmd TestType basic_python_unittest Scripts C:\Temp\TesterOutput UnitTests --debug",
                                r"Builder.cmd Build . C:\Temp\BuilderOutput --debug",
                            ],
                        ),
                    )

                else:
                    assert False, config.shell  # pragma: no cover

                command_line = 'docker run --rm {docker_image_name} {commands}'.format(
                    docker_image_name=_CreateDockerTagTemplate(image_name, config.name).format("activated"),
                    commands=commands,
                )

                config_dm.WriteVerbose("Command line: {}\n\n".format(command_line))

                sink = io.StringIO()

                with config_dm.YieldVerboseStream() as verbose_stream:
                    config_dm.result = SubprocessEx.Stream(command_line, StreamDecorator([verbose_stream, sink]))

                if config_dm.result != 0 and not config_dm.is_verbose:
                    config_dm.WriteError(sink.getvalue())


# ----------------------------------------------------------------------
def Publish(
    configuration: _configurations_and_all=typer.Argument(..., help="Docker image configurations to push."),  # type: ignore
    image_name: str=typer.Argument(..., help="Docker image name specified during Build."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
) -> None:
    """Publishes images to docker hub"""

    if configuration.value == "All":
        configurations = CONFIGURATIONS
    else:
        configurations = [
            next((config for config in CONFIGURATIONS if config.name == configuration.value), None),
        ]

        assert configurations[0]

    configurations = cast(List[ConfigurationInfo], configurations)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        for config_index, config in enumerate(configurations):
            with dm.Nested(
                "Processing '{}' ({} of {})...".format(
                    config.name,
                    config_index + 1,
                    len(configurations),
                ),
                suffix="\n" if dm.is_verbose else "",
            ) as config_dm:
                command_line = 'docker push {}'.format(
                    _CreateDockerTagTemplate(image_name, config.name).format("activated"),
                )

                config_dm.WriteVerbose("Command line: {}\n\n".format(command_line))

                sink = io.StringIO()

                with config_dm.YieldVerboseStream() as verbose_stream:
                    config_dm.result = SubprocessEx.Stream(command_line, StreamDecorator([sink, verbose_stream]))

                if config_dm.result != 0 and not config_dm.is_verbose:
                    config_dm.WriteError(sink.getvalue())


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _CreateDockerTagTemplate(
    image_name: str,
    configuration: str,
) -> str:
    # TODO: Hard-coded version
    return "{}:4.0.0-{}-{{}}".format(
        image_name,
        CurrentShell.ScrubFilename(configuration),
    )


# ----------------------------------------------------------------------
def __UpdateOpenSUSE15BaseInstructions(
    instructions: List[str],
) -> List[str]:
    instructions.insert(1, "RUN zypper install -y tar gzip")
    return instructions


# ----------------------------------------------------------------------
def __UpdateOpenSUSE423BaseInstructions(
    instructions: List[str],
) -> List[str]:
    instructions.insert(1, "RUN zypper install -y tar; exit 0")
    return instructions


# ----------------------------------------------------------------------
def __UpdateFedora36SetupInstructions(
    instructions: List[str],
) -> List[str]:
    instructions.insert(1, "RUN yum install -y libxcrypt-compat")
    return instructions


# ----------------------------------------------------------------------
def __UpdateFedora23BaseInstructions(
    instructions: List[str],
) -> List[str]:
    instructions.insert(1, "RUN yum install -y findutils tar")
    return instructions


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
