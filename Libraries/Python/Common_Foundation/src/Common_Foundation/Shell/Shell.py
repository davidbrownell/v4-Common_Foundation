# ----------------------------------------------------------------------
# |
# |  Shell.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 14:14:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Shell object"""

import os
import re
import stat
import tempfile
import unicodedata

from abc import abstractmethod, ABC
from pathlib import Path
from typing import Generator, List, Optional, Set, Union

from .Commands import Command
from .CommandVisitor import CommandVisitor

from ..ContextlibEx import ExitStack
from .. import SubprocessEx


# ----------------------------------------------------------------------
class Shell(ABC):
    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the shell"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def family_name(self) -> str:
        """\
        While `name` is the OS, "family" is a more general concept that can cover multiple operating
        systems.

        Example:

            Operating System                name        family_name
            ------------------------------  ----------  ------------------
            Ubuntu 22.04                    Ubuntu      Linux
            Ubuntu 18.04                    Ubuntu      Linux
            Windows 11                      Windows     Windows
            Windows 10                      Windows     Windows

        """
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def script_extensions(self) -> List[str]:
        """File extensions used to identify scripts"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def executable_extensions(self) -> Optional[List[str]]:
        """File extensions used to identify executables"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def compression_extensions(self) -> Optional[List[str]]:
        """File extensions used to identify compressed files"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def all_arguments_script_variable(self) -> str:
        """Convention used to indicate all variables should be passed to a script. (e.g. "%*" or "$@")"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def has_case_sensitive_file_system(self) -> bool:
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def supported_architectures(self) -> List[str]:
        """Potential architecture values (e.g. "x64", "x86", etc.)"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def current_architecture(self) -> str:
        """Returns the current architecture"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def user_directory(self) -> Path:
        """Directory associated with the active user account"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def temp_directory(self) -> Path:
        """Directory associated with temporary content"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def path_sep(self) -> str:
        """Path separator"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def command_visitor(self) -> CommandVisitor:
        """CommandVisitor used to process commands for the derived object."""
        raise Exception("Abstract property")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Methods
    # |
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def IsActive(
        platform_names: Set[str],
    ) -> bool:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def IsContainerEnvironment() -> bool:
        """Return True if we are running within a container"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def RemoveDir(
        path: Path
    ) -> None:
        """Removes a directory in the most efficient way possible"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def DecorateEnvironmentVariable(
        var_name: str,
    ) -> str:
        """Returns a var name that is decorated so that it can be used in a script"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def UpdateOwnership(
        file_or_directory: Path,
        *,
        recurse=False,
    ) -> None:
        """Updates the ownership of a file or a directory to the current (non-admin) user when running as sudo"""
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    def GenerateCommands(
        self,
        command_or_commands: Union[None, Command, List[Command]],
        *,
        no_prefix: bool=False,
        no_suffix: bool=False,
    ) -> str:
        if command_or_commands is None:
            return ""

        if isinstance(command_or_commands, list):
            commands = command_or_commands
        else:
            commands = [command_or_commands, ]

        results: List[str] = []

        if not no_prefix:
            prefix = self._GeneratePrefixContent()  # pylint: disable=assignment-from-none
            if prefix:
                results.append(prefix)

        visitor = self.command_visitor

        for command in commands:
            result = visitor.Accept(command)
            if result:
                results.append(result)

        if not no_suffix:
            suffix = self._GenerateSuffixContent()  # pylint: disable=assignment-from-none
            if suffix:
                results.append(suffix)

        return "\n".join(results)

    # ----------------------------------------------------------------------
    def ExecuteCommands(
        self,
        command_or_commands: Union[Command, List[Command]],
    ) -> str:
        """\
        Creates a temporary script file, writes the commands to that file,
        and then executes it. Returns the result and output generated during
        execution.
        """

        temp_filename = self.CreateTempFilename(self.script_extensions[0])

        with temp_filename.open("w") as f:
            f.write(self.GenerateCommands(command_or_commands))

        with ExitStack(temp_filename.unlink):
            self.MakeFileExecutable(temp_filename)

            return SubprocessEx.Run(str(temp_filename)).output

    # ----------------------------------------------------------------------
    def EnumEnvironmentVariableValues(
        self,
        name: str,
    ) -> Generator[str, None, None]:
        """Enumerates all of the values within an environment variable"""

        value = os.getenv(name)
        if value is None:
            return

        for item in value.split(os.pathsep):
            item = item.strip()
            if item:
                yield item

    # ----------------------------------------------------------------------
    def ScrubFilename(
        self,
        filename: str,
        replace_char: str="_",
    ) -> str:
        """Returns a filename where all invalid characters have been replaced with the provided char"""

        # Taken from https://github.com/django/django/blob/master/django/utils/text.py
        # Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
        # dashes to single dashes. Remove characters that aren't alphanumerics,
        # underscores, or hyphens. Convert to lowercase. Also strip leading and
        # trailing whitespace, dashes, and underscores.
        filename = unicodedata.normalize('NFKD', filename).encode('ascii', 'ignore').decode('ascii')

        filename = re.sub(r'[^\w\s\-\(\)\[\]\.]', replace_char, filename)
        return filename

    # ----------------------------------------------------------------------
    def CreateTempFilename(
        self,
        suffix: Optional[str]=None,
    ) -> Path:
        filename_handle, filename = tempfile.mkstemp(suffix=suffix)

        os.close(filename_handle)
        os.remove(filename)

        return Path(filename)

    # ----------------------------------------------------------------------
    def CreateTempDirectory(
        self,
        suffix: Optional[str]=None,
        *,
        create_dir: bool=True,
    ) -> Path:
        directory = self.CreateTempFilename(suffix=suffix)

        if create_dir:
            directory.mkdir(parents=True)

        return directory

    # ----------------------------------------------------------------------
    def MakeFileExecutable(
        self,
        filename: Path,
    ) -> None:
        assert filename.is_file(), filename
        filename.chmod(stat.S_IXUSR | stat.S_IWUSR | stat.S_IRUSR)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # @extensionmethod
    def _GeneratePrefixContent(self) -> Optional[str]:
        return None

    # ----------------------------------------------------------------------
    # @extensionmethod
    def _GenerateSuffixContent(self) -> Optional[str]:
        return None
