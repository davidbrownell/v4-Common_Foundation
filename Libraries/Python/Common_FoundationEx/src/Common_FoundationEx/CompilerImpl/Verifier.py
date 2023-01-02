# ----------------------------------------------------------------------
# |
# |  Verifier.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 14:04:42
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Verifier object"""

from typing import Any, Callable, Dict, TextIO, Tuple, Union

from . import CommandLine
from .CompilerImpl import CompilerImpl

from .Mixins.InputProcessorMixins.IndividualInputProcessorMixin import IndividualInputProcessorMixin
from .Mixins.InvocationQueryMixins.AlwaysInvocationQueryMixin import AlwaysInvocationQueryMixin
from .Mixins.OutputProcessorMixins.NoOutputProcessorMixin import NoOutputProcessorMixin

# Convenience imports
from .CompilerImpl import InputType, InvokeReason  # pylint: disable=unused-import


# ----------------------------------------------------------------------
class Verifier(
    CompilerImpl,
    IndividualInputProcessorMixin,
    AlwaysInvocationQueryMixin,
    NoOutputProcessorMixin,
):
    """Pre-configured object for a compiler that verifies code"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(Verifier, self).__init__(
            "Verify",
            "Verifying",
            *args,
            **{
                **kwargs,
                **{
                    "requires_output_dir": False,
                },
            },
        )

    # ----------------------------------------------------------------------
    def Verify(
        self,
        context: Dict[str, Any],
        output_stream: TextIO,              # Log output
        on_progress_func: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        verbose: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short description that provides contextual information about the return code
        ],
    ]:
        return self._Invoke(context, output_stream, on_progress_func, verbose=verbose)


# ----------------------------------------------------------------------
CreateVerifyCommandLineFunc                 = CommandLine.CreateInvokeCommandLineFunc
CreateListCommandLineFunc                   = CommandLine.CreateListCommandLineFunc
