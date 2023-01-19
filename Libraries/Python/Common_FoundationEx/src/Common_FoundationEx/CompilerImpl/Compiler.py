# ----------------------------------------------------------------------
# |
# |  Compiler.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-19 14:03:14
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Compiler object"""

from typing import Any, Callable, Dict, TextIO, Tuple, Union

from . import CommandLine
from .CompilerImpl import CompilerImpl

# Convenience Imports
from .CompilerImpl import InputType, InvokeReason  # pylint: disable=unused-import


# ----------------------------------------------------------------------
class Compiler(CompilerImpl):
    """Pre-configured object for a standard compiler"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(Compiler, self).__init__(
            "Compile",
            "Compiling",
            *args,
            **{
                **kwargs,
                **{
                    "requires_output_dir": True,
                },
            },
        )

    # ----------------------------------------------------------------------
    def Compile(
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
        debug: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short description that provides contextual information about the return code
        ],
    ]:
        return self._Invoke(
            context,
            output_stream,
            on_progress_func,
            verbose=verbose,
            debug=debug,
        )


# ----------------------------------------------------------------------
CreateCompileCommandLineFunc                = CommandLine.CreateInvokeCommandLineFunc
CreateCleanCommandLineFunc                  = CommandLine.CreateCleanCommandLineFunc
CreateListCommandLineFunc                   = CommandLine.CreateListCommandLineFunc
