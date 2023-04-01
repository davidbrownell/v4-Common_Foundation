# ----------------------------------------------------------------------
# |
# |  Setup_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-29 12:56:07
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=missing-module-docstring

import uuid                                             # pylint: disable=unused-import

from typing import Dict, List, Optional, Union

from semantic_version import Version as SemVer          # pylint: disable=unused-import

from Common_Foundation.Shell.All import CurrentShell                        # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Shell import Commands                                # type: ignore  # pylint: disable=import-error,unused-import
from Common_Foundation.Streams.DoneManager import DoneManager               # type: ignore  # pylint: disable=import-error,unused-import

from RepositoryBootstrap import Configuration                               # type: ignore  # pylint: disable=import-error,unused-import
from RepositoryBootstrap import Constants                                   # type: ignore  # pylint: disable=import-error,unused-import


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

    return Configuration.Configuration(
        "",
        [
            Configuration.Dependency(
                uuid.UUID("e4170a9d-70f9-4615-85b6-d514055e62b6"),
                "Common_PythonDevelopment",
                "python310",
                "https://github.com/davidbrownell/v4-Common_PythonDevelopment.git",
            ),
        ],
        Configuration.VersionSpecs(
            [],                             # tools
            {
                "Python": [
                    Configuration.VersionInfo("cx_Freeze", SemVer("6.14.7")),
                ],
            },                             # libraries
        ),
    )


# ----------------------------------------------------------------------
# Note that it is safe to remove this function if it will never be used.
def GetCustomActions(
    # Note that it is safe to remove any parameters that are not used
    dm: DoneManager,                                    # pylint: disable=unused-argument
    explicit_configurations: Optional[List[str]],       # pylint: disable=unused-argument
    force: bool,                                        # pylint: disable=unused-argument
    interactive: Optional[bool],                        # pylint: disable=unused-argument
) -> List[Commands.Command]:
    """Return custom actions invoked as part of the setup process for this repository"""

    return []
