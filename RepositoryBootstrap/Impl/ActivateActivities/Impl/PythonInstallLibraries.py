# ----------------------------------------------------------------------
# |
# |  PythonInstallLibraries.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 11:33:48
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Installs internal python libraries in editable mode"""

import json
import os
import sys

from contextlib import ExitStack
from pathlib import Path
from typing import List, Set

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
    assert len(args) >= 2, args

    path = Path(args[1])
    assert path.is_file(), path

    debug: bool = False
    verbose: bool = False

    for arg in args[2:]:
        if arg == "--debug":
            debug = True
        elif arg == "--verbose":
            verbose = True
        else:
            assert False, arg

    # Execute

    # ----------------------------------------------------------------------
    def LibraryPlural(
        count: int,
    ) -> str:
        # Normally, I'd use inflect for this type of thing but this code will
        # be invoked before inflect is available.
        return "library" if count == 1 else "libraries"

    # ----------------------------------------------------------------------

    with DoneManager.Create(
        sys.stdout,
        "Installing internal Python libraries (this may take some time)...",
        lambda: "{} internal {} available".format(
            len(possible_libraries),
            LibraryPlural(len(possible_libraries)),
        ),
        suffix="\n",
        output_flags=DoneManagerFlags.Create(
            verbose=verbose,
            debug=debug,
        ),
    ) as dm:
        possible_libraries: Set[Path] = set()

        # Get the possible libraries
        with dm.VerboseNested(
            "Calculating all potential internal libraries...",
            lambda: "{} {} found".format(
                len(possible_libraries),
                LibraryPlural(len(possible_libraries)),
            ),
            suffix="\n",
        ) as potential_dm:
            with path.open() as f:
                for path in f.readlines():
                    path = path.strip()

                    potential_dm.WriteLine("- {}\n".format(path))
                    possible_libraries.add(Path(path))

            if not possible_libraries:
                return dm.result

        # Get the installed libraries
        installed_libraries: Set[Path] = set()

        with dm.VerboseNested(
            "Calculating all installed internal libraries...",
            lambda: "{} {} found".format(
                len(installed_libraries),
                LibraryPlural(len(installed_libraries)),
            ),
            suffix="\n",
        ) as installed_dm:
            # PYTHONPATH in the environment prevents `pip list` from working as expected
            environ = os.environ.copy()
            environ.pop("PYTHONPATH", None)

            result = SubprocessEx.Run(
                "python -m pip list --verbose --format json --require-virtualenv --editable",
                env=environ,
            )

            installed_dm.result = result.returncode

            if installed_dm.result != 0:
                installed_dm.WriteError(result.output)

                return installed_dm.result

            installed_dm.WriteDebug(result.output)

            content = json.loads(result.output)

            for item in content:
                path = Path(item["editable_project_location"]).resolve()

                if path.name == "src":
                    path = path.parent

                installed_dm.WriteLine("- {}\n".format(str(path)))

                installed_libraries.add(path)

        # Get the libraries to install
        libraries_to_install: Set[Path] = set()

        with dm.VerboseNested(
            "Calculating libraries to install...",
            lambda: "{} {} to install".format(
                len(libraries_to_install),
                LibraryPlural(len(libraries_to_install)),
            ),
            suffix="\n",
        ):
            libraries_to_install = possible_libraries.difference(installed_libraries)

            if not libraries_to_install:
                return dm.result

        # Install the libraries
        with dm.Nested("Installing libraries...") as install_dm:
            for library_index, library in enumerate(libraries_to_install):
                with install_dm.Nested(
                    "'{}' ({} of {})...".format(
                        library,
                        library_index + 1,
                        len(libraries_to_install),
                    ),
                ) as this_install_dm:
                    result = SubprocessEx.Run(
                        'python -m pip install --require-virtualenv --disable-pip-version-check --editable "{}"'.format(
                            library,
                        ),
                    )

                    this_install_dm.result = result.returncode

                    if this_install_dm.result != 0:
                        this_install_dm.WriteError(result.output)
                    else:
                        with this_install_dm.YieldVerboseStream() as stream:
                            stream.write(result.output)

            return dm.result


# ----------------------------------------------------------------------
sys.exit(EntryPoint(sys.argv))
