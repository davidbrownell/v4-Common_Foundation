# pylint: disable=invalid-name
# pylint: disable=missing-module-docstring

from pathlib import Path
from typing import Any, Optional, Union

from Common_Foundation.Shell import Commands                                # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Shell.All import CurrentShell                        # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Streams.DoneManager import DoneManager               # type: ignore  # pylint: disable=import-error,unused-import

from RepositoryBootstrap import Configuration                               # type: ignore  # pylint: disable=import-error,unused-import
from RepositoryBootstrap import DataTypes                                   # type: ignore  # pylint: disable=import-error,unused-import


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActions(                                                       # pylint: disable=too-many-arguments
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                                        # pylint: disable=unused-argument
    repositories: list[DataTypes.ConfiguredRepoDataWithPath],               # pylint: disable=unused-argument
    generated_dir: Path,                                                    # pylint: disable=unused-argument
    configuration: Optional[str],                                           # pylint: disable=unused-argument
    version_specs: Configuration.VersionSpecs,                              # pylint: disable=unused-argument
    force: bool,                                                            # pylint: disable=unused-argument
    is_mixin_repo: bool,                                                    # pylint: disable=unused-argument
) -> list[Commands.Command]:
    """Returns a list of actions that should be invoked as part of the activation process."""

    raise Exception(
        "Remove this exception once you have updated the custom actions for your new repository (GetCustomActions).",
    )

    # pylint: disable=unreachable
    return [
        Commands.Message("This is a sample message"),
    ]


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActionsEpilogue(                                               # pylint: disable=too-many-arguments
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                                        # pylint: disable=unused-argument
    repositories: list[DataTypes.ConfiguredRepoDataWithPath],               # pylint: disable=unused-argument
    generated_dir: Path,                                                    # pylint: disable=unused-argument
    configuration: Optional[str],                                           # pylint: disable=unused-argument
    version_specs: Configuration.VersionSpecs,                              # pylint: disable=unused-argument
    force: bool,                                                            # pylint: disable=unused-argument
    is_mixin_repo: bool,                                                    # pylint: disable=unused-argument
) -> list[Commands.Command]:
    """\
    Returns a list of actions that should be invoked as part of the activation process. Note
    that this is called after `GetCustomActions` has been called for each repository in the dependency
    list.

    ********************************************************************************************
    Note that it is very rare to have the need to implement this method. In most cases, it is
    safe to delete the entire method. However, keeping the default implementation (that
    essentially does nothing) is not a problem.
    ********************************************************************************************
    """

    return []


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomScriptExtractors(
    # Note that it is safe to remove any parameters that are not used
    repositories: list[DataTypes.ConfiguredRepoDataWithPath],               # pylint: disable=unused-argument
    version_specs: Configuration.VersionSpecs,                              # pylint: disable=unused-argument
) -> Union[
    None,
    tuple[
        Any,        # RepositoryBootstrap.Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap
        list[Any],  # RepositoryBootstrap.Impl.ActivateActivities.ScriptActivateActivity.DirGenerator
    ],
    tuple[
        Any,        # RepositoryBootstrap.Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap
        Any,        # RepositoryBootstrap.Impl.ActivateActivities.ScriptActivateActivity.DirGenerator
    ],
    Any,            # RepositoryBootstrap.Impl.ActivateActivities.ScriptActivateActivity.ExtractorMap
]:
    """
    Returns information that can be used to enumerate, extract, and generate documentation
    for scripts stored in the Scripts directory in this repository and all repositories
    that depend upon it.

    ********************************************************************************************
    Note that it is very rare to have the need to implement this method. In most cases, it is
    safe to delete the entire method. However, keeping the default implementation (that
    essentially does nothing) is not a problem.
    ********************************************************************************************
    """

    return None
