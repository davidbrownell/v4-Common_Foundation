# ----------------------------------------------------------------------
# |
# |  LocalSevenZipInstaller.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 14:06:54
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the LocalSevenZipInstaller object"""

from pathlib import Path
from typing import Union

from semantic_version import Version as SemVer

from .Impl.LocalSourceMixin import LocalSourceMixin
from .Impl.SevenZipInstallerArchiveMixin import SevenZipInstallerArchiveMixin


# ----------------------------------------------------------------------
class LocalSevenZipInstaller(
    LocalSourceMixin,
    SevenZipInstallerArchiveMixin,
):
    """Installs local content using 7zip"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        install_filename: Path,
        tool_dir: Path,
        required_version: Union[None, SemVer, str],
    ):
        LocalSourceMixin.__init__(self, install_filename)
        SevenZipInstallerArchiveMixin.__init__(self, tool_dir, required_version)
