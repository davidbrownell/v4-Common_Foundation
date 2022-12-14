# ----------------------------------------------------------------------
# |
# |  Enlist.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-24 16:58:26
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
import itertools
import multiprocessing
import textwrap
import traceback
import uuid

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, TypeVar, Union

import inflect as inflect_mod
import typer

from click.exceptions import UsageError
from rich import print as rich_print
from rich.tree import Tree
from rich.progress import Progress, TaskID
from typer.core import TyperGroup

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.SourceControlManager import DistributedRepository, SourceControlManager
from Common_Foundation.SourceControlManagers import UpdateMergeArgs
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from . import RepositoryMapCalculator

from .. import Constants


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
Scm                                         = Types.StringsToEnum("Scm", (scm.name for scm in ALL_SCMS))


# ----------------------------------------------------------------------
@app.command("Enlist", no_args_is_help=True)
def Enlist(
    source_repository: Path=typer.Argument(..., help="Path to a repository with dependencies that must be enlisted."),
    all_repositories_root: Path=typer.Argument(..., help="Root path to a directory where all dependencies are enlisted; this path may be shared by multiple repositories, each with their own set of dependencies."),
    scm_name: Scm=typer.Option(next(iter(Scm)).value, case_sensitive=False, help="Name of the SCM to use for enlistment."),  # type: ignore
    branch: Optional[str]=typer.Option(None, help="Name of branch to enlist in; the default branch associated with the SCM will be used if a branch is not provided."),
    branch_overrides: Optional[str]=typer.Option(None, "--branch-overrides", help="Concatenated list of repositories and branches that should be applied when enlisting; format is `<repo_name1>:<branch_name1>;<repo_name2>:<branch_name2>`."),
    configurations: Optional[List[str]]=typer.Option(None, "--configuration", help="Configurations to determine dependencies for enlistment; all configurations will be used if explicit values are not provided."),
    traverse_all: bool=typer.Option(False, "--traverse-all", help="Traverse all dependencies, not just those that relate to the source repository; enable this flag if the all repositories root is shared by multiple repositories (not just this one)."),
    search_depth: int=typer.Option(6, min=1, help="Limit searches to N path-levels deep."),
    max_num_searches: Optional[int]=typer.Option(None, min=1, help="Limit the number of directories searched when looking for dependencies; this value can be used to reduce the overall time it takes to search for dependencies that ultimately can't be found."),
    working_directory: Path=typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The working directory used to resolve path arguments."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
):
    """Enlists in a repository and its dependencies."""

    # This script needs to be invoked as a module ("python -m RepositoryBootstrap.Impl.Enlist") to
    # ensure that relative imports work as expected. However, it is exposed within the repository
    # as a script (../../../Scripts/Enlist.py). The explicit working directory argument is provided
    # to ensure that relative paths on the command line work as expected even after that script
    # changes the working directory to ensure that relative imports in the Python script work. This
    # is why Path-based arguments (other than working_directory) are provided as Paths without
    # validation.
    source_repository = _InitalizeSourceRepository(working_directory, source_repository)
    all_repositories_root = _InitializeAllRepositoriesRoot(working_directory, all_repositories_root)

    # TODO: Save the value of all_repositories_root after successful enlistment.
    #       Generate a warning if someone runs enlistment again with a different value.
    #       Save value needs to be specific to repo, OS, environment name, etc.

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        _EnlistImpl(
            dm,
            source_repository,
            all_repositories_root,
            scm_name.value,
            branch,
            branch_overrides,
            configurations,
            traverse_all=traverse_all,
            search_depth=search_depth,
            max_num_searches=max_num_searches,
        )


