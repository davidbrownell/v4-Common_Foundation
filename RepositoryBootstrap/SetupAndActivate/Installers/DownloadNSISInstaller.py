# ----------------------------------------------------------------------
# |
# |  DownloadNSISInstaller.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 14:23:24
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the DownloadNSISInstaller object"""

from pathlib import Path
from typing import Optional, Union

from semantic_version import Version as SemVer

from .Impl.DownloadSourceMixin import DownloadSourceMixin
from .Impl.NSISInstallerMixin import NSISInstallerMixin


# ----------------------------------------------------------------------
class DownloadNSISInstaller(
    DownloadSourceMixin,
    NSISInstallerMixin,
):
    """Downloads and installs NSIS content"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        url: str,
        sha256: Optional[str],
        tool_dir: Path,
        required_version: Union[None, SemVer, str],
    ):
        DownloadSourceMixin.__init__(self, url, sha256)
        NSISInstallerMixin.__init__(self, tool_dir, required_version)
