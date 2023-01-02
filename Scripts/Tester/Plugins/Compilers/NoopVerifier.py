# ----------------------------------------------------------------------
# |
# |  NoopVerifier.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 08:10:48
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

from pathlib import Path
from typing import Optional

from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.Verifier import InputType, Verifier as VerifierBase
from Common_FoundationEx.CompilerImpl.Interfaces.IInvoker import IInvoker
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class Verifier(VerifierBase, IInvoker):
    """\
    Verifier that doesn't do anything.

    This verifier exists to demonstrate the capabilities of Tester and should not be used with
    any real code.
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        super(Verifier, self).__init__(
            "Noop",
            "Sample Verifier intended to demonstrate the capabilities of Tester; DO NOT USE with real workloads (as it doesn't do anything).",
            InputType.Files,
            can_execute_in_parallel=True,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupported(  # pylint: disable=arguments-renamed
        self,
        filename_or_directory: Path,
    ) -> bool:
        return filename_or_directory.is_file()

    # ----------------------------------------------------------------------
    @overridemethod
    def SupportsTestItemMatching(self) -> bool:
        # This compiler is designed to match anything, so we don't want it tp produce False positives
        # when we can't find tests associated with source files matched by this compiler.
        return False

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(self, *args, **kwargs) -> int:  # pylint: disable=unused-argument
        return 1

    # ----------------------------------------------------------------------
    @overridemethod
    def _InvokeImpl(self, *args, **kwargs) -> Optional[str]:  # pylint: disable=unused-argument
        # Nothing to do here
        return None
