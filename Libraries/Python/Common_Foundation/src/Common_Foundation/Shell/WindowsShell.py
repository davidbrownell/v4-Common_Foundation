# ----------------------------------------------------------------------
# |
# |  WindowsShell.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 15:25:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the WindowsShell object"""

import os
import shlex
import textwrap
import uuid

from pathlib import Path
from typing import List, Optional, Set as SetType

from .Commands import (
    Augment,
    AugmentPath,
    Call,
    CommandPrompt,
    Comment,
    Copy,
    Delete,
    EchoOff,
    Execute,
    Exit,
    ExitOnError,
    Message,
    Move,
    PersistError,
    PopDirectory,
    PushDirectory,
    Raw,
    Set,
    SetPath,
    SymbolicLink,
)

from .CommandVisitor import CommandVisitor
from .Shell import Shell

from ..Types import overridemethod


# ----------------------------------------------------------------------
class WindowsShell(Shell):
    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Windows"

    @property
    def family_name(self) -> str:
        return "Windows"

    @property
    def script_extensions(self) -> List[str]:
        return [".cmd", ]

    @property
    def executable_extensions(self) -> Optional[List[str]]:
        return [".exe", ]

    @property
    def compression_extensions(self) -> Optional[List[str]]:
        return [".zip", ".7z", ]

    @property
    def all_arguments_script_variable(self) -> str:
        return "%*"

    @property
    def has_case_sensitive_file_system(self) -> bool:
        return False

    @property
    def supported_architectures(self) -> List[str]:
        return ["x64", "x86"]

    @property
    def current_architecture(self) -> str:
        return "x64" if os.getenv("ProgramFiles(x86)") else "x86"

    @property
    def user_directory(self) -> Path:
        home_drive = os.getenv("HOMEDRIVE")
        home_path = os.getenv("HOMEPATH")

        if home_drive is not None and home_path is not None:
            return Path(home_drive) / home_path

        path = os.getenv("HOMEPATH")
        assert path is not None

        return Path(path)

    @property
    def temp_directory(self) -> Path:
        if self.IsContainerEnvironment():
            # TEMP and TMP env vars point to directories that aren't writable on nanoserver. Create
            # a directory and write temp files there.
            path = Path(r"C:\Temp")
            path.mkdir(parents=True, exist_ok=True)

            return path

        path = os.getenv("TMP")
        assert path is not None

        return Path(path)

    @property
    def path_sep(self) -> str:
        return "\\"

    @property
    def command_visitor(self) -> CommandVisitor:
        return self._command_visitor

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(self):
        self._command_visitor               = WindowsCommandVisitor()

        is_nanoserver = False

        license_file = Path(r"C:\License.txt")
        if license_file.is_file() and "WINDOWS CONTAINER BASE IMAGE" in license_file.open().read():
            is_nanoserver = True

        self._is_nanoserver                 = is_nanoserver

    # ----------------------------------------------------------------------
    @overridemethod
    def IsActive(
        self,
        platform_names: SetType[str],
    ) -> bool:
        if "nt" in platform_names:
            return True

        return any("windows" in platform_name for platform_name in platform_names)

    # ----------------------------------------------------------------------
    @overridemethod
    def IsContainerEnvironment(self) -> bool:
        return self._is_nanoserver

    # ----------------------------------------------------------------------
    @overridemethod
    def RemoveDir(
        self,
        path: Path,
    ) -> None:
        if path.is_dir():
            os.system('rmdir /S /Q "{}"'.format(str(path)))

    # ----------------------------------------------------------------------
    @overridemethod
    def DecorateEnvironmentVariable(
        self,
        var_name: str,
    ) -> str:
        return "%{}%".format(var_name)

    # ----------------------------------------------------------------------
    @overridemethod
    def UpdateOwnership(
        self,
        file_or_directory: Path,  # pylint: disable=unused-argument
        *,
        recurse=False,  # pylint: disable=unused-argument
    ) -> None:
        # Nothing to do here
        pass

    # ----------------------------------------------------------------------
    @overridemethod
    def CreateTempFilename(
        self,
        suffix: Optional[str]=None,
    ) -> Path:
        temp_filename = super(WindowsShell, self).CreateTempFilename(suffix)

        if not self.IsContainerEnvironment():
            return temp_filename

        return self.temp_directory / temp_filename.name


