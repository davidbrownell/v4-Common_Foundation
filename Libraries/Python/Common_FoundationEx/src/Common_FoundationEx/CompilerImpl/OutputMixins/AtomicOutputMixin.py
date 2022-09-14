# ----------------------------------------------------------------------
# |
# |  AtomicOutputMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-30 09:38:45
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the AtomicOutputMixin object"""

from pathlib import Path
from typing import Any, Dict, List, TextIO

from Common_Foundation.Streams.DoneManager import DoneManager

from ..ICompilerImpl import ICompilerImpl


# ----------------------------------------------------------------------
class AtomicOutputMixin(ICompilerImpl):
    """Mixin for compilers that generate a single file"""

    # Required
    ATTRIBUTE_NAME                          = "output_filename"

    # ----------------------------------------------------------------------
    @classmethod
    def GetOutputItems(
        cls,
        metadata_or_context: Dict[str, Any],
    ) -> List[Path]:
        return [ metadata_or_context[cls.ATTRIBUTE_NAME], ]

    # ----------------------------------------------------------------------
    def Clean(
        self,
        dm: DoneManager,                    # Status information while the program is running
        output_stream: TextIO,              # Log output
        context: Dict[str, Any],
    ) -> None:
        if (
            context[self.__class__.ATTRIBUTE_NAME] not in self.GetInputItems(context)
            and context[self.__class__.ATTRIBUTE_NAME].is_file()
        ):
            output_filename = context[self.__class__.ATTRIBUTE_NAME]

            with dm.Nested("Removing '{}'...".format(output_filename)):
                output_filename.unlink()
                output_stream.write("Removed '{}'.\n".format(output_filename))

        super(AtomicOutputMixin, self).Clean(dm, output_stream, context)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @classmethod
    def _GetRequiredMetadataNames(cls) -> List[str]:
        return [cls.ATTRIBUTE_NAME, ] + super(AtomicOutputMixin, cls)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @classmethod
    def _CreateContext(
        cls,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata[cls.ATTRIBUTE_NAME] = metadata[cls.ATTRIBUTE_NAME].resolve()

        metadata[cls.ATTRIBUTE_NAME].parent.mkdir(parents=True, exist_ok=True)

        return super(AtomicOutputMixin, cls)._CreateContext(dm, metadata)
