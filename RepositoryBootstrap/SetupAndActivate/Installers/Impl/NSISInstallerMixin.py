# ----------------------------------------------------------------------
# |
# |  NSISInstallerMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 14:24:07
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the NSISInstallerMixin object"""

from pathlib import Path

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation.Types import overridemethod

from ..Installer import Installer


# ----------------------------------------------------------------------
class NSISInstallerMixin(Installer):
    """Installer that processes NSIS Installer files (https://nsis.sourceforge.io)"""

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _Install(
        self,
        dm: DoneManager,
        install_source: Path,
        *,
        is_interactive: bool=False,
    ) -> None:
        # Note that this command line is very particular; '/D=' must be the
        # last item and it cannot have quotes.
        #
        # More info: https://www.exemsi.com/documentation/installer-frameworks/nsis-nullsoft-scriptable-install-system/
        self.__class__._Execute(  # pylint: disable=protected-access
            dm,
            '"{}"{} /D={}'.format(
                install_source,
                " /S" if not is_interactive else "",
                self.output_dir,
            ),
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def _Uninstall(
        self,
        dm: DoneManager,
        *,
        is_interactive: bool=False,
    ) -> None:
        self.__class__._Execute(  # pylint: disable=protected-access
            dm,
            '"{}" uninstall{}'.format(
                self.output_dir / "Uninstall.exe",
                " /S" if not is_interactive else "",
            ),
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def _Execute(
        dm: DoneManager,
        command_line: str,
    ) -> None:
        result = SubprocessEx.Run(command_line)

        dm.result = result.returncode

        if dm.result != 0:
            dm.WriteError(result.output)
            return

        with dm.YieldVerboseStream() as stream:
            stream.write(result.output)
