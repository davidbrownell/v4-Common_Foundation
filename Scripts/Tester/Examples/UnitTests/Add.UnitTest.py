# ----------------------------------------------------------------------
# |
# |  Add.UnitTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 08:32:33
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""\
Unit tests for Add.

This code to demonstrate the capabilities of Tester and should not be used with any
real code. A real Python test parser is available as part of the `Common_PythonDevelopment`
repository, available at `https://github.com/davidbrownell/v4-Common_PythonDevelopment`.
"""

import os
import sys
import traceback

from pathlib import Path

from Common_Foundation.ContextlibEx import ExitStack


# ----------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]
    from Add import Add  # type: ignore  # pylint: disable=import-error


# ----------------------------------------------------------------------
def test_Add():
    assert Add(1, 23) == 24
    assert Add(23, 1) == 24


# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        test_Add()
    except AssertionError as ex:
        sys.stdout.write(traceback.format_exc())
        sys.exit(-1)
