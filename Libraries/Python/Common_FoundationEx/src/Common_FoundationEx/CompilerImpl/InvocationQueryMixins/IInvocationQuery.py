# ----------------------------------------------------------------------
# |
# |  IInvocationQuery.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 08:51:57
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IInvocationQuery object"""

from abc import abstractmethod, ABC
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
    """Interface for InvocationQuery mixin objects"""

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _GetInvokeReason(
        dm: DoneManager,
        context: Dict[str, Any],
    ) -> Optional[InvokeReason]:
        """Implemented by an InvocationQueryMixin"""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _PersistContext(
        context: Dict[str, Any],
    ) -> None:
        """Implemented by an InvocationQueryMixin"""
        raise Exception("Abstract method")
