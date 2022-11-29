# ----------------------------------------------------------------------
# |
# |  EnumSource.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-06 14:39:57
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains utilities helpful when locally enumerating source code"""

import os

from pathlib import Path
from typing import Callable, Generator, List, Optional, Tuple

from .SourceControlManagers.All import ALL_SCMS


# ----------------------------------------------------------------------
def IsSCMWorkingDir(
    path: Path,
) -> bool:
    """Returns True if the path is a SCM working directory"""

    return (
        path.is_dir()
        and any(path.name in (scm.working_directories or []) for scm in ALL_SCMS)
    )


# ----------------------------------------------------------------------
def IsGeneratedDir(
    path: Path,
) -> bool:
    """Returns True if the path is a Generated directory"""

    return path.is_dir() and path.name == "Generated"


# ----------------------------------------------------------------------
def IsToolsDir(
    path: Path,
) -> bool:
    """Returns True if the path is a Tools directory"""

    return path.is_dir() and path.name == "Tools" and (path.parent / "__RepositoryId__").is_file()


# ----------------------------------------------------------------------
def IsPycacheDir(
    path: Path,
) -> bool:
    """Returns True if the path is a python cache"""

    return path.is_dir() and path.name == "__pycache__"


# ----------------------------------------------------------------------
def IsDetailsDir(
    path: Path,
) -> bool:
    """Returns True if the path is a directory that ends with 'Details'"""

    return path.is_dir() and path.name.lower().endswith("details")


# ----------------------------------------------------------------------
def IsImplDir(
    path: Path,
) -> bool:
    """Returns True if the path is a directory that ends with 'Impl'"""

    return path.is_dir() and path.name.lower().endswith("impl")


# ----------------------------------------------------------------------
DEFAULT_SKIP_FUNCS: List[Callable[[Path], bool]]        = [
    IsSCMWorkingDir,
    IsGeneratedDir,
    IsToolsDir,
    IsPycacheDir,
]

ALL_SKIP_FUNCS: List[Callable[[Path], bool]]            = DEFAULT_SKIP_FUNCS + [
    IsDetailsDir,
    IsImplDir
]


# ----------------------------------------------------------------------
def EnumSource(
    root_dir: Path,
    skip_funcs: Optional[List[Callable[[Path], bool]]]=None,
) -> Generator[Tuple[Path, List[str], List[str]], None, None]:
    """\
    Enumerates source similar to os.walk, but avoid traversing into directories that are black
    holes of not-very-useful content.
    """

    skip_funcs = skip_funcs or DEFAULT_SKIP_FUNCS

    for root, directories, filenames in os.walk(root_dir):
        root = Path(root)

        if any(skip_func(root) for skip_func in skip_funcs):
            directories[:] = []
            continue

        yield root, directories, filenames
