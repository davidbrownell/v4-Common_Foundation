# ----------------------------------------------------------------------
# |
# |  Utilities.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 10:55:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""General utilities"""

import hashlib
import os
import uuid

from pathlib import Path
from typing import Dict, List, Optional, Pattern

from Common_Foundation.RegularExpression import TemplateStringToRegex  # type: ignore

from .. import Constants
from .. import DataTypes

# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def GetFoundationRepositoryRoot() -> Path:
    """Returns the path to the foundation repository"""

    # Try to get the value from the environment
    env_var = os.getenv(Constants.DE_FOUNDATION_ROOT_NAME)
    if env_var is not None:
        return Path(env_var).resolve()

    # Try to get the value from bootstrap data
    potential_path = Path.cwd() / Constants.GENERATED_DIRECTORY_NAME
    if potential_path.is_dir():
        # Get the bootstrap data file
        # ----------------------------------------------------------------------
        def GetBootstrapFilename() -> Optional[Path]:
            for root, _, filenames in os.walk(potential_path):
                for filename in filenames:
                    if filename == Constants.GENERATED_BOOTSTRAP_DATA_FILENAME:
                        return Path(root) / filename

                return None

        # ----------------------------------------------------------------------

        bootstrap_filename = GetBootstrapFilename()
        if bootstrap_filename is not None:
            foundation_root: Optional[Path] = None

            for line in open(bootstrap_filename).readlines():
                if line.startswith("foundation_repo="):
                    foundation_root = Path(line[len("foundation_repo="):].strip())
                    break

            if foundation_root is not None:
                foundation_root = (Path.cwd() / foundation_root).resolve()
                if foundation_root.is_dir():
                    return foundation_root

    # Get the value relative to this file. This should always work, expect if the
    # environment has been frozen in some unique way.
    potential_path = Path(__file__).parent / Constants.GENERATED_DIRECTORY_NAME
    if potential_path.is_dir():
        return potential_path.resolve()

    raise Exception("The foundation repository could not be found.")


# ----------------------------------------------------------------------
_get_repository_info_regex: Pattern         = TemplateStringToRegex(Constants.REPOSITORY_ID_CONTENT_TEMPLATE)

def GetRepoData(
    repo_root: Path,
    raise_on_error: bool=True,
) -> Optional[DataTypes.RepoData]:
    """Returns the name and unique id of the repository at the given path"""

    repository_id_filename = repo_root / Constants.REPOSITORY_ID_FILENAME
    if not repository_id_filename.is_file():
        if raise_on_error:
            raise Exception("Unable to find repository information for '{}'.".format(repository_id_filename))

        return None

    # Attempt to match the content
    with open(repository_id_filename) as f:
        content = f.read()

    match = _get_repository_info_regex.match(content)
    if not match:
        if raise_on_error:
            raise Exception("The content in '{}' appears to be corrupt.".format(repository_id_filename))

        return None

    return DataTypes.RepoData(match.group("name"), uuid.UUID(match.group("id")))


# ----------------------------------------------------------------------
def CalculateFingerprint(
    repo_dirs: List[Path],
) -> Dict[Path, str]:
    results: Dict[Path, str] = {}

    for repo_dir in repo_dirs:
        setup_filename = repo_dir / Constants.SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME
        if not setup_filename.is_file():
            raise Exception(
                "'{}' is not a valid repository ('{}' not found)".format(
                    str(repo_dir),
                    Constants.SETUP_ENVIRONMENT_CUSTOMIZATION_FILENAME,
                ),
            )

        hasher = hashlib.sha256()

        with setup_filename.open("rb") as f:
            # Skip the file header, as it has no impact on the file's functionality
            in_file_header = True

            for line in f:
                if in_file_header and line.lstrip().startswith(b"#"):
                    continue

                in_file_header = False
                hasher.update(line)

        results[repo_dir] = hasher.hexdigest()

    return results
