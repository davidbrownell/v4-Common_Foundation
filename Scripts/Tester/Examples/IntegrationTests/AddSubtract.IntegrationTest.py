# ----------------------------------------------------------------------
# |
# |  AddSubtract.IntegrationTest.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-08 08:56:50
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""\
Integration tests for Add and Subtract.

This code to demonstrate the capabilities of Tester and should not be used with any
real code. A real Python test parser is available as part of the `Common_PythonDevelopment`
repository, available at `https://github.com/davidbrownell/v4-Common_PythonDevelopment`.
"""

import os
import sys
import unittest

from pathlib import Path

from Common_Foundation.ContextlibEx import ExitStack


# ----------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
with ExitStack(lambda: sys.path.pop(0)):
    assert os.path.isdir(sys.path[0]), sys.path[0]

    from Add import Add  # pylint: disable=import-error
    from Subtract import Subtract  # pylint: disable=import-error


# ----------------------------------------------------------------------
class TestSuite(unittest.TestCase):
    def test_AddSubtract(self):
        self.assertEqual(Add(1, Subtract(23, 2)), 22)
        self.assertEqual(Subtract(4, Add(23, 1)), -20)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    try:
        sys.exit(
            unittest.main(
                verbosity=2,
            ),
        )
    except KeyboardInterrupt:
        pass
