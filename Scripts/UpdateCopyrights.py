# ----------------------------------------------------------------------
# |
# |  UpdateCopyrights.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-12-29 11:11:02
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Updates copyright headers in source files with the current year."""

import datetime
import re
import textwrap
import traceback

from enum import auto, Enum
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import typer

from typer.core import TyperGroup

from Common_Foundation.EnumSource import EnumSource
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx

from Common_FoundationEx import ExecuteTasks
from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # pylint: disable=missing-class-docstring
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
MAX_FILE_SIZE                               = 100 * 1024 * 1024             # 100 MB

COPYRIGHT_REGEXES                           = [
    re.compile(r".*?Copyright (?P<copyright>.+)"),
]

# The following expressions must have a 'begin' capture; 'end' is optional.
YEAR_REGEXES                                = [
    re.compile(r"(?P<begin>\d{4})-(?P<end>\d{2,4})"),   # Matches multi-year range
    re.compile(r"(?P<begin>\d{4})"),                    # Matches single year
]


# ----------------------------------------------------------------------
@app.command("EntryPoint", help=__doc__, no_args_is_help=True)
def EntryPoint(
    code_dir: Path=typer.Argument(..., file_okay=False, exists=True, resolve_path=True, help="Directory containing source code to update."),
    year: int=typer.Argument(datetime.datetime.now().year, min=1, max=10000, help="New copyright year."),
    ssd: bool=typer.Option(False, "--ssd", help="Processes tasks in parallel to leverage the capabilities of solid-state-drives."),
    dry_run: bool=typer.Option(False, "--dry-run", help="Show the files that would be updated, but do not modify the files themselves."),
    quiet: bool=typer.Option(False, "--quiet", help="Reduce the amount of information displayed."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    year_str = str(year)
    two_digit_year = str(year % 100)

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        tasks: List[ExecuteTasks.TaskData] = []

        with dm.Nested(
            "Processing files in '{}'...".format(code_dir),
            lambda: "{} found".format(inflect.no("file", len(tasks))),
        ) as process_dm:
            for root, _, filenames in EnumSource(code_dir):
                for filename in filenames:
                    fullpath = root / filename

                    try:
                        if fullpath.stat().st_size > MAX_FILE_SIZE:
                            process_dm.WriteInfo("'{}' is tool large to process.\n".format(fullpath))
                            continue

                        tasks.append(ExecuteTasks.TaskData(str(fullpath), fullpath))

                    except Exception as ex:  # pylint: disable=broad-except
                        if process_dm.is_debug:
                            error = traceback.format_exc()
                        else:
                            error = str(ex)

                        process_dm.WriteWarning(
                            textwrap.dedent(
                                """\
                                An exception was encountered while processing '{}':

                                    {}
                                """,
                            ).format(TextwrapEx.Indent(error, 4, skip_first_line=True)),
                        )

            if not tasks:
                return

        # ----------------------------------------------------------------------
        class UpdateStatus(Enum):
            Reading                         = 0
            Parsing                         = auto()
            Updating                        = auto()

        # ----------------------------------------------------------------------
        class UpdateResult(Enum):
            Updated                         = auto()
            BinaryFile                      = auto()
            NotUpdated                      = auto()
            UnexpectedCopyrightFormat       = auto()

        # ----------------------------------------------------------------------
        def UpdateCopyright(
            context: Path,
            on_simple_status_func: Callable[[str], None],  # pylint: disable=unused-argument
        ) -> Tuple[
            Optional[int],
            ExecuteTasks.TransformStep2FuncType[UpdateResult],
        ]:
            fullpath = context
            del context

            # ----------------------------------------------------------------------
            def Impl(
                status: ExecuteTasks.Status,
            ) -> Tuple[UpdateResult, Optional[str]]:
                status.OnProgress(UpdateStatus.Reading.value, "Reading...")

                try:
                    with fullpath.open() as f:
                        lines = f.read().split("\n")
                        newline_char = (f.newlines[0] if isinstance(f.newlines, tuple) else f.newlines) or "\r\n"

                except (UnicodeDecodeError, MemoryError):
                    return UpdateResult.BinaryFile, None

                status.OnProgress(UpdateStatus.Parsing.value, "Parsing...")

                has_updates = False

                for index, line in enumerate(lines):
                    for copyright_regex in COPYRIGHT_REGEXES:
                        copyright_match = copyright_regex.match(line)
                        if not copyright_match:
                            continue

                        copyright = copyright_match.group("copyright")

                        year_match = None

                        for year_regex in YEAR_REGEXES:
                            year_match = year_regex.search(copyright)
                            if year_match:
                                break

                        if not year_match:
                            status.OnInfo(
                                "The file appears to have a copyright, but it isn't in the expected format ('{}') [0].\n".format(line.strip()),
                                verbose=False,
                            )

                            return UpdateResult.UnexpectedCopyrightFormat, None

                        begin = year_match.group("begin")
                        end = year_match.group("end") if "end" in year_match.groupdict() else begin

                        if len(end) == 2:
                            end = str(((year // 100) * 100) + int(end))

                        if len(begin) != 4:
                            status.OnInfo(
                                "This file appears to have a copyright, but it isn't in the expected format ('{}') [1].\n".format(line.strip()),
                                verbose=False,
                            )

                            return UpdateResult.UnexpectedCopyrightFormat, None

                        if len(end) != 4:
                            status.OnInfo(
                                "This file appears to have a copyright, but it isn't in the expected format ('{}') [2].\n".format(line.strip()),
                                verbose=False,
                            )

                            return UpdateResult.UnexpectedCopyrightFormat, None

                        if end == year_str:
                            continue

                        copyright = "{}{}{}".format(
                            copyright[:year_match.start()],
                            "{}-{}".format(begin, two_digit_year),
                            copyright[year_match.end():],
                        )

                        line = "{}{}{}".format(
                            line[:copyright_match.start() + copyright_match.start("copyright")],
                            copyright,
                            line[copyright_match.end("copyright"):],
                        )

                        if line != lines[index]:
                            lines[index] = line
                            has_updates = True

                if not has_updates:
                    return UpdateResult.NotUpdated, None

                if not dry_run:
                    status.OnProgress(UpdateStatus.Updating.value, "Updating...")

                    with fullpath.open(
                        "w",
                        newline=newline_char,
                    ) as f:
                        f.write("\n".join(lines))

                return UpdateResult.Updated, None

            # ----------------------------------------------------------------------

            return len(UpdateStatus), Impl

        # ----------------------------------------------------------------------

        results: List[Optional[UpdateResult]] = ExecuteTasks.Transform(
            dm,
            "Processing",
            tasks,
            UpdateCopyright,
            quiet=quiet,
            max_num_threads=1 if not ssd else None,
        )

        grouped_results: Dict[UpdateResult, List[Path]] = {}

        for result, task_data in zip(results, tasks):
            assert result is not None
            grouped_results.setdefault(result, []).append(task_data.context)

        with dm.YieldStream() as stream:
            stream.write("\n")

            if dry_run:
                stream.write("--dry-run was specified on the command line; no files were updated during processing.\n\n")

            for desc, update_result, always_display, verbose_only in [
                ("Updated", UpdateResult.Updated, True, False),
                ("Not Updated", UpdateResult.NotUpdated, False, True),
                ("Binary Files", UpdateResult.BinaryFile, False, True),
                ("Unexpected Copyright Format", UpdateResult.UnexpectedCopyrightFormat, False, False),
            ]:
                if verbose_only and not dm.is_verbose:
                    continue

                filenames = grouped_results.get(update_result, [])

                if not always_display and not filenames:
                    continue

                filenames = [str(filename) for filename in filenames]
                filenames.sort()

                stream.write("{}:\n\n".format(desc))

                for index, filename in enumerate(filenames):
                    stream.write("    {}) {}\n".format(index + 1, filename))

                if filenames:
                    stream.write("\n")


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
