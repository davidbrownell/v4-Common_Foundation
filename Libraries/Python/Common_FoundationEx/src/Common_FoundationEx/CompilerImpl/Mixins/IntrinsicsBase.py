# ----------------------------------------------------------------------
# |
# |  IntrinsicsBase.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-06 20:17:16
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IntrinsicsBase object"""

from typing import Any, Dict, Generator, List, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from ..Interfaces.ICompilerIntrinsics import ICompilerIntrinsics


# ----------------------------------------------------------------------
class IntrinsicsBase(ICompilerIntrinsics):
    """Implements common functionality for all Mixins"""

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        if False:
            yield

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return []

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return []

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return metadata
