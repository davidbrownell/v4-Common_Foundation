# ----------------------------------------------------------------------
# |
# |  LinuxShell.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-19 11:54:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the LinuxShell object"""

from typing import Set

from .Impl.LinuxShellImpl import LinuxShellImpl


# ----------------------------------------------------------------------
class LinuxShell(LinuxShellImpl):
    """Linux Shell implementation"""

    # Most of the functionality is implemented in a base class because I expect
    # to see distro-specific customizations over time. Or, this could be an
    # example of premature over-architecture.

    # ----------------------------------------------------------------------
    def __init__(self):
        try:
            import distro  # type: ignore

            name = distro.info()["id"]
            is_active_override = None

        except ImportError:
            name = "<Not Linux>"
            is_active_override = False

        super(LinuxShell, self).__init__()

        self._name                          = name
        self._is_active_override            = is_active_override

    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return self._name

    # ----------------------------------------------------------------------
    def IsActive(
        self,
        platform_names: Set[str],
    ) -> bool:
        if self._is_active_override is not None:
            return self._is_active_override

        return super(LinuxShell, self).IsActive(platform_names)
