# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-09 09:15:01
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds github content"""

import os
import sys

from pathlib import Path

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation import Types

foundation_root_dir = PathEx.EnsureDir(Path(Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION"))))

github_src_root = PathEx.EnsureDir(foundation_root_dir / ".github" / "src")

sys.path.insert(0, str(github_src_root))
with ExitStack(lambda: sys.path.pop(0)):
    from BuildImpl import CreateBuildInfoInstance  # type: ignore


# ----------------------------------------------------------------------
_build_info = CreateBuildInfoInstance(Path(__file__).parent)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    _build_info.Run()
