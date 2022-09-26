# ----------------------------------------------------------------------
# |
# |  Enlist.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-24 18:51:15
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enlistment activities for a repository and its dependencies."""

# This script serves to make Enlist.py discoverable, while still letting is reside in the appropriate
# location at ../RepositoryBootstrap/Impl/Enlist.py.

import os
import sys

from pathlib import Path
from typing import List

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import SubprocessEx


# ----------------------------------------------------------------------
def Execute(
    args: List[str],
) -> int:
    foundation_repo_root = Path(__file__).parent.parent
    assert foundation_repo_root.is_dir(), foundation_repo_root

    prev_dir = Path.cwd()
    os.chdir(foundation_repo_root)

    with ExitStack(lambda: os.chdir(prev_dir)):
        enlist_script_filename = Path("RepositoryBootstrap") / "Impl" / "Enlist.py"
        assert (foundation_repo_root / enlist_script_filename).is_file(), (foundation_repo_root, enlist_script_filename)

        if len(args) <= 2 or "--help" in args:
            working_dir = ""
        else:
            working_dir = ' --working-directory "{}"'.format(prev_dir)

        command_line = 'python -m "{script}"{args}{working_dir}'.format(
            script=".".join(enlist_script_filename.with_suffix("").parts),
            args=" {}".format(" ".join('"{}"'.format(arg) for arg in args[1:])) if len(args) > 1 else "",
            working_dir=working_dir,
        )

        return SubprocessEx.Stream(command_line, sys.stdout)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(Execute(sys.argv))
