# ----------------------------------------------------------------------
# |
# |  ICompilerImpl.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 08:34:37
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ICompilerImpl object"""

from abc import abstractmethod
from pathlib import Path
from typing import Any, Dict, Generator, List, Tuple

from Common_Foundation.Streams.DoneManager import DoneManager

from .InputProcessingMixins.IInputProcessing import IInputProcessing
from .InvocationQueryMixins.IInvocationQuery import IInvocationQuery
from .InvocationMixins.IInvocation import IInvocation
from .OutputMixins.IOutput import IOutput

# Convenience imports
from .InvocationQueryMixins.IInvocationQuery import InvokeReason  # pylint: disable=unused-import


# ----------------------------------------------------------------------
class ICompilerImpl(
    IInputProcessing,
    IInvocationQuery,
    IInvocation,
    IOutput,
):
    """Interface for CompilerImpl objects; this class exists to serve as a base for all mixins"""

    # ----------------------------------------------------------------------
    # |
    # |  Protected Methods
    # |
    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _EnumerateOptionalMetadata() -> Generator[Tuple[str, Any], None, None]:
        """\
        Metadata that should be applied to generated context items if it doesn't already exist.
        """
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _GetRequiredMetadataNames() -> List[str]:
        """Names that must be a part of generated metadata."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _GetRequiredContextNames() -> List[str]:
        """Names that must be a part of generated context."""
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def _CreateContext(
        dm: DoneManager,  # pylint: disable=unused-argument
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Returns a context object tuned specifically for the metadata provided."""
        raise Exception("Abstract method")
