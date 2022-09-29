# ----------------------------------------------------------------------
# |
# |  Activate_custom.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-11 11:26:59
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------

import textwrap

from pathlib import Path
from typing import List, Optional

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore
from Common_Foundation import SubprocessEx  # type: ignore
from Common_Foundation import TextwrapEx  # type: ignore

from RepositoryBootstrap.Impl.ActivateActivities.ScriptsActivateActivity import Extractor, ExtractorMap
from RepositoryBootstrap import Constants
from RepositoryBootstrap import DynamicPluginArchitecture


# ----------------------------------------------------------------------
def GetCustomActions(
    dm: DoneManager,
    force: bool,
) -> List[Commands.Command]:
    commands: List[Commands.Command] = []

    this_dir = Path(__file__).parent
    assert this_dir.is_dir(), this_dir

    scripts_dir = this_dir / Constants.SCRIPTS_SUBDIR
    assert scripts_dir.is_dir(), scripts_dir

    with dm.VerboseNested(
        "Activating dynamic plugins from '{}'...".format(this_dir),
        suffix="\n" if dm.is_debug else "",
    ) as nested_dm:
        for env_name, subdir, name_suffixes in [
            ("DEVELOPMENT_ENVIRONMENT_COMPILERS", "Compilers", ["Compiler", "Verifier"]),
            ("DEVELOPMENT_ENVIRONMENT_TEST_EXECUTORS", "TestExecutors", ["TestExecutor"]),
            ("DEVELOPMENT_ENVIRONMENT_TEST_PARSERS", "TestParsers", ["TestParser"]),
            ("DEVELOPMENT_ENVIRONMENT_CODE_COVERAGE_VALIDATORS", "CodeCoverageValidators", ["CodeCoverageValidator"]),
        ]:
            commands += DynamicPluginArchitecture.CreateRegistrationCommands(
                nested_dm,
                env_name,
                scripts_dir / "Tester" / "Plugins" / subdir,
                lambda fullpath: (
                    fullpath.suffix == ".py"
                    and any(fullpath.stem.endswith(name_suffix) for name_suffix in name_suffixes)
                ),
                force=force,  # This should be the only repo that can force the creation of these environment vars
            )

    commands.append(
        Commands.Augment(
            "DEVELOPMENT_ENVIRONMENT_TESTER_CONFIGURATIONS",
            [
                # <configuration name>-<python type>-<value>[-pri=<priority>]
                "basic_python_unittest-compiler-Noop-pri=10000",
                "basic_python_unittest-test_parser-PythonUnittest",
            ],
        ),
    )

    if CurrentShell.family_name == "Windows":
        import winreg

        # Check to see if developer mode is enabled on Windows
        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock",
            )

            with ExitStack(lambda: winreg.CloseKey(hkey)):
                value = winreg.QueryValueEx(hkey, "AllowDevelopmentWithoutDevLicense")[0]

                if value != 1:
                    commands.append(
                        Commands.Message(
                            TextwrapEx.Indent(
                                TextwrapEx.CreateWarningText(
                                    textwrap.dedent(
                                        """\
                                        Windows Developer Mode is not enabled; this is a requirement for the setup process
                                        as Developer Mode allows for the creation of symbolic links without admin privileges.

                                        To enable Developer Mode in Windows:

                                            1) Launch 'Developer settings'
                                            2) Select 'Developer mode'
                                        """,
                                    ),
                                ),
                                2,
                            ),
                        ),
                    )

        except FileNotFoundError:
            # This key isn't available on all versions of Windows
            pass

        # Python imports can begin to break down if long paths aren't enabled
        try:
            hkey = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\ControlSet001\Control\FileSystem",
            )
            with ExitStack(lambda: winreg.CloseKey(hkey)):
                value = winreg.QueryValueEx(hkey, "LongPathsEnabled")[0]

                if value != 1:
                    commands.append(
                        Commands.Message(
                            TextwrapEx.Indent(
                                TextwrapEx.CreateWarningText(
                                    textwrap.dedent(
                                        """\
                                        Long path support is not enabled. While this isn't a requirement for running on
                                        Windows, it could present problems with python imports in deeply nested directory
                                        hierarchies.

                                        To enable long path support in Windows:

                                            1) Launch 'regedit'
                                            2) Navigate to 'HKEY_LOCAL_MACHINE\\SYSTEM\\ControlSet001\\Control\\FileSystem'
                                            3) Edit the value 'LongPathsEnabled'
                                            4) Set the value to 1
                                        """,
                                    ),
                                ),
                                2,
                            ),
                        ),
                    )

        except FileNotFoundError:
            # This key isn't available on all versions of Windows
            pass

    # Check to see if git is installed and if its settings are set to the best defaults
    if SubprocessEx.Run("git rev-parse --show-toplevel").returncode == 0:
        # core.autocrlf
        git_output = SubprocessEx.Run("git config --get core.autocrlf").output.strip()
        if git_output != "false":
            commands.append(
                Commands.Message(
                    TextwrapEx.Indent(
                        TextwrapEx.CreateWarningText(
                            textwrap.dedent(
                                """\
                                Git is configured to modify line endings on checkin and/or checkout.
                                While this was the recommended setting in the past, it presents problems
                                when editing code on both Windows and Linux using modern editors.

                                It is recommended that you change this setting to not modify line endings:

                                    1) `git config --global core.autocrlf false`
                                """,
                            ),
                        ),
                        2,
                    ),
                ),
            )

        # init.defaultBranch
        git_output = SubprocessEx.Run("git config --get init.defaultBranch").output.strip()
        if git_output != "main":
            commands.append(
                Commands.Message(
                    TextwrapEx.Indent(
                        TextwrapEx.CreateErrorText(
                            textwrap.dedent(
                                """\
                                The git default branch is {}, but needs to be set to 'main'.

                                To change the default branch for this repository:

                                    1) `git config init.defaultBranch main`
                                """,
                            ).format(
                                "empty" if not git_output else "set to '{}'".format(git_output),
                            ),
                        ),
                        2,
                    ),
                ),
            )

    return commands