# ----------------------------------------------------------------------
class WindowsCommandVisitor(CommandVisitor):
    # ----------------------------------------------------------------------
    @overridemethod
    def OnAugment(
        self,
        command: Augment,
    ) -> Optional[str]:
        statements: List[str] = []

        if command.is_space_delimited_string:
            sep = " "
        else:
            sep = os.pathsep

        if command.append_values:
            add_statement_template = "%{name}%{sep}{value}"
        else:
            add_statement_template = "{value}{sep}%{name}%"

        statement_template = "set {name}={add_statement}"

        if not command.simple_format:
            statement_template = textwrap.dedent(
                """\
                echo "{{sep}}%{{name}}%{{sep}}" | findstr /C:"{{sep}}{{value}}{{sep}}" >nul
                if %ERRORLEVEL% == 0 goto skip_{{unique_id}}

                {statement_template}

                :skip_{{unique_id}}

                """,
            ).format(
                statement_template=statement_template,
            )

        statements = [
            statement_template.format(
                name=command.name,
                value=value,
                sep=sep,
                unique_id=str(uuid.uuid4()).replace("-", ""),
                add_statement=add_statement_template.format(
                    name=command.name,
                    value=value,
                    sep=sep,
                ),
            )
            for value in command.EnumValues()
        ]

        return "\n".join(statements)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnAugmentPath(
        self,
        command: AugmentPath,
    ) -> Optional[str]:
        return self.OnAugment(command)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCall(
        self,
        command: Call,
    ) -> Optional[str]:
        result = "call {}".format(command.command_line)
        if command.exit_on_error:
            result += "\n{}\n".format(self.Accept(ExitOnError()))

        return result

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommandPrompt(
        self,
        command: CommandPrompt,
    ) -> Optional[str]:
        return "set PROMPT=({}) $P$G".format(command.prompt)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnComment(
        self,
        command: Comment,
    ) -> Optional[str]:
        return "REM {}".format(command.value)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCopy(
        self,
        command: Copy,
    ) -> Optional[str]:
        return 'copy /T "{source}" "{dest}"'.format(
            source=command.source,
            dest=command.dest,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnDelete(
        self,
        command: Delete,
    ) -> Optional[str]:
        if command.is_dir:
            return 'rmdir /S /Q "{}"'.format(command.path)

        return 'del "{}"'.format(command.path)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnEchoOff(
        self,
        command: EchoOff,
    ) -> Optional[str]:
        return "@echo off"

    # ----------------------------------------------------------------------
    @overridemethod
    def OnExecute(
        self,
        command: Execute,
    ) -> Optional[str]:
        # Execute the command line with a special prefix if the command line invokes a .bat or .cmd file
        commands = shlex.split(command.command_line)

        if commands[0].endswith(".bat") or commands[0].endswith(".cmd"):
            result = "cmd /c {}".format(command.command_line)
        else:
            result = command.command_line

        if command.exit_on_error:
            result += "\n{}\n".format(self.Accept(ExitOnError()))

        return result

    # ----------------------------------------------------------------------
    @overridemethod
    def OnExit(
        self,
        command: Exit,
    ) -> Optional[str]:
        return textwrap.dedent(
            """\
            {success}
            {error}
            exit /B {return_code}
            """,
        ).format(
            success="if %ERRORLEVEL% EQ 0 ( pause )" if command.pause_on_success else "",
            error="if %ERRORLEVEL% NEQ 0 ( pause )" if command.pause_on_error else "",
            return_code=command.return_code or 0,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnExitOnError(
        self,
        command: ExitOnError,
    ) -> Optional[str]:
        variable_name = command.variable_name or "ERRORLEVEL"

        return "if %{}% NEQ 0 (exit /B {})".format(
            variable_name,
            command.return_code or "%{}%".format(variable_name),
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnMessage(
        self,
        command: Message,
    ) -> Optional[str]:
        substitution_lookup = {
            "%": "%%",
            "&": "^&",
            "<": "^<",
            ">": "^>",
            "|": "^|",
            ",": "^,",
            ";": "^;",
            "(": "^(",
            ")": "^)",
            "[": "^[",
            "]": "^]",
        }

        output = []

        for line in command.value.split("\n"):
            if not line.strip():
                # Note that the trailing space seems to be necessary on some terminals
                output.append("echo. ")
                continue

            line = line.replace("^", "__caret_placeholder__")

            for source, dest in substitution_lookup.items():
                line = line.replace(source, dest)

            line = line.replace("__caret_placeholder__", "^")

            output.append("echo {}".format(line))

        return " && ".join(output)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnMove(
        self,
        command: Move,
    ) -> Optional[str]:
        return 'move /Y "{source}" "{dest}"'.format(
            source=command.source,
            dest=command.dest,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPersistError(
        self,
        command: PersistError,
    ) -> Optional[str]:
        return "set {}=%ERRORLEVEL%".format(command.variable_name)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPopDirectory(
        self,
        command: PopDirectory,  # pylint: disable=unused-argument
    ) -> Optional[str]:
        return "popd"

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPushDirectory(
        self,
        command: PushDirectory,
    ) -> Optional[str]:
        directory = command.value or "%~dp0"
        return 'pushd "{}"'.format(directory)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnRaw(
        self,
        command: Raw,
    ) -> Optional[str]:
        return command.value

    # ----------------------------------------------------------------------
    @overridemethod
    def OnSet(
        self,
        command: Set,
    ) -> Optional[str]:
        if command.value_or_values is None:
            return "SET {}=".format(command.name)

        return "SET {}={}".format(command.name, os.pathsep.join(command.EnumValues()))

    # ----------------------------------------------------------------------
    @overridemethod
    def OnSetPath(
        self,
        command: SetPath,
    ) -> Optional[str]:
        return self.OnSet(command)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnSymbolicLink(
        self,
        command: SymbolicLink,
    ) -> Optional[str]:
        d = {
            "link": command.link_filename,
            "target": command.target,
        }

        return textwrap.dedent(
            """\
            {remove}mklink{dir_flag} "{link}" "{target}" > NUL
            """,
        ).format(
            **{
                **d,
                **{
                    "remove": "" if not command.remove_existing
                        else 'if exist "{link}" ({remove} "{link}")\n'.format(
                            **{
                                **d,
                                **{
                                    "remove":  "rmdir" if command.is_dir else "del /Q",
                                },
                            },
                        ),
                    "dir_flag": " /D /J" if command.is_dir else "",
                },
            },
        )
