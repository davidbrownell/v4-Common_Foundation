# ----------------------------------------------------------------------
# |
# |  TextWriter.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-14 17:30:17
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the TextWriter ABC"""

from abc import abstractmethod, ABC


# ----------------------------------------------------------------------
class TextWriter(ABC):
    """\
    Abstract base class used to define the minimum functionality required to be considered a text writer
    for functionality in this module; this is mostly for documentation purposes.
    """

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def isatty() -> bool:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def write(
        content: str,
    ) -> int:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def flush() -> None:
        raise Exception("Abstract method")  # pragma: no cover

    # ----------------------------------------------------------------------
    @staticmethod
    @abstractmethod
    def close() -> None:
        raise Exception("Abstract method")  # pragma: no cover
