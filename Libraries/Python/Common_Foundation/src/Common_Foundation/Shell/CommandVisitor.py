# ----------------------------------------------------------------------
# |
# |  CommandVisitor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 14:28:14
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CommandVisitor object"""

from abc import abstractmethod, ABC
from typing import Optional

from .Commands import (
    Augment,
    AugmentPath,
    Call,
    CommandPrompt,
    Command,
    Comment,
    Copy,
    Delete,
    EchoOff,
    Execute,
    Exit,
    ExitOnError,
    Message,
    Move,
    PersistError,
    PopDirectory,
    PushDirectory,
    Raw,
    Set,
    SetPath,
    SymbolicLink,
)


# ----------------------------------------------------------------------
class CommandVisitor(ABC):
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnAugment(
        command: Augment,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnAugmentPath(
        command: AugmentPath,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnCall(
        command: Call,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnCommandPrompt(
        command: CommandPrompt,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnComment(
        command: Comment,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnCopy(
        command: Copy,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnDelete(
        command: Delete,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnEchoOff(
        command: EchoOff,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnExecute(
        command: Execute,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnExit(
        command: Exit,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnExitOnError(
        command: ExitOnError,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnMessage(
        command: Message,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnMove(
        command: Move,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnPersistError(
        command: PersistError,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnPopDirectory(
        command: PopDirectory,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnPushDirectory(
        command: PushDirectory,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnRaw(
        command: Raw,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnSet(
        command: Set,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnSetPath(
        command: SetPath,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def OnSymbolicLink(
        command: SymbolicLink,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def Accept(
        cls,
        command: Command,
    ) -> Optional[str]:
        lookup_map = {
            Augment: cls.OnAugment,
            AugmentPath: cls.OnAugmentPath,
            Call: cls.OnCall,
            CommandPrompt: cls.OnCommandPrompt,
            Comment: cls.OnComment,
            Copy: cls.OnCopy,
            Delete: cls.OnDelete,
            EchoOff: cls.OnEchoOff,
            Execute: cls.OnExecute,
            Exit: cls.OnExit,
            ExitOnError: cls.OnExitOnError,
            Message: cls.OnMessage,
            Move: cls.OnMove,
            PersistError: cls.OnPersistError,
            PopDirectory: cls.OnPopDirectory,
            PushDirectory: cls.OnPushDirectory,
            Raw: cls.OnRaw,
            Set: cls.OnSet,
            SetPath: cls.OnSetPath,
            SymbolicLink: cls.OnSymbolicLink,
        }

        func = lookup_map.get(type(command), None)  # type: ignore

        assert func is not None, command

        return func(command)
