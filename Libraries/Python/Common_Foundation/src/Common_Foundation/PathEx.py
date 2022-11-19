# ----------------------------------------------------------------------
# |
# |  PathEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 10:22:42
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements to the awesome Path object"""

import shutil
import time

from pathlib import Path, PurePath
from typing import Callable, Optional

from .Shell.All import CurrentShell


# ----------------------------------------------------------------------
def EnsureExists(
    path: Optional[Path],
) -> Path:
    assert path is not None and path.exists(), path
    return path


# ----------------------------------------------------------------------
def EnsureFile(
    path: Optional[Path],
) -> Path:
    assert path is not None and path.is_file(), path
    return path


# ----------------------------------------------------------------------
def EnsureDir(
    path: Optional[Path],
) -> Path:
    assert path is not None and path.is_dir(), path
    return path


# ----------------------------------------------------------------------
def IsDescendant(
    query: PurePath,
    root: PurePath,
) -> bool:
    """Returns True if `query` is a descendant of `root`"""

    root_parts_length = len(root.parts)

    if len(query.parts) < root_parts_length:
        return False

    index = 0

    while index < root_parts_length:
        if query.parts[index] != root.parts[index]:
            return False

        index += 1

    return True


# ----------------------------------------------------------------------
def CreateRelativePath(
    from_path: PurePath,
    to_path: PurePath,
) -> PurePath:
    from_parts_length = len(from_path.parts)
    to_parts_length = len(to_path.parts)

    min_length = min(from_parts_length, to_parts_length)

    matching_index = 0

    while matching_index < min_length:
        if from_path.parts[matching_index] != to_path.parts[matching_index]:
            break

        matching_index += 1

    relative_path = PurePath(".")

    if matching_index < from_parts_length:
        relative_path = relative_path.joinpath(*(["..",] * (from_parts_length - matching_index)))

    if matching_index < to_parts_length:
        relative_path = relative_path.joinpath(*to_path.parts[matching_index:])

    return relative_path


# ----------------------------------------------------------------------
def GetCommonPath(
    *path_args: Path,
) -> Optional[Path]:
    paths = [path.resolve() for path in path_args]

    if len(paths) == 1:
        if paths[0].is_dir():
            return paths[0]

        return paths[0].parent

    path_index = 0

    while True:
        if path_index > len(paths[0].parts) - 1:
            break

        is_match = True

        for path in paths[1:]:
            if path_index > len(path.parts) - 1 or path.parts[path_index] != paths[0].parts[path_index]:
                is_match = False
                break

        if not is_match:
            break

        path_index += 1

    if path_index == 0:
        return None

    return Path(*paths[0].parts[:path_index])


# ----------------------------------------------------------------------
def RemoveTree(
    path: Path,
    *,
    retry_iterations: int=5,
) -> bool:
    """Removes a directory and its children in the most efficient way possible"""

    if not path.is_dir():
        return False

    _RemoveImpl(CurrentShell.RemoveDir, path, retry_iterations=retry_iterations)
    return True


# ----------------------------------------------------------------------
def RemoveFile(
    path: Path,
    *,
    retry_iterations: int=5,
) -> bool:
    """Removes a file in the most efficient way possible"""

    if not path.is_file():
        return False

    _RemoveImpl(lambda path: path.unlink(), path, retry_iterations=retry_iterations)
    return True


# ----------------------------------------------------------------------
def RemoveItem(
    path: Path,
    *,
    retry_iterations: int=5,
) -> bool:
    """Removes a file or directory in the most efficient way possible"""

    if path.is_dir():
        return RemoveTree(path, retry_iterations=retry_iterations)
    elif path.is_file():
        return RemoveFile(path, retry_iterations=retry_iterations)

    return False


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _RemoveImpl(
    func: Callable[[Path], None],
    path: Path,
    *,
    retry_iterations: int,
) -> None:
    assert path.exists(), path

    # Rename the dir or item to a temporary one and then remove the renamed item. This technique
    # works around timing issues associated with quickly creating a new item after a previous version
    # was just deleted.
    iteration = 0

    while True:
        potential_renamed_path = Path("{}_ToDelete{}".format(str(path), iteration))
        if not potential_renamed_path.exists():
            renamed_path = potential_renamed_path
            break

        iteration += 1

    # Invoke
    iteration = 0

    while True:
        try:
            shutil.move(str(path), renamed_path)
            break
        except:
            time.sleep(iteration * 0.5 + 0.5)  # seconds

            iteration += 1
            if iteration < retry_iterations:
                continue

            raise

    func(renamed_path)
