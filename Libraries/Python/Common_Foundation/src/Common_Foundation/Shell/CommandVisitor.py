# ----------------------------------------------------------------------
# |
# |  CommandVisitor.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 14:28:14
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
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
    @abstractmethod
    def OnAugment(
        self,
        command: Augment,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnAugmentPath(
        self,
        command: AugmentPath,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnCall(
        self,
        command: Call,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnCommandPrompt(
        self,
        command: CommandPrompt,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnComment(
        self,
        command: Comment,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnCopy(
        self,
        command: Copy,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnDelete(
        self,
        command: Delete,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnEchoOff(
        self,
        command: EchoOff,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnExecute(
        self,
        command: Execute,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnExit(
        self,
        command: Exit,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnExitOnError(
        self,
        command: ExitOnError,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnMessage(
        self,
        command: Message,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnMove(
        self,
        command: Move,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnPersistError(
        self,
        command: PersistError,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnPopDirectory(
        self,
        command: PopDirectory,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnPushDirectory(
        self,
        command: PushDirectory,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnRaw(
        self,
        command: Raw,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnSet(
        self,
        command: Set,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnSetPath(
        self,
        command: SetPath,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @abstractmethod
    def OnSymbolicLink(
        self,
        command: SymbolicLink,
    ) -> Optional[str]:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def Accept(
        self,
        command: Command,
    ) -> Optional[str]:
        lookup_map = {
            Augment: self.OnAugment,
            AugmentPath: self.OnAugmentPath,
            Call: self.OnCall,
            CommandPrompt: self.OnCommandPrompt,
            Comment: self.OnComment,
            Copy: self.OnCopy,
            Delete: self.OnDelete,
            EchoOff: self.OnEchoOff,
            Execute: self.OnExecute,
            Exit: self.OnExit,
            ExitOnError: self.OnExitOnError,
            Message: self.OnMessage,
            Move: self.OnMove,
            PersistError: self.OnPersistError,
            PopDirectory: self.OnPopDirectory,
            PushDirectory: self.OnPushDirectory,
            Raw: self.OnRaw,
            Set: self.OnSet,
            SetPath: self.OnSetPath,
            SymbolicLink: self.OnSymbolicLink,
        }

        func = lookup_map.get(type(command), None)  # type: ignore

        assert func is not None, command

        return func(command)
