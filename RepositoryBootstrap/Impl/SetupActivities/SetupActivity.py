# ----------------------------------------------------------------------
# |
# |  SetupActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 21:33:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the SetupActivity object"""

from abc import abstractmethod, ABC
from typing import List

from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore


# ----------------------------------------------------------------------
class SetupActivity(ABC):
    """
    Base class for activities that are performed at environment setup time.
    """

    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    @abstractmethod
    def name(self) -> str:
        raise Exception("Abstract property")  # pragma: no cover

    # ----------------------------------------------------------------------
    # |
    # |  Methods
    # |
    # ----------------------------------------------------------------------
    def CreateCommands(
        self,
        dm: DoneManager,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        with dm.Nested(
            "\nSetting up '{}'...".format(self.name),
            display_exceptions=False,
        ) as nested_dm:
            return self._CreateCommandsImpl(nested_dm, force=force)

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _CreateCommandsImpl(
        dm: DoneManager,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        """Returns commands that are invoked during setup"""
        raise Exception("Abstract method")  # pragma: no cover
