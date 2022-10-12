# ----------------------------------------------------------------------
# |
# |  ArchiveMixinImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 13:50:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ArchiveMixinImpl object"""

from abc import abstractmethod
from pathlib import Path

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from ..Installer import Installer


# ----------------------------------------------------------------------
class ArchiveMixinImpl(Installer):
    """Installer that is implemented by unpacking an archive"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(ArchiveMixinImpl, self).__init__(
            *args,
            **{
                **kwargs,
                **{
                    "sentinel_lives_in_tool_root": False,
                },
            },
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _Install(
        self,
        dm: DoneManager,
        install_source: Path,
        *,
        is_interactive: bool=False,  # pylint: disable=unused-argument
    ) -> None:
        command_line = self._GetInstallCommandLine(install_source)

        result = SubprocessEx.Run(
            command_line,
            cwd=install_source.parent,
        )

        dm.result = result.returncode

        if dm.result != 0:
            dm.WriteError(result.output)
            return

        with dm.YieldVerboseStream() as stream:
            stream.write(result.output)

    # ----------------------------------------------------------------------
    @overridemethod
    def _Uninstall(
        self,
        dm: DoneManager,
        *,
        is_interactive: bool=False,  # pylint: disable=unused-argument
    ) -> None:
        if not self.output_dir.is_dir():
            return

        with dm.Nested("Removing '{}'...".format(self.output_dir)):
            PathEx.RemoveTree(self.output_dir)

    # ----------------------------------------------------------------------
    @abstractmethod
    def _GetInstallCommandLine(
        self,
        install_source: Path,
    ) -> str:
        """Returns the command line used to extract the archive"""
        raise Exception("Abstract method")
