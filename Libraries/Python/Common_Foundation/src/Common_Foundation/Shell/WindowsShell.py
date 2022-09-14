# ----------------------------------------------------------------------
# |
# |  WindowsShell.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 15:25:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
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
        path = os.getenv("HOMEPATH") or os.getenv("APPDATA")
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
    @staticmethod
    def IsActive(
        platform_names: SetType[str],
    ) -> bool:
        if "nt" in platform_names:
            return True

        return any("windows" in platform_name for platform_name in platform_names)

    # ----------------------------------------------------------------------
    def IsContainerEnvironment(self) -> bool:
        return self._is_nanoserver

    # ----------------------------------------------------------------------
    @staticmethod
    def RemoveDir(
        path: Path,
    ) -> None:
        if path.is_dir():
            os.system('rmdir /S /Q "{}"'.format(str(path)))

    # ----------------------------------------------------------------------
    @staticmethod
    def DecorateEnvironmentVariable(
        var_name: str,
    ) -> str:
        return "%{}%".format(var_name)

    # ----------------------------------------------------------------------
    @staticmethod
    def UpdateOwnership(
        file_or_directory: Path,  # pylint: disable=unused-argument
        *,
        recurse=False,  # pylint: disable=unused-argument
    ) -> None:
        # Nothing to do here
        pass

    # ----------------------------------------------------------------------
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
    @staticmethod
    def OnAugment(
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
    @classmethod
    def OnAugmentPath(
        cls,
        command: AugmentPath,
    ) -> Optional[str]:
        return cls.OnAugment(command)

    # ----------------------------------------------------------------------
    @classmethod
    def OnCall(
        cls,
        command: Call,
    ) -> Optional[str]:
        result = "call {}".format(command.command_line)
        if command.exit_on_error:
            result += "\n{}\n".format(cls.Accept(ExitOnError()))

        return result

    # ----------------------------------------------------------------------
    @staticmethod
    def OnCommandPrompt(
        command: CommandPrompt,
    ) -> Optional[str]:
        return "set PROMPT=({}) $P$G".format(command.prompt)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnComment(
        command: Comment,
    ) -> Optional[str]:
        return "REM {}".format(command.value)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnCopy(
        command: Copy,
    ) -> Optional[str]:
        return 'copy /T "{source}" "{dest}"'.format(
            source=command.source,
            dest=command.dest,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def OnDelete(
        command: Delete,
    ) -> Optional[str]:
        if command.is_dir:
            return 'rmdir /S /Q "{}"'.format(command.path)

        return 'del "{}"'.format(command.path)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnEchoOff(
        command: EchoOff,
    ) -> Optional[str]:
        return "@echo off"

    # ----------------------------------------------------------------------
    @classmethod
    def OnExecute(
        cls,
        command: Execute,
    ) -> Optional[str]:
        # Execute the command line with a special prefix if the command line invokes a .bat or .cmd file
        commands = shlex.split(command.command_line)

        if commands[0].endswith(".bat") or commands[0].endswith(".cmd"):
            result = "cmd /c {}".format(command.command_line)
        else:
            result = command.command_line

        if command.exit_on_error:
            result += "\n{}\n".format(cls.Accept(ExitOnError()))

        return result

    # ----------------------------------------------------------------------
    @staticmethod
    def OnExit(
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
    @staticmethod
    def OnExitOnError(
        command: ExitOnError,
    ) -> Optional[str]:
        variable_name = command.variable_name or "ERRORLEVEL"

        return "if %{}% NEQ 0 (exit /B {})".format(
            variable_name,
            command.return_code or "%{}%".format(variable_name),
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def OnMessage(
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
                output.append("echo.")
                continue

            line = line.replace("^", "__caret_placeholder__")

            for source, dest in substitution_lookup.items():
                line = line.replace(source, dest)

            line = line.replace("__caret_placeholder__", "^")

            output.append("echo {}".format(line))

        return " && ".join(output)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnMove(
        command: Move,
    ) -> Optional[str]:
        return 'move /Y "{source}" "{dest}"'.format(
            source=command.source,
            dest=command.dest,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def OnPersistError(
        command: PersistError,
    ) -> Optional[str]:
        return "set {}=%ERRORLEVEL%".format(command.variable_name)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnPopDirectory(
        command: PopDirectory,
    ) -> Optional[str]:
        return "popd"

    # ----------------------------------------------------------------------
    @staticmethod
    def OnPushDirectory(
        command: PushDirectory,
    ) -> Optional[str]:
        directory = command.value or "%~dp0"
        return 'pushd "{}"'.format(directory)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnRaw(
        command: Raw,
    ) -> Optional[str]:
        return command.value

    # ----------------------------------------------------------------------
    @staticmethod
    def OnSet(
        command: Set,
    ) -> Optional[str]:
        if command.value_or_values is None:
            return "SET {}=".format(command.name)

        return "SET {}={}".format(command.name, os.pathsep.join(command.EnumValues()))

    # ----------------------------------------------------------------------
    @classmethod
    def OnSetPath(
        cls,
        command: SetPath,
    ) -> Optional[str]:
        return cls.OnSet(command)

    # ----------------------------------------------------------------------
    @staticmethod
    def OnSymbolicLink(
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
