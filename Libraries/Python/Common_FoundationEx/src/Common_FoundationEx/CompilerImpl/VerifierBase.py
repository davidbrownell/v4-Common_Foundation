# ----------------------------------------------------------------------
# |
# |  VerifierBase.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 10:26:36
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the VerifierBase object"""

from typing import Any, Callable, Dict, TextIO, Tuple, Union

from .CommandLineImpl import CreateInvokeCommandLineFunc
from .CompilerImpl import CompilerImpl
from .InputProcessingMixins.IndividualInputProcessingMixin import IndividualInputProcessingMixin
from .InvocationQueryMixins.AlwaysInvocationQueryMixin import AlwaysInvocationQueryMixin
from .OutputMixins.NoOutputMixin import NoOutputMixin

# Convenience imports
from .CompilerImpl import InputType, InvokeReason  # pylint: disable=unused-import


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class VerifierBase(  # pylint: disable=too-many-ancestors
    CompilerImpl,
    IndividualInputProcessingMixin,
    AlwaysInvocationQueryMixin,
    NoOutputMixin,
):
    """Pre-configured object for a compiler that verifies code"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(VerifierBase, self).__init__("Verify", "Verifying", *args, **kwargs)

    # ----------------------------------------------------------------------
    def Verify(
        self,
        context: Dict[str, Any],
        output_stream: TextIO,              # Log output
        on_progress: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        verbose: bool=False,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return self._Invoke(context, output_stream, on_progress, verbose=verbose)


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
CreateVerifyCommandLineFunc                 = CreateInvokeCommandLineFunc
