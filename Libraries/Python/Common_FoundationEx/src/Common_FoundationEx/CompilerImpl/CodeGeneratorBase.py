# ----------------------------------------------------------------------
# |
# |  CodeGeneratorBase.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 10:17:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeGeneratorBase object"""

from typing import Any, Callable, Dict, TextIO, Tuple, Union

from .CompilerImpl import CompilerImpl
from .InvocationQueryMixins.ConditionalInvocationQueryMixin import ConditionalInvocationQueryMixin


# ----------------------------------------------------------------------
class CodeGeneratorBase(  # pylint: disable=too-many-ancestors
    CompilerImpl,
    ConditionalInvocationQueryMixin,
):
    """Pre-configured object for a compiler that generates code"""

    # ----------------------------------------------------------------------
    def __init__(self, *args, **kwargs):
        super(CodeGeneratorBase, self).__init__("Generate", "Generating", *args, **kwargs)

    # ----------------------------------------------------------------------
    def Generate(
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
