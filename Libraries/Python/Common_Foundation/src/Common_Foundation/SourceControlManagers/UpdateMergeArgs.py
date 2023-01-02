# ----------------------------------------------------------------------
# |
# |  UpdateMergeArgs.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-20 19:27:47
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains various types used for updates and merges"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Change(object):
    """A specific change"""

    change: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Date(object):
    """Change nearest to the date on the current branch"""

    date: datetime
    greater_than: Optional[bool]            = field(default=None)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Branch(object):
    """Tip on specified branch"""

    branch: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class BranchAndDate(object):
    """Change nearest to the date on the specified branch"""

    branch: str
    date: datetime
    greater_than: Optional[bool]            = field(default=None)
