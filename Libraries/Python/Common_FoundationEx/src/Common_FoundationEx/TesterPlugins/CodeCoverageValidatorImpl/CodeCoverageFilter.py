# ----------------------------------------------------------------------
# |
# |  CodeCoverageFilter.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-11 15:16:02
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeCoverageFilter object"""

import itertools
import json

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

from Common_Foundation import JsonEx


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CodeCoverageContentFilter(object):
    """Glob filters applied to the contents of a source file"""

    # ----------------------------------------------------------------------
    includes: Optional[List[str]]           # Example: MyNamespace::MyClass::*
    excludes: Optional[List[str]]

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.includes is None or self.includes
        assert self.excludes is None or self.excludes


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CodeCoverageFilter(object):
    """Glob filters applied to a file name"""

    # ----------------------------------------------------------------------
    binary_file_filters: Dict[
        str,                                            # Glob matching binary filename
        Union[
            None,                                       # Do not apply this filter to the file
            bool,                                       # True to include everything associated with the binary, False to exclude
            CodeCoverageContentFilter,                  # Conditionally apply content across all sources
            Dict[
                str,                                    # Glob matching source filename
                Union[
                    bool,                               # True to include everything associated with the source file, False to exclude
                    CodeCoverageContentFilter,          # Conditionally apply content across this source
                ],
            ],
        ],
    ]

    continue_processing: Optional[bool]     = field(kw_only=True, default=None)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert self.binary_file_filters
        assert self.continue_processing is None or self.continue_processing is False

    # ----------------------------------------------------------------------
    @classmethod
    def FromFile(
        cls,
        filename: Path,
    ) -> "CodeCoverageFilter":
        with filename.open() as f:
            contents = json.load(f)

        binary_file_filters: Dict[
            str,
            Union[
                None,
                bool,
                CodeCoverageContentFilter,
                Dict[
                    str,
                    Union[
                        bool,
                        CodeCoverageContentFilter,
                    ],
                ],
            ],
        ] = {}

        for key, value in contents.get("binary_file_filters", {}).items():
            if value is not None and not isinstance(value, bool):
                if "includes" in value and "excludes" in value:
                    value = CodeCoverageContentFilter(value["includes"] or None, value["excludes"] or None)
                elif isinstance(value, dict):
                    value = {
                        k: v if isinstance(v, bool) else CodeCoverageContentFilter(
                            v.get("includes", None),
                            v.get("excludes", None),
                        )
                        for k, v in value.items()
                    }
                else:
                    assert False, value  # pragma: no cover

            binary_file_filters[key] = value

        return cls(
            binary_file_filters,
            continue_processing=contents.get("continue_processing", None),
        )

    # ----------------------------------------------------------------------
    def ToFile(
        self,
        filename: Path,
    ) -> None:
        filename.parent.mkdir(parents=True, exist_ok=True)

        with filename.open("w") as f:
            JsonEx.Dump(self.__dict__, f)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CoverageResult(object):
    covered: int
    uncovered: int


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def ApplyFilters(
    binary_filename: Path,
    input_sources: List[Path],
    process_content_func: Callable[
        [
            Dict[
                str,                        # source filename glob
                CodeCoverageContentFilter,
            ],
        ],
        Optional[CoverageResult],
    ],
    code_coverage_filter_filename: str="CodeCoverageFilter.json",
) -> Optional[CoverageResult]:
    # Gather all of the filters that might be used
    raw_source_content_filters: Dict[
        int,                                # Depth from root
        List[
            Dict[
                str,                        # Glob matching source filename
                CodeCoverageContentFilter,
            ],
        ],
    ] = {}

    applied_filters: Set[Path] = set()

    for search_path in itertools.chain([binary_filename, ], input_sources):
        if search_path.is_dir():
            parents = itertools.chain([search_path, ], search_path.parents)
        else:
            parents = search_path.parents

        for parent in parents:
            fullpath = parent / code_coverage_filter_filename
            if not fullpath.is_file():
                continue

            if fullpath in applied_filters:
                continue

            applied_filters.add(fullpath)

            coverage_filter = CodeCoverageFilter.FromFile(fullpath)

            for binary_filename_glob, binary_match_action in coverage_filter.binary_file_filters.items():
                if not binary_filename.match(binary_filename_glob):
                    continue

                if binary_match_action is False:
                    return None

                if binary_match_action is True:
                    source_match_action = {
                        "*": CodeCoverageContentFilter(["*"], None),
                    }

                elif isinstance(binary_match_action, CodeCoverageContentFilter):
                    source_match_action = {
                        "*": binary_match_action,
                    }

                elif isinstance(binary_match_action, dict):
                    source_match_action = {
                        source_glob: (
                            CodeCoverageContentFilter(["*"], None) if source_action is True
                                else CodeCoverageContentFilter(None, ["*"]) if source_action is False
                                    else source_action
                        )
                        for source_glob, source_action in binary_match_action.items()
                    }

                else:
                    assert False, binary_match_action  # pragma: no cover

                raw_source_content_filters.setdefault(len(parent.parts), []).append(source_match_action)

            if coverage_filter.continue_processing is False:
                break

    # Normalize the filters by favoring items nested in deeper directories over those nested higher
    # within a hierarchy.
    source_content_filters: Dict[str, CodeCoverageContentFilter] = {}

    keys = list(raw_source_content_filters.keys())
    keys.sort(reverse=True)

    for key in keys:
        sources_filters = raw_source_content_filters[key]

        for sources_filter in sources_filters:
            for source_glob, source_content_filter in sources_filter.items():
                existing_filter = source_content_filters.get(source_glob, None)

                if existing_filter is None:
                    source_content_filters[source_glob] = source_content_filter
                else:
                    source_content_filters[source_glob] = CodeCoverageContentFilter(
                        list(itertools.chain(existing_filter.includes or [], source_content_filter.includes or [])) or None,
                        list(itertools.chain(existing_filter.excludes or [], source_content_filter.excludes or [])) or None,
                    )

    return process_content_func(source_content_filters)