# ----------------------------------------------------------------------
@app.command("Setup", no_args_is_help=True)
def Setup(
    source_repository: Path=typer.Argument(..., help="Path to a repository with dependencies that should be setup."),
    all_repositories_root: Path=typer.Argument(..., help="Root path to a directory where all dependencies are enlisted; this path may be shared by multiple repositories, each with their own set of dependencies."),
    configurations: Optional[List[str]]=typer.Option(None, "--configuration", help="Configurations to determine dependencies for setup; all configurations will be used if explicit values are not provided."),
    traverse_all: bool=typer.Option(False, "--traverse-all", help="Traverse all dependencies, not just those that relate to the source repository; enable this flag if the all repositories root is shared by multiple repositories (not just this one)."),
    search_depth: int=typer.Option(6, min=1, help="Limit searches to N path-levels deep."),
    max_num_searches: Optional[int]=typer.Option(None, min=1, help="Limit the number of directories searched when looking for dependencies; this value can be used to reduce the overall time it takes to search for dependencies that ultimately can't be found."),
    working_directory: Path=typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The working directory used to resolve path arguments."),
    no_hooks: bool=typer.Option(False, "--no-hooks", help="Do not setup SCM hooks."),
    force: bool=typer.Option(False, "--force", help="Force the setup of environment data; if not specified."),
    interactive: Optional[bool]=typer.Option(None, help="Force/Prevent an interactive experience (if any)."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
):
    """Invokes Setup for a repository and its dependencies."""

    # See the notes in Enlist as to why the source_repository, all_repositories_root, and working_directory
    # parameters are unusual.
    source_repository = _InitalizeSourceRepository(working_directory, source_repository)
    all_repositories_root = _InitializeAllRepositoriesRoot(working_directory, all_repositories_root)

    configurations = Types.EnsurePopulatedList(configurations)

    if configurations and traverse_all:
        raise UsageError("Explicit configurations and traverse all cannot be used together.")

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        _SetupImpl(
            dm,
            source_repository,
            all_repositories_root,
            configurations,
            traverse_all=traverse_all,
            search_depth=search_depth,
            max_num_searches=max_num_searches,
            no_hooks=no_hooks,
            force=force,
            interactive=interactive,
        )


# ----------------------------------------------------------------------
@app.command("EnlistAndSetup", no_args_is_help=True)
def EnlistAndSetup(
    source_repository: Path=typer.Argument(..., help="Path to a repository with dependencies that must be enlisted."),
    all_repositories_root: Path=typer.Argument(..., help="Root path to a directory where all dependencies are enlisted; this path may be shared by multiple repositories, each with their own set of dependencies."),
    scm_name: Scm=typer.Option(next(iter(Scm)).value, case_sensitive=False, help="Name of the SCM to use for enlistment."),  # type: ignore
    branch: Optional[str]=typer.Option(None, help="Name of branch to enlist in; the default branch associated with the SCM will be used if a branch is not provided."),
    branch_overrides: Optional[str]=typer.Option(None, "--branch-overrides", help="Concatenated list of repositories and branches that should be applied when enlisting; format is `<repo_name1>:<branch_name1>;<repo_name2>:<branch_name2>`."),
    configurations: Optional[List[str]]=typer.Option(None, "--configuration", help="Configurations to determine dependencies for enlistment; all configurations will be used if explicit values are not provided."),
    traverse_all: bool=typer.Option(False, "--traverse-all", help="Traverse all dependencies, not just those that relate to the source repository; enable this flag if the all repositories root is shared by multiple repositories (not just this one)."),
    search_depth: int=typer.Option(6, min=1, help="Limit searches to N path-levels deep."),
    max_num_searches: Optional[int]=typer.Option(None, min=1, help="Limit the number of directories searched when looking for dependencies; this value can be used to reduce the overall time it takes to search for dependencies that ultimately can't be found."),
    working_directory: Path=typer.Option(Path.cwd(), exists=True, file_okay=False, resolve_path=True, help="The working directory used to resolve path arguments."),
    no_hooks: bool=typer.Option(False, "--no-hooks", help="Do not setup SCM hooks."),
    force: bool=typer.Option(False, "--force", help="Force the setup of environment data; if not specified."),
    interactive: Optional[bool]=typer.Option(None, help="Force/Prevent an interactive experience (if any)."),
    verbose: bool=typer.Option(False, "--verbose", help= "Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
):
    """Enlists in a repository and its dependencies and then invokes Setup on each of them."""

    # See the notes in Enlist as to why the source_repository, all_repositories_root, and working_directory
    # parameters are unusual.
    source_repository = _InitalizeSourceRepository(working_directory, source_repository)
    all_repositories_root = _InitializeAllRepositoriesRoot(working_directory, all_repositories_root)

    configurations = Types.EnsurePopulatedList(configurations)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        with dm.Nested(
            "Enlisting...",
            suffix="\n",
        ) as enlist_dm:
            _EnlistImpl(
                enlist_dm,
                source_repository,
                all_repositories_root,
                scm_name.value,
                branch,
                branch_overrides,
                configurations,
                traverse_all=traverse_all,
                search_depth=search_depth,
                max_num_searches=max_num_searches,
            )

            if enlist_dm.result != 0:
                return

        with dm.Nested(
            "Setting up...",
            suffix="\n",
        ) as setup_dm:
            _SetupImpl(
                setup_dm,
                source_repository,
                all_repositories_root,
                configurations,
                traverse_all=traverse_all,
                search_depth=search_depth,
                max_num_searches=max_num_searches,
                no_hooks=no_hooks,
                force=force,
                interactive=interactive,
            )

            if setup_dm.result != 0:
                return


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _InitalizeSourceRepository(
    working_directory: Path,
    source_repository: Path,
) -> Path:
    source_repository = (working_directory / source_repository).resolve()
    if not source_repository.is_dir():
        raise typer.BadParameter("Directory '{}' does not exist.".format(source_repository))

    return source_repository


# ----------------------------------------------------------------------
def _InitializeAllRepositoriesRoot(
    working_directory: Path,
    all_repositories_root: Path,
) -> Path:
    all_repositories_root = (working_directory / all_repositories_root).resolve()

    if all_repositories_root.is_file():
        raise typer.BadParameter("'{}' is a file.".format(all_repositories_root))

    if not all_repositories_root.is_dir():
        raise typer.BadParameter("Directory '{}' does not exist.".format(all_repositories_root))

    return all_repositories_root


# ----------------------------------------------------------------------
def _EnlistImpl(
    dm: DoneManager,
    source_repository: Path,
    all_repositories_root: Path,
    scm_name: str,
    branch: Optional[str],
    branch_overrides: Optional[str],
    configurations: Optional[List[str]],
    *,
    traverse_all: bool,
    search_depth: int,
    max_num_searches: Optional[int],
) -> None:
    scm = next(scm for scm in ALL_SCMS if scm.name == scm_name)
    configurations = Types.EnsurePopulatedList(configurations)

    if PathEx.IsDescendant(all_repositories_root, source_repository):
        raise typer.BadParameter("The path for all repositories cannot be a descendant of the path for the source repository.")

    # ----------------------------------------------------------------------
    def CalculateBranchInfo() -> Tuple[str, Dict[str, str]]:
        branch_lookup: Dict[str, str] = {}

        for branch_override_value in (branch_overrides or "").split(";"):
            branch_override_value = branch_override_value.strip()
            if not branch_override_value:
                continue

            branch_override_parts = branch_override_value.split(":")

            if len(branch_override_parts) != 2:
                raise typer.BadParameter("'{}' is not a valid branch override value.".format(branch_override_value))

            repo_name, override_branch = branch_override_parts

            if repo_name in branch_lookup:
                raise typer.BadParameter("The repository '{}' has already been defined.".format(repo_name))

            branch_lookup[repo_name] = override_branch

        return (
            branch or scm.release_branch_name,
            branch_lookup,
        )

    # ----------------------------------------------------------------------

    branch, branch_lookup = CalculateBranchInfo()

    all_repositories_root.mkdir(parents=True, exist_ok=True)

    for iteration in itertools.count(1):
        with dm.Nested(
            "Iteration {}...".format(iteration),
            display_exceptions=False,
            suffix="\n\n",
        ) as iteration_dm:
            # Calculate the map
            calculator = _CreateRepositoryMapCalculator(
                iteration_dm,
                source_repository,
                all_repositories_root,
                search_depth,
                max_num_searches,
                required_ancestor_dirs=[
                    source_repository,
                    all_repositories_root,
                ],
                explicit_configurations=configurations,
            )

            # Print the tree
            root: Optional[Tree] = None
            tree_stack: List[
                Tuple[
                    Tree,
                    Optional[RepositoryMapCalculator.EncounteredRepoData],
                ],
            ] = []

            # ----------------------------------------------------------------------
            @contextmanager
            def OnWalkItem(
                item: Union[
                    RepositoryMapCalculator.EncounteredRepoData,
                    RepositoryMapCalculator.PendingRepoData,
                    Optional[str],
                ],
                is_being_used: bool,
            ) -> Iterator[None]:
                if isinstance(item, RepositoryMapCalculator.EncounteredRepoData):
                    nonlocal root
                    item_text = r"{}{} <{}> \[{}]".format(
                        "" if is_being_used else "Not Used: ",
                        item.name,
                        str(item.id),
                        str(item.root),
                    )

                    if not tree_stack:
                        assert root is None

                        root = Tree(item_text)
                        tree_item = root
                    else:
                        assert root is not None
                        tree_item = tree_stack[-1][0].add(item_text)

                    tree_stack.append((tree_item, item))
                    with ExitStack(tree_stack.pop):
                        yield

                    return

                assert tree_stack

                if isinstance(item, RepositoryMapCalculator.PendingRepoData):
                    tree_stack[-1][0].add(
                        r"{}{} <{}> \[{}]".format(
                            item.friendly_name,
                            " {}".format(item.configuration) if item.configuration else "",
                            str(item.repository_id),
                            _GetCloneUri(item, scm),
                        ),
                    )

                    yield

                elif isinstance(item, Optional[str]):
                    parent_data = tree_stack[-1][1]
                    assert isinstance(parent_data, RepositoryMapCalculator.EncounteredRepoData), parent_data

                    stack_cleanup_func = lambda: None

                    if parent_data.has_configurations:
                        item = item or "<None>"

                        if not is_being_used:
                            tree_stack[-1][0].add("Not Used: {}".format(item))
                        else:
                            tree_stack.append(
                                (
                                    tree_stack[-1][0].add(item),
                                    None,
                                ),
                            )

                            stack_cleanup_func = tree_stack.pop

                    with ExitStack(stack_cleanup_func):
                        yield

                else:
                    assert False, item  # pragma: no cover

            # ----------------------------------------------------------------------

            calculator.Walk(
                source_repository,
                OnWalkItem,
                traverse_all=traverse_all,
            )

            assert root is not None
            assert not tree_stack, tree_stack

            with iteration_dm.YieldStream() as stream:
                stream.write("\n")

                rich_print(
                    root,
                    file=stream,  # type: ignore
                )

                stream.write("\n")

            # Update encountered repositories

            # ----------------------------------------------------------------------
            def GetUpdateName(
                item: Tuple[uuid.UUID, RepositoryMapCalculator.EncounteredRepoData],
            ) -> str:
                return str(item[1].root)

            # ----------------------------------------------------------------------
            def OnUpdateItem(
                item: Tuple[uuid.UUID, RepositoryMapCalculator.EncounteredRepoData],
            ) -> str:
                data = item[1]

                if data.root == source_repository:
                    return "Skipping the source repository."

                this_scm = next(
                    (
                        scm
                        for scm in ALL_SCMS
                        if scm.IsAvailable() and scm.IsActive(data.root)
                    ),
                    None,
                )

                if this_scm is None:
                    raise Exception("No SCM was found for '{}'.".format(str(data.root)))

                repo = this_scm.Open(data.root)

                if repo.HasWorkingChanges() or repo.HasUntrackedWorkingChanges():
                    raise Exception(
                        "This repository has working changes and will not be processed by '{}'.".format(
                            this_scm.name,
                        ),
                    )

                this_branch = branch_lookup.get(data.name, branch)

                output: List[str] = []

                if isinstance(repo, DistributedRepository):
                    result = repo.Pull(this_branch)
                    result.RaiseOnError()

                    output.append(result.output)

                update_arg = None

                if this_branch is not None:
                    update_arg = UpdateMergeArgs.Branch(this_branch)

                result = repo.Update(update_arg)
                result.RaiseOnError()

                output.append(result.output)

                return "\n".join(output).rstrip()

            # ----------------------------------------------------------------------

            _ProcessItems(
                iteration_dm,
                "Updating {}...".format(inflect.no("repository", len(calculator.encountered_repos))),
                list(calculator.encountered_repos.items()),
                GetUpdateName,
                OnUpdateItem,
            )

            iteration_dm.ExitOnError()

            if not calculator.pending_repos:
                break

            # Enlist in pending repos

            # ----------------------------------------------------------------------
            def GetPendingName(
                item: Tuple[uuid.UUID, RepositoryMapCalculator.PendingRepoData],
            ) -> str:
                return _GetCloneUri(item[1], scm)

            # ----------------------------------------------------------------------
            def OnPendingItem(
                item: Tuple[uuid.UUID, RepositoryMapCalculator.PendingRepoData],
            ) -> None:
                data = item[1]

                if data.clone_uri is None:
                    assert calculator is not None

                    referencing_repo = calculator.encountered_repos[data.source_id]

                    raise Exception(
                        textwrap.dedent(
                            """\
                            The repo '{} <{}>' does not have a clone uri and cannot be processed.

                                Referenced by: {}{} <{}> [{}]
                            """,
                        ).format(
                            str(data.repository_id),
                            data.friendly_name,
                            referencing_repo.name,
                            " ({})".format(data.source_configuration) if data.source_configuration else "",
                            str(referencing_repo.id),
                            str(referencing_repo.root),
                        ),
                    )

                clone_uri = _GetCloneUri(data, scm)
                this_output_dir = all_repositories_root.joinpath(*data.friendly_name.split("_"))

                scm.Clone(clone_uri, this_output_dir)

            # ----------------------------------------------------------------------

            _ProcessItems(
                iteration_dm,
                "Cloning {}...".format(inflect.no("repository", len(calculator.pending_repos))),
                list(calculator.pending_repos.items()),
                GetPendingName,
                OnPendingItem,
            )

            if iteration_dm.result != 0:
                break


# ----------------------------------------------------------------------
def _SetupImpl(
    dm: DoneManager,
    source_repository: Path,
    all_repositories_root: Path,
    configurations: Optional[List[str]],
    *,
    traverse_all: bool,
    search_depth: int,
    max_num_searches: Optional[int],
    no_hooks: bool,
    force: bool,
    interactive: Optional[bool],
) -> None:
    calculator = _CreateRepositoryMapCalculator(
            dm,
            source_repository,
            all_repositories_root,
            search_depth,
            max_num_searches,
            required_ancestor_dirs=[
                source_repository,
                all_repositories_root,
            ],
            explicit_configurations=configurations,
        )

    assert calculator is not None

    if calculator.pending_repos:
        errors: List[str] = []

        for pending_data in calculator.pending_repos.values():
            referencing_repo = calculator.encountered_repos[pending_data.source_id]

            errors.append(
                "- {} <{}>, requested by {}{} <{}> [{}]".format(
                    pending_data.friendly_name,
                    str(pending_data.repository_id),
                    referencing_repo.name,
                    " ({})".format(pending_data.source_configuration),
                    str(referencing_repo.id),
                    str(referencing_repo.root),
                ),
            )

        dm.WriteError(
            textwrap.dedent(
                """\

                Setup cannot continue while required repositories are missing:

                {}

                """,
            ).format("\n".join(errors)),
        )

        dm.ExitOnError()

    # Get the setup commands
    setup_commands: Dict[Path, str] = {}

    with dm.Nested(
        "\nOrganizing repositories....",
        lambda: "{} found".format(inflect.no("repository", len(calculator.encountered_repos))),
        suffix="\n",
    ):
        setup_info: Dict[Path, List[Optional[str]]] = {}
        commands_stack: List[List[Optional[str]]] = []

        # ----------------------------------------------------------------------
        @contextmanager
        def OnWalkItem(
            item: Union[
                RepositoryMapCalculator.EncounteredRepoData,
                RepositoryMapCalculator.PendingRepoData,
                Optional[str],
            ],
            is_being_used: bool,
        ) -> Iterator[None]:
            if isinstance(item, RepositoryMapCalculator.EncounteredRepoData):
                setup_info[item.root] = []

                commands_stack.append(setup_info[item.root])
                with ExitStack(commands_stack.pop):
                    yield

                return

            elif isinstance(item, RepositoryMapCalculator.PendingRepoData):
                assert False, item  # pragma: no cover

            elif isinstance(item, Optional[str]):
                if is_being_used:
                    assert commands_stack
                    commands_stack[-1].append(item)

            else:
                assert False, item  # pragma: no cover

            yield

        # ----------------------------------------------------------------------

        calculator.Walk(
            source_repository,
            OnWalkItem,
            configurations,  # type: ignore
            traverse_all=traverse_all,
        )

        for setup_path, setup_configurations in setup_info.items():
            command_suffixes: List[str] = [
                "--search-depth", str(search_depth),
                "--required-ancestor-dir", str(all_repositories_root),
            ]

            if max_num_searches is not None:
                command_suffixes += [
                    "--max-num-searches", str(max_num_searches),
                ]

            if not traverse_all and setup_configurations:
                command_suffixes += [
                    '--configuration "{}"'.format(configuration)
                    for configuration in setup_configurations
                ]

            if no_hooks:
                command_suffixes.append("--no-hooks")
            if force:
                command_suffixes.append("--force")

            if interactive is True:
                command_suffixes.append("--interactive")
            elif interactive is False:
                command_suffixes.append("--no-interactive")

            if dm.is_verbose:
                command_suffixes.append("--verbose")
            if dm.is_debug:
                command_suffixes.append("--debug")

            setup_commands[setup_path] = '"{}" {}'.format(
                setup_path / "{}{}".format(
                    Constants.SETUP_ENVIRONMENT_NAME,
                    CurrentShell.script_extensions[0],
                ),
                " ".join(command_suffixes),
            )

    # Setup the repositories

    # ----------------------------------------------------------------------
    def GetSetupName(
        item: Tuple[Path, str],
    ) -> str:
        return str(item[0])

    # ----------------------------------------------------------------------
    def OnSetupItem(
        item: Tuple[Path, str],
    ) -> str:
        result = SubprocessEx.Run(item[1])
        result.RaiseOnError()

        return result.output.rstrip()

    # ----------------------------------------------------------------------

    _ProcessItems(
        dm,
        "Setting up {}...".format(inflect.no("repository", len(setup_commands))),
        list(setup_commands.items()),
        GetSetupName,
        OnSetupItem,
    )


# ----------------------------------------------------------------------
def _CreateRepositoryMapCalculator(
    dm: DoneManager,
    source_repository: Path,
    all_repositories_root: Path,
    search_depth: int,
    max_num_searches: Optional[int],
    required_ancestor_dirs: Optional[List[Path]],
    explicit_configurations: Optional[List[str]],
) -> RepositoryMapCalculator.RepositoryMapCalculator:
    calculator: Optional[RepositoryMapCalculator.RepositoryMapCalculator] = None

    with dm.Nested(
        "Searching for dependencies of '{}' in '{}'...".format(
            source_repository,
            all_repositories_root,
        ),
        [
            lambda: None if calculator is None else "{} found".format(inflect.no("repository", len(calculator.encountered_repos))),
            lambda: None if calculator is None else "{} missing".format(inflect.no("repository", len(calculator.pending_repos))),
        ],
        preserve_status=False,
    ) as nested_dm:
        # ----------------------------------------------------------------------
        class InternalRepositoryMapCalculator(RepositoryMapCalculator.RepositoryMapCalculator):
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
            @staticmethod
            def _OnModuleError(*args, **kwargs) -> bool:  # pylint: disable=unused-argument
                # Nothing to do here
                return True

            # ----------------------------------------------------------------------
            @staticmethod
            def _OnDependencyNameMismatch(*args, **kwargs) -> None:  # pylint: disable=unused-argument
                # Nothing to do here
                pass

            # ----------------------------------------------------------------------
            @staticmethod
            def _OnPendingNameMismatch(*args, **kwargs) -> None:  # pylint: disable=unused-argument
                # Nothing to do here
                pass

            # ----------------------------------------------------------------------
            @contextmanager
            def _SearchContext(self, *args, **kwargs) -> Iterator[None]:  # pylint: disable=unused-argument
                self._OutputStatus(0, 0, 0, 0, None)
                yield

            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
            # ----------------------------------------------------------------------
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
                    ),
                )

        # ----------------------------------------------------------------------

        calculator = InternalRepositoryMapCalculator(
            source_repository,
            search_depth,
            max_num_searches,
            required_ancestor_dirs,
            recurse=True,
            explicit_configurations=explicit_configurations,
            additional_search_dirs=[all_repositories_root],
        )

        calculator.Filter()

        return calculator


