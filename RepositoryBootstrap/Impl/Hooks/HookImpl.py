# ----------------------------------------------------------------------
# |
# |  HookImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 08:45:50
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
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
import textwrap
import traceback

from pathlib import Path
from typing import Callable, List, Optional

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap import Constants
from RepositoryBootstrap.DataTypes import ChangeInfo, PushInfo, MergeInfo, SCMPlugin
from RepositoryBootstrap.Impl.ActivationData import ActivationData


# ----------------------------------------------------------------------
def Commit(
    dm: DoneManager,
    repository: Repository,
    changes: List[ChangeInfo],
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - Commit\n\n")

        for commit_index, commit in enumerate(changes):
            stream.write(
                textwrap.dedent(
                    """\
                    {} ) {}

                    """,
                ).format(
                    commit_index + 1,
                    TextwrapEx.Indent(
                        str(commit),
                        len(str(commit_index + 1)) + 3,
                        skip_first_line=True,
                    ),
                ),
            )

    dm.WriteLine("")

    _Impl(
        dm,
        repository.repo_root,
        changes[0],
        SCMPlugin.Flag.OnCommit,
        SCMPlugin.Flag.OnCommitCanBeDisabled,
        lambda plugin_dm, plugin: plugin.OnCommit(plugin_dm, repository, changes),
    )


# ----------------------------------------------------------------------
def OnPush(
    dm: DoneManager,
    repository: Repository,
    push_info: PushInfo,
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - PrePush\n\n{}\n\n".format(push_info))

    dm.WriteLine("")

    _Impl(
        dm,
        repository.repo_root,
        push_info.changes[0],
        SCMPlugin.Flag.OnPush,
        SCMPlugin.Flag.OnPushCanBeDisabled,
        lambda plugin_dm, plugin: plugin.OnPush(plugin_dm, repository, push_info),
    )


# ----------------------------------------------------------------------
def OnMerge(
    dm: DoneManager,
    repository: Repository,
    merge_info: MergeInfo,
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - PreIntegrate\n\n{}\n\n".format(merge_info))

    dm.WriteLine("")

    _Impl(
        dm,
        repository.repo_root,
        merge_info.changes[0],
        SCMPlugin.Flag.OnMerge,
        SCMPlugin.Flag.OnMergeCanBeDisabled,
        lambda plugin_dm, plugin: plugin.OnMerge(plugin_dm, repository, merge_info),
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Impl(
    dm: DoneManager,
    repo_root: Path,
    most_recent_change: ChangeInfo,
    action_flag: SCMPlugin.Flag,
    disable_flag: SCMPlugin.Flag,
    invoke_func: Callable[[DoneManager, SCMPlugin], None],
) -> None:
    with dm.Nested(
        "Loading repository information for '{}'...".format(repo_root),
        suffix="\n",
    ) as activation_dm:
        # ----------------------------------------------------------------------
        def GetConfiguration() -> Optional[str]:
            # Use the configuration associated with the current environment if this functionality
            # is invoked in an activated environment.
            current_repo_root = os.getenv(Constants.DE_REPO_ROOT_NAME)
            if current_repo_root:
                current_repo_root = Path(current_repo_root)

                if repo_root == current_repo_root:
                    configuration = os.getenv(Constants.DE_REPO_CONFIGURATION_NAME)
                    if configuration is not None or os.getenv(Constants.DE_REPO_ACTIVATED_KEY):
                        return configuration

            # If here, we aren't running in an activated environment or the environment activated
            # is different from the repository.
            activate_name = "{}{}".format(Constants.ACTIVATE_ENVIRONMENT_NAME, CurrentShell.script_extensions[0])

            activate_filename: Optional[Path] = None

            for parent in itertools.chain([repo_root, ], repo_root.parents):
                potential_activate_filename = parent / activate_name

                if potential_activate_filename.is_file():
                    activate_filename = potential_activate_filename
                    break

            assert activate_filename is not None

            # List the configurations
            result = SubprocessEx.Run(
                '"{}" ListConfigurations --display-format json'.format(activate_filename),
            )

            result.RaiseOnError()

            json_content = json.loads(result.output)

            if len(json_content) == 1 and "null" in json_content:
                return None

            return next(iter(json_content.keys()))

        # ----------------------------------------------------------------------

        activation_data: Optional[ActivationData] = None

        with activation_dm.VerboseNested("") as activation_data_dm:
            activation_data = ActivationData.Load(
                activation_data_dm,
                repo_root,
                GetConfiguration(),
                force=True,
            )

        assert activation_data is not None

    hook_filenames: list[Path] = []

    with dm.Nested(
        "Calculating hook files...",
        lambda: "{} found".format(inflect.no("hook file", len(hook_filenames))),
    ):
        for repo in activation_data.prioritized_repositories:
            potential_hook_filename = repo.root / Constants.HOOK_ENVIRONMENT_CUSTOMIZATION_FILENAME

            if potential_hook_filename.is_file():
                hook_filenames.append(potential_hook_filename)

    plugins: list[SCMPlugin] = []

    with dm.Nested(
        "Extracting plugins...",
        lambda: "{} found".format(inflect.no("plugin", len(plugins))),
        suffix="\n",
    ) as plugin_dm:
        for hook_filename_index, hook_filename in enumerate(hook_filenames):
            prev_len_plugins = len(plugins)

            with plugin_dm.VerboseNested(
                "Processing '{}' ({} of {})...".format(hook_filename, hook_filename_index + 1, len(hook_filenames)),
                lambda: "{} added".format(inflect.no("plugin", len(plugins) - prev_len_plugins)),
            ) as repo_dm:
                sys.path.insert(0, str(hook_filename.parent))
                with ExitStack(lambda: sys.path.pop(0)):
                    try:
                        mod = importlib.import_module(hook_filename.stem)

                        with ExitStack(lambda: sys.modules.pop(hook_filename.stem)):
                            plugins += [
                                plugin
                                for plugin in getattr(mod, Constants.HOOK_ENVIRONMENT_GET_PLUGINS_METHOD_NAME)()
                                if plugin.flags & action_flag
                            ]

                    except:  # pylint: disable=bare-except
                        repo_dm.WriteError(traceback.format_exc())

        plugins.sort(key=lambda plugin: (plugin.priority, plugin.name))

    with dm.Nested("Processing plugins...") as process_dm:
        for plugin_index, plugin in enumerate(plugins):
            with process_dm.Nested(
                "'{}' ({} of {})...".format(plugin.name, plugin_index + 1, len(plugins)),
                suffix="\n" if process_dm.is_verbose else "",
            ) as this_dm:
                # Has this plugin been disabled via environment variable?
                env_value = os.getenv(plugin.disable_environment_variable)
                if env_value is not None and env_value != "0":
                    this_dm.WriteVerbose(
                        "Skipping '{}' due to the '{}' environment variable.".format(
                            plugin.name,
                            plugin.disable_environment_variable,
                        ),
                    )
                    continue

                # Has this plugin been disabled via commit message?
                if plugin.flags & disable_flag:
                    # ----------------------------------------------------------------------
                    def GetDisableCommitMessage(
                        value: str,
                    ) -> Optional[str]:
                        for disable_commit_message in plugin.disable_commit_messages:
                            if disable_commit_message.lower() in value:
                                return disable_commit_message

                        return None

                    # ----------------------------------------------------------------------

                    dcm = GetDisableCommitMessage(most_recent_change.title)

                    if dcm is None and most_recent_change.description:
                        dcm = GetDisableCommitMessage(most_recent_change.description)

                    if dcm is not None:
                        this_dm.WriteVerbose(
                            "Skipping '{}' due to '{}' in the change message for '{}'.".format(
                                plugin.name,
                                dcm,
                                most_recent_change.id,
                            ),
                        )
                        continue

                try:
                    invoke_func(this_dm, plugin)
                except Exception as ex:
                    plugin.DisplayError(
                        this_dm,
                        str(ex),
                        disable_flag,
                    )
