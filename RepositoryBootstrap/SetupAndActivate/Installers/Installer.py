# ----------------------------------------------------------------------
# |
# |  Installer.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-06 15:39:38
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Installer object"""

import math
import os
import textwrap
import time

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional, Union

from semantic_version import Version as SemVer

from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import RegularExpression
from Common_Foundation import Types

from ... import Constants


# ----------------------------------------------------------------------
class Installer(ABC):
    """Abstract concept of an entity that is able to install/uninstall components"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        tool_dir: Path,
        required_version: Union[None, SemVer, str],
        *,
        # Write the installed sentinel in the tool root (which is the parent of installed_root) rather than the install dir.
        # Set this to True when the installed root is read-only.
        sentinel_lives_in_tool_root: bool=False,
    ):
        self.tool_dir                                   = tool_dir
        self.output_dir                                 = tool_dir / Types.EnsureValid(os.getenv(Constants.DE_ENVIRONMENT_NAME))
        self.required_version: Optional[str]            = None if required_version is None else str(required_version)
        self.sentinel_lives_in_tool_root                = sentinel_lives_in_tool_root

    # ----------------------------------------------------------------------
    def Install(
        self,
        dm: DoneManager,
        *,
        force: bool=False,
        prompt_for_interactive: bool=False,
    ) -> None:
        sentinel_filename = self._GetSentinelFilename(self.tool_dir, sentinel_in_tool_root=self.sentinel_lives_in_tool_root)

        if not force and not self._ShouldInstall(dm, sentinel_filename):
            dm.WriteVerbose(
                "'{}' exists and is up-to-date{}.\n".format(
                    sentinel_filename,
                    "" if not self.required_version else " with version '{}'".format(self.required_version),
                ),
            )

            return

        if prompt_for_interactive:
            is_interactive = self.__class__._PromptForInteractive(dm)  # pylint: disable=protected-access
        else:
            is_interactive = False

        with self._YieldInstallSource(dm) as install_source:
            if install_source is None:
                return

            if self.output_dir.is_dir():
                self._UninstallImpl(
                    dm,
                    sentinel_filename,
                    is_interactive,
                )

            with dm.Nested("Installing...") as install_dm:
                self._Install(
                    install_dm,
                    install_source,
                    is_interactive=is_interactive,
                )

                if install_dm.result != 0:
                    return

            with dm.Nested("Writing '{}'...".format(sentinel_filename)):
                with sentinel_filename.open("w") as f:
                    if self.required_version is None:
                        f.write("Installation was successful.\n")
                    else:
                        f.write(self.__class__._versioned_sentinel_content.format(version=self.required_version))  # pylint: disable=protected-access

    # ----------------------------------------------------------------------
    def Uninstall(
        self,
        dm: DoneManager,
        *,
        prompt_for_interactive: bool=False,
    ) -> None:
        sentinel_filename = self._GetSentinelFilename(self.tool_dir, sentinel_in_tool_root=self.sentinel_lives_in_tool_root)

        if sentinel_filename.is_file():
            if prompt_for_interactive:
                is_interactive = self.__class__._PromptForInteractive(dm)  # pylint: disable=protected-access
            else:
                is_interactive = False

            self._UninstallImpl(dm, sentinel_filename, is_interactive)

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    @contextmanager
    def _YieldInstallSource(
        self,
        dm: DoneManager,
    ) -> Iterator[Optional[Path]]:
        """Generates the install source"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _Install(
        self,
        dm: DoneManager,
        install_source: Path,
        *,
        is_interactive: bool=False,
    ) -> None:
        """Installs content"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _Uninstall(
        self,
        dm: DoneManager,
        *,
        is_interactive: bool=False,
    ) -> None:
        """Uninstalls content"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    def _UninstallImpl(
        self,
        dm: DoneManager,
        sentinel_filename: Path,
        is_interactive: bool,
    ) -> None:
        if sentinel_filename.is_file():
            with dm.Nested("Uninstalling...") as uninstall_dm:
                self._Uninstall(uninstall_dm, is_interactive=is_interactive)

            if sentinel_filename.is_file():
                with dm.Nested("Removing '{}'...".format(sentinel_filename)):
                    sentinel_filename.unlink()

    # ----------------------------------------------------------------------
    @staticmethod
    def _PromptForInteractive(
        dm: DoneManager,
        wait_seconds: int=5,
        prompt: str="Press any key to enable an interactive experience",
    ) -> bool:
        if CurrentShell.family_name != "Windows":
            return False

        # Importing msvcrt here, as it is only available on Windows and we don't want to
        # see an import error when attempting to activate the environment on Windows;
        # we want to see other, more informative errors in that scenario.
        import msvcrt

        # By default, the tools will install without user intervention, but this becomes
        # problematic when there are errors during install as the UX goes away and the
        # error information is only available by perusing the setup log files. Create
        # an experience where the install will proceeded without intervention by default,
        # but let's the user select an interactive installation if they want it within
        # a relatively short period of time.
        interactive_install = False

        with dm.YieldStdout() as stdout_content:
            stdout_content.persist_content = False

            # ----------------------------------------------------------------------
            def GetDisplayString(
                time_remaining: float,
            ) -> str:
                seconds_remaining = int(math.ceil(time_remaining))

                return "\r{}{} ({} remaining)  ".format(
                    stdout_content.line_prefix,
                    prompt,
                    "{} {}".format(
                        seconds_remaining,
                        "seconds" if seconds_remaining != 1 else "second",
                    ),
                )

            # ----------------------------------------------------------------------

            wait_seconds = 5
            start_time = time.perf_counter()

            while True:
                if msvcrt.kbhit():
                    msvcrt.getch()

                    interactive_install = True
                    break

                elapsed_time = time.perf_counter() - start_time
                if elapsed_time > wait_seconds:
                    break

                stdout_content.stream.write(GetDisplayString(wait_seconds - elapsed_time))

            stdout_content.stream.write(
                "\r{}\r".format(" " * len(GetDisplayString(0))),
            )

        return interactive_install

    # ----------------------------------------------------------------------
    def _ShouldInstall(
        self,
        dm: DoneManager,
        sentinel_filename: Path,
    ) -> bool:
        if not sentinel_filename.is_file():
            dm.WriteVerbose("'{}' does not exist.\n".format(sentinel_filename))
            return True

        if self.required_version:
            with sentinel_filename.open() as f:
                content = f.read()

            match = RegularExpression.TemplateStringToRegex(self.__class__._versioned_sentinel_content).match(content)  # pylint: disable=protected-access
            if not match:
                dm.WriteVerbose("'{}' was not versioned.\n".format(sentinel_filename))
                return True

            previous_version = match.group("version")

            if previous_version != self.required_version:
                dm.WriteInfo("The version '{}' does not match the required version '{}'.\n".format(previous_version, self.required_version))
                return True

        if not self.output_dir.is_dir():
            dm.WriteVerbose("'{}' does not exist.\n".format(self.output_dir))
            return True

        return False

    # ----------------------------------------------------------------------
    def _GetSentinelFilename(
        self,
        tool_dir: Path,
        *,
        sentinel_in_tool_root: bool=False,
    ) -> Path:
        if sentinel_in_tool_root:
            environment_name = Types.EnsureValid(os.getenv(Constants.DE_ENVIRONMENT_NAME))
            return tool_dir / "SuccessfulInstallation.{}.txt".format(environment_name)

        return self.output_dir / "SuccessfulInstallation.txt"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _versioned_sentinel_content                 = textwrap.dedent(
        """\
            Installation of '{version}' was successful.
        """,
    )
