# ----------------------------------------------------------------------
# |
# |  AlwaysInvocationQueryMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:48:51
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AlwaysInvocationQueryMixin object"""

from typing import Any, Dict, Generator, List, Optional, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ..IntrinsicsBase import IntrinsicsBase

from ...Interfaces.IInvocationQuery import IInvocationQuery, InvokeReason


# ----------------------------------------------------------------------
class AlwaysInvocationQueryMixin(
    IntrinsicsBase,
    IInvocationQuery,
):
    """Always invokes the compiler"""

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _GetInvokeReason(
        self,
        dm: DoneManager,                    # pylint: disable=unused-argument
        context: Dict[str, Any],            # pylint: disable=unused-argument
    ) -> Optional[InvokeReason]:
        return InvokeReason.Always

    # ----------------------------------------------------------------------
    @overridemethod
    def _PersistContext(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> None:
        # Nothing to persist
        pass

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        return super(AlwaysInvocationQueryMixin, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(AlwaysInvocationQueryMixin, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(AlwaysInvocationQueryMixin, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return super(AlwaysInvocationQueryMixin, self)._CreateContext(dm, metadata)
