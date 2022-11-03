# ----------------------------------------------------------------------
# |
# |  PanelPrint.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-25 14:57:15
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Called by scripts to write a pretty panel to the terminal"""

import sys

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

Console(
    file=sys.stdout,  # type: ignore
    color_system="standard",
    force_terminal=True,
    force_interactive=False,
    legacy_windows=False,
    no_color=False,
).print(
    Panel(
        Text(sys.argv[1]),
        expand=False,
        padding=(1, 2),
        style=sys.argv[2] if len(sys.argv) > 2 else "",
    ),
)
