# ----------------------------------------------------------------------
# |
# |  StreamDecorator_UnitTests.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-14 09:10:18
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Unit tests for StreamDecorator"""

import textwrap

from io import StringIO

from ..StreamDecorator import StreamDecorator


# TODO: More tests required; use coverage as a guide

# ----------------------------------------------------------------------
def test_Standard():
    sink = StringIO()
    s = StreamDecorator(sink, prefix="Header\n\n", line_prefix="<<", line_suffix=">>")

    s.write("\n1")
    s.write("two")
    s.write("3\n")
    s.write("four\nfive\nsix")
    s.flush()
    s.write("seven\n")
    s.write("eight")
    s.flush()

    sink = sink.getvalue()

    s.close()

    assert sink == textwrap.dedent(
        """\
        Header

        <<>>
        <<1two3>>
        <<four>>
        <<five>>
        <<sixseven>>
        <<eight""",
    )
