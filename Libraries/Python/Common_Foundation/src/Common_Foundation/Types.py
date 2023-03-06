# ----------------------------------------------------------------------
# |
# |  Types.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-25 08:23:36
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Common type-related functionality"""

from enum import Enum
from typing import Iterable, List, Optional, Type, TypeVar, Union


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
TypeT                                       = TypeVar("TypeT")


# ----------------------------------------------------------------------
class DoesNotExist(object):  # pylint: disable=too-few-public-methods
    """\
    Unique object to distinguish from None during lookup operations where None is a valid value.

    For Example:
        d: Dict[str, Optional[str] = {
            "Foo": None,
            "Bar": "Bar",
        }

        # Before
        if d.get("Foo", None) is None:
            d["Foo"] = "new foo value"      # Potential error, as we are overwriting a valid value

        # After
        if d.get("Foo", DoesNotExist.instance) is DoesNotExist.instance:
            raise Exception("This will never happen.")
    """

    # Set below
    instance: "DoesNotExist"                = None  # type: ignore


DoesNotExist.instance                       = DoesNotExist()


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def extensionmethod(func):  # pylint: disable=invalid-name
    """\
    Decorator that indicates that the method is a method that is intended to be extended by derived
    classes to override functionality if necessary.

    This decorator does not add any functionality, but serves as documentation that communicates
    intentions behind how the class is intended to be used.
    """

    return func


# ----------------------------------------------------------------------
def overridemethod(func):  # pylint: disable=invalid-name
    """\
    Decorator that indicates that the method is a method that overrides an abstract- or extension-
    method in a base class.

    This decorator does not add any functionality, but serves as documentation that communicates
    intentions behind how the class is intended to be used.
    """

    return func


# ----------------------------------------------------------------------
def EnsureValid(
    value: Optional[TypeT],
) -> TypeT:
    """Ensures that an optional value is not None and returns it"""

    if value is None:
        raise ValueError("Invalid value")

    return value


# ----------------------------------------------------------------------
def EnsurePopulatedList(
    items: Union[List[TypeT], Optional[List[TypeT]]],
) -> Optional[List[TypeT]]:
    """Converts the list to None if it doesn't have any items"""

    return items or None


# ----------------------------------------------------------------------
def StringsToEnum(
    enum_name: str,
    items: Iterable[str],
) -> Type:
    """Convert from a list of strings into an enumeration that contains the same values"""

    return Enum(enum_name, {item: item for item in items})
