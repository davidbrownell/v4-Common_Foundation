# ----------------------------------------------------------------------
# |
# |  Deactivate.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-11 15:00:25
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Deactivates a repository"""

import json
import os
import sys
import textwrap

from typing import List

try:
    import typer
except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.ContextlibEx import ExitStack  # type: ignore
from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags  # Type: ignore
from Common_Foundation import TextwrapEx  # type: ignore

from .GenerateCommands import GenerateCommands

from .. import Constants


# ----------------------------------------------------------------------
def EntryPoint(
    output_filename_or_stdout: str=typer.Argument(..., help="Filename for generated content or standard output if the value is 'stdout'."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write additional debug information to the terminal."),
):
    # ----------------------------------------------------------------------
    def Execute() -> List[Commands.Command]:
        with DoneManager.Create(
            sys.stdout,
            heading=None,
            line_prefix="",
            display=False,
            output_flags=DoneManagerFlags.Create(
                verbose=verbose,
                debug=debug,
            ),
        ) as dm:
            commands: List[Commands.Command] = []

            original_environment_filename = CurrentShell.temp_directory / Constants.GENERATED_ACTIVATION_ORIGINAL_ENVIRONMENT_FILENAME_TEMPLATE.format(
                os.getenv(Constants.DE_REPO_ACTIVATED_KEY),
            )

            if not original_environment_filename.is_file():
                raise Exception("State created during initial activation could not be found; deactivation cannot be completed.")

            with original_environment_filename.open() as f:
                original_environment = json.load(f)

            for k in os.environ.keys():
                if k.startswith("_DEVELOPMENT"):
                    continue

                commands.append(Commands.Set(k, None))

            for k, v in original_environment.items():
                commands.append(Commands.Set(k, v))

            if CurrentShell.family_name == "Linux":
                commands += [
                    Commands.Message("\n"),
                    Commands.Message(
                        TextwrapEx.CreateWarningText(
                            textwrap.dedent(
                                """\
                                I don't know of a good way to restore the original prompt given that the prompt isn't stored as an environment variable.
                                Hopefully, this scenario is uncommon enough that the wonky prompt isn't a significant issue.

                                """,
                            ),
                            capabilities=dm.capabilities,
                        ),
                    ),
                    Commands.CommandPrompt("DEACTIVATED"),
                ]

            return commands

    # ----------------------------------------------------------------------

    result, commands = GenerateCommands(
        Execute,
        debug=debug,
    )

    if output_filename_or_stdout == "stdout":
        final_output_stream = sys.stdout
        close_stream_func = lambda: None
    else:
        final_output_stream = open(output_filename_or_stdout, "w")
        close_stream_func = final_output_stream.close

    with ExitStack(close_stream_func):
        final_output_stream.write(CurrentShell.GenerateCommands(commands))

    return result


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    typer.run(EntryPoint)
