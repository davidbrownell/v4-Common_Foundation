# ----------------------------------------------------------------------
# |
# |  MultipleOutputMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:55:25
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the MultipleOutputMixin object"""

from pathlib import Path
from typing import Any, Dict, List, Set, TextIO

from Common_Foundation.Streams.DoneManager import DoneManager

from ..ICompilerImpl import ICompilerImpl


# ----------------------------------------------------------------------
class MultipleOutputMixin(ICompilerImpl):
    """Mixin for compilers that generate multiple output files"""

    # Required
    ATTRIBUTE_NAME                          = "output_filenames"

    # ----------------------------------------------------------------------
    @classmethod
    def GetOutputItems(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return metadata_or_context[cls.ATTRIBUTE_NAME]

    # ----------------------------------------------------------------------
    def Clean(
        self,
        dm: DoneManager,                    # Status information while the program is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        input_items: Set[Path] = set(self.GetInputItems(context))

        for output_filename in context[self.ATTRIBUTE_NAME]:
            if output_filename in input_items:
                continue

            with dm.Nested("Removing '{}'...".format(output_filename)):
                output_filename.unlink()
                output_stream.write("Removed '{}'.\n".format(output_filename))

        super(MultipleOutputMixin, self).Clean(dm, output_stream, context)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _GetRequiredMetadataNames(cls) -> List[str]:
        return [cls.ATTRIBUTE_NAME, ] + super(MultipleOutputMixin, cls)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @classmethod
    def _CreateContext(
        cls,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        output_filenames = metadata[cls.ATTRIBUTE_NAME]

        for index, output_filename in enumerate(output_filenames):
            output_filenames[index] = output_filename.resolve()
            output_filenames.parent.mkdir(parents=True, exist_ok=True)

        return super(MultipleOutputMixin, cls)._CreateContext(dm, metadata)
