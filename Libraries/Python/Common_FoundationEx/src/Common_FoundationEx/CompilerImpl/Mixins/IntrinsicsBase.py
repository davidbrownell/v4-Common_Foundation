# ----------------------------------------------------------------------
# |
# |  IntrinsicsBase.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-06 20:17:16
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the IntrinsicsBase object"""

import inspect

from pathlib import Path
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
        dm: DoneManager,  # pylint: disable=unused-argument
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        return metadata

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateGeneratorFiles(
        self,
        context: Dict[str, Any],  # pylint: disable=unused-argument
    ) -> Generator[Path, None, None]:
        for base_class in inspect.getmro(type(self)):
            if base_class.__name__ != "object":
                yield Path(inspect.getfile(base_class))
