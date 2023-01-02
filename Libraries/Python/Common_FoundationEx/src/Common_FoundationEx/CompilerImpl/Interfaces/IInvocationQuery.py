# ----------------------------------------------------------------------
# |
# |  IInvocationQuery.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-17 16:58:10
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInvocationQuery object"""

from abc import ABC, abstractmethod
from enum import auto, Enum
from typing import Any, Dict, Optional

from Common_Foundation.Streams.DoneManager import DoneManager


# ----------------------------------------------------------------------
class InvokeReason(Enum):
    """Reasons why a compiler can be invoked given a set of inputs and outputs"""

    Always                                  = auto()
    Force                                   = auto()
    PreviousContextMissing                  = auto()
    NewerGenerators                         = auto()
    MissingOutput                           = auto()
    DifferentOutput                         = auto()
    NewerInput                              = auto()
    DifferentInputs                         = auto()
    DifferentMetadata                       = auto()
    OptIn                                   = auto()


# ----------------------------------------------------------------------
class IInvocationQuery(ABC):
    """Interface for mixins that look at criteria to determine if compilation is necessary"""

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @abstractmethod
    def _GetInvokeReason(
        self,
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> Optional[InvokeReason]:
        """Returns why compilation is necessary or None if it is not"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def _PersistContext(
        self,
        context: Dict[str, Any],
    ) -> None:
        """Persist context information that can be used in the future to determine if compilation is necessary"""
        raise Exception("Abstract method")
