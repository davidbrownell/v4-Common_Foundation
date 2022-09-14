# ----------------------------------------------------------------------
# |
# |  SimplePythonVerifier.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 08:10:48
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the Verifier object"""

from pathlib import Path
from typing import Optional

from Common_FoundationEx.CompilerImpl.VerifierBase import InputType, VerifierBase
from Common_FoundationEx.CompilerImpl.InvocationMixins.IInvocation import IInvocation
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class Verifier(VerifierBase, IInvocation):
    """\
    Verifier that runs python files.

    This verifier exists to demonstrate the capabilities of Tester and should not be used with
    any real code. A real Python verifier is available as part of the `Common_PythonDevelopment`
    repository, available at `https://github.com/davidbrownell/v4-Common_PythonDevelopment`.
    """

    # ----------------------------------------------------------------------
    def __init__(self):
        super(Verifier, self).__init__(
            "SimplePython",
            "Sample Verifier intended to demonstrate the capabilities of Tester; DO NOT USE with real workloads.",
            InputType.Files,
            execute_in_parallel=True,
        )

    # ----------------------------------------------------------------------
    def IsSupported(  # pylint: disable=arguments-renamed
        self,
        filename: Path,
    ) -> bool:
        return (
            filename.suffix == ".py"
            and super(Verifier, self).IsSupported(filename)
        )

    # ----------------------------------------------------------------------
    @staticmethod
    def GetCustomArgs() -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    def _GetNumStepsImpl(*args, **kwargs) -> int:  # pylint: disable=unused-argument
        return 1

    # ----------------------------------------------------------------------
    @staticmethod
    def _InvokeImpl(*args, **kwargs) -> Optional[str]:  # pylint: disable=unused-argument
        # Nothing to do here
        return None
