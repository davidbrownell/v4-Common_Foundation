# pylint: disable=missing-module-docstring

from typing import List, Optional

from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager

from RepositoryBootstrap.DataTypes import CommitInfo, PreIntegrateInfo, PrePushInfo  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
def OnCommit(
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,                 # pylint: disable=unused-argument
    commits: List[CommitInfo],              # pylint: disable=unused-argument
    *,
    first_configuration_in_repo: bool,      # True when this function is called for this first time with this repository
) -> Optional[bool]:                        # Return False to prevent the execution of other hooks
    """Called before changes are committed to the local repository."""

    raise Exception("Implement me")
    # pylint: disable=unreachable

    # Do not perform validation across multiple configurations for the same repository if configuration
    # information isn't used as part of the validation.
    if not first_configuration_in_repo:
        return

    # Specific validation goes here


# ----------------------------------------------------------------------
def OnPrePush(
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,                 # pylint: disable=unused-argument
    pre_push_info: PrePushInfo,             # pylint: disable=unused-argument
    *,                                      # pylint: disable=unused-argument
    first_configuration_in_repo: bool,      # pylint: disable=unused-argument
) -> Optional[bool]:
    """Called before changes are pushed to a remote repository."""

    raise Exception("Implement me")
    # pylint: disable=unreachable

    # Do not perform validation across multiple configurations for the same repository if configuration
    # information isn't used as part of the validation.
    if not first_configuration_in_repo:
        return

    # Specific validation goes here


# ----------------------------------------------------------------------
def OnPreIntegrate(
    dm: DoneManager,                        # pylint: disable=unused-argument
    configuration: Optional[str],           # pylint: disable=unused-argument
    repository: Repository,                 # pylint: disable=unused-argument
    pre_integrate_info: PreIntegrateInfo,   # pylint: disable=unused-argument
    *,                                      # pylint: disable=unused-argument
    first_configuration_in_repo: bool,      # pylint: disable=unused-argument
) -> Optional[bool]:
    """Called before changes are integrated into the local repository when pushed from a remote repository."""

    raise Exception("Implement me")
    # pylint: disable=unreachable

    # Do not perform validation across multiple configurations for the same repository if configuration
    # information isn't used as part of the validation.
    if not first_configuration_in_repo:
        return

    # Specific validation goes here
