# ----------------------------------------------------------------------
# |
# |  PluginBase.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-01-11 14:59:02
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the PluginBase object"""

import inspect
import os
import textwrap

from abc import abstractmethod, ABC
from typing import Any, Optional

from Common_Foundation.Types import extensionmethod

from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class PluginBase(ABC):
    """\
    Abstract base class for plugins that are used by concrete CodeGenerator objects."""

    # ----------------------------------------------------------------------
    # |
    # |  Public Properties
    # |
    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        """Name used to uniquely identify the plugin"""
        raise Exception("Abstract property")  # pragma: no cover

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the plugin (often displayed on the command line)"""
        raise Exception("Abstract property")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Public Methods
    # |
    # ----------------------------------------------------------------------
    @extensionmethod
    def ValidateEnvironment(self) -> Optional[str]:
        """\
        Opportunity to valid that a plugin can be run in the current environment.
        """

        # Do nothing by default
        return None

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return command line arguments required by the plugin"""

        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def GetNumAdditionalSteps(
        self,
        context: dict[str, Any],
    ) -> int:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @classmethod
    def _GenerateFileHeader(
        cls,
        line_prefix: str="",
        line_break: str="--------------------------------------------------------------------------------",
        filename_parts: int=3,              # Number of filename parts to display in the header
        filename_prefix: Optional[str]=None,
        callstack_offset: int=0,
    ) -> str:
        """Returns a string that can be included at the top of output files generated"""

        frame = inspect.stack()[callstack_offset + 1][0]
        filename = frame.f_code.co_filename

        filename = "/".join(filename.split(os.path.sep)[-filename_parts:])

        return textwrap.dedent(
            """\
            {prefix}{line_break}
            {prefix}|
            {prefix}|  WARNING:
            {prefix}|  This file was generated; any local changes will be overwritten during
            {prefix}|  future invocations of the generator!
            {prefix}|
            {prefix}|  Generated by: {filename_prefix}{filename}
            {prefix}|
            {prefix}{line_break}
            """,
        ).format(
            prefix=line_prefix,
            line_break=line_break,
            filename_prefix=filename_prefix or "",
            filename=filename,
        )