# ----------------------------------------------------------------------
_ProcessItemsT                              = TypeVar("_ProcessItemsT")

def _ProcessItems(
    dm: DoneManager,
    desc: str,
    items: List[_ProcessItemsT],
    get_name_func: Callable[[_ProcessItemsT], str],
    on_item_func: Callable[[_ProcessItemsT], Any],
) -> None:
    with dm.Nested(
        desc,
        suffix="\n",
    ) as nested_dm:
        names: List[str] = []
        results: List[Optional[Any]] = [None for _ in range(len(items))]
        exceptions: List[Optional[str]] = [None for _ in range(len(items))]

        with nested_dm.YieldStdout() as context:
            context.persist_content = False

            with Progress(
                transient=True,
            ) as progress:
                total_progress_id = progress.add_task(
                    "{}Total Progress".format(context.line_prefix),
                    total=len(items),
                )

                line_prefix = "{}  ".format(context.line_prefix)

                with ThreadPoolExecutor(
                    min(len(items), multiprocessing.cpu_count()),
                ) as executor:
                    # ----------------------------------------------------------------------
                    def Impl(
                        index: int,
                        task_id: TaskID,
                        item: _ProcessItemsT,
                    ) -> None:
                        progress.update(task_id, visible=True)

                        with ExitStack(
                            lambda: progress.update(task_id, completed=True, visible=False),
                            lambda: progress.advance(total_progress_id, 1),
                        ):
                            try:
                                results[index] = on_item_func(item)
                            except Exception as ex:
                                if nested_dm.is_debug:
                                    exceptions[index] = traceback.format_exc()
                                else:
                                    exceptions[index] = str(ex)

                    # ----------------------------------------------------------------------

                    futures = []

                    for index, item in enumerate(items):
                        names.append(get_name_func(item))

                        futures.append(
                            executor.submit(
                                Impl,
                                index,
                                progress.add_task(
                                    "{}{}".format(line_prefix, names[-1]),
                                    total=1,
                                    visible=False,
                                ),
                                item,
                            ),
                        )

                    for future in futures:
                        future.result()

        for name, exception, result in zip(names, exceptions, results):
            if exception is not None:
                nested_dm.WriteError(
                    textwrap.dedent(
                        """\
                        {}
                        {}

                        """,
                    ).format(name, TextwrapEx.Indent(exception, 4)),
                )

            elif nested_dm.is_verbose:
                nested_dm.WriteSuccess(
                    textwrap.dedent(
                        """\
                        {}
                        {}

                        """,
                    ).format(name, TextwrapEx.Indent(str(result), 4)),
                )


# ----------------------------------------------------------------------
def _GetCloneUri(
    data: RepositoryMapCalculator.PendingRepoData,
    scm: SourceControlManager,
) -> str:
    if data.clone_uri is None:
        return "Unknown ({})".format(str(data.repository_id))

    elif isinstance(data.clone_uri, str):
        return data.clone_uri

    elif callable(data.clone_uri):
        return data.clone_uri(scm.name)

    assert False, data.clone_uri  # pragma: no cover


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
