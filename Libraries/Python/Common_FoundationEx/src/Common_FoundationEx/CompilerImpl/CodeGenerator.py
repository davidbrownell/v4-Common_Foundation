# ----------------------------------------------------------------------
# |
# |  CodeGenerator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 13:54:55
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeGenerator object"""

from typing import Any, Callable, Dict, TextIO, Tuple, Union

from . import CommandLine
from .CompilerImpl import CompilerImpl

from .Mixins.InvocationQueryMixins.ConditionalInvocationQueryMixin import ConditionalInvocationQueryMixin


# ----------------------------------------------------------------------
class CodeGenerator(
    CompilerImpl,
    ConditionalInvocationQueryMixin,
):
    """Pre-configured object for a compiler that generates code"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(CodeGenerator, self).__init__(
            "Generate",
            "Generating",
            *args,
            **{
                **kwargs,
                **{
                    "requires_output_dir": True,
                },
            },
        )

    # ----------------------------------------------------------------------
    def Generate(
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
CreateGenerateCommandLineFunc               = CommandLine.CreateInvokeCommandLineFunc
CreateCleanCommandLineFunc                  = CommandLine.CreateCleanCommandLineFunc
