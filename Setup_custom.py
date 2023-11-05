# ----------------------------------------------------------------------
# |
# |  Setup_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-09 07:10:31
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=missing-module-docstring

from pathlib import Path
from typing import Dict, List, Optional, Union

from semantic_version import Version as SemVer

from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Shell import Commands  # type: ignore

from RepositoryBootstrap import Configuration


# ----------------------------------------------------------------------
def GetConfigurations() -> Union[Configuration.Configuration, Dict[str, Configuration.Configuration]]:
    configurations: Dict[str, Configuration.Configuration] = {}

    basic_python_libraries: List[Configuration.VersionInfo] = [
        Configuration.VersionInfo("pip", SemVer("22.2.2")),
        Configuration.VersionInfo("setuptools", SemVer("63.2.0")),
        Configuration.VersionInfo("virtualenv", SemVer("20.16.3")),
        Configuration.VersionInfo("wheel", SemVer("0.37.1")),
    ]

    # python310
    python_libraries: List[Configuration.VersionInfo] = basic_python_libraries + [
        Configuration.VersionInfo("colorama", SemVer("0.4.5")),
        Configuration.VersionInfo("inflect", SemVer("6.0.0")),
        Configuration.VersionInfo("requests", SemVer("2.28.1")),
        Configuration.VersionInfo("rich", SemVer("12.6.0")),
        Configuration.VersionInfo("semantic_version", SemVer("2.10.0")),
        Configuration.VersionInfo("typer", SemVer("0.6.1")),
        Configuration.VersionInfo("typer-config", SemVer("1.2.1")),
        Configuration.VersionInfo("wrapt", SemVer("1.14.1")),

        # Libraries not required for Setup activities
        Configuration.VersionInfo("cookiecutter", SemVer("2.2.3")),
        Configuration.VersionInfo("jinja2", SemVer("3.1.2")),
        Configuration.VersionInfo("jsonschema", SemVer.coerce("4.17.3")),
        Configuration.VersionInfo("rtyaml", SemVer("1.0.0")),
    ]

    if CurrentShell.family_name == "Windows":
        python_libraries += [
            Configuration.VersionInfo("pywin32", SemVer.coerce("304")),
        ]
    elif CurrentShell.family_name in ["Linux", "BSD"]:
        python_libraries += [
            Configuration.VersionInfo("distro", SemVer("1.7.0")),
        ]

    configurations["python310"] = Configuration.Configuration(
        "Python v3.10.6",
        [],
        Configuration.VersionSpecs(
            [
                Configuration.VersionInfo("Python", SemVer("3.10.6")),
            ],
            {
                "Python": python_libraries,
            },
        ),
    )

    # python310_nolibs
    configurations["python310_nolibs"] = Configuration.Configuration(
        "Python v3.10.6 without any libraries",
        [],
        Configuration.VersionSpecs(
            [
                Configuration.VersionInfo("Python", SemVer("3.10.6")),
            ],
            {
                "Python": basic_python_libraries,
            },
        ),
    )

    return configurations


# ----------------------------------------------------------------------
def GetCustomActions(
    explicit_configurations: Optional[List[str]],  # pylint: disable=unused-argument
) -> List[Commands.Command]:
    commands: list[Commands.Command] = []

    root_dir = Path(__file__).parent

    # At one point, DynamicPluginArchitecture lived in './RepositoryBootstrap/SetupAndActivate' but
    # it now lives in './Libraries/Python/Common_Foundation/src/Common_Foundation'. Create a link to
    # the new file at the previous location to maintain backwards compatibility.
    current_filename = PathEx.EnsureFile(root_dir / "Libraries" / "Python" / "Common_Foundation" / "src" / "Common_Foundation" / "DynamicPluginArchitecture.py")

    commands.append(
        Commands.SymbolicLink(
            PathEx.EnsureDir(root_dir / "RepositoryBootstrap" / "SetupAndActivate") / current_filename.name,
            current_filename,
            remove_existing=True,
            relative_path=True,
        ),
    )

    return commands
