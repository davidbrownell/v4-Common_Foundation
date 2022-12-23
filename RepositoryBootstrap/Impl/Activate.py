# ----------------------------------------------------------------------
# |
# |  Activate.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 11:42:33
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Activates a repository"""

import json
import os
import sys
import textwrap
import uuid

from enum import Enum
from pathlib import Path
from typing import Callable, cast, List, Optional, Union

import typer

from typer.core import TyperGroup

from Common_Foundation.ContextlibEx import ExitStack                                # type: ignore
from Common_Foundation.Shell import Commands                                        # type: ignore
from Common_Foundation.Shell.All import CurrentShell                                # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags     # type: ignore
from Common_Foundation.Streams.StreamDecorator import StreamDecorator               # type: ignore
from Common_Foundation import TextwrapEx                                            # type: ignore

from .ActivationData import ActivationData, Fingerprints
from .EnvironmentBootstrap import EnvironmentBootstrap
from .GenerateCommands import GenerateCommands

from .ActivateActivities.PythonActivateActivity import PythonActivateActivity
from .ActivateActivities.ScriptsActivateActivity import ScriptsActivateActivity
from .ActivateActivities.ToolsActivateActivity import ToolsActivateActivity

from ..ActivateActivity import ActivateActivity
from ..Configuration import VersionSpecs
from .. import Constants


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command("Activate", no_args_is_help=True)
def Activate(
    output_filename_or_stdout: str=typer.Argument(..., help="Filename for generated content or standard output if the value is 'stdout'."),
    repository_root: Path=typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Root of the repository."),
    configuration: str=typer.Argument(..., help="Configuration to activate; 'None' implies the default configuration."),
    force: bool=typer.Option(False, "--force", help="Force the regeneration of environment data; if not specified, activation will attempt to use cached data."),
    force_if_necessary: bool=typer.Option(False, "--force-if-necessary", help="Force the regeneration of environment data when necessary."),
    mixin: Optional[List[Path]]=typer.Option(None, exists=True, file_okay=False, resolve_path=True, help="Activate a mixin repository at the specified folder location along with this repository."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
):
    """Activates an environment for development."""

    configuration_value: Optional[str] = configuration if configuration != "None" else None

    mixins = cast(List[Path], mixin)
    del mixin

    # ----------------------------------------------------------------------
    def Execute() -> List[Commands.Command]:
        with DoneManager.Create(
            sys.stdout,
            heading=None,
            line_prefix="",
            display=False,
            display_exceptions=False,
            output_flags=DoneManagerFlags.Create(
                verbose=verbose,
                debug=debug,
            ),
        ) as dm:
            nonlocal force
            nonlocal configuration_value

            environment_activated_key = os.getenv(Constants.DE_REPO_ACTIVATED_KEY)
            if environment_activated_key is not None:
                activation_key = environment_activated_key
            else:
                activation_key = str(uuid.uuid4()).upper().replace("-", "")

            # Load the activation data
            activation_data = ActivationData.Load(
                dm,
                repository_root,
                configuration_value,  # pylint: disable=used-before-assignment
                force=force or environment_activated_key is None,
            )

            # Ensure that the generated dir exists
            generated_dir = activation_data.GetActivationDir()
            generated_dir.mkdir(parents=True, exist_ok=True)

            # Determine if the fingerprints activated in the past match the fingerprints
            # calculated with this activation data. If they don't match, the repository
            # needs to be activated with the force flag.
            prev_fingerprints_filename = generated_dir / Constants.GENERATED_ACTIVATION_FINGERPRINT_FILENAME

            update_fingerprints_file = False

            if force or not prev_fingerprints_filename.is_file():
                update_fingerprints_file = True
            else:
                with prev_fingerprints_filename.open() as f:
                    prev_fingerprint_content = Fingerprints.CreateFromJson(
                        activation_data.root,
                        json.load(f),
                    )

                if prev_fingerprint_content != activation_data.fingerprints:
                    if force_if_necessary:
                        dm.WriteInfo("\nThe repository or one of its dependencies have changed; force will be applied.\n\n")
                        force = True

                    if not force:
                        raise Exception(
                            textwrap.dedent(
                                """\
                                ****************************************************************************************************
                                {repo_root}
                                ****************************************************************************************************

                                This repository or one of its dependencies have changed.

                                Please run '{activate}' with the '--force' or '--force-if-necessary' flag.

                                ****************************************************************************************************
                                ****************************************************************************************************
                                """,
                            ).format(
                                repo_root=repository_root,
                                activate="{}{}".format(Constants.ACTIVATE_ENVIRONMENT_NAME, CurrentShell.script_extensions[0]),
                            ),
                        )

                    update_fingerprints_file = True

            # ----------------------------------------------------------------------
            def LoadMixinLibrary(
                mixin_path: Path,
            ) -> None:
                if mixin_path == activation_data.root:
                    return

                mixin_activation_data = ActivationData.Load(
                    dm,
                    mixin_path,
                    None,
                    force=True, # force ensures that we are loading the activation data for the mixin repo and not the currently activated repo
                )

                if not mixin_activation_data.is_mixin_repo:
                    raise Exception("The repository at '{}' is not a mixin repository.".format(str(mixin_path)))

                mixin_repo = mixin_activation_data.prioritized_repositories[-1]
                assert mixin_repo.root == mixin_path, (mixin_repo.root, mixin_path)
                assert mixin_repo.is_mixin_repo

                # Add this repo as one to be activated if it isn't already in the list
                if not any(repo.id == mixin_repo.id for repo in activation_data.prioritized_repositories):
                    activation_data.prioritized_repositories.append(mixin_repo)

            # ----------------------------------------------------------------------

            is_mixin_repo = EnvironmentBootstrap.Load(repository_root).is_mixin_repo

            if is_mixin_repo:
                if force:
                    raise Exception("'force' cannot be used with mixin repositories.")

                if mixins:
                    raise Exception("A mixin repository cannot be activated with other mixins.")

                LoadMixinLibrary(repository_root)

                configuration_value = activation_data.configuration

            for mixin in mixins:
                LoadMixinLibrary(mixin)

            # Create the parameters
            kwargs = {
                "activation_key": activation_key,
                "dm": dm,
                "configuration": configuration_value,
                "activation_data": activation_data,
                "version_specs": activation_data.version_specs,
                "generated_dir": generated_dir,
                "force": force,
            }

            # Initialize the activities
            activities: List[
                Callable[
                    ...,
                    Union[None, int, List[Commands.Command]],
                ]
            ] = []

            if not is_mixin_repo:
                activities += [
                    _ActivateOriginalEnvironment,
                    _ActivateRepoEnvironmentVars,
                    _ActivateActivationData,
                ]

            activities += [
                _ActivateNameDisplay,

                # Note that activating python will reset environment variables, so it must come early
                # in the activation process.
                _ActivatePython,

                _ActivateTools,
                _ActivateScripts,
                _ActivateCustom,
                _ActivatePrompt,
                _ActivateActivatedKey,
            ]

            if update_fingerprints_file:
                activities.append(_ActivateFingerprintsFile)

            # Invoke the activities
            commands: List[Commands.Command] = []

            for activity in activities:
                these_commands = activity(**kwargs)
                if these_commands is not None:
                    if isinstance(these_commands, int):
                        raise typer.Exit(these_commands)

                    commands += these_commands

                dm.ExitOnError()

            return commands

    # ----------------------------------------------------------------------

    result, commands = GenerateCommands(
        Execute,
        debug=debug,
    )

    if output_filename_or_stdout == "stdout":
        final_output_stream = sys.stdout
        close_stream_func = lambda: None
    else:
        final_output_stream = open(output_filename_or_stdout, "w")
        close_stream_func = final_output_stream.close

    with ExitStack(close_stream_func):
        final_output_stream.write(CurrentShell.GenerateCommands(commands))

    return result


# ----------------------------------------------------------------------
class DisplayFormat(str, Enum):
    standard                                = "standard"
    json                                    = "json"
    command_line                            = "command_line"


@app.command("ListConfigurations", no_args_is_help=True)
def ListConfigurations(
    repository_root: Path=typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Root of the repository."),
    display_format: DisplayFormat=typer.Option(DisplayFormat.standard, case_sensitive=False, help="Format to use when displaying results."),
):
    """Lists all configurations available for activation by this repository."""

    try:
        repo_info = EnvironmentBootstrap.Load(repository_root)

    except Exception as ex:
        if display_format != DisplayFormat.command_line:
            raise

        sys.stdout.write(TextwrapEx.CreateErrorText(TextwrapEx.Indent(str(ex), 9)))
        raise typer.Exit(-1)

    if display_format == DisplayFormat.json:
        # This is a bare-bones representation of the data for a controlled set of scenarios.
        # Additional scenarios should populate additional data as needed.
        items = {
            config_name: {
                "description": configuration.description,
            }
            for config_name, configuration in repo_info.configurations.items()
        }

        sys.stdout.write(json.dumps(items))
        return 0

    # Get the size of the largest configuration name
    if len(repo_info.configurations) == 1:
        key = next(iter(repo_info.configurations))
        max_config_name_length = len(key or "")
    else:
        max_config_name_length = max(*[len(config_name) if config_name is not None else 0 for config_name in repo_info.configurations.keys()])

    max_config_name_length = min(max_config_name_length, 30)

    # Create the content
    content: List[str] = []

    for config_name, configuration in repo_info.configurations.items():
        content.append(
            "{0:<{1}}{2}".format(
                config_name or "",
                max_config_name_length,
                " : {}\n".format(configuration.description),
            ),
        )

    if display_format == DisplayFormat.standard:
        if not repo_info.is_configurable:
            sys.stdout.write("The repository is not configurable\n")
            raise typer.Exit(1)

        sys.stdout.write(
            textwrap.dedent(
                """\

                Available configurations:

                {}

                """,
            ).format("".join("    - {}".format(line) for line in content)),
        )

    elif display_format == DisplayFormat.command_line:
        if not repo_info.is_configurable:
            sys.stdout.write("The repository is not configurable\n")
            raise typer.Exit(1)

        sys.stdout.write(
            TextwrapEx.CreateErrorText(
                TextwrapEx.Indent("".join(content), 9),
                error_per_line=True,
            ),
        )

    else:
        assert False, display_format  # pragma: no cover

    return 0


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ActivateOriginalEnvironment(
    activation_key: str,
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,        # pylint: disable=unused-argument
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,                    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
) -> None:
    original_environment_filename = CurrentShell.temp_directory / Constants.GENERATED_ACTIVATION_ORIGINAL_ENVIRONMENT_FILENAME_TEMPLATE.format(
        activation_key,
    )

    if original_environment_filename.is_file():
        return

    original_environment = dict(os.environ)

    elimination_funcs: List[Callable[[str], bool]] = [
        lambda value: value.startswith("PYTHON"),
        lambda value: value.startswith("DEVELOPMENT_ENVIRONMENT"),
        lambda value: value.startswith("_DEVELOPMENT_ENVIRONMENT"),
    ]

    for k in list(original_environment.keys()):
        for elimination_func in elimination_funcs:
            if elimination_func(k):
                del original_environment[k]
                break

    # The path used here contains a path to a python binary, which was added by the activation scripts.
    # Replace the current path with the original path (which doesn't have this information).
    original_path = os.getenv(Constants.DE_ORIGINAL_PATH)
    assert original_path is not None

    original_environment["PATH"] = original_path

    with original_environment_filename.open("w") as f:
        json.dump(original_environment, f)


# ----------------------------------------------------------------------
def _ActivateRepoEnvironmentVars(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],
    activation_data: ActivationData,        # pylint: disable=unused-argument
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,
    force: bool,                            # pylint: disable=unused-argument
) -> List[Commands.Command]:
    # To get the root, we need to go up 3 levels ("Generated", operating system, and configuration) plus
    # any levels associated with the custom environment name.
    environment_name = os.getenv(Constants.DE_ENVIRONMENT_NAME)
    assert environment_name is not None

    dirs_to_remove = 3 + len(environment_name.split(os.path.sep))

    assert dirs_to_remove <= len(generated_dir.parts), (dirs_to_remove, generated_dir.parts)
    root_name = generated_dir.joinpath(*(["..", ] * dirs_to_remove))

    commands: List[Commands.Command] = [
        Commands.Set(Constants.DE_REPO_ROOT_NAME, str(root_name.resolve())),
        Commands.Set(Constants.DE_REPO_GENERATED_NAME, str(generated_dir.resolve())),
        Commands.Set(Constants.DE_OPERATING_SYSTEM_NAME, CurrentShell.family_name),
    ]

    if configuration is not None:
        commands += [
            Commands.Set(Constants.DE_REPO_CONFIGURATION_NAME, configuration),
        ]

    return commands


# ----------------------------------------------------------------------
def _ActivateActivationData(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,                    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
) -> None:
    activation_data.Save()


# ----------------------------------------------------------------------
def _ActivateNameDisplay(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,                    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
) -> None:
    names: List[str] = []

    for repo in activation_data.prioritized_repositories:
        names.append(
            "{}{}{}".format(
                repo.name,
                " ({})".format(repo.configuration) if repo.configuration else "",
                " [Mixin]" if repo.is_mixin_repo else "",
            ),
        )

    with dm.YieldStream() as stream:
        if len(activation_data.prioritized_repositories) == 1:
            status_text = "Activating this repository..."
        else:
            status_text = "Activating these repositories..."

        stream.write("\n{}\n\n\n".format(status_text))

        StreamDecorator(stream, "    ").write(
            TextwrapEx.CreateTable(
                [
                    "Repository Name",
                    "Id",
                    "Location",
                ],
                [
                    [
                        name,
                        str(repo.id),
                        str(repo.root),
                    ]
                    for repo, name in zip(activation_data.prioritized_repositories, names)
                ]
            ),
        )

        stream.write("\n\n")


# ----------------------------------------------------------------------
def _ActivateTools(
    activation_key: str,  # pylint: disable=unused-argument
    dm: DoneManager,
    configuration: Optional[str],
    activation_data: ActivationData,
    version_specs: VersionSpecs,
    generated_dir: Path,
    force: bool,
) -> List[Commands.Command]:
    return ToolsActivateActivity().CreateCommands(
        dm,
        configuration,
        activation_data.prioritized_repositories,
        version_specs,
        generated_dir,
        force=force,
    )


# ----------------------------------------------------------------------
def _ActivateScripts(
    activation_key: str,  # pylint: disable=unused-argument
    dm: DoneManager,
    configuration: Optional[str],
    activation_data: ActivationData,
    version_specs: VersionSpecs,
    generated_dir: Path,
    force: bool,
) -> List[Commands.Command]:
    return ScriptsActivateActivity().CreateCommands(
        dm,
        configuration,
        activation_data.prioritized_repositories,
        version_specs,
        generated_dir,
        force=force,
    )


# ----------------------------------------------------------------------
def _ActivatePython(
    activation_key: str,  # pylint: disable=unused-argument
    dm: DoneManager,
    configuration: Optional[str],
    activation_data: ActivationData,
    version_specs: VersionSpecs,
    generated_dir: Path,
    force: bool,
) -> List[Commands.Command]:
    return PythonActivateActivity().CreateCommands(
        dm,
        configuration,
        activation_data.prioritized_repositories,
        version_specs,
        generated_dir,
        force=force,
    )


# ----------------------------------------------------------------------
# Update the comments in ../Constants.py if this method name changes
def _ActivateCustom(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,
    version_specs: VersionSpecs,
    generated_dir: Path,
    force: bool,
) -> List[Commands.Command]:
    # Massage the args a bit to make them a bit easier to consume
    kwargs = {
        "dm": dm,
        "repositories": activation_data.prioritized_repositories,
        "is_mixin_repo": activation_data.is_mixin_repo,
        "version_specs": version_specs,
        "generated_dir": generated_dir,
        "force": force,
    }

    commands: List[Commands.Command] = []

    # Standard invocation
    for repo in activation_data.prioritized_repositories:
        kwargs["configuration"] = repo.configuration

        result = ActivateActivity.CallCustomMethod(
            repo.root / Constants.ACTIVATE_ENVIRONMENT_CUSTOMIZATION_FILENAME,
            Constants.ACTIVATE_ENVIRONMENT_ACTIONS_METHOD_NAME,
            kwargs,
            result_is_list=True,
        )

        if result is not None:
            commands += result

    # Epilogue invocation
    for repo in activation_data.prioritized_repositories:
        kwargs["configuration"] = repo.configuration

        result = ActivateActivity.CallCustomMethod(
            repo.root / Constants.ACTIVATE_ENVIRONMENT_CUSTOMIZATION_FILENAME,
            Constants.ACTIVATE_ENVIRONMENT_ACTIONS_EPILOGUE_METHOD_NAME,
            kwargs,
            result_is_list=True,
        )

        if result is not None:
            commands += result

    return commands


# ----------------------------------------------------------------------
def _ActivatePrompt(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],
    activation_data: ActivationData,
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,                    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
) -> List[Commands.Command]:
    mixin_names: List[str] = []

    index = -1
    while activation_data.prioritized_repositories[index].is_mixin_repo:
        mixin_names.append(activation_data.prioritized_repositories[index].name)
        index -= 1

    prompt = activation_data.prioritized_repositories[index].name
    if configuration:
        prompt += " - {}".format(configuration)

    if mixin_names:
        mixin_names.reverse()

        prompt += " [{}]".format(", ".join(mixin_names))

    return [
        Commands.CommandPrompt(
            prompt,
            is_prefix=True,
        ),
    ]


# ----------------------------------------------------------------------
def _ActivateActivatedKey(
    activation_key: str,
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,        # pylint: disable=unused-argument
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,                    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
) -> List[Commands.Command]:
    return [
        Commands.Set(Constants.DE_REPO_ACTIVATED_KEY, activation_key),
    ]


# ----------------------------------------------------------------------
def _ActivateFingerprintsFile(
    activation_key: str,                    # pylint: disable=unused-argument
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    activation_data: ActivationData,
    version_specs: VersionSpecs,            # pylint: disable=unused-argument
    generated_dir: Path,
    force: bool,                            # pylint: disable=unused-argument
) -> None:
    with (generated_dir / Constants.GENERATED_ACTIVATION_FINGERPRINT_FILENAME).open("w") as f:
        json.dump(activation_data.fingerprints.ToJson(activation_data.root), f)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
