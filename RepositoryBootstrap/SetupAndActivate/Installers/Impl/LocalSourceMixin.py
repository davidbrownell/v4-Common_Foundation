# ----------------------------------------------------------------------
# |
# |  LocalSourceMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 13:30:31
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the LocalSourceMixin object"""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod


# ----------------------------------------------------------------------
class LocalSourceMixin(object):
    """Mixin that provides install content via a local source"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        source_file: Path,
    ):
        self.source_file                    = source_file

    # ----------------------------------------------------------------------
    @overridemethod
    @contextmanager
    def _YieldInstallSource(
        self,
        dm: DoneManager,  # pylint: disable=unused-argument
    ) -> Iterator[Optional[Path]]:
        yield self.source_file
