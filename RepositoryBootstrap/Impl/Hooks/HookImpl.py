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

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

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
def OnCommit(
    dm: DoneManager,
    repository: Repository,
    changes: List[ChangeInfo],
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - OnCommit\n\n")

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

    ExecutePlugins(
        dm,
        repository,
        changes,
        SCMPlugin.Flag.OnCommit,
        SCMPlugin.Flag.OnCommitCanBeDisabled,
    )


# ----------------------------------------------------------------------
def OnPush(
    dm: DoneManager,
    repository: Repository,
    push_info: PushInfo,
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - OnPush\n\n{}\n\n".format(push_info))

    dm.WriteLine("")

    ExecutePlugins(
        dm,
        repository,
        push_info.changes,
        SCMPlugin.Flag.OnPush,
        SCMPlugin.Flag.OnPushCanBeDisabled,
    )


# ----------------------------------------------------------------------
def OnMerge(
    dm: DoneManager,
    repository: Repository,
    merge_info: MergeInfo,
) -> None:
    with dm.YieldVerboseStream() as stream:
        stream.write("HookImpl.py - OnMerge\n\n{}\n\n".format(merge_info))

    dm.WriteLine("")

    ExecutePlugins(
        dm,
        repository,
        merge_info.changes,
        SCMPlugin.Flag.OnMerge,
        SCMPlugin.Flag.OnMergeCanBeDisabled,
    )


# ----------------------------------------------------------------------
def GetPlugins(
    dm: DoneManager,
    repo_root: Path,
    action_flag: SCMPlugin.Flag,
) -> list[SCMPlugin]:
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

    scm_plugins_filenames: list[Path] = []

    with dm.Nested(
        "Calculating plugin files...",
        lambda: "{} found".format(inflect.no("plugin file", len(scm_plugins_filenames))),
    ):
        for repo in activation_data.prioritized_repositories:
            potential_scm_plugins_filename = repo.root / Constants.SCM_PLUGINS_CUSTOMIZATION_FILENAME

            if potential_scm_plugins_filename.is_file():
                scm_plugins_filenames.append(potential_scm_plugins_filename)

    plugins: list[SCMPlugin] = []

    with dm.Nested(
        "Extracting plugins...",
        lambda: "{} found".format(inflect.no("plugin", len(plugins))),
        suffix="\n",
    ) as plugin_dm:
        for scm_plugins_filename_index, scm_plugins_filename in enumerate(scm_plugins_filenames):
            prev_len_plugins = len(plugins)

            with plugin_dm.VerboseNested(
                "Processing '{}' ({} of {})...".format(scm_plugins_filename, scm_plugins_filename_index + 1, len(scm_plugins_filenames)),
                lambda: "{} added".format(inflect.no("plugin", len(plugins) - prev_len_plugins)),
            ) as repo_dm:
                sys.path.insert(0, str(scm_plugins_filename.parent))
                with ExitStack(lambda: sys.path.pop(0)):
                    try:
                        mod = importlib.import_module(scm_plugins_filename.stem)

                        with ExitStack(lambda: sys.modules.pop(scm_plugins_filename.stem)):
                            for plugin in getattr(mod, Constants.SCM_PLUGINS_ENVIRONMENT_GET_PLUGINS_METHOD_NAME)():
                                if not plugin.flags & action_flag:
                                    continue

                                env_var = os.getenv(plugin.disable_environment_variable)
                                if env_var is not None and env_var != "0":
                                    repo_dm.WriteVerbose(
                                        "The plugin '{}' was skipped due to the environment variable '{}'.".format(
                                            plugin.name,
                                            plugin.disable_environment_variable,
                                        ),
                                    )
                                    continue

                                plugins.append(plugin)

                    except:  # pylint: disable=bare-except
                        repo_dm.WriteError(traceback.format_exc())

        plugins.sort(key=lambda plugin: (plugin.priority, plugin.name))

    return plugins


# ----------------------------------------------------------------------
def ExecutePlugins(
    dm: DoneManager,
    repository: Repository,
    changes: list[ChangeInfo],
    action_flag: SCMPlugin.Flag,
    disable_flag: SCMPlugin.Flag,
) -> None:
    plugins = GetPlugins(dm, repository.repo_root, action_flag)
    if not plugins:
        return

    # ----------------------------------------------------------------------
    @dataclass
    class ResultInfo(object):
        errors: int                         = field(init=False, default=0)
        warnings: int                       = field(init=False, default=0)

    # ----------------------------------------------------------------------

    result_infos: dict[int, ResultInfo] = {}

    for change_index, change in enumerate(changes):
        heading = "Processing '{} <{}>'".format(change.change_info.id, change.change_info.author_date)

        if len(changes) > 1:
            heading += " ({} of {})".format(change_index + 1, len(changes))

        heading += "..."

        with dm.Nested(
            heading,
            suffix="\n",
        ) as change_dm:
            for plugin_index, plugin in enumerate(plugins):
                was_plugin_successful = False

                with change_dm.Nested(
                    "'{}' ({} of {})...".format(plugin.name, plugin_index + 1, len(plugins)),
                    suffix="\n" if dm.is_verbose or not was_plugin_successful or plugin.has_verbose_output else "",
                ) as plugin_dm:
                    if plugin.flags & disable_flag:
                        lower_content = change.title.lower() + (change.description.lower() if change.description else "")

                        disable_commit_message = next(
                            (
                                dcm
                                for dcm in plugin.disable_commit_messages
                                if dcm.lower() in lower_content
                            ),
                            None,
                        )

                        if disable_commit_message is not None:
                            plugin_dm.WriteInfo(
                                "The plugin '{}' was skipped because '{}' appeared within the commit description.".format(
                                    plugin.name,
                                    disable_commit_message,
                                ),
                            )

                            continue

                    try:
                        plugin.Execute(plugin_dm, repository, change)
                    except Exception as ex:
                        if plugin_dm.is_debug:
                            error = traceback.format_exc()
                        else:
                            error = str(ex)

                        plugin_dm.WriteError(error)

                    if plugin_dm.result != 0:
                        result_info_key = id(plugin)

                        if result_info_key not in result_infos:
                            result_infos[result_info_key] = ResultInfo()

                        if plugin_dm.result < 0:
                            result_infos[result_info_key].errors += 1
                        elif plugin_dm.result > 0:
                            result_infos[result_info_key].warnings += 1
                        else:
                            assert False, plugin_dm.result  # pragma: no cover
                    else:
                        was_plugin_successful = True

    if result_infos:
        num_errors = sum(result_info.errors for result_info in result_infos.values())
        num_warnings = sum(result_info.warnings for result_info in result_infos.values())

        with dm.Nested(
            "{} and {} {} encountered...".format(
                inflect.no("error", num_errors),
                inflect.no("warning", num_warnings),
                inflect.plural_verb("was", num_errors + num_warnings),
            ),
        ) as error_dm:
            for plugin in plugins:
                result_info = result_infos.get(id(plugin), None)
                if result_info is None:
                    continue

                with error_dm.Nested(
                    "'{}': {} and {}...".format(
                        plugin.name,
                        inflect.no("error", result_info.errors),
                        inflect.no("warning", result_info.warnings),
                    ),
                    suffix="\n",
                ) as plugin_dm:
                    if result_info.errors:
                        plugin_dm.result = -1
                    elif result_info.warnings:
                        plugin_dm.result = 1
                    else:
                        assert False, result_info  # pragma: no cover

                    plugin_dm.WriteInfo(
                        textwrap.dedent(
                            """\
                            # ----------------------------------------------------------------------
                            To permanently disable this plugin, set this environment variable to a
                            non-zero value during activation for this repository.

                                {}

                            This is not recommended.

                            """,
                        ).format(plugin.disable_environment_variable),
                    )

                    if disable_flag != 0:
                        disable_commit_messages = plugin.disable_commit_messages

                        plugin_dm.WriteInfo(
                            textwrap.dedent(
                                """\
                                # ----------------------------------------------------------------------
                                To disable this plugin for this change, add any of the following values
                                to the commit message associated with the change:

                                {}

                                """,
                            ).format(
                                "\n".join("    - {}".format(dcm) for dcm in disable_commit_messages),
                            ),
                        )
