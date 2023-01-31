# ----------------------------------------------------------------------
# |
# |  DynamicPluginArchitecture.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 14:08:58
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""
Contains methods that help when creating dynamic plugin architectures across
repository boundaries.

Repositories often times have to modify how scripts in other repositories operate
in a way that doesn't create a hard dependency from the base repository to the
extension (or plugin) repository.

For example, Common_Foundation defines a script called Tester, where the code is
able to compile tests written in different languages through the use of language-
specific plugins in the form of Compilers. However, these compilers are defined
in repositories outside of Common_Foundation.

To address these dependencies, we create a layer of indirection through this module;
the script that is defined in the base repository defines an environment variable
that is updated by other repositories that provide plugins for that script. When
the script is launched, it queries that environment variable and instantiates all
the plugins that have been associated with it. Care is taken to ensure that the
environment variable can be associated with a large number of plugins.
"""

import importlib
import os
import sys
import types

from pathlib import Path
from typing import Callable, List, Generator, Set

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell import Commands
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator


# ----------------------------------------------------------------------
def EnumeratePlugins(
    environment_var_name: str,
) -> Generator[types.ModuleType, None, None]:
    """Enumerates plugins that have been registered with the provided environment name"""

    filename = os.getenv(environment_var_name)
    if filename is None:
        raise Exception("The environment name '{}' is not defined.".format(environment_var_name))

    filename = Path(filename)
    if not filename.is_file():
        raise Exception(
            "The file associated with the environment variable '{}' does not exist ({}).".format(
                environment_var_name,
                filename,
            ),
        )

    with filename.open() as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        plugin = Path(line)
        if not plugin.is_file():
            raise Exception(
                "The plugin '{}', associated with the environment variable '{}', does not exist.".format(
                    plugin,
                    environment_var_name,
                ),
            )

        yield LoadPlugin(plugin)


# ----------------------------------------------------------------------
def LoadPlugin(
    path: Path,
) -> types.ModuleType:
    """Dynamically loads a python module"""

    assert path.is_file(), path

    path = path.resolve()

    sys.path.insert(0, str(path.parent))
    with ExitStack(lambda: sys.path.pop(0)):
        return importlib.import_module(path.stem)


# ----------------------------------------------------------------------
def CreateRegistrationCommands(
    dm: DoneManager,
    environment_var_name: str,
    directory: Path,
    is_valid_func: Callable[[Path], bool],
    *,
    force: bool=False,                      # This should only be True for the repository that defines the environment var
) -> List[Commands.Command]:
    """Adds all files within a directory to the file associated with the provided environment variable"""

    filenames: Set[str] = set()
    original_num_plugins = 0

    # ----------------------------------------------------------------------
    def PluralPlugin(
        value: int,
    ) -> str:
        return "{} {}".format(value, "plugin" if value == 1 else "plugins")

    # ----------------------------------------------------------------------

    with dm.Nested(
        "Processing '{}'...".format(environment_var_name),
        [
            lambda: "{} found".format(PluralPlugin(len(filenames))),
            lambda: "{} added".format(PluralPlugin(len(filenames) - original_num_plugins)),
        ],
        suffix="\n" if dm.is_debug else "",
    ) as this_dm:
        if not directory.is_dir():
            raise Exception("'{}' is not a valid directory.".format(directory))

        for child in directory.iterdir():
            if not child.is_file():
                continue

            if not is_valid_func(child):
                continue

            filenames.add(str(child.resolve()))

        commands: List[Commands.Command] = []

        source_filename = os.getenv(environment_var_name)
        if force or not source_filename:
            source_filename = CurrentShell.CreateTempFilename(
                ".DynamicPluginArchitecture.SourceRepositoryTools",
            )

            source_filename_str = str(source_filename)

            commands.append(Commands.Set(environment_var_name, source_filename_str))

            # Add this filename to the environment so that it can be used by other activation scripts
            os.environ[environment_var_name] = source_filename_str

            this_dm.WriteLine("Creating '{}'".format(source_filename_str))

        else:
            source_filename = Path(source_filename)

            with source_filename.open() as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                line = Path(line)
                if not line.is_file():
                    continue

                filenames.add(str(line.resolve()))
                original_num_plugins += 1

        content = "\n".join(sorted(filenames))

        with source_filename.open("w") as f:
            f.write(content)

        with this_dm.YieldDebugStream() as stream:
            indented_stream = StreamDecorator(stream, "    ")

            indented_stream.write("\n")
            indented_stream.write(content)
            indented_stream.write("\n\n")

        return commands
