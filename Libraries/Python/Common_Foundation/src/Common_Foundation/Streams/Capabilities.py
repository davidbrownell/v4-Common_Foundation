# ----------------------------------------------------------------------
# |
# |  Capabilities.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-13 10:34:12
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Information about the capabilities of streams"""

import sys
import textwrap

from dataclasses import dataclass, field
from typing import TextIO, Union

from .TextWriter import TextWriter


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Capabilities(object):
    """Specific capabilities of a stream"""

    # ----------------------------------------------------------------------
    DEFAULT_CONSOLE_WIDTH                   = 200

    # ----------------------------------------------------------------------
    is_interactive: bool                    = field(kw_only=True)
    supports_colors: bool                   = field(kw_only=True)

    # Headless streams indicate that it is running in a terminal window without the ability to
    # launch multi-process windows; programs should not display links as there isn't anything
    # to process them.
    is_headless: bool                       = field(kw_only=True)

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        stream: Union[TextIO, TextWriter]=sys.stdout,
    ) -> "Capabilities":
        is_interactive = stream.isatty()
        supports_colors = is_interactive

        try:
            from ..Shell.All import CurrentShell

            is_headless = CurrentShell.IsContainerEnvironment()
        except Exception as ex:
            # This functionality can be invoked very early during the activation process. If so,
            # catch this error and assume that we are headless until we know otherwise.
            if "No shell found for" in str(ex):
                is_headless = True
            else:
                raise

        if not is_interactive:
            is_headless = True

        return cls(
            is_interactive=is_interactive,
            supports_colors=supports_colors,
            is_headless=is_headless,
        )

    # ----------------------------------------------------------------------
    def __post_init__(self):
        try:
            import rich

            console = rich.get_console()

            # Update rich if we are headless
            if not self.is_interactive:
                console.size = (self.__class__.DEFAULT_CONSOLE_WIDTH, console.height)

            elif (
                not self.__class__._displayed_width_warning  # pylint: disable=protected-access
                and console.width < self.__class__.DEFAULT_CONSOLE_WIDTH
            ):
                # Importing here to avoid circular imports
                from .StreamDecorator import StreamDecorator
                from .. import TextwrapEx

                StreamDecorator(
                    sys.stdout,
                    line_prefix=TextwrapEx.CreateWarningPrefix(self),
                ).write(
                    textwrap.dedent(
                        """\


                        Output is configured for a width of '{}', but your terminal has a width of '{}'.

                        Some formatting may not appear as intended.


                        """,
                    ).format(
                        self.__class__.DEFAULT_CONSOLE_WIDTH,
                        console.width,
                    ),
                )

                self.__class__._displayed_width_warning = True  # pylint: disable=protected-access

        except ImportError:
            pass

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _displayed_width_warning                = False
