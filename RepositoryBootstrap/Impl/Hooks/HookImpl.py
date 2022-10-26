# ----------------------------------------------------------------------
# |
# |  HookImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 08:45:50
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Common implementation of SCM hook functionality"""

import importlib
import itertools
import json
import os
import sys
import traceback

from collections import namedtuple
from pathlib import Path
from typing import Dict, Generator, List, Optional, Set, Union

from rich import reconfigure, get_console

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx

from RepositoryBootstrap import Constants
from RepositoryBootstrap.DataTypes import CommitInfo, PreIntegrateInfo, PrePushInfo
from RepositoryBootstrap.Impl.ActivationData import ActivationData


# ----------------------------------------------------------------------
# Update rich, as it's default terminal gets confused in this scenario
reconfigure(
    legacy_windows=False,
    # Setting this to True causes '25h' to be printed to the console when the cursor is shown.
    # Dig into the problem in rich if disabling this flag turns out to be a problem here.
    #
    # force_terminal=True,
    width=get_console().width,
)


# ----------------------------------------------------------------------
def Commit(
    dm: DoneManager,
    repository: Repository,
    commit_info: CommitInfo,
) -> None:
    _Impl(dm, repository, commit_info, "OnCommit")


# ----------------------------------------------------------------------
def PrePush(
    dm: DoneManager,
    repository: Repository,
    pre_push_info: PrePushInfo,
) -> None:
    _Impl(dm, repository, pre_push_info, "OnPrePush")


# ----------------------------------------------------------------------
def PreIntegrate(
    dm: DoneManager,
    repository: Repository,
    pre_integrate_info: PreIntegrateInfo,
) -> None:
    _Impl(dm, repository, pre_integrate_info, "OnPreIntegrate")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Impl(
    dm: DoneManager,
    repository: Repository,
    info: Union[CommitInfo, PreIntegrateInfo, PrePushInfo],
    function_name: str,
) -> None:
    for customization in _EnumerateScmCustomizations(dm, repository.repo_root):
        func = getattr(customization.mod, function_name)
        if func is None:
            continue

        result = func(
            customization.dm,
            customization.repo_data.configuration,
            repository,
            info,
            first_configuration_in_repo=customization.is_first_configuration_in_repo,
        )

        if result is False:
            break


# ----------------------------------------------------------------------
_EnumerateScmCustomizationsType             = namedtuple(
    "_EnumerateScmCustomizationsType",
    [
        "dm",
        "repo_data",
        "is_first_configuration_in_repo",
        "mod",
    ],
)

def _EnumerateScmCustomizations(
    dm: DoneManager,
    repo_root: Path,
) -> Generator[_EnumerateScmCustomizationsType, None, None]:
    activation_data_items: List[ActivationData] = []

    with dm.Nested(
        "Loading repository information for '{}'...".format(repo_root),
        suffix="\n",
    ) as activation_dm:
        # Get the configurations to process
        configurations: List[Optional[str]] = []

        # Use the environment's configuration if we are attempting to modify the repo associated
        # with the repository that is activated in the current environment.
        current_repo_root = os.getenv(Constants.DE_REPO_ROOT_NAME)

        if current_repo_root:
            current_repo_root = Path(current_repo_root)
            assert current_repo_root.is_dir(), current_repo_root

            if (
                len(current_repo_root.parts) <= len(repo_root.parts)
                and current_repo_root.parts == repo_root.parts[:len(current_repo_root.parts)]
            ):
                configuration = os.getenv(Constants.DE_REPO_CONFIGURATION_NAME)
                if configuration:
                    configurations.append(configuration)
                elif os.getenv(Constants.DE_REPO_ACTIVATED_KEY):
                    # If here, the repo isn't configurable
                    configurations.append(None)

        if not configurations:
            # If here, we are either running outside of an activated environment or the current
            # directory isn't in the repository
            activate_basename = "{}{}".format(Constants.ACTIVATE_ENVIRONMENT_NAME, CurrentShell.script_extensions[0])

            activate_filename: Optional[Path] = None

            for parent in itertools.chain([repo_root, ], repo_root.parents):
                potential_activate_filename = parent / activate_basename

                if potential_activate_filename.is_file():
                    activate_filename = potential_activate_filename
                    break

            assert activate_filename is not None, repo_root

            command_line = '"{}" ListConfigurations --display-format json'.format(activate_filename)

            result = SubprocessEx.Run(command_line)

            json_content = json.loads(result.output)

            if len(json_content) == 1 and "null" in json_content:
                configurations.append(None)
            else:
                configurations += json_content.keys()

        assert configurations, repo_root

        for configuration in configurations:
            with activation_dm.VerboseNested("") as this_dm:
                activation_data_items.append(
                    ActivationData.Load(
                        this_dm,
                        repo_root,
                        configuration,
                        force=True,
                    ),
                )

    processed_repositories: Dict[Path, Set[Optional[str]]] = {}

    for activation_data in activation_data_items:
        # Ensure that the root repo is included in the enumerated repositories
        if not any(pr.root == repo_root for pr in activation_data.prioritized_repositories):
            ConfiguredRepoDataWithPathProxyType         = namedtuple(
                "ConfiguredRepoDataWithPathProxyType",
                ["id", "name", "configuration", "is_mixin_repo", "root"],
            )

            processed_repository_items = list(
                itertools.chain(
                    activation_data.prioritized_repositories,
                    [
                        ConfiguredRepoDataWithPathProxyType(
                            activation_data.id,
                            "Current Repository",
                            activation_data.configuration,
                            activation_data.is_mixin_repo,
                            activation_data.root,
                        ),
                    ],
                ),
            )

        else:
            processed_repository_items = activation_data.prioritized_repositories

        for repo_data in reversed(processed_repository_items):
            processed_configurations = processed_repositories.get(repo_data.root, None)

            if processed_configurations is None:
                is_first_configuration_in_repo = True

                processed_configurations = set()
                processed_repositories[repo_data.root] = processed_configurations
            else:
                is_first_configuration_in_repo = False

            if repo_data.configuration in processed_configurations:
                continue

            processed_configurations.add(repo_data.configuration)

            potential_filename = repo_data.root / Constants.HOOK_ENVIRONMENT_CUSTOMIZATION_FILENAME
            if not potential_filename.is_file():
                continue

            with dm.Nested(
                "Processing '{}{}'...".format(
                    repo_data.root,
                    " [{}]".format(repo_data.configuration) if repo_data.configuration else "",
                ),
                suffix="\n",
            ) as repo_dm:
                sys.path.insert(0, str(potential_filename.parent))
                with ExitStack(lambda: sys.path.pop(0)):
                    try:
                        mod = importlib.import_module(potential_filename.stem)

                        with ExitStack(lambda: sys.modules.pop(potential_filename.stem)):
                            yield _EnumerateScmCustomizationsType(
                                repo_dm,
                                repo_data,
                                is_first_configuration_in_repo,
                                mod,
                            )

                    except:  # pylint: disable=bare-except
                        repo_dm.WriteError(traceback.format_exc())
