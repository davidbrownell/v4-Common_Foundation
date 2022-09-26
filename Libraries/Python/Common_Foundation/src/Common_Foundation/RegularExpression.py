# ----------------------------------------------------------------------
# |
# |  RegularExpression.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 22:06:56
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality that helps when working with regular expressions"""

import re
import textwrap

from enum import auto, Enum
from typing import Dict, List, Generator, Optional, Pattern, Set


# ----------------------------------------------------------------------
class TagType(Enum):
    String                                  = auto()
    Integer                                 = auto()
    Number                                  = auto()


# ----------------------------------------------------------------------
def TemplateStringToRegex(
    content: str,
    optional_tags: Optional[Set[str]]=None,
    tag_types: Optional[Dict[str, TagType]]=None,
    *,
    match_whole_string: bool=True,
) -> Pattern:
    """\
    Converts a template string into a regular expression whose matches capture all
    template values.

    Example:
        "{foo}  {bar}  {baz}" -> (?P<foo>.+)  (?P<bar>.+)  (?P<baz>.+)
    """

    regex_string = TemplateStringToRegexString(
        content,
        optional_tags,
        tag_types,
        match_whole_string=match_whole_string,
    )

    return re.compile(regex_string, re.DOTALL | re.MULTILINE)


# ----------------------------------------------------------------------
def TemplateStringToRegexString(
    content: str,
    optional_tags: Optional[Set[str]]=None,
    tag_types: Optional[Dict[str, TagType]]=None,
    *,
    match_whole_string: bool=True,
) -> str:
    optional_tags = optional_tags or set()
    tag_types = tag_types or {}

    # Replace newline chars with placeholders so that they don't get escaped
    newline_placeholder = "__<<!!??Newline??!!>>__"

    content = re.sub(r"\r?\n", lambda match: newline_placeholder, content, re.DOTALL | re.MULTILINE)

    output: List[str] = []
    prev_index = 0
    found_tags: Set[str] = set()

    for match in _TemplateStringToRegexString_tag_regex.finditer(content):
        # Escape everything before this match
        output.append(re.escape(content[prev_index : match.start()]))

        # Modify the match
        tag = match.group("tag")
        if tag in found_tags:
            output.append("(?P={})".format(tag))
        else:
            found_tags.add(tag)

            tag_type = tag_types.get(tag, TagType.String)

            if tag_type == TagType.String:
                char_class_template = ".{arity}"
            elif tag_type == TagType.Integer:
                char_class_template = r"\-?[0-9]{arity}"
            elif tag_type == TagType.Number:
                char_class_template = r"(?:\-?[0-9]*\.[0-9]+){}".format(
                    "?" if tag in optional_tags else "",
                )
            else:
                assert False, tag_type  # pragma: no cover

            output.append(
                r"(?P<{tag}>{content})".format(
                    tag=tag,
                    content=char_class_template.format(
                        arity="*?" if tag in optional_tags else "+?",
                    ),
                ),
            )

        prev_index = match.end()

    output.append(re.escape(content[prev_index:]))

    regex_string = "".join(output)

    if match_whole_string:
        regex_string = "^{}$".format(regex_string)

    regex_string = regex_string.replace(re.escape(newline_placeholder), r"\r?\n")
    regex_string = regex_string.replace(r"\ ", " ")

    return regex_string


# ----------------------------------------------------------------------
def Generate(
    regex: Pattern,
    content: str,
    *,
    leading_delimiter: bool=False,
) -> Generator[
    Dict[
        Optional[str],                      # A string key will be the match group name; None key is the leading or following text (depending on the value of `leading_delimiter`)
        str
    ],
    None,
    None,
]:
    """\
    Handles some of the wonkiness associated with re.split by providing a consistent experience
    regardless of the input and matches.

    If `leading_delimiter` is True, the generated items will be text and the delimiter information
    that proceeded it.

    If `leading_delimiter` is False, the generated items will be text and the delimiter information
    that follows it.

    Examples:
        regex = re.compile(r"(?P<whitespace>\s+)")
        value = "This is a test."

        Generate(re.compile(regex, value, leading_delimiter=True) == [
            {None: "This"},
            {None: "is", "whitespace": " "},
            {None: "a", "whitespace": " "},
            {None: "test.", "whitespace": " "},
        ]

        Generate(re.compile(regex, value, leading_delimiter=False) == [
            {None: "This", "whitespace": " ",},
            {None: "is", "whitespace": " "},
            {None: "a", "whitespace": " "},
            {None: "test."},
        ]
    """

    results = regex.split(content)

    if regex.groups:
        if len(results) == 1:
            # If here, there weren't any matches
            yield {None: results[0] }
            return

        assert len(results) % (regex.groups + 1) in [0, 1], len(results)

        if leading_delimiter:
            # If there is 1 extra element in the list of results, that will be the first
            # element that doesn't have a corresponding match.
            if len(results) % (regex.groups + 1) == 1:
                index_offset = 1

                if results[0]:
                    yield {None: results[0]}

            else:
                index_offset = 0

            for index in range(index_offset, len(results), regex.groups + 1):
                result: Dict[Optional[str], str] = {None: results[index + regex.groups]}

                for group_index, group_name in enumerate(regex.groupindex):
                    result[group_name] = results[index + group_index]

                yield result

        else:
            for index in range(0, len(results), regex.groups + 1):
                result: Dict[Optional[str], str] = {None: results[index]}

                if index != len(results) - 1:
                    for group_index, group_name in enumerate(regex.groupindex):
                        result[group_name] = results[index + group_index + 1]

                if len(result) == 1 and not result[None]:
                    continue

                yield result

    else:
        # If we have a string with just matches and no content, we can ignore the first result
        # as it represents that content that comes before the first match (which will be nothing)
        if results and all(not result for result in results):
            results = results[1:]

        yield from results


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
_TemplateStringToRegexString_tag_regex      = re.compile(
    textwrap.dedent(
        r"""(?#
        Left Bracket                        )\{\s*(?#
            Tag                             )(?P<tag>.+?)(?#
            [optional begin]                )(?:(?#
                Delimiter                   )\:.*?(?#
            [optional end]                  ))?(?#
        Right Bracket                       )\s*\}(?#
        )""",
    ),
)
