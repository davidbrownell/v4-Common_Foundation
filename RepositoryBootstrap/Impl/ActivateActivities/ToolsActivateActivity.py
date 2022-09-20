# ----------------------------------------------------------------------
# |
# |  ToolsActivateActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 21:01:25
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ToolsActivateActivity object"""

import os
import traceback

from pathlib import Path
from typing import List, Optional

import inflect as inflect_mod

from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore
from Common_Foundation.Types import overridemethod

from ...ActivateActivity import ActivateActivity
from ...Configuration import VersionSpecs
from ... import Constants
from ... import DataTypes


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()


# ----------------------------------------------------------------------
class ToolsActivateActivity(ActivateActivity):
    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Tools"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateCommandsImpl(
        self,
        dm: DoneManager,
        configuration: Optional[str],
        repositories: List[DataTypes.ConfiguredRepoDataWithPath],
        version_specs: VersionSpecs,
        generated_dir: Path,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        commands: List[Commands.Command] = []
        paths: List[Path] = []

        with dm.VerboseNested(
            "Searching...",
            lambda: "{} found".format(inflect.no("tool", len(paths))),
            display_exceptions=False,
        ) as nested_dm:
            for repository_index, repository in enumerate(repositories):
                original_num_commands = len(commands)
                original_num_paths = len(paths)

                with nested_dm.Nested(
                    "'{}' ({} of {})...".format(
                        repository.root,
                        repository_index + 1,
                        len(repositories),
                    ),
                    lambda: "{} added".format(
                        len(commands) - original_num_commands + len(paths) - original_num_paths,
                    ),
                    display_exceptions=False,
                ) as this_dm:
                    potential_tools_path = repository.root / Constants.TOOLS_SUBDIR
                    if not potential_tools_path.is_dir():
                        continue

                    for tool_path in potential_tools_path.iterdir():
                        if not tool_path.is_dir():
                            continue

                        if (tool_path / Constants.IGNORE_DIRECTORY_AS_TOOL_SENTINEL_FILENAME).exists():
                            continue

                        try:
                            path = self.GetVersionedDirectory(tool_path, version_specs.tools)

                        except Exception as ex:
                            if this_dm.is_debug:
                                warning = traceback.format_exc()
                            else:
                                warning = str(ex)

                            this_dm.WriteWarning(warning)
                            this_dm.WriteLine("\n")

                            continue

                        # Don't count any tools as official if they are just here to prevent warnings
                        items = list(path.iterdir())

                        if len(items) == 1 and items[0].name.lower() in ["readme.txt", "readme.md"]:
                            continue

                        # Look for an activation customization script here. If it exists, invoke that
                        # rather than our custom functionality.
                        potential_activation_filepath = path / "{}{}".format(
                            Constants.ACTIVATE_ENVIRONMENT_NAME,
                            CurrentShell.script_extensions[0],
                        )

                        if potential_activation_filepath.is_file():
                            commands.append(Commands.Call(str(potential_activation_filepath)))
                            continue

                        # Add well-known suffixes to the path if they exist
                        new_paths: List[Path] = []

                        for potential_suffix in [
                            "bin",
                            "sbin",
                            os.path.join("usr", "bin"),
                            os.path.join("usr", "sbin"),
                        ]:
                            potential_path = path / potential_suffix
                            if potential_path.is_dir():
                                new_paths.append(potential_path)

                        if not new_paths:
                            new_paths.append(path)

                        paths += new_paths

        if paths:
            commands.append(Commands.AugmentPath.Create([str(path) for path in paths]))

        return commands
