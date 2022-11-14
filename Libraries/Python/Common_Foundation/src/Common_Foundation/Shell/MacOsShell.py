# ----------------------------------------------------------------------
# |
# |  MacOsShell.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-13 23:10:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the MacOsShell object"""

from typing import Optional, Set as SetType

from Common_Foundation.Types import overridemethod

from .Commands import SymbolicLink
from .CommandVisitor import CommandVisitor
from .Impl.LinuxShellImpl import LinuxCommandVisitor, LinuxShellImpl


# ----------------------------------------------------------------------
class MacOsShell(LinuxShellImpl):
    """Shell for MacOS systems"""

    # ----------------------------------------------------------------------
    def __init__(self):
        self._command_visitor               = MacOsCommandVisitor()

    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Darwin"

    @property
    def family_name(self) -> str:
        return "BSD"

    @property
    def command_visitor(self) -> CommandVisitor:
        return self._command_visitor

    # ----------------------------------------------------------------------
    @overridemethod
    def IsActive(
        self,
        platform_names: SetType[str],
    ) -> bool:
        return self.name.lower() in platform_names


# ----------------------------------------------------------------------
class MacOsCommandVisitor(LinuxCommandVisitor):
    """Visitor that overrides commands unique to MacOS"""

    # ----------------------------------------------------------------------
    @overridemethod
    def OnSymbolicLink(
        self,
        command: SymbolicLink,
    ) -> Optional[str]:
        # Darwin doesn't support the dir or relative flags
        return super(MacOsCommandVisitor, self).OnSymbolicLink(
            SymbolicLink(
                command.link_filename,
                command.target,
                remove_existing=command.remove_existing,
                relative_path=False,
                is_dir_param=False,
            ),
        )