# ----------------------------------------------------------------------
def GetCustomScriptExtractors() -> ExtractorMap:
    # ----------------------------------------------------------------------
    def CreatePythonCommands(
        path: Path,
    ) -> Optional[List[Commands.Command]]:
        if path.name == "__init__.py":
            return None

        if path.name == "__main__.py":
            # Invoke the dir
            path = path.parent
        else:
            # Don't invoke anything that descends from a directory that has a main file
            if any((parent / "__main__.py").is_file() for parent in path.parents):
                return None

            # Don't invoke scripts in commonly named directories that aren't directly useful
            if any(parent.name.endswith("Plugins") for parent in path.parents):
                return None

        return [
            Commands.EchoOff(),
            Commands.Execute(
                'python "{}" {}'.format(
                    str(path.resolve()),
                    CurrentShell.all_arguments_script_variable,
                ),
            ),
        ]

    # ----------------------------------------------------------------------
    def CreatePythonDocs(
        path: Path,
    ) -> str:
        with path.open() as f:
            data = f.read()

        co = compile(data, str(path), "exec")

        if (
            co
            and co.co_consts
            and isinstance(co.co_consts[0], str)
            and co.co_consts[0][0] != "_"
        ):
            return textwrap.TextWrapper(
                width=120,
            ).fill(co.co_consts[0])

        return ""

    # ----------------------------------------------------------------------
    def PythonScriptNameDecorator(
        path: Path,
    ) -> str:
        if path.name == "__main__.py":
            return path.parent.parts[-1]

        return path.stem

    # ----------------------------------------------------------------------
    def CreateStandardCommands(
        path: Path,
    ) -> List[Commands.Command]:
        return [
            Commands.EchoOff(),
            Commands.Execute(
                '"{}" {}'.format(str(path.resolve()), CurrentShell.all_arguments_script_variable),
            ),
        ]

    # ----------------------------------------------------------------------

    return {
        (".py", ): Extractor(CreatePythonCommands, CreatePythonDocs, PythonScriptNameDecorator),
        tuple(CurrentShell.script_extensions): Extractor(CreateStandardCommands, None, None),
    }
