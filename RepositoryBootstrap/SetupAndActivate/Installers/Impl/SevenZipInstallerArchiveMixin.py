# ----------------------------------------------------------------------
# |
# |  SevenZipArchiveMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 13:57:07
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the SevenZipInstallerArchiveMixin object"""

from pathlib import Path

from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Types import overridemethod

from .ArchiveMixinImpl import ArchiveMixinImpl


# ----------------------------------------------------------------------
class SevenZipInstallerArchiveMixin(ArchiveMixinImpl):
    """Installs content by extracting a 7zip archive"""

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetInstallCommandLine(
        self,
        install_source: Path,
    ) -> str:
        if CurrentShell.family_name == "Windows":
            return '7z x -y "-o{}" {}'.format(self.output_dir, install_source.name)

        return '7zz x -y "-o{}" {}'.format(self.output_dir, install_source.name)
