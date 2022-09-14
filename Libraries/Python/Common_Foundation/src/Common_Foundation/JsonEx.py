# ----------------------------------------------------------------------
# |
# |  JsonEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-16 10:30:09
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Enhancements for the json library"""

import json

from pathlib import Path
from typing import Any, Optional, TextIO


# ----------------------------------------------------------------------
def Dump(
    obj: Any,
    f: TextIO,
) -> None:
    return json.dump(
        obj,
        f,
        cls=_Encoder,
    )


# ----------------------------------------------------------------------
def DumpToString(
    obj: Any,
) -> str:
    return json.dumps(
        obj,
        cls=_Encoder,
    )


# ----------------------------------------------------------------------
def JsonToOptional(
    value: str,
) -> Optional[str]:
    if value == "null":
        return None

    return value


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
class _Encoder(json.JSONEncoder):
    # ----------------------------------------------------------------------
    def default(self, obj):
        if isinstance(obj, Path):
            return obj.as_posix()

        return obj.__dict__
