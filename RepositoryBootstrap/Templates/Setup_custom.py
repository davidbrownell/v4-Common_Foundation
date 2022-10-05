# pylint: disable=missing-module-docstring

import uuid

from typing import Dict, List, Optional, Union

from semantic_version import Version as SemVer          # pylint: disable=unused-import

from Common_Foundation.Shell.All import CurrentShell                        # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Shell import Commands                                # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Streams.DoneManager import DoneManager               # type: ignore  # pylint: disable=import-error,unused-import

from RepositoryBootstrap import Configuration                               # type: ignore  # pylint: disable=import-error,unused-import


# ----------------------------------------------------------------------
# Uncomment the decorator below to make this repository a mixin repository.
# Mixin repositories can not be activated on their own and cannot have tool
# or version specifications. Mixin repositories are valuable because they
# can provide scripts or tools that augment other repositories when activated.
#
# @Configuration.MixinRepository
def GetConfigurations() -> Union[
    Configuration.Configuration,
    Dict[
        str,                                # configuration name
        Configuration.Configuration,
    ],
]:
    """Return configuration information for the repository"""

    raise Exception(
        "Remove this exception once you have updated the configuration for your new repository (GetDependencies).",
    )

    # pylint: disable=unreachable
    return Configuration.Configuration(
        "",
        [
            Configuration.Dependency(
                uuid.UUID("DD6FCD30-B043-4058-B0D5-A6C8BC0374F4"),
                "Common_Foundation",
                "python310",
                "https://github.com/davidbrownell/v4-Common_Foundation.git",
            ),
        ],
        Configuration.VersionSpecs(
            [],                             # tools
            {},                             # libraries
        ),
    )


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActions(
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                    # pylint: disable=unused-argument
    explicit_configurations: Optional[List[str]],       # pylint: disable=unused-argument
    force: bool,                                        # pylint: disable=unused-argument
) -> List[Commands.Command]:
    """Return custom actions invoked as part of the setup process for this repository"""

    return []
