# ----------------------------------------------------------------------
# |
# |  TextwrapEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-23 13:06:19
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements for the textwrap library"""

import math
import re
import sys
import textwrap

from enum import auto, Enum
from typing import Callable, List, Optional, Pattern, Union

from .Streams.Capabilities import Capabilities


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
# Normally, I'd use colorama for these values, but this package cannot have any
# external dependencies.
BRIGHT_RED_COLOR_ON                         = "\033[31;1m"  # Red / Bright
BRIGHT_GREEN_COLOR_ON                       = "\033[32;1m"  # Green / Bright
BRIGHT_YELLOW_COLOR_ON                      = "\033[33;1m"  # Yellow / Bright

BRIGHT_WHITE_COLOR_ON                       = "\033[37;1m"  # White / Bright
DIM_WHITE_COLOR_ON                          = "\033[;7m"    # Inverse video

# ----------------------------------------------------------------------
ERROR_COLOR_ON                              = BRIGHT_RED_COLOR_ON
INFO_COLOR_ON                               = DIM_WHITE_COLOR_ON
SUCCESS_COLOR_ON                            = BRIGHT_GREEN_COLOR_ON
WARNING_COLOR_ON                            = BRIGHT_YELLOW_COLOR_ON
VERBOSE_COLOR_ON                            = DIM_WHITE_COLOR_ON
DEBUG_COLOR_ON                              = BRIGHT_WHITE_COLOR_ON

# ----------------------------------------------------------------------
COLOR_OFF                                   = "\033[0m" # Reset


# ----------------------------------------------------------------------
class Justify(Enum):
    """Line justification"""

    Left                                    = auto()
    Center                                  = auto()
    Right                                   = auto()

    # ----------------------------------------------------------------------
    def Justify(
        self,
        value: str,
        padding: int,
    ) -> str:
        if self == Justify.Left:
            return value.ljust(padding)

        if self == Justify.Center:
            return value.center(padding)

        if self == Justify.Right:
            return value.rjust(padding)

        assert False, self  # pragma: no cover


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def Indent(
    value: str,
    indentation: Union[str, int],
    *,
    skip_first_line: bool=False,
) -> str:
    if isinstance(indentation, int):
        indentation = " " * indentation

    if skip_first_line:
        is_first_line = True

        # ----------------------------------------------------------------------
        def ShouldIndent(_) -> bool:
            nonlocal is_first_line

            if is_first_line:
                is_first_line = False
                return False

            return True

        # ----------------------------------------------------------------------

        should_indent = ShouldIndent
    else:
        should_indent = lambda _: True

    assert isinstance(indentation, str), indentation
    return textwrap.indent(value, indentation, should_indent)


# ----------------------------------------------------------------------
def CreateTable(
    headers: List[str],
    all_values: List[List[str]],
    col_justifications: Optional[List[Justify]]=None,
    decorate_values_func: Optional[Callable[[int, List[str]], List[str]]]=None,
    on_col_sizes_calculated: Optional[Callable[[List[int]], None]]=None,
    col_padding: str="  ",
    *,
    decorate_headers: bool=False,
    is_vertical: bool=False,
) -> str:
    assert col_justifications is None or len(col_justifications) == len(headers)
    assert decorate_headers is False or decorate_values_func

    col_justifications = col_justifications or [ Justify.Left, ] * len(headers)
    decorate_values_func = decorate_values_func or (lambda _, row: row)
    on_col_sizes_calculated = on_col_sizes_calculated or (lambda _: None)

    # Calculate the col sizes
    col_sizes: List[int] = []

    if is_vertical:
        # Get the column size for the header
        for header_index, header in enumerate(headers):
            if not header.endswith(":"):
                header += ":"
                headers[header_index] = header

        col_sizes = [max(len(header) for header in headers), 0]

    else:
        # Get the column sizes for each row
        col_sizes = [len(header) for header in headers]

        for row in all_values:
            if not row:
                continue

            assert len(row) == len(headers)
            for index, col_value in enumerate(row):
                col_sizes[index] = max(len(col_value), col_sizes[index])

    on_col_sizes_calculated(col_sizes)

    # Create the template
    row_template = "{}\n".format(
        col_padding.join(
            "{{:<{}}}".format(col_size) if col_size != 0 else "{}" for col_size in col_sizes
        ),
    )

    # Create the rows
    rows: List[str] = []

    if is_vertical:
        decorated_headers: List[str] = []

        # Headers
        for col_justification, header_value in zip(col_justifications, headers):
            decorated_headers.append(col_justification.Justify(header_value, col_sizes[0]))

        if decorate_headers:
            decorated_headers = decorate_values_func(-2, decorated_headers)

        for values_index, values in enumerate(all_values):
            values = decorate_values_func(values_index, values)

            for header, value in zip(headers, values):
                rows.append(row_template.format(header, value))

            rows.append("\n")

    else:
        # ----------------------------------------------------------------------
        def CreateRow(
            index: int,
            values: List[str],
        ):
            decorated_values: List[str] = []

            for col_justification, col_value, col_size in zip(col_justifications, values, col_sizes):
                decorated_values.append(col_justification.Justify(col_value, col_size))

            if index >= 0 or decorate_headers:
                decorated_values = decorate_values_func(index, decorated_values)

            rows.append(row_template.format(*decorated_values))

        # ----------------------------------------------------------------------

        CreateRow(-2, headers)
        CreateRow(-1, ["-" * col_size for col_size in col_sizes])

        for index, values in enumerate(all_values):
            CreateRow(index, values)

    return "".join(rows)


# ----------------------------------------------------------------------
def CreateAnsiHyperLink(
    url: str,
    value: str,
) -> str:
    return "\033]8;;{}\033\\{}\033]8;;\033\\".format(url, value)


# ----------------------------------------------------------------------
# "      Text [suffix]    " -> "      Text [suffix]    "
#                                           ^^^^^^
#                                          hyperlink
_create_ansi_hyperlink_suffix_regex: Optional[Pattern]                      = None

# "      Text         " -> "       Text         "
#                                  ^^^^
#                                hyperlink
_create_ansi_hyperlink_standard_regex: Optional[Pattern]                    = None

def CreateAnsiHyperLinkEx(
    url: str,
    value: str,
) -> str:
    """Intelligently Creates an Ansi Hyperlink using common conventions"""

    global _create_ansi_hyperlink_suffix_regex      # pylint: disable=global-statement
    global _create_ansi_hyperlink_standard_regex    # pylint: disable=global-statement

    if _create_ansi_hyperlink_suffix_regex is None:
        _create_ansi_hyperlink_suffix_regex = re.compile(
            r"""(?#
            Start                           )^(?#
            Whitespace prefix               )(?P<prefix>\s*)(?#
            Text                            )(?P<text>.+?)(?#
            Link Text                       )\[(?P<link_text>[^\]]+)\](?#
            Whitespace suffix               )(?P<suffix>\s*)(?#
            End                             )$(?#
            )""",
        )

    match = _create_ansi_hyperlink_suffix_regex.match(value)
    if match:
        return "{prefix}{text}[{link}]{suffix}".format(
            prefix=match.group("prefix"),
            text=match.group("text"),
            link=CreateAnsiHyperLink(url, match.group("link_text")),
            suffix=match.group("suffix"),
        )

    if _create_ansi_hyperlink_standard_regex is None:
        _create_ansi_hyperlink_standard_regex = re.compile(
            r"""(?#
            Start                           )^(?#
            Whitespace prefix               )(?P<prefix>\s*)(?#
            Text                            )(?P<text>.+?)(?#
            Whitespace suffix               )(?P<suffix>\s*)(?#
            End                             )$(?#
            )""",
        )

    match = _create_ansi_hyperlink_standard_regex.match(value)
    if match:
        return "{prefix}{url}{suffix}".format(
            prefix=match.group("prefix"),
            url=CreateAnsiHyperLink(url, match.group("text")),
            suffix=match.group("suffix"),
        )

    return CreateAnsiHyperLink(url, value)


# ----------------------------------------------------------------------
def GetSizeDisplay(
    num_bytes: int,
    *,
    exact_value: bool=False,
) -> str:
    if num_bytes < 1024:
        if not exact_value:
            return "1 KB"

        return "{} B".format(num_bytes)

    result = float(num_bytes) / 1024.0

    for unit in [ 'K', 'M', 'G', 'T', 'P', 'E', 'Z', ]:
        if result < 1024.0:
            if not exact_value:
                result = int(math.ceil(result))

            return "{} {}B".format(result, unit)

        result /= 1024.0

    return "%.1f YiB" % result


# ----------------------------------------------------------------------
def CreateCustomPrefixFunc(
    header: str,
    color_value: str,
) -> Callable[[Optional[Capabilities]], str]:
    # ----------------------------------------------------------------------
    def Impl(
        capabilities: Optional[Capabilities],
    ) -> str:
        if (capabilities or Capabilities.Get(sys.stdout)).supports_colors:
            this_color_on = color_value
            this_color_off = COLOR_OFF
        else:
            this_color_on = ""
            this_color_off = ""

        return "{}{}:{} ".format(this_color_on, header, this_color_off)

    # ----------------------------------------------------------------------

    return Impl


# ----------------------------------------------------------------------
CreateErrorPrefix                           = CreateCustomPrefixFunc("ERROR", ERROR_COLOR_ON)
CreateWarningPrefix                         = CreateCustomPrefixFunc("WARNING", WARNING_COLOR_ON)
CreateInfoPrefix                            = CreateCustomPrefixFunc("INFO", INFO_COLOR_ON)
CreateSuccessPrefix                         = CreateCustomPrefixFunc("SUCCESS", SUCCESS_COLOR_ON)
CreateVerbosePrefix                         = CreateCustomPrefixFunc("VERBOSE", VERBOSE_COLOR_ON)
CreateDebugPrefix                           = CreateCustomPrefixFunc("DEBUG", DEBUG_COLOR_ON)


# ----------------------------------------------------------------------
def CreateErrorText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    error_per_line: bool=False,
) -> str:
    return CreateText(CreateErrorPrefix, value, capabilities=capabilities, prefix_per_line=error_per_line)


# ----------------------------------------------------------------------
def CreateWarningText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    warning_per_line: bool=False,
) -> str:
    return CreateText(CreateWarningPrefix, value, capabilities=capabilities, prefix_per_line=warning_per_line)


# ----------------------------------------------------------------------
def CreateInfoText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    info_per_line: bool=False,
) -> str:
    return CreateText(CreateInfoPrefix, value, capabilities=capabilities, prefix_per_line=info_per_line)


# ----------------------------------------------------------------------
def CreateSuccessText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    success_per_line: bool=False,
) -> str:
    return CreateText(CreateSuccessPrefix, value, capabilities=capabilities, prefix_per_line=success_per_line)


# ----------------------------------------------------------------------
def CreateVerboseText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    verbose_per_line: bool=False,
) -> str:
    return CreateText(CreateVerbosePrefix, value, capabilities=capabilities, prefix_per_line=verbose_per_line)


# ----------------------------------------------------------------------
def CreateDebugText(
    value: str,
    *,
    capabilities: Optional[Capabilities]=None,
    debug_per_line: bool=False,
) -> str:
    return CreateText(CreateDebugPrefix, value, capabilities=capabilities, prefix_per_line=debug_per_line)


# ----------------------------------------------------------------------
def CreateText(
    create_prefix_func: Callable[[Optional[Capabilities]], str],
    value: str,
    *,
    capabilities: Optional[Capabilities],
    prefix_per_line: bool,
) -> str:
    prefix = create_prefix_func(capabilities)

    if prefix_per_line:
        return Indent(value, prefix)

    # Put newlines before the header
    starting_index = 0

    while starting_index < len(value) and value[starting_index] == "\n":
        starting_index += 1

    return "{}{}".format(
        "\n" * starting_index,
        Indent(
            "{}{}".format(prefix, value[starting_index:]),
            # The indent is the length of the prefix without color decorations
            len(
                create_prefix_func(
                    Capabilities.Alter(
                        sys.stdout,
                        supports_colors=False,
                    )[1],
                ),
            ),
            skip_first_line=True,
        ),
    )


# ----------------------------------------------------------------------
def CreateStatusText(
    succeeded: Optional[int],
    failed: Optional[int],
    warnings: Optional[int],
    *,
    capabilities: Optional[Capabilities]=None,
) -> str:
    if (capabilities or Capabilities.Get(sys.stdout)).supports_colors:
        success_on = SUCCESS_COLOR_ON
        failed_on = ERROR_COLOR_ON
        warning_on = WARNING_COLOR_ON
        color_off = COLOR_OFF
    else:
        success_on = ""
        failed_on = ""
        warning_on = ""
        color_off = ""

    parts: List[str] = []

    if succeeded is not None:
        if succeeded == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(success_on, succeeded, color_off)

        parts.append("{} succeeded".format(prefix))

    if failed is not None:
        if failed == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(failed_on, failed, color_off)

        parts.append("{} failed".format(prefix))

    if warnings is not None:
        if warnings == 0:
            prefix = "0"
        else:
            prefix = "{}{}{}".format(warning_on, warnings, color_off)

        parts.append("{} warnings".format(prefix))

    return ", ".join(parts)
