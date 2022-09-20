# ----------------------------------------------------------------------
# |
# |  PythonSetupActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 21:38:32
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the PythonSetupActivity object"""

import os
import re

from enum import Enum
from pathlib import Path
from typing import Dict, List

import inflect as inflect_mod

from Common_Foundation.Shell import Commands    # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore
from Common_Foundation.Types import overridemethod

from ...ActivateActivity import ActivateActivity
from ... import Constants
from ...SetupActivity import SetupActivity


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()

# ----------------------------------------------------------------------
class NormalizeScriptResult(Enum):
    NoMatch                                 = "No Match"
    NoChange                                = "No Change"
    Modified                                = "Modified"


# ----------------------------------------------------------------------
class PythonSetupActivity(SetupActivity):
    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Python"

    # ----------------------------------------------------------------------
    @classmethod
    def NormalizeScript(
        cls,
        script_filename: Path,
    ) -> NormalizeScriptResult:
        """Normalizes a python script so that it can be run from within a generic python installation"""

        if script_filename.suffix == ".exe":
            with open(script_filename, "rb") as f:
                content = f.read()

            content = cls._NormalizeScript_executable_shebang_regex.split(
                content,
                maxsplit=1,
            )

            if len(content) != 3:
                return NormalizeScriptResult.NoMatch

            prev_content = content[1]

            content[1] = b"#!python.exe"
            assert len(prev_content) >= len(content[1]), (
                len(prev_content),
                len(content[1]),
            )
            content[1] += b" " * (len(prev_content) - len(content[1]) - 2)
            content[1] += b"\r\n"

            if content[1] == prev_content:
                return NormalizeScriptResult.NoChange

            with open(script_filename, "wb") as f:
                f.write(b"".join(content))

        else:
            try:
                with script_filename.open() as f:
                    content = f.read()

                content = cls._NormalizeScript_script_shebang_regex.split(
                    content,
                    maxsplit=1,
                )

            except (UnicodeDecodeError, OSError):
                content = []

            if len(content) != 3:
                return NormalizeScriptResult.NoMatch

            prev_content = content[1]
            content[1] = "#!/usr/bin/env python"

            if content[1] == prev_content:
                return NormalizeScriptResult.NoChange

            with script_filename.open("w") as f:
                f.write("".join(content))

        return NormalizeScriptResult.Modified

    # ----------------------------------------------------------------------
    # |
    # |  Private Data
    # |
    # ----------------------------------------------------------------------
    _NormalizeScript_executable_shebang_regex           = re.compile(b"(#!.+pythonw?\\.exe)")
    _NormalizeScript_script_shebang_regex               = re.compile(r"^\s*(#!.+python.*?)$", re.MULTILINE)

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateCommandsImpl(
        self,
        dm: DoneManager,
        *,
        force: bool,  # pylint: disable=unused-argument
    ) -> List[Commands.Command]:
        stats: Dict[str, int] = {
            k.value: 0 for k in NormalizeScriptResult
        }

        with dm.Nested(
            "Normalizing python scripts...",
            [
                lambda: "{} modified".format(inflect.no("script", stats[NormalizeScriptResult.Modified.value])),
                lambda: "{} matched".format(inflect.no("script", stats[NormalizeScriptResult.NoChange.value])),
                lambda: "{} skipped".format(inflect.no("script", stats[NormalizeScriptResult.NoMatch.value])),
            ],
        ) as nested_dm:
            python_versions: Dict[str, Path] = {}

            if os.getenv("is_darwin") == "1":
                python_root = Path("/Library/Frameworks/Python.framework/Versions")
                assert python_root.is_dir(), python_root

                for child in python_root.iterdir():
                    if child.name == "Current":
                        continue

                    python_versions[child.name] = child

                # ----------------------------------------------------------------------
                def DarwinPostprocessEnvironmentPath(
                    fullpath: Path,
                ) -> Path:
                    # Remove the environment and os name
                    return fullpath.parent.parent

                # ----------------------------------------------------------------------

                postprocess_environment_path_func = DarwinPostprocessEnvironmentPath

            else:
                python_root = (Path(__file__).parent / ".." / ".." / ".." / Constants.TOOLS_SUBDIR / self.name).resolve()
                assert python_root.is_dir(), python_root

                for child in python_root.iterdir():
                    if not child.is_dir():
                        continue

                    # Ensure that python exists for this os
                    os_fullpath = ActivateActivity.GetCustomizedFullpath(child)
                    if not os_fullpath.is_dir():
                        continue

                    python_versions[child.name] = child

                # ----------------------------------------------------------------------
                def StandardPostprocessEnvironmentPath(
                    fullpath: Path,
                ) -> Path:
                    # Nothing to do here
                    return fullpath

                # ----------------------------------------------------------------------

                postprocess_environment_path_func = StandardPostprocessEnvironmentPath

            for index, (python_version, fullpath) in enumerate(python_versions.items()):
                with nested_dm.VerboseNested(
                    "Processing '{}' ({} of {})...".format(
                        python_version,
                        index + 1,
                        len(python_versions),
                    ),
                    suffix="\n" if nested_dm.is_verbose else "",
                ) as this_dm:
                    fullpath = ActivateActivity.GetCustomizedFullpath(fullpath)
                    fullpath = postprocess_environment_path_func(fullpath)

                    assert fullpath.is_dir(), fullpath

                    if CurrentShell.family_name == "Windows":
                        scripts_dir = fullpath / "Scripts"
                    elif CurrentShell.family_name in ["Linux", "BSD"]:
                        scripts_dir = fullpath / "bin"
                    else:
                        assert False, CurrentShell.family_name  # pragma: no cover

                    if not scripts_dir.is_dir():
                        # Ensure that there aren't any other dirs under the fullpath. We want to
                        # skip the scenario where we didn't expand the content for this version,
                        # but still capture potential errors associated with bad script dir names.
                        assert not any(child for child in fullpath.iterdir() if child.is_dir()), fullpath
                        continue

                    for script in scripts_dir.iterdir():
                        if script.name == "__pycache__":
                            continue

                        if script.suffix in [".pyc", ".pyo"]:
                            continue

                        if not script.is_file():
                            continue

                        result = self.NormalizeScript(script)
                        stats[result.value] += 1

                        this_dm.WriteLine(
                            "{0:<40} {1}\n".format(
                                "'{}':".format(script.name),
                                result.value,
                            ),
                        )

        return []
