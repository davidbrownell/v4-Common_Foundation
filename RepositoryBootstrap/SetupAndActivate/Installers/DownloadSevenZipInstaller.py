# ----------------------------------------------------------------------
# |
# |  DownloadSevenZipInstaller.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-14 15:45:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the DownloadSevenZipInstaller object"""

from pathlib import Path
from typing import Optional, Union

from semantic_version import Version as SemVer

from .Impl.DownloadSourceMixin import DownloadSourceMixin
from .Impl.SevenZipInstallerArchiveMixin import SevenZipInstallerArchiveMixin


# ----------------------------------------------------------------------
class DownloadSevenZipInstaller(
    DownloadSourceMixin,
    SevenZipInstallerArchiveMixin,
):
    """Downloads and installs zip content"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        url: str,
        sha256: Optional[str],
        tool_dir: Path,
        required_version: Union[None, SemVer, str],
    ):
        DownloadSourceMixin.__init__(self, url, sha256)
        SevenZipInstallerArchiveMixin.__init__(self, tool_dir, required_version)
