# ----------------------------------------------------------------------
# |
# |  LinuxShellImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 18:58:31
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the LinuxShellImpl object"""

import os
import textwrap

from pathlib import Path
from typing import List, Optional, Set as SetType

from ..Commands import (
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
    WindowTitle,
)

from ..CommandVisitor import CommandVisitor
from ..Shell import Shell
from ...Types import overridemethod


# ----------------------------------------------------------------------
class LinuxShellImpl(Shell):
    """Implements common Linux functionality"""

    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def family_name(self) -> str:
        return "Linux"

    @property
    def script_extensions(self) -> List[str]:
        return [".sh", ]

    @property
    def executable_extensions(self) -> Optional[List[str]]:
        return None

    @property
    def compression_extensions(self) -> Optional[List[str]]:
        return [".tgz", ".tar", ".gz"]

    @property
    def all_arguments_script_variable(self) -> str:
        return "$@"

    @property
    def has_case_sensitive_file_system(self) -> bool:
        return True

    @property
    def supported_architectures(self) -> List[str]:
        return ["x64"]

    @property
    def current_architecture(self) -> str:
        return "x64"

    @property
    def user_directory(self) -> Path:
        return Path(os.path.expanduser("~"))

    @property
    def temp_directory(self) -> Path:
        return Path("/tmp")

    @property
    def path_sep(self) -> str:
        return "/"

    @property
    def command_visitor(self) -> CommandVisitor:
        return self._command_visitor

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    def __init__(self):
        self._command_visitor               = LinuxCommandVisitor()

    # ----------------------------------------------------------------------
    @overridemethod
    def IsActive(
        self,
        platform_names: SetType[str],
    ) -> bool:
        return self.name.lower() in platform_names

    # ----------------------------------------------------------------------
    @overridemethod
    def IsContainerEnvironment(self) -> bool:
        # Hard-coded for docker
        return Path("/.dockerenv").is_file()

    # ----------------------------------------------------------------------
    @overridemethod
    def RemoveDir(
        self,
        path: Path,
    ) -> None:
        if path.is_dir():
            os.system('rm -Rfd "{}"'.format(str(path)))

    # ----------------------------------------------------------------------
    @overridemethod
    def DecorateEnvironmentVariable(
        self,
        var_name: str,
    ) -> str:
        return "${}".format(var_name)

    # ----------------------------------------------------------------------
    @overridemethod
    def UpdateOwnership(
        self,
        file_or_directory: Path,  # pylint: disable=unused-argument
        *,
        recurse: bool=False,
    ) -> None:
        if (
            hasattr(os, "geteuid")
            and os.geteuid() == 0  # type: ignore  # pylint: disable=no-member
            and not any(var for var in ["SUDO_UID", "SUDO_GID"] if var not in os.environ)
        ):
            os.system(
                'chown {recurse} {user}:{group} "{input}"'.format(
                    # '--recurse' is not available on all systems, so changing to '-R'
                    recurse="-R" if recurse and file_or_directory.is_dir() else "",
                    user=os.environ["SUDO_UID"],
                    group=os.environ["SUDO_GID"],
                    input=str(file_or_directory),
                ),
            )

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _GeneratePrefixContent(self) -> Optional[str]:
        return "#!/bin/bash"

    # ----------------------------------------------------------------------
    @overridemethod
    def _GenerateSuffixContent(self) -> Optional[str]:
        return None


# ----------------------------------------------------------------------
class LinuxCommandVisitor(CommandVisitor):
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
            add_statement_template = "${{{name}}}{sep}{value}"
        else:
            add_statement_template = "{value}{sep}${{{name}}}"

        statement_template = 'export {name}="{add_statement}"'

        if not command.simple_format:
            statement_template = '[[ "{sep}${{{name}}}{sep}" != *"{sep}{value}{sep}"* ]] && ' + statement_template

        statements = [
            statement_template.format(
                name=command.name,
                value=value,
                sep=sep,
                add_statement=add_statement_template.format(
                    name=command.name,
                    value=value,
                    sep=sep,
                ),
            ) for value in command.EnumValues()
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
        result = "source {}".format(command.command_line)

        if command.exit_on_error:
            result += "\n{}\n".format(
                self.Accept(
                    ExitOnError(
                        use_return_statement=command.exit_via_return_statement,
                    ),
                ),
            )

        return result

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCommandPrompt(
        self,
        command: CommandPrompt,
    ) -> Optional[str]:
        if command.is_prefix:
            return r'PS1="{}$PS1"'.format(
                "({}) ".format(command.prompt),
            )

        return r'PS1=$PS1{}'.format(
            " ({})".format(command.prompt),
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnComment(
        self,
        command: Comment,
    ) -> Optional[str]:
        return "# {}".format(command.value)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnCopy(
        self,
        command: Copy,
    ) -> Optional[str]:
        return 'cp "{source}" "{dest}"'.format(
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
            return 'rm -Rfd "{}"'.format(str(command.path))

        return 'rm -f "{}"'.format(str(command.path))

    # ----------------------------------------------------------------------
    @overridemethod
    def OnEchoOff(
        self,
        command: EchoOff,  # pylint: disable=unused-argument
    ) -> Optional[str]:
        return "set +x"

    # ----------------------------------------------------------------------
    @overridemethod
    def OnExecute(
        self,
        command: Execute,
    ) -> Optional[str]:
        result = command.command_line
        if command.exit_on_error:
            result += "\n{}\n".format(
                self.Accept(
                    ExitOnError(
                        use_return_statement=command.exit_via_return_statement,
                    ),
                ),
            )

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
            return {return_code}
            """,
        ).format(
            success=textwrap.dedent(
                """\
                if [[ $? -eq 0 ]]
                then
                    read -p "Press [Enter] to continue"
                fi
                """,
            ) if command.pause_on_success else "",
            error=textwrap.dedent(
                """\
                if [[ $? -ne 0]]
                then
                    read -p "Press [Enter] to continue"
                fi
                """,
            ) if command.pause_on_error else "",
            return_code=command.return_code or 0,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnExitOnError(
        self,
        command: ExitOnError,
    ) -> Optional[str]:
        variable_name = "${}".format(command.variable_name) if command.variable_name else "$?"

        return textwrap.dedent(
            """\
            error_code={variable_name}
            if [[ $error_code -ne 0 ]]
            then
                {exit_statement} {return_code}
            fi
            """,
        ).format(
            variable_name=variable_name,
            exit_statement="return" if command.use_return_statement else "exit",
            return_code=command.return_code or "$error_code",
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnMessage(
        self,
        command: Message,
    ) -> Optional[str]:
        substitution_lookup = {
            "$": r"\$",
            '"': r"\"",
            '`': r"\\\`",
        }

        output: List[str] = []

        for line in command.value.split("\n"):
            if not line.strip():
                output.append('echo ""')
                continue

            for source, dest in substitution_lookup.items():
                line = line.replace(source, dest)

            output.append('echo "{}"'.format(line))

        return " && ".join(output)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnMove(
        self,
        command: Move,
    ) -> Optional[str]:
        return 'mv "{source}" "{dest}"'.format(
            source=command.source,
            dest=command.dest,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPersistError(
        self,
        command: PersistError,
    ) -> Optional[str]:
        return "{}=$?".format(command.variable_name)

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPopDirectory(
        self,
        command: PopDirectory,  # pylint: disable=unused-argument
    ) -> Optional[str]:
        return "popd > /dev/null"

    # ----------------------------------------------------------------------
    @overridemethod
    def OnPushDirectory(
        self,
        command: PushDirectory,
    ) -> Optional[str]:
        directory = command.value

        if directory is None:
            directory = """$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"""
        else:
            directory = str(directory)

        return 'pushd "{}" > /dev/null'.format(directory)

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
            return "unset {}".format(command.name)

        values = os.pathsep.join(command.EnumValues())
        if values.startswith('"'):
            values = values[1:]
        if values.endswith('"'):
            values = values[:-1]

        return 'export {}="{}"'.format(command.name, values)

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
        return textwrap.dedent(
            """\
            ln -{force_flag}{dir_flag}{relative_flag}s "{target}" "{link}"
            """,
        ).format(
            force_flag="" if not command.remove_existing else "f",
            dir_flag="d" if command.is_dir else "",
            relative_flag="r" if command.relative_path else "",
            target=command.target,
            link=command.link_filename,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def OnWindowTitle(
        self,
        command: WindowTitle,
    ) -> Optional[str]:
        # I'm not sure how to do this consistently across distros and terminal
        # types on Linux.
        return None
