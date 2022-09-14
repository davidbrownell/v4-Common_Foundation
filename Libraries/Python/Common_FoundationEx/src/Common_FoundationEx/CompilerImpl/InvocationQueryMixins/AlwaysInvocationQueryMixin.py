# ----------------------------------------------------------------------
# |
# |  AlwaysInvocationQueryMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 16:16:40
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AlwaysInvocationQueryMixin object"""

from typing import Any, Dict, Optional

from Common_Foundation.Streams.DoneManager import DoneManager

from .IInvocationQuery import IInvocationQuery, InvokeReason


# ----------------------------------------------------------------------
class AlwaysInvocationQueryMixin(IInvocationQuery):
    """Always invoke"""

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _GetInvokeReason(
        dm: DoneManager,                    # pylint: disable=unused-argument
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> Optional[InvokeReason]:
        return InvokeReason.Always

    # ----------------------------------------------------------------------
    @staticmethod
    def _PersistContext(
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> None:
        # Nothing to persist
        pass
