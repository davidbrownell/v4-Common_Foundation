# ----------------------------------------------------------------------
# |
# |  Setup.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-07 15:05:16
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""One-time environment preparation for a repository."""

import os
import shutil
import sys
import textwrap
import traceback
import types
import uuid

from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Set, Tuple, Union

import colorama
import inflect as inflect_mod
import typer

from typer.core import TyperGroup

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.DynamicFunctions import CreateInvocationWrapper
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Shell import Commands
from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.SourceControlManager import SourceControlManager
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from .EnvironmentBootstrap import EnvironmentBootstrap
from . import RepositoryMapCalculator
from .SetupActivities.PythonSetupActivity import PythonSetupActivity

from . import Utilities

from .. import Configuration
from .. import Constants
from .. import DataTypes
from ..Impl.GenerateCommands import GenerateCommands


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()

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
DEFAULT_SEARCH_DEPTH                        = 6


# ----------------------------------------------------------------------
@app.command("Setup", no_args_is_help=True)
def Setup(
    output_filename_or_stdout: str=typer.Argument(..., help="Filename for generated content or standard output if the value is 'stdout'."),
    repository_root: Path=typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Root of the repository."),
    configurations: Optional[List[str]]=typer.Option(None, "--configuration", help="Configurations to setup; all configurations will be setup if explicit values are not provided."),
    search_depth: Optional[int]=typer.Option(DEFAULT_SEARCH_DEPTH, min=1, help="Limit searches to N path-levels deep."),
    max_num_searches: Optional[int]=typer.Option(None, min=1, help="Limit the number of directories searched when looking for dependencies; this value can be used to reduce the overall time it takes to search for dependencies that ultimately can't be found."),
    required_ancestor_dirs: Optional[List[Path]]=typer.Option(None, "--required-ancestor-dir", exists=True, file_okay=False, resolve_path=True, help="When searching for dependencies, limit the search to directories that are descendants of this ancestor."),
    no_hooks: bool=typer.Option(False, "--no-hooks", help="Do not setup SCM hooks."),
    force: bool=typer.Option(False, "--force", help="Force the setup of environment data; if not specified."),
    interactive: Optional[bool]=typer.Option(None, help="Force/Prevent an interactive experience (if any)."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
) -> None:
    """Perform setup activities for this repository."""

    configurations = Types.EnsurePopulatedList(configurations)

    # Convert ["None"] -> None
    if (
        configurations
        and len(configurations) == 1
        and configurations[0] == "None"
    ):
        configurations = None

    if any(config == "None" for config in (configurations or [])):
        raise typer.BadParameter("'None' is not a valid configuration.")

    # Update the search depth based on the require dir info
    if required_ancestor_dirs and search_depth == DEFAULT_SEARCH_DEPTH:
        if len(required_ancestor_dirs) == 1:
            max_num_required_dirs = len(required_ancestor_dirs[0].parts)
        else:
            max_num_required_dirs = max(*(len(path.parts) for path in required_ancestor_dirs))

        search_depth += max_num_required_dirs

    with RepositoryMapCalculator.GetCustomizationMod(repository_root) as customization_mod:
        # ----------------------------------------------------------------------
        def Execute() -> List[Commands.Command]:
            with DoneManager.Create(
                sys.stdout,
                heading=None,
                line_prefix="",
                display=False,
                output_flags=DoneManagerFlags.Create(
                    verbose=verbose,
                    debug=debug,
                ),
            ) as dm:
                kwargs = {
                    "dm": dm,
                    "customization_mod": customization_mod,
                    "repository_root": repository_root,
                    "configurations": configurations,
                    "force": force,
                    "interactive": interactive,
                }

                activities: List[
                    Callable[
                        ...,
                        Union[None, int, List[Commands.Command]]
                    ]
                ] = []

                activities += [
                    # Note that setup bootstrap MUST be the first activity invoked, as it creates
                    # information leveraged by the other activities.
                    lambda **kwargs: _SetupBootstrap(
                        **{
                            **kwargs,
                            **{
                                "search_depth": search_depth,
                                "max_num_searches": max_num_searches,
                                "required_ancestor_dirs": required_ancestor_dirs,
                            },
                        },
                    ),
                    _SetupPython,
                    _SetupCustom,
                    _SetupActivateScripts,
                ]

                if not no_hooks:
                    activities += [_SetupScmHooks, ]

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

        typer.Exit(result)


# ----------------------------------------------------------------------
# |
# |  Private Functions
# |
# ----------------------------------------------------------------------
def _SetupBootstrap(
    dm: DoneManager,
    repository_root: Path,
    customization_mod: types.ModuleType,    # pylint: disable=unused-argument
    configurations: Optional[List[str]],
    force: bool,                            # pylint: disable=unused-argument
    interactive: Optional[bool],            # pylint: disable=unused-argument
    search_depth: int,
    max_num_searches: Optional[int],
    required_ancestor_dirs: List[Path],
) -> None:
    if dm.capabilities.supports_colors:
        error_on = "{}{}".format(colorama.Fore.RED, colorama.Style.BRIGHT)
        success_on = "{}{}".format(colorama.Fore.GREEN, colorama.Style.BRIGHT)
        highlight_on = "{}{}".format(colorama.Fore.WHITE, colorama.Style.BRIGHT)
        color_off = colorama.Style.RESET_ALL
    else:
        error_on = ""
        highlight_on = ""
        color_off = ""

    calculator: Optional[RepositoryMapCalculator.RepositoryMapCalculator] = None

    with dm.Nested(
        "Searching for dependencies of '{}'...".format(repository_root),
        [
            lambda: None if calculator is None else "{} found".format(inflect.no("repository", len(calculator.encountered_repos))),
            lambda: None if calculator is None else "{} missing".format(inflect.no("repository", len(calculator.pending_repos))),
        ],
        suffix="\n",
        preserve_status=True,
    ) as nested_dm:
        # ----------------------------------------------------------------------
        class InternalRepositoryMapCalculator(RepositoryMapCalculator.RepositoryMapCalculator):
            # ----------------------------------------------------------------------
            def __init__(self, *args, **kwargs):
                self._invalid_module_warnings: Dict[Path, str]                  = {}

                self._encountered_name_warnings: Dict[
                    Tuple[str, Path, uuid.UUID],
                    Dict[Optional[str], Dict[uuid.UUID, str]],
                ]                               = {}

                self._pending_name_warnings: Dict[
                    Tuple[str, Path, uuid.UUID],
                    Dict[Optional[str], Dict[uuid.UUID, str]],
                ]                               = {}

                super(InternalRepositoryMapCalculator, self).__init__(*args, **kwargs)

            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
            def _OnStatusUpdate(
                self,
                directories_searched: int,
                directories_pending: int,
                repositories_found: int,
                repositories_pending: int,
                current_path: Optional[Path],
            ) -> bool:
                self._OutputStatus(
                    directories_searched,
                    directories_pending,
                    repositories_found,
                    repositories_pending,
                    current_path,
                )

                return True

            # ----------------------------------------------------------------------
            def _OnModuleError(
                self,
                ex: Exception,
                repo_data: DataTypes.RepoData,
                repo_path: Path,
            ) -> bool:
                if nested_dm.is_debug:
                    error = traceback.format_exc()
                else:
                    error = str(ex)

                self._invalid_module_warnings[repo_path] = error.rstrip()
                return True

            # ----------------------------------------------------------------------
            def _OnDependencyNameMismatch(
                self,
                encountered_data: RepositoryMapCalculator.EncounteredRepoData,
                dependency_name: str,
                requesting_data: DataTypes.RepoData,
                requesting_path: Path,
                requesting_configuration: Optional[str],
            ) -> None:
                key = (requesting_data.name, requesting_path, requesting_data.id)

                (
                    self._encountered_name_warnings
                        .setdefault(key, {})
                        .setdefault(requesting_configuration, {})
                        [encountered_data.id]
                ) = textwrap.dedent(
                    """\
                    Specified: {error_on}{dependency_name}{color_off}
                    Actual:    {success_on}{actual_name}{color_off}

                        Repo Id:        {actual_id}
                        Repo Location:  {actual_location}
                    """,
                ).format(
                    dependency_name=dependency_name,
                    actual_name=encountered_data.name,
                    actual_id=encountered_data.id,
                    actual_location=str(encountered_data.root),
                    error_on=error_on,
                    success_on=success_on,
                    color_off=color_off,
                )

                # Remove any pending warnings about this dependency, as the encountered data is the authority
                (
                    self._pending_name_warnings
                        .get(key, {})
                        .get(requesting_configuration, {})
                        .pop(encountered_data.id, None)
                )

            # ----------------------------------------------------------------------
            def _OnPendingNameMismatch(
                self,
                pending_data: RepositoryMapCalculator.PendingRepoData,
                pending_path: Path,
                dependency_name: str,
                requesting_data: DataTypes.RepoData,
                requesting_path: Path,
                requesting_configuration: Optional[str],
            ) -> None:
                key = (requesting_data.name, requesting_path, requesting_data.id)

                (
                    self._pending_name_warnings
                        .setdefault(key, {})
                        .setdefault(requesting_configuration, {})
                        [pending_data.source_id]
                ) = textwrap.dedent(
                    """\
                    Specified: {error_on}{dependency_name}{color_off}
                    Previous:  {prev_name}

                        Repo Config:    {prev_config}
                        Repo Id:        {prev_id}
                        Repo Location:  {prev_location}
                    """,
                ).format(
                    dependency_name=dependency_name,
                    prev_name=pending_data.friendly_name,
                    prev_config=pending_data.source_configuration or "<None>",
                    prev_id=pending_data.source_id,
                    prev_location=pending_path,
                    error_on=error_on,
                    color_off=color_off,
                )

            # ----------------------------------------------------------------------
            @contextmanager
            def _SearchContext(
                self,
                encountered_repos: Dict[uuid.UUID, RepositoryMapCalculator.EncounteredRepoData],
                pending_repos: Dict[uuid.UUID, RepositoryMapCalculator.PendingRepoData],
            ) -> Iterator[None]:
                assert len(encountered_repos) == 1, encountered_repos
                this_repo = next(iter(encountered_repos.values()))

                with nested_dm.YieldStream() as stream:
                    stream.write("\nYour system will be scanned for these repositories...\n\n")

                    indented_stream = StreamDecorator(stream, "  ")

                    # ----------------------------------------------------------------------
                    def GetUniqueConfigurations(
                        pending_repo_data: RepositoryMapCalculator.PendingRepoData,
                    ) -> List[str]:
                        configurations: Set[str] = set()

                        for config_dependents in pending_repo_data.dependents.values():
                            for config_repo_data in config_dependents:
                                if config_repo_data.configuration is None:
                                    continue

                                configurations.add(config_repo_data.configuration)

                        return list(
                            sorted(
                                configurations,
                                key=str.lower,
                            ),
                        )

                    # ----------------------------------------------------------------------

                    indented_stream.write(
                        TextwrapEx.CreateTable(
                            ["Repository Name", "Id", "Requesting Configuration(s)"],
                            [
                                [
                                    pending_data.friendly_name,
                                    str(pending_repo_id),
                                    ", ".join(GetUniqueConfigurations(pending_data)),
                                ]
                                for pending_repo_id, pending_data in pending_repos.items()
                            ],
                        ),
                    )

                    if this_repo.has_configurations:
                        indented_stream.write(
                            textwrap.dedent(
                                """\


                                Based on these configurations:

                                """,
                            ),
                        )

                        StreamDecorator(indented_stream, "    ").write(
                            TextwrapEx.CreateTable(
                                ["Configuration", "Description"],
                                [
                                    [
                                        config_name or "<None>",
                                        config_data.description,
                                    ]
                                    for config_name, config_data in this_repo.configurations.items()
                                ],
                            ),
                        )

                        if not this_repo.are_configurations_filtered:
                            indented_stream.write(
                                textwrap.dedent(
                                    """\


                                    To operate on specific configurations, specify the name of the configuration(s)
                                    on the command line:

                                        --configuration <configuration_name>
                                    """,
                                ),
                            )

                    stream.write("\n\n")

                self._OutputStatus(0, 0, 0, 0, None)

                yield

                dm.result = 0 if not pending_repos else -1

                if (
                    self._invalid_module_warnings
                    or self._encountered_name_warnings
                    or self._pending_name_warnings
                ):
                    if self._invalid_module_warnings:
                        nested_dm.WriteWarning(
                            textwrap.dedent(
                                """\
                                The following repositories contained errors. These errors will prevent the repositories from
                                from being discovered as dependencies.

                                {}

                                """,
                            ).format(
                                TextwrapEx.Indent(
                                    "\n".join(
                                        textwrap.dedent(
                                            """\
                                            - {}
                                            {}
                                            """,
                                        ).format(
                                            str(module_path / Constants.SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME),
                                            TextwrapEx.Indent(module_error, 4),
                                        )
                                        for module_path, module_error in self._invalid_module_warnings.items()
                                    ),
                                    4,
                                ),
                            ),
                        )

                    if self._encountered_name_warnings:
                        nested_dm.WriteWarning(
                            textwrap.dedent(
                                """\
                                The following repositories specify dependency names that are different from the actual names.
                                While this isn't something that prevents repository discovery from working when all repositories
                                are on the system, it does add confusion when they are not and enlistment is required.

                                These names should be reconciled.

                                {}

                                """,
                            ).format(
                                "\n".join(
                                    textwrap.dedent(
                                        """\
                                        - {name} <{id}> [{location}]
                                        {data}
                                        """,
                                    ).format(
                                        name=repo_name,
                                        id=repo_id,
                                        location=str(repo_root),
                                        data=TextwrapEx.Indent(
                                            "".join(
                                                textwrap.dedent(
                                                    """\
                                                    {config_name}
                                                    {items}
                                                    """,
                                                ).format(
                                                    config_name=config_name,
                                                    items="\n".join(
                                                        TextwrapEx.Indent(item, 4) for item in items.values()
                                                    ),
                                                )
                                                for config_name, items in repo_data.items()
                                            ),
                                            4,
                                        ).rstrip(),
                                    )
                                    for (repo_name, repo_root, repo_id), repo_data in self._encountered_name_warnings.items()
                                ),
                            ),
                        )

                    if self._pending_name_warnings:
                        nested_dm.WriteWarning(
                            textwrap.dedent(
                                """\
                                The following repositories specify dependency names that are different from what was specified by
                                other repositories with the same dependency. While this isn't something that prevents repository
                                discovery from working when all repositories are on the system, it does add confusion when they are
                                not and enlistment is required.

                                These names should be reconciled.

                                {}

                                """,
                            ).format(
                                "\n".join(
                                    textwrap.dedent(
                                        """\
                                        - {name} <{id}> [{location}]
                                        {data}
                                        """,
                                    ).format(
                                        name=repo_name,
                                        id=repo_id,
                                        location=str(repo_root),
                                        data=TextwrapEx.Indent(
                                            "".join(
                                                textwrap.dedent(
                                                    """\
                                                    {config_name}
                                                    {items}
                                                    """,
                                                ).format(
                                                    config_name=config_name,
                                                    items="\n".join(
                                                        TextwrapEx.Indent(item, 4) for item in items.values()
                                                    ),
                                                )
                                                for config_name, items in repo_data.items()
                                            ),
                                            4,
                                        ).rstrip(),
                                    )
                                    for (repo_name, repo_root, repo_id), repo_data in self._pending_name_warnings.items()
                                ),
                            ),
                        )

            # ----------------------------------------------------------------------
            def _OutputStatus(
                self,
                directories_searched: int,
                directories_pending: int,
                repositories_found: int,
                repositories_pending: int,
                current_path: Optional[Path],
            ) -> None:
                nested_dm.WriteStatus(
                    textwrap.dedent(
                        """\
                        Directories searched:   {}
                        Directories pending:    {}
                        Repositories found:     {}
                        Repositories pending:   {}
                        Searching:              {}
                        """,
                    ).format(
                        directories_searched,
                        directories_pending,
                        repositories_found,
                        repositories_pending,
                        current_path or "<None>",
                    ).rstrip(),
                )

        # ----------------------------------------------------------------------

        calculator = InternalRepositoryMapCalculator(
            repository_root,
            search_depth,
            max_num_searches,
            required_ancestor_dirs or None,
            recurse=False,
            explicit_configurations=configurations or None,
            additional_search_dirs=required_ancestor_dirs or None,
        )

        nested_dm.PreserveStatus()
        nested_dm.WriteLine("\n\n")

        calculator.Filter()

        if calculator.pending_repos:
            # ----------------------------------------------------------------------
            def GetCloneUri(
                value: Configuration.Dependency.CLONE_URI_TYPE,
            ) -> str:
                if value is None:
                    return "Unknown Clone Uri"
                elif isinstance(value, str):
                    return value
                elif callable(value):
                    return value("git")
                else:
                    assert False, value  # pragma: no cover

            # ----------------------------------------------------------------------

            nested_dm.WriteError(
                textwrap.dedent(
                    """\
                    {num_pending} {was_plural} not found.

                    {repos}

                    If these repositories are already on your system, consider modifying the default
                    values for these search parameters to increase the scope of the search. The default
                    values attempt to strike a balance between search speed and accuracy, but they
                    may not be ideal for the directory structure of your system.

                      --max-num-searches <int>        # Current value is: {max_num_searches}

                          Limits the total number of searches performed.

                      --search-depth <int>            # Current value is: {search_depth}

                          Limit searches to N path-levels deep.

                      --required-ancestor-dir <path>  # Current value is: {required_ancestor_dirs}

                          Ensures that only the children of these paths are included in the search space.

                    """,
                ).format(
                    num_pending=inflect.no("repository", len(calculator.pending_repos)),
                    was_plural=inflect.plural_verb("was", len(calculator.pending_repos)),
                    repos="\n".join(
                        "  - {} <{}> [{}]".format(
                            pending_repo.friendly_name,
                            pending_repo.repository_id,
                            GetCloneUri(pending_repo.clone_uri),
                        )
                        for pending_repo in calculator.pending_repos.values()
                    ),
                    max_num_searches=max_num_searches,
                    search_depth=search_depth,
                    required_ancestor_dirs="None" if not required_ancestor_dirs else ", ".join(
                        '"{}"'.format(required_ancestor_dir)
                        for required_ancestor_dir in required_ancestor_dirs
                    ),
                ),
            )

            return

        all_repos = list(calculator.EnumDependencyOrder(repository_root))

        # Display the output
        with nested_dm.YieldStream() as stream:
            if len(calculator.encountered_repos) == 1:
                status_text = "1 repository was found at this location:"
            else:
                status_text = "{} were found at these locations:".format(
                    inflect.no("repository", len(calculator.encountered_repos)),
                )

            stream.write("{}\n\n".format(status_text))

            # ----------------------------------------------------------------------
            def DecorateRow(
                row_index: int,  # pylint: disable=unused-argument
                row: List[str],
            ) -> List[str]:
                row[-1] = "{}{}{}".format(highlight_on, row[-1], color_off)

                return row

            # ----------------------------------------------------------------------

            StreamDecorator(stream, "    ").write(
                TextwrapEx.CreateTable(
                    ["Repository Name", "Id", "Location"],
                    [
                        [
                            repo_data.name,
                            str(repo_data.id),
                            str(repo_data.root),
                        ]
                        for repo_data in all_repos
                    ],
                    decorate_values_func=DecorateRow,
                    decorate_headers=True,
                ),
            )

            stream.write("\n\n")

    # Create the dependencies map and fingerprints
    repo_data = all_repos[-1]

    dependencies: Dict[uuid.UUID, Path] = {}
    fingerprints: Dict[Optional[str], Dict[Path, str]] = {}

    for configuration_name, configured_repos in repo_data.dependencies.items():
        for configured_repo_data in configured_repos:
            if configured_repo_data.id not in dependencies:
                dependencies[configured_repo_data.id] = calculator.encountered_repos[configured_repo_data.id].root

        fingerprints[configuration_name] = Utilities.CalculateFingerprint(
            [repo_data.root, ] + [
                calculator.encountered_repos[configured_repo.id].root for configured_repo in configured_repos
            ],
        )

    # Find the foundation repository (we will only find this if the repo has a direct dependency on it)
    foundation_repo = None
    foundation_repo_id = uuid.UUID("DD6FCD30-B043-4058-B0D5-A6C8BC0374F4")

    for repo in all_repos:
        if repo.id == foundation_repo_id:
            foundation_repo = repo
            break

    foundation_repo_root = foundation_repo.root if foundation_repo else Utilities.GetFoundationRepositoryRoot()

    # Update the environment so this value is used by the other activities
    os.environ[Constants.DE_FOUNDATION_ROOT_NAME] = str(foundation_repo_root)

    # Create the bootstrap data
    EnvironmentBootstrap(
        foundation_repo_root,
        repo_data.configurations,
        fingerprints,
        dependencies,
        is_mixin_repo=repo_data.is_mixin_repository,
        is_configurable=repo_data.has_configurations,
    ).Save(
        repository_root,
    )


# ----------------------------------------------------------------------
def _SetupPython(
    dm: DoneManager,
    customization_mod: types.ModuleType,    # pylint: disable=unused-argument
    repository_root: Path,                  # pylint: disable=unused-argument
    configurations: Optional[List[str]],    # pylint: disable=unused-argument
    force: bool,
    interactive: Optional[bool],            # pylint: disable=unused-argument
) -> Optional[List[Commands.Command]]:
    return PythonSetupActivity().CreateCommands(dm, force=force)


# ----------------------------------------------------------------------
# Update the comments in ../Constants.py if this method name changes
def _SetupCustom(
    dm: DoneManager,                        # pylint: disable=unused-argument
    customization_mod: types.ModuleType,
    repository_root: Path,                  # pylint: disable=unused-argument
    configurations: Optional[List[str]],
    interactive: Optional[bool],
    force: bool,
) -> Optional[List[Commands.Command]]:
    custom_func = getattr(customization_mod, Constants.SETUP_ENVIRONMENT_ACTIONS_METHOD_NAME, None)
    if custom_func is None:
        return None

    return CreateInvocationWrapper(custom_func)(
        {
            "dm": dm,
            "explicit_configurations": configurations,
            "force": force,
            "interactive": interactive,
        },
    )


# ----------------------------------------------------------------------
def _SetupActivateScripts(
    dm: DoneManager,                        # pylint: disable=unused-argument
    customization_mod: types.ModuleType,    # pylint: disable=unused-argument
    repository_root: Path,
    configurations: Optional[List[str]],    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
    interactive: Optional[bool],            # pylint: disable=unused-argument
) -> None:
    environment_name = os.getenv(Constants.DE_ENVIRONMENT_NAME)
    assert environment_name is not None

    # Activate commands
    activate_script_name = Path("{}{}".format(Constants.ACTIVATE_ENVIRONMENT_NAME, CurrentShell.script_extensions[0]))

    implementation_script = Path(__file__).parent / activate_script_name
    assert implementation_script.is_file(), implementation_script

    commands: List[Commands.Command] = [
        Commands.EchoOff(),
        Commands.Set(Constants.DE_ENVIRONMENT_NAME, environment_name),
        Commands.PushDirectory(None),
        Commands.Call(
            '"{}" {}'.format(implementation_script, CurrentShell.all_arguments_script_variable),
            exit_on_error=False,
        ),
        Commands.PersistError("_DEVELOPMENT_ENVIRONMENT_ACTIVATE_ERROR"),
        Commands.PopDirectory(),
        Commands.ExitOnError("_DEVELOPMENT_ENVIRONMENT_ACTIVATE_ERROR"),
    ]

    # Write the file
    activate_filename = repository_root / "{}{}{}".format(
        activate_script_name.stem,
        ".{}".format(environment_name) if environment_name != Constants.DEFAULT_ENVIRONMENT_NAME else "",
        activate_script_name.suffix,
    )

    with activate_filename.open("w") as f:
        f.write(CurrentShell.GenerateCommands(commands))

    CurrentShell.MakeFileExecutable(activate_filename)
    CurrentShell.UpdateOwnership(activate_filename)

    # Deactivate
    deactivate_script_name = Path("{}{}".format(Constants.DEACTIVATE_ENVIRONMENT_NAME, CurrentShell.script_extensions[0]))

    implementation_script = Path(__file__).parent / deactivate_script_name
    assert implementation_script.is_file(), implementation_script

    commands: List[Commands.Command] = [
        Commands.EchoOff(),
        Commands.PushDirectory(None),
        Commands.Call(
            '"{}" {}'.format(implementation_script, CurrentShell.all_arguments_script_variable),
            exit_on_error=False,
        ),
        Commands.PersistError("_DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR"),
        Commands.PopDirectory(),
        Commands.ExitOnError("_DEVELOPMENT_ENVIRONMENT_DEACTIVATE_ERROR"),
    ]

    # Write the file
    deactivate_filename = repository_root / "{}{}{}".format(
        deactivate_script_name.stem,
        ".{}".format(environment_name) if environment_name != Constants.DEFAULT_ENVIRONMENT_NAME else "",
        deactivate_script_name.suffix,
    )

    with deactivate_filename.open("w") as f:
        f.write(CurrentShell.GenerateCommands(commands))

    CurrentShell.MakeFileExecutable(deactivate_filename)
    CurrentShell.UpdateOwnership(deactivate_filename)


# ----------------------------------------------------------------------
def _SetupScmHooks(
    dm: DoneManager,                        # pylint: disable=unused-argument
    customization_mod: types.ModuleType,    # pylint: disable=unused-argument
    repository_root: Path,
    configurations: Optional[List[str]],    # pylint: disable=unused-argument
    force: bool,                            # pylint: disable=unused-argument
    interactive: Optional[bool],            # pylint: disable=unused-argument
) -> None:

    if dm.is_verbose:
        dm.WriteLine("")

    scm: Optional[SourceControlManager] = None
    working_directory: Optional[Path] = None

    with dm.VerboseNested("Detecting SCM...") as detect_dm:
        for potential_scm in ALL_SCMS:
            for working_directory_name in (potential_scm.working_directories or []):
                potential_working_directory = repository_root / working_directory_name

                if potential_working_directory.is_dir():
                    scm = potential_scm
                    working_directory = potential_working_directory

                    break

            if scm is not None:
                break

        if scm is None:
            return

        detect_dm.WriteLine("SCM is '{}'.".format(scm.name))

    assert scm is not None
    assert working_directory is not None

    # ----------------------------------------------------------------------
    def Mercurial() -> None:
        pass # raise NotImplementedError("TODO: Mercurial hooks are not implemented yet")

    # ----------------------------------------------------------------------
    def Git() -> None:
        with dm.VerboseNested("Creating 'Git' hooks...") as verbose_dm:
            foundation_root = os.getenv(Constants.DE_FOUNDATION_ROOT_NAME)
            if foundation_root:
                foundation_root = Path(foundation_root)
            else:
                foundation_root = repository_root

            assert foundation_root.is_dir(), foundation_root

            python_activate_name = (
                foundation_root
                / Constants.GENERATED_DIRECTORY_NAME
                / CurrentShell.family_name
                / Types.EnsureValid(os.getenv(Constants.DE_ENVIRONMENT_NAME))
                / "python310"
                / "Python"
            )

            if CurrentShell.family_name == "Windows":
                python_activate_name /= "Scripts"
            else:
                python_activate_name /= "bin"

            python_activate_name /= "activate"
            assert python_activate_name.is_file() or foundation_root == repository_root, python_activate_name

            # Note that git uses bash on Windows, so the generated scripts are the same on all operating systems
            for script_name in [
                "prepare-commit-msg",
                "commit-msg",
                # TODO (This functionality is not implemented yet; See ./Hooks/GitHooks.py): "pre-push",
                # TODO (This functionality is not implemented yet; See ./Hooks/GitHooks.py): "pre-receive",
            ]:
                dest_filename = working_directory / "hooks" / script_name

                # Create a backup
                if dest_filename.is_file():
                    backup_filename = dest_filename.parent / "{}.bak".format(dest_filename.name)

                    if not backup_filename.is_file():
                        with verbose_dm.Nested("Creating backup of '{}'...".format(dest_filename)):
                            shutil.copyfile(dest_filename, backup_filename)

                with verbose_dm.Nested("Writing '{}'...".format(script_name)):
                    with dest_filename.open(
                        "w",
                        newline="\n",
                    ) as f:
                        f.write(
                            textwrap.dedent(
                                """\
                                #!/bin/bash

                                # Auto
                                name=`git config --global --get user.name`
                                email=`git config --global --get user.email`

                                cwd=`pwd`

                                VIRTUAL_ENV_DISABLE_PROMPT=1 . "{activate}"

                                pushd "{foundation_root}" > /dev/null

                                if [[ -z ${{GIT_HOOKS_VERBOSE}} ]]; then
                                    verbose_flag=""
                                else
                                    verbose_flag=" --verbose"
                                fi

                                if [[ -z ${{GIT_HOOKS_DEBUG}} ]]; then
                                    debug_flag=""
                                else
                                    debug_flag=" --debug"
                                fi

                                PYTHONIOENCODING=UTF-8 python -m RepositoryBootstrap.Impl.Hooks.GitHooks {function} "${{cwd}}" "${{name}}" "${{email}}" "$@" ${{verbose_flag}} ${{debug_flag}}
                                error=$?

                                popd > /dev/null

                                exit ${{error}}
                                """,
                            ).format(
                                activate=python_activate_name.as_posix(),
                                foundation_root=foundation_root.as_posix(),
                                function=script_name.replace("-", "_"),

                            ),
                        )

                CurrentShell.MakeFileExecutable(dest_filename)

    # ----------------------------------------------------------------------

    if scm.name == "Git":
        Git()
    elif scm.name == "Mercurial":
        Mercurial()
    else:
        assert False, scm.name  # pragma: no cover


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
