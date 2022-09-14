# ----------------------------------------------------------------------
# |
# |  All.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 15:06:07
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality that looks across all known Shells"""

import os

from typing import Set

from .LinuxShell import LinuxShell
from .WindowsShell import WindowsShell


# ----------------------------------------------------------------------
ALL_SHELLS                                  = [
    LinuxShell(),
    WindowsShell(),
]


# ----------------------------------------------------------------------
def _GetShell():
    # ----------------------------------------------------------------------
    def GetPlatformNames() -> Set[str]:
        result = os.getenv("DEVELOPMENT_ENVIRONMENT_SHELL_NAME")
        if result:
            return set(result.lower())

        results: Set[str] = set()

        try:
            import distro  # type: ignore  # pylint: disable=import-outside-toplevel

            distro_info = distro.info()

            results.add(distro_info["id"].lower())

            for part in distro_info["like"].split(" "):
                part = part.strip()
                if part:
                    results.add(part.lower())

        except ImportError:
            pass

        if not results:
            results.add(os.name.lower())

        return results

    # ----------------------------------------------------------------------

    platform_names = GetPlatformNames()

    for shell in ALL_SHELLS:
        if shell.IsActive(platform_names):
            return shell

    raise Exception(
        "No shell found for {}".format(
            ", ".join("'{}'".format(platform_name) for platform_name in platform_names),
        ),
    )


# ----------------------------------------------------------------------
CurrentShell                                = _GetShell()

del _GetShell
