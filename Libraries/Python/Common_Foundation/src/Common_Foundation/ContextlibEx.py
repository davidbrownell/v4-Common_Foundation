# ----------------------------------------------------------------------
# |
# |  ContextlibEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-23 06:20:30
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements to the contextlib package"""

from contextlib import contextmanager, ExitStack as ExitStackImpl
from typing import Any, Callable


# ----------------------------------------------------------------------
@contextmanager
def ExitStack(
    *args: Callable[[], Any],
):
    with ExitStackImpl() as exit_stack:
        for arg in args:
            exit_stack.callback(arg)

        yield exit_stack
