# ----------------------------------------------------------------------
# |
# |  StreamTestHelpers.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-12-06 07:43:54
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Test helpers for content found in ../Streams"""

import re

from io import StringIO
from typing import Generator, Match, Optional, Union

from Common_Foundation.Streams.Capabilities import Capabilities
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags


# ----------------------------------------------------------------------
def GenerateDoneManagerAndSink(
    heading: str="Heading",
    *,
    expected_result: Optional[int]=None,
    verbose: bool=False,
    debug: bool=False,
    keep_duration_hours: bool=False,
    keep_duration_minutes: bool=False,
    keep_duration_seconds: bool=False,
) -> Generator[
    Union[
        DoneManager,                        # 1st yield
        str,                                # 2nd yield
    ],
    None,
    None,
]:
    """\
    Generates a DoneManager followed by a sink populated by the DoneManager.

    Example Usage:
        dm_and_sink = iter(GenerateDoneManagerAndSink())

        dm = cast(DoneManager, next(dm_and_sink))

        dm.WriteInfo("Content")

        sink = cast(str, next(dm_and_sink))

        assert sink == textwrap.dedent(
            '''\
            Heading...
              INFO: Content
            DONE! (0, <scrubbed time duration>)
            ''',
        )
    """

    sink = StringIO()

    # ----------------------------------------------------------------------
    def GetSinkOutput() -> str:
        nonlocal sink

        sink = sink.getvalue()

        # Remove durations from the output, as they are going to vary from execution-to-execution
        if keep_duration_hours or keep_duration_minutes or keep_duration_seconds:
            # ----------------------------------------------------------------------
            def Replace(
                match: Match,
            ) -> str:
                hours = match.group("hours") if keep_duration_hours else "??"
                minutes = match.group("minutes") if keep_duration_minutes else "??"
                seconds = match.group("seconds") if keep_duration_seconds else "??"

                return "{}:{}:{}".format(hours, minutes, seconds)

            # ----------------------------------------------------------------------

            replace_func = Replace
        else:
            replace_func = lambda _: "<scrubbed duration>"

        sink = re.sub(
            r"""(?#
            Hours                               )(?P<hours>\d+)(?#
            sep                                 )\:(?#
            Minutes                             )(?P<minutes>\d+)(?#
            sep                                 )\:(?#
            Seconds                             )(?P<seconds>\d+(?:\.\d+)?)(?#
            )""",
            replace_func,
            sink,
        )

        # Remove any trailing whitespace
        sink = "\n".join(line.rstrip() for line in sink.split("\n"))

        return sink

    # ----------------------------------------------------------------------

    # Do not decorate the output, regardless of what environment variables specify
    Capabilities.Create(
        sink,
        is_interactive=False,
        supports_colors=False,
        is_headless=True,
    )

    with DoneManager.Create(
        sink,
        heading,
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        yield dm

        assert expected_result is None or dm.result == expected_result, (dm.result, expected_result, GetSinkOutput())

    yield GetSinkOutput()
