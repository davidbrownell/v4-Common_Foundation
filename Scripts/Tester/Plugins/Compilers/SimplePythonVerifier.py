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

from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.Verifier import InputType, Verifier as VerifierBase
from Common_FoundationEx.CompilerImpl.Interfaces.IInvoker import IInvoker
from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx


# ----------------------------------------------------------------------
class Verifier(VerifierBase, IInvoker):
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
            can_execute_in_parallel=True,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    @overridemethod
    def IsSupported(  # pylint: disable=arguments-renamed
        filename: Path,
    ) -> bool:
        return filename.suffix == ".py"

    # ----------------------------------------------------------------------
    @overridemethod
    def ItemToTestName(
        self,
        item: Path,
        test_type_name: str,
    ) -> Optional[Path]:
        if self.IsSupportedTestItem(item):
            return item

        return item.parent / "{}_{}{}".format(
            item.stem,
            inflect.singular_noun(test_type_name) or test_type_name,
            item.suffix,
        )

    # ----------------------------------------------------------------------
    @staticmethod
    @overridemethod
    def GetCustomCommandLineArgs() -> TyperEx.TypeDefinitionsType:
        return {}

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @staticmethod
    @overridemethod
    def _GetNumStepsImpl(*args, **kwargs) -> int:  # pylint: disable=unused-argument
        return 1

    # ----------------------------------------------------------------------
    @staticmethod
    @overridemethod
    def _InvokeImpl(*args, **kwargs) -> Optional[str]:  # pylint: disable=unused-argument
        # Nothing to do here
        return None
