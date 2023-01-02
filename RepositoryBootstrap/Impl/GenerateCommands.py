# ----------------------------------------------------------------------
# |
# |  GenerateCommands.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 14:05:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality used when generating commands to be executed during environment setup/activation"""

import textwrap
import traceback

from typing import Callable, cast, List, Tuple, Union

import typer

from Common_Foundation.Shell.All import CurrentShell                        # type: ignore
from Common_Foundation.Shell.Commands import Command, Exit, Message         # type: ignore
from Common_Foundation.Streams.Capabilities import Capabilities             # type: ignore
from Common_Foundation import TextwrapEx                                    # type: ignore


# ----------------------------------------------------------------------
def GenerateCommands(
    functor: Callable[
        [],
        Union[
            int,
            List[Command],
            Tuple[int, List[Command]],
        ],
    ],
    *,
    debug: bool,
) -> Tuple[int, List[Command]]:
    assert functor

    capabilities = Capabilities.Create()

    commands: List[Command] = []

    is_error_condition = False

    try:
        result = functor()

        if isinstance(result, int):
            commands = []
        elif isinstance(result, tuple):
            result, commands = result
        else:
            commands = result
            result = 0

    except typer.Exit:
        raise

    except Exception as ex:
        if debug:
            error = traceback.format_exc()
        else:
            error = str(ex)

        is_error_condition = True

        commands = [
            Message(
                "\n\n{}".format(
                    TextwrapEx.CreateErrorText(
                        error,
                        capabilities=capabilities,
                    ),
                ),
            ),
            Exit(return_code=-1),
        ]

        result = -1

    if debug and not is_error_condition and commands:
        commands = cast(
            List[Command],
            [
                Message(
                    "\n{}\n".format(
                        TextwrapEx.CreateText(
                            TextwrapEx.CreateCustomPrefixFunc("DEBUG", TextwrapEx.BRIGHT_WHITE_COLOR_ON),
                            textwrap.dedent(
                                """\
                                -----------------------------------------------------------
                                -----------------------------------------------------------

                                The following commands were dynamically generated based on
                                information in the repository and its dependencies and will
                                now be run.

                                -----------------------------------------------------------
                                -----------------------------------------------------------

                                {}
                                """,
                            ).format(CurrentShell.GenerateCommands(commands)),
                            capabilities=capabilities,
                            prefix_per_line=True,
                        ),
                    ),
                ),
            ],
        ) + commands

    return result, commands
