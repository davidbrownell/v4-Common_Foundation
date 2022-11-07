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

from pathlib import Path
from typing import Any, Callable, Dict, Optional, TextIO, Tuple, Union

from Common_Foundation.Types import overridemethod

from . import CommandLine
from .CompilerImpl import CompilerImpl

from .Interfaces.IInputProcessor import IInputProcessor
from .Interfaces.IOutputProcessor import IOutputProcessor

from .Mixins.InvocationQueryMixins.ConditionalInvocationQueryMixin import ConditionalInvocationQueryMixin

# Convenience Imports
from .CompilerImpl import InputType, InvokeReason  # pylint: disable=unused-import


# ----------------------------------------------------------------------
class CodeGenerator(
    CompilerImpl,
    ConditionalInvocationQueryMixin,
):
    """Pre-configured object for a compiler that generates code"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        input_processor: IInputProcessor,
        output_processor: IOutputProcessor,
        *args,
        **kwargs,
    ):
        CompilerImpl.__init__(
            self,
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

        ConditionalInvocationQueryMixin.__init__(self, input_processor, output_processor)

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupportedTestItem(
        self,
        item: Path,  # pylint: disable=unused-argument
    ) -> bool:
        return False

    # ----------------------------------------------------------------------
    @overridemethod
    def ItemToTestName(
        self,
        item: Path,                         # pylint: disable=unused-argument
        test_type_name: str,                # pylint: disable=unused-argument
    ) -> Optional[Path]:
        return None

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
CreateListCommandLineFunc                   = CommandLine.CreateListCommandLineFunc
