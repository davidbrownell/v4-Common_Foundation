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

import functools
import os
import sys
import textwrap

from dataclasses import dataclass, field
from typing import Any, Dict, IO, Optional, TextIO, Tuple, Union

from .TextWriter import TextWriter


# ----------------------------------------------------------------------
@dataclass(frozen=True)
@functools.total_ordering
class Capabilities(object):
    """Specific capabilities of a stream"""

    # ----------------------------------------------------------------------
    DEFAULT_CONSOLE_WIDTH                   = 200

    # Note that there is pretty broad support for the `COLUMNS` environment variable, so using that
    # rather than a custom variable name.
    SIMULATE_TERMINAL_COLUMNS_ENV_VAR       = "COLUMNS"
    SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR   = "SIMULATE_TERMINAL_CAPABILITIES_IS_INTERACTIVE"
    SIMULATE_TERMINAL_COLORS_ENV_VAR        = "SIMULATE_TERMINAL_CAPABILITIES_SUPPORTS_COLORS"
    SIMULATE_TERMINAL_HEADLESS_ENV_VAR      = "SIMULATE_TERMINAL_CAPABILITIES_IS_HEADLESS"

    _processed_stdout                       = False

    # ----------------------------------------------------------------------
    columns: int

    is_interactive: bool                    = field(kw_only=True)
    supports_colors: bool                   = field(kw_only=True)

    # Headless streams indicate that it is running in a terminal window without the ability to
    # launch multi-process windows; programs should not display links as there isn't anything
    # to process them.
    is_headless: bool                       = field(kw_only=True)

    _forced_columns: bool                   = field(kw_only=True, compare=False)
    _forced_is_interactive: bool            = field(kw_only=True, compare=False)
    _forced_supports_colors: bool           = field(kw_only=True, compare=False)
    _forced_is_headless: bool               = field(kw_only=True, compare=False)

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        stream: Union[TextIO, TextWriter]=sys.stdout,
        *,
        columns: Optional[int]=None,
        is_interactive: Optional[bool]=None,
        supports_colors: Optional[bool]=None,
        is_headless: Optional[bool]=None,
        no_column_warning: bool=False,
    ) -> "Capabilities":
        """Creates a new capabilities instance"""

        assert (
            getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None) is None
        ), "Capabilities are assigned to a stream when it is first created and cannot be changed. Consider using the method `YieldCapabilities`."

        result = cls._CreateInstance(
            stream,
            columns=columns,
            is_interactive=is_interactive,
            supports_colors=supports_colors,
            is_headless=is_headless,
        )

        # Associate the instance with the stream
        cls.Set(stream, result)

        # As a convenience, cajole rich into simulating this functionality as well
        if stream is sys.stdout and cls._processed_stdout is False:
            try:
                import rich

                if (
                    result._forced_columns
                    or result._forced_is_interactive
                    or result._forced_supports_colors
                    or result._forced_is_headless
                ):
                    rich_args = result._GetRichConsoleArgs()

                    # Width needs to be set separately
                    width_arg = rich_args.pop("width", None)

                    rich.reconfigure(**rich_args)

                    if width_arg:
                        console = rich.get_console()
                        console.size = (width_arg, console.height)

                # Validate the the width is acceptable. This has to be done AFTER
                # the capabilities have been associated with the stream.
                if not no_column_warning:
                    console = rich.get_console()

                    if console.width < cls.DEFAULT_CONSOLE_WIDTH:
                        # Importing here to avoid circular imports
                        from .StreamDecorator import StreamDecorator
                        from .. import TextwrapEx

                        StreamDecorator(
                            sys.stdout,
                            line_prefix=TextwrapEx.CreateWarningPrefix(result),
                        ).write(
                            textwrap.dedent(
                                """\


                                Output is configured for a width of '{}', but your terminal has a width of '{}'.

                                Some formatting may not appear as intended.


                                """,
                            ).format(cls.DEFAULT_CONSOLE_WIDTH, console.width),
                        )

            except ImportError:
                pass

            cls._processed_stdout = True

        return result

    # ----------------------------------------------------------------------
    @classmethod
    def Get(
        cls,
        stream: Union[TextIO, TextWriter],
    ) -> "Capabilities":
        current_capabilities = getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None)
        if current_capabilities is not None:
            return current_capabilities

        return cls.Create(stream)

    # ----------------------------------------------------------------------
    @classmethod
    def Set(
        cls,
        stream: Union[TextIO, TextWriter],
        capabilities: "Capabilities",
    ) -> None:
        assert getattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, None) is None
        setattr(stream, cls._EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME, capabilities)

    # ----------------------------------------------------------------------
    @classmethod
    def Alter(
        cls,
        stream: Union[TextIO, TextWriter],
        *,
        columns: Optional[int]=None,
        is_interactive: Optional[bool]=None,
        supports_colors: Optional[bool]=None,
        is_headless: Optional[bool]=None,
    ) -> Tuple[IO[str], "Capabilities"]:
        current_capabilities = cls.Get(stream)

        # Importing here to avoid circular dependencies
        from .StreamDecorator import StreamDecorator

        stream_decorator = StreamDecorator(stream)

        capabilities = cls._CreateInstance(
            stream_decorator,
            columns=columns if columns is not None else current_capabilities.columns,
            is_interactive=is_interactive if is_interactive is not None else current_capabilities.is_interactive,
            supports_colors=supports_colors if supports_colors is not None else current_capabilities.supports_colors,
            is_headless=is_headless if is_headless is not None else current_capabilities.is_headless,
        )

        return stream_decorator, capabilities # type: ignore

    # ----------------------------------------------------------------------
    def __lt__(
        self,
        other: "Capabilities",
    ) -> bool:
        for attribute_name in [
            "columns",
            "is_interactive",
            "supports_colors",
            "is_headless",
        ]:
            this_value = getattr(self, attribute_name)
            that_value = getattr(other, attribute_name)

            if this_value != that_value:
                return this_value < that_value

        return False

    # ----------------------------------------------------------------------
    try:
        from rich.console import Console

        def CreateRichConsole(
            self,
            file: Optional[IO[str]]=None,
        ) -> Console:
            """Creates a `rich` `Console` instance"""

            args = self._GetRichConsoleArgs()

            # Width needs to be set separately
            width_arg = args.pop("width", None)

            args["file"] = file

            from rich.console import Console
            result = Console(**args)

            if width_arg:
                result.size = (width_arg, result.height)

            return result

    except ImportError:
        # This means that rich wasn't found, which is OK
        pass

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    _EMBEDDED_CAPABILITIES_ATTRIBUTE_NAME   = "__stream_capabilities"

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _CreateInstance(
        cls,
        stream: Union[TextIO, TextWriter],
        *,
        columns: Optional[int]=None,
        is_interactive: Optional[bool]=None,
        supports_colors: Optional[bool]=None,
        is_headless: Optional[bool]=None,
    ) -> "Capabilities":
        # columns
        forced_columns = False

        if columns is not None:
            forced_columns = True
        else:
            value = os.getenv(cls.SIMULATE_TERMINAL_COLUMNS_ENV_VAR)
            if value is not None:
                columns = int(value)
                forced_columns = True
            else:
                columns = cls.DEFAULT_CONSOLE_WIDTH
                forced_columns = True

        # is_interactive
        forced_is_interactive = False

        if is_interactive:
            forced_is_interactive = True
        else:
            value = os.getenv(cls.SIMULATE_TERMINAL_INTERACTIVE_ENV_VAR)
            if value is not None:
                is_interactive = not value == "0"
                forced_is_interactive = True
            else:
                is_interactive = stream.isatty()

        # supports_colors
        forced_supports_colors = False

        if supports_colors is not None:
            forced_supports_colors = True
        else:
            value = os.getenv(cls.SIMULATE_TERMINAL_COLORS_ENV_VAR)
            if value is not None:
                supports_colors = not value == "0"
                forced_supports_colors = True
            else:
                supports_colors = is_interactive

        # is_headless
        forced_is_headless = False

        if is_headless is not None:
            forced_is_headless = True
        else:
            value = os.getenv(cls.SIMULATE_TERMINAL_HEADLESS_ENV_VAR)
            if value is not None:
                is_headless = not value == "0"
                forced_is_headless = True
            else:
                # default is based on interactive
                is_headless = not is_interactive

                if not is_headless:
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

        assert is_headless is not None

        return Capabilities(
            columns=columns,
            is_interactive=is_interactive,
            supports_colors=supports_colors,
            is_headless=is_headless,
            _forced_columns=forced_columns,
            _forced_is_interactive=forced_is_interactive,
            _forced_supports_colors=forced_supports_colors,
            _forced_is_headless=forced_is_headless,
        )

    # ----------------------------------------------------------------------
    def _GetRichConsoleArgs(self) -> Dict[str, Any]:
        """Returns arguments suitable to instantiate a rich `Console` instance"""

        args: Dict[str, Any] = {
            "legacy_windows": False,
        }

        if self._forced_columns:
            args["width"] = self.columns

        if self._forced_is_interactive:
            args["force_interactive"] = self.is_interactive

        if self._forced_supports_colors:
            if self.supports_colors:
                # We can't be too aggressive in the selection of a color
                # system or else the content won't display if we over-reach.
                args["color_system"] = "standard"
            else:
                args["no_color"] = True

        return args
