# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-12-30 10:50:03
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
# pylint: disable=invalid-name
# pylint: disable=missing-module-docstring
# pylint: disable=missing-class-docstring

from pathlib import Path
from typing import Callable, Optional, TextIO, Tuple, Union

from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import ExecuteTasks


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="ExecuteTasks-based Build",
            configurations=None,

            requires_output_dir=True,
            suggested_output_dir_location=None,         # Optional[Path]
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Optional[Path],         # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        return 0

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Optional[Path],         # pylint: disable=unused-argument
        output_stream: TextIO,              # pylint: disable=unused-argument
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step Index
                str,                        # Status Info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Return code
        Tuple[
            int,                            # Return code
            str,                            # Short status desc
        ],
    ]:
        with self.__class__.YieldDoneManager(
            output_stream,
            "The Heading",
            is_verbose=is_verbose,
            is_debug=is_debug,
        ) as dm:
            # ----------------------------------------------------------------------
            def Execute(
                context: int,
                on_simple_status_func: Callable[[str], None],  # pylint: disable=unused-argument
            ) -> Tuple[
                Optional[int],
                ExecuteTasks.TransformStep2FuncType[int],
            ]:
                # ----------------------------------------------------------------------
                def Impl(
                    status: ExecuteTasks.Status,  # pylint: disable=unused-argument
                ) -> Tuple[
                    int,
                    Optional[str],
                ]:
                    return context * 2, "{} * 2 = {}".format(context, context * 2)

                # ----------------------------------------------------------------------

                return None, Impl

            # ----------------------------------------------------------------------

            results = ExecuteTasks.Transform(
                dm,
                "Processing",
                [ExecuteTasks.TaskData(str(x), x) for x in range(10)],
                Execute,
            )

            for result in results:
                dm.WriteInfo("Result: {}\n".format(result))

            return dm.result


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
