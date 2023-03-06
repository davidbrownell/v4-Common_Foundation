# ----------------------------------------------------------------------
# |
# |  PullRequestValidator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-06 13:32:07
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Validates pull requests."""

# This script serves to make PullRequestValidator.py accessible as a script, while still letting it reside
# it its logical location at ../RepositoryBootstrap/Impl/PullRequestValidator.py.

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
        script_filename = Path("RepositoryBootstrap") / "Impl" / "PullRequestValidator.py"
        assert (foundation_repo_root / script_filename).is_file(), (foundation_repo_root, script_filename)

        if len(args) <= 1 or "--help" in args:
            working_dir = ""
        else:
            working_dir = ' --working-directory "{}"'.format(prev_dir)

        command_line = 'python -m "{script}"{args}{working_dir}'.format(
            script=".".join(script_filename.with_suffix("").parts),
            args=" {}".format(" ".join('"{}"'.format(arg) for arg in args[1:])) if len(args) > 1 else "",
            working_dir=working_dir,
        )

        return SubprocessEx.Stream(command_line, sys.stdout)


# ----------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(Execute(sys.argv))
