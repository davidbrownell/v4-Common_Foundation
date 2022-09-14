# ----------------------------------------------------------------------
# |
# |  All.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-21 19:43:27
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality that looks across all known SourceControlManagers"""

from typing import List

from .GitSourceControlManager import GitSourceControlManager
from .MercurialSourceControlManager import MercurialSourceControlManager
from .SourceControlManager import SourceControlManager


# ----------------------------------------------------------------------
ALL_SCMS: List[SourceControlManager]        = [
    # Oftentimes, scripts using this functionality will default to the first item in this list
    # if a SCM (or name of a SCM) is not explicitly provided. Therefore, this first value should
    # be the most commonly used SCM.
    GitSourceControlManager(),

    MercurialSourceControlManager(),
]
