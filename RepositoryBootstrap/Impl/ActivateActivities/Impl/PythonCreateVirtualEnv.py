# ----------------------------------------------------------------------
# |
# |  PythonCreateVirtualEnv.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 13:21:01
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Creates a python virtual environment"""

import os
import sys

from contextlib import ExitStack
from pathlib import Path
from typing import List

# Manually import functionality within Common_Foundation
from .... import Constants

import_path = os.getenv(Constants.DE_FOUNDATION_ROOT_NAME)
assert import_path is not None

import_path = Path(import_path) / Constants.LIBRARIES_SUBDIR / "Python" / "Common_Foundation" / "src"
assert import_path.is_dir(), import_path

sys.path.insert(0, str(import_path))
with ExitStack() as exit_stack:
    exit_stack.callback(lambda: sys.path.pop(0))

    from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags  # type: ignore
    from Common_Foundation import SubprocessEx  # type: ignore


# ----------------------------------------------------------------------
def EntryPoint(
    args: List[str],
) -> int:
    # Process the arguments
    assert len(args) >= 5, args

    path = Path(args[1])
    pip_version = args[2]
    setuptools_version = args[3]
    wheel_version = args[4]

    verbose: bool = False

    for arg in args[5:]:
        if arg == "--verbose":
            verbose = True
        else:
            assert False, arg

    # Execute
    with DoneManager.Create(
        sys.stdout,
        "Creating the Python virtual environment (this may take some time)...",
        suffix="\n" if verbose else "",
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
        ),
    ) as dm:
        result = SubprocessEx.Run(
            'python -m virtualenv --clear --no-periodic-update --no-vcs-ignore --verbose --pip "{pip_version}" --setuptools "{setuptools_version}" --wheel "{wheel_version}" "{virtual_env_dir}"'.format(
                pip_version=pip_version,
                setuptools_version=setuptools_version,
                wheel_version=wheel_version,
                virtual_env_dir=path,
            ),
        )

        dm.result = result.returncode

        if dm.result != 0:
            dm.WriteError(result.output)
        else:
            with dm.YieldVerboseStream() as stream:
                stream.write(result.output)

        return dm.result


# ----------------------------------------------------------------------
sys.exit(EntryPoint(sys.argv))
