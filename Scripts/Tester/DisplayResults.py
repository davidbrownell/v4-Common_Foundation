# ----------------------------------------------------------------------
# |
# |  DisplayResults.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-09-02 14:55:49
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Displays results produced by test runs"""

import textwrap

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from rich import print as rich_print
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

from Results import BuildResult, CodeCoverageResult, ConfigurationResult, ErrorResult, Result, TestIterationResult, TestResult


# ----------------------------------------------------------------------
HEADER_WIDTH                                = 60
INDENTATION_PER_PANEL                       = 3


# ----------------------------------------------------------------------
def Display(
    dm: DoneManager,
    results: List[Result],
    *,
    result_color: str="bold white",
    debug_configuration_color: str="deep_sky_blue1",
    release_configuration_color: str="purple",
    build_results_color: str="bright_black",
    test_results_color: str="bright_black",
    code_coverage_color: str="bright_black",

) -> None:
    # ----------------------------------------------------------------------
    def GetResultDisplay(
        result: int,
        short_desc: Optional[str],
    ) -> str:
        if result < 0:
            color = "bold red"
        elif result > 0:
            color = "bold yellow"
        else:
            color = "bold green"

        return "[{color}]{result}{short}[/]".format(
            color=color,
            result=result,
            short=" ({})".format(short_desc) if short_desc else "",
        )

    # ----------------------------------------------------------------------
    def GetLogDisplay(
        log_filename: Path,
    ) -> str:
        return "{}{}".format(
            TextwrapEx.GetSizeDisplay(log_filename.stat().st_size),
            "" if dm.capabilities.is_headless else r" \[[link=file://{}]View Log[/]]".format(
                log_filename.as_posix(),
            ),
        )

    # ----------------------------------------------------------------------
    def GetOutputDirDisplay(
        output_dir: Path,
    ) -> str:
        if dm.capabilities.is_headless:
            return str(output_dir)

        return r"{} \[[link=file://{}]View[/]]".format(
            inflect.no("item", sum(1 for _ in output_dir.iterdir())),
            output_dir.as_posix(),
        )

    # ----------------------------------------------------------------------
    def CreateAlignedKeyValueText(
        values: Dict[str, str],
        *,
        panel_level: int,
        indentation: int=0,
    ) -> str:
        col_width = HEADER_WIDTH - (panel_level * INDENTATION_PER_PANEL) - indentation

        return "\n".join(
            "{} {}".format(
                "{}:".format(k).ljust(col_width),
                v,
            )
            for k, v in values.items()
        )

    # ----------------------------------------------------------------------
    def CreateErrorResultPanel(
        error: ErrorResult,
        title: str,
        border_style: str,
    ) -> Panel:
        return Panel(
            CreateAlignedKeyValueText(
                {
                    "Result": GetResultDisplay(error.result, error.short_desc),
                    "Log Output": GetLogDisplay(error.log_filename),
                    "Execution Time": str(error.execution_time),
                },
                panel_level=2,
            ).rstrip(),
            border_style=border_style,
            padding=(1, 2),
            title=title,
            title_align="left",
        )

    # ----------------------------------------------------------------------
    def CreateConfigurationPanel(
        result: ConfigurationResult,
        *,
        is_debug_configuration: bool,
    ) -> Panel:
        panels: List[Panel] = []

        # Build
        if result.build_result:
            build_result = result.build_result

            if isinstance(build_result, ErrorResult):
                panels.append(CreateErrorResultPanel(build_result, "Build Results", build_results_color))

            elif isinstance(build_result, BuildResult):
                panels.append(
                    Panel(
                        CreateAlignedKeyValueText(
                            {
                                "Result": GetResultDisplay(build_result.result, build_result.short_desc),
                                "Log Output": GetLogDisplay(build_result.log_filename),
                                "Total Execution Time": str(build_result.execution_time),
                                "Build Execution Time": str(build_result.build_execution_time),
                            },
                            panel_level=2,
                        ).rstrip(),
                        border_style=build_results_color,
                        padding=(1, 2),
                        title="Build Results",
                        title_align="left",
                    ),
                )

            else:
                assert False, build_result  # pragma: no cover

        # Test
        if result.test_result:
            # ----------------------------------------------------------------------
            def CreateTestIterationText(
                result: TestIterationResult,
            ) -> str:
                return textwrap.dedent(
                    """\
                    Test Execution:
                    {execution}

                    Test Extraction:
                    {basic_extraction}{subtests}{benchmarks}
                    """,
                ).format(
                    execution=TextwrapEx.Indent(
                        CreateAlignedKeyValueText(
                            {
                                "Result": GetResultDisplay(result.execute_result.result, result.execute_result.short_desc),
                                "Log Output": GetLogDisplay(result.execute_result.log_filename),
                                "Execution Time": str(result.execute_result.execution_time),
                            },
                            panel_level=2,
                            indentation=4,
                        ),
                        4,
                        skip_first_line=False,
                    ),
                    basic_extraction=TextwrapEx.Indent(
                        CreateAlignedKeyValueText(
                            {
                                "Result": GetResultDisplay(result.parse_result.result, result.parse_result.short_desc),
                                "Execution Time": str(result.parse_result.execution_time),
                            },
                            panel_level=2,
                            indentation=4,
                        ),
                        4,
                        skip_first_line=False,
                    ),
                    subtests="" if not result.parse_result.subtest_results else "\n\n    Tests:\n{}".format(
                        TextwrapEx.Indent(
                            CreateAlignedKeyValueText(
                                {
                                    k: "{} ({})".format(GetResultDisplay(v.result, None), v.execution_time)
                                    for k, v in result.parse_result.subtest_results.items()
                                },
                                panel_level=2,
                                indentation=8,
                            ),
                            8,
                            skip_first_line=False,
                        ),
                    ).rstrip(),
                    benchmarks="" if not result.parse_result.benchmarks else "\n\nBenchmarks:\n\n{}\n".format(
                        TextwrapEx.CreateTable(
                            [
                                "Name",
                                "Source Filename",
                                "Line",
                                "Extractor",
                                "Min",
                                "Max",
                                "Mean",
                                "Std Deviation",
                                "Samples",
                                "Units",
                                "Iterations",
                            ],
                            [
                                [
                                    bm.name,
                                    str(bm.source_filename),
                                    str(bm.source_line),
                                    bm.extractor,
                                    str(bm.min_value),
                                    str(bm.max_value),
                                    str(bm.mean_value),
                                    str(bm.standard_deviation),
                                    str(bm.samples),
                                    str(bm.units),
                                    str(bm.iterations),
                                ]
                                for bm in result.parse_result.benchmarks
                            ],
                            [
                                TextwrapEx.Justify.Left,
                                TextwrapEx.Justify.Left,
                                TextwrapEx.Justify.Right,
                                TextwrapEx.Justify.Left,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                                TextwrapEx.Justify.Center,
                            ],
                        ).rstrip(),
                    ),
                )

            # ----------------------------------------------------------------------

            test_result = result.test_result

            if isinstance(test_result, ErrorResult):
                panels.append(CreateErrorResultPanel(test_result, "Test Results", test_results_color))

            elif isinstance(test_result, TestResult):
                if test_result.has_multiple_iterations:
                    iteration_display_items: List[Union[str, Panel]] = [
                        CreateAlignedKeyValueText(
                            {
                                "Average Execution Time": str(test_result.average_time),
                            },
                            panel_level=2,
                        ),
                    ]

                    for index, test_iteration_result in enumerate(test_result.test_results):
                        iteration_display_items += [
                            "",
                            Rule("Iteration #{}".format(index + 1), style="none"),
                            "",
                            CreateAlignedKeyValueText(
                                {
                                    "Result": GetResultDisplay(test_iteration_result.result, test_iteration_result.short_desc),
                                    "Total Execution Time": str(test_iteration_result.total_time),
                                },
                                panel_level=2,
                            ),
                            "",
                            CreateTestIterationText(test_iteration_result),
                        ]

                else:
                    iteration_display_items: List[Union[str, Panel]] = [
                        "",
                        CreateTestIterationText(test_result.test_results[0]),
                    ]

                assert iteration_display_items
                assert isinstance(iteration_display_items[-1], str), iteration_display_items[-1]
                iteration_display_items[-1] = iteration_display_items[-1].rstrip()

                panels.append(
                    Panel(
                        Group(
                            CreateAlignedKeyValueText(
                                {
                                    "Result": GetResultDisplay(test_result.result, test_result.short_desc),
                                    "Log Output": GetLogDisplay(test_result.log_filename),
                                    "Total Execution Time": str(test_result.execution_time),
                                },
                                panel_level=2,
                            ).rstrip(),
                            *iteration_display_items,
                        ),
                        border_style=test_results_color,
                        padding=(1, 2),
                        title="Test Results",
                        title_align="left",
                    ),
                )

            else:
                assert False, test_result  # pragma: no cover

        # Coverage
        if result.coverage_result:
            coverage_result = result.coverage_result

            if isinstance(coverage_result, ErrorResult):
                panels.append(CreateErrorResultPanel(coverage_result, "Coverage Results", code_coverage_color))

            elif isinstance(coverage_result, CodeCoverageResult):
                data_items: Dict[str, str] = {
                    "Result": GetResultDisplay(coverage_result.result, coverage_result.short_desc),
                    "Total Execution Time": str(coverage_result.execution_time),
                    "Coverage Percentage": "{:.02f}%".format(coverage_result.coverage_percentage * 100),
                    "Minimum Percentage": "{:.02f}%".format(coverage_result.minimum_percentage * 100),
                }

                assert isinstance(result.test_result, TestResult), result.test_result
                assert result.test_result.test_results
                assert result.test_result.test_results[0].execute_result.coverage_result

                coverage_execute_result = result.test_result.test_results[0].execute_result.coverage_result

                assert coverage_execute_result.coverage_percentage is not None

                if coverage_execute_result.coverage_data_filename is not None:
                    assert coverage_execute_result.coverage_data_filename.is_file(), coverage_execute_result.coverage_data_filename

                    data_items["Coverage Data File"] = r"{} \[{}]".format(
                        TextwrapEx.GetSizeDisplay(coverage_execute_result.coverage_data_filename.stat().st_size),
                        coverage_execute_result.coverage_data_filename if dm.capabilities.is_headless else "[link=file://{}]View[/]".format(
                            coverage_execute_result.coverage_data_filename.as_posix(),
                        ),
                    )

                panels.append(
                    Panel(
                        textwrap.dedent(
                            """\
                            {data}{files}
                            """,
                        ).format(
                            data=CreateAlignedKeyValueText(
                                data_items,
                                panel_level=2,
                            ),
                            files="" if not coverage_execute_result.coverage_percentages else "\n\nIndividual Results:\n{}".format(
                                TextwrapEx.Indent(
                                    CreateAlignedKeyValueText(
                                        {
                                            k: "{:.02f}%".format(v * 100)
                                            for k, v in coverage_execute_result.coverage_percentages.items()
                                        },
                                        panel_level=2,
                                        indentation=4,
                                    ),
                                    4,
                                    skip_first_line=False,
                                ),
                            ),
                        ).rstrip(),
                        border_style=code_coverage_color,
                        padding=(1, 2),
                        title="Coverage Results",
                        title_align="left",
                    ),
                )

            else:
                assert False, coverage_result  # pragma: no cover

        # Top-level stats
        top_level_data: Dict[str, str] = {
            "Result": GetResultDisplay(result.result, result.short_desc),
            "Total Execution Time": str(result.execution_time),
        }

        if result.has_multiple_iterations:
            top_level_data["Average Execution Time"] = str(result.average_time)

        top_level_data["Output Directory"] = GetOutputDirDisplay(result.output_dir)

        return Panel(
            Group(
                CreateAlignedKeyValueText(top_level_data, panel_level=1),
                "",
                *panels,
            ),
            border_style=debug_configuration_color if is_debug_configuration else release_configuration_color,
            padding=(1, 2),
            title=str(result.configuration),
            title_align="left",
        )

    # ----------------------------------------------------------------------

    for result in results:
        configuration_panels: List[Panel] = []

        if result.debug:
            configuration_panels.append(CreateConfigurationPanel(result.debug, is_debug_configuration=True))
        if result.release:
            configuration_panels.append(CreateConfigurationPanel(result.release, is_debug_configuration=False))

        rich_print(
            Group(
                Panel(
                    Group(
                        CreateAlignedKeyValueText(
                            {
                                "Result": GetResultDisplay(result.result, None),
                            },
                            panel_level=0,
                        ),
                        *configuration_panels,
                    ),
                    border_style=result_color,
                    expand=not len(results) == 1,
                    padding=(1, 2),
                    title=str(result.test_item) if dm.capabilities.is_headless else "[link=file://{}]{}[/]".format(
                        result.test_item.as_posix(),
                        result.test_item,
                    ),
                    title_align="left",
                ),
                "",
            ),
        )


# ----------------------------------------------------------------------
def DisplayQuiet(
    dm: DoneManager,
    results: List[Result],
) -> None:
    # Get a common path (if any)
    common_path = PathEx.GetCommonPath(*(result.test_item for result in results))
    if common_path:
        len_common_path_parts = len(common_path.parts)
    else:
        len_common_path_parts = 0

    rows: List[List[str]] = []
    row_data_items: List[Tuple[Path, ConfigurationResult]] = []

    # ----------------------------------------------------------------------
    def AddRow(
        test_item: Path,
        result: ConfigurationResult,
        display_name: str,
        configuration: str,
    ) -> None:
        rows.append(
            [
                display_name,
                configuration,
                "Failed ({})".format(result.result) if result.result < 0
                    else "Unknown ({})".format(result.result) if result.result > 0
                        else "Succeeded ({})".format(result.result)
                ,
                str(result.execution_time),
                str(result.output_dir) if dm.capabilities.is_headless else "{} [View]".format(
                    inflect.no("item", sum(1 for _ in result.output_dir.iterdir())),
                ),
                result.short_desc or "",
            ],
        )

        row_data_items.append((test_item, result))

    # ----------------------------------------------------------------------

    for result in results:
        display_name = result.test_item

        if len_common_path_parts != 0:
            assert len_common_path_parts < len(display_name.parts), (common_path, display_name)
            display_name = Path(*display_name.parts[len_common_path_parts:])

        display_name = str(display_name)

        if result.debug is not None:
            AddRow(result.test_item, result.debug, display_name, "Debug")
        if result.release is not None:
            AddRow(result.test_item, result.release, display_name, "Release")

    if dm.capabilities.supports_colors:
        success_on = TextwrapEx.SUCCESS_COLOR_ON
        failure_on = TextwrapEx.ERROR_COLOR_ON
        warning_on = TextwrapEx.WARNING_COLOR_ON
        color_off = TextwrapEx.COLOR_OFF
    else:
        success_on = ""
        failure_on = ""
        warning_on = ""
        color_off = ""

    # ----------------------------------------------------------------------
    def DecorateRow(
        index: int,
        values: List[str],
    ) -> List[str]:
        test_item, result = row_data_items[index]

        if not dm.capabilities.is_headless:
            values[0] = TextwrapEx.CreateAnsiHyperLinkEx(
                "file://{}".format(test_item.as_posix()),
                values[0],
            )

            values[4] = TextwrapEx.CreateAnsiHyperLinkEx(
                "file://{}".format(result.output_dir.as_posix()),
                values[4],
            )

        if result.result < 0:
            color_on = failure_on
        elif result.result > 0:
            color_on = warning_on
        else:
            color_on = success_on

        values[2] = "{}{}{}".format(color_on, values[2], color_off)

        return values

    # ----------------------------------------------------------------------

    with dm.YieldStream() as stream:
        indented_stream = StreamDecorator(stream, "    ")

        if common_path:
            indented_stream.write(
                textwrap.dedent(
                    """\

                    Test items are relative to '{}'.


                    """,
                ).format(
                    common_path if dm.capabilities.is_headless else TextwrapEx.CreateAnsiHyperLink(
                        "file://{}".format(common_path.as_posix()),
                        str(common_path),
                    ),
                ),
            )

        indented_stream.write(
            TextwrapEx.CreateTable(
                [
                    "Test Item",
                    "Configuration",
                    "Result",
                    "Execution Time",
                    "Output Directory",
                    "Short Description",
                ],
                rows,
                [
                    TextwrapEx.Justify.Left,
                    TextwrapEx.Justify.Center,
                    TextwrapEx.Justify.Left,
                    TextwrapEx.Justify.Left,
                    TextwrapEx.Justify.Left if dm.capabilities.is_headless else TextwrapEx.Justify.Right,
                    TextwrapEx.Justify.Left,
                ],
                decorate_values_func=DecorateRow,
            ),
        )

        indented_stream.write("\n")

    # Write the final output
    success_count = 0
    warning_count = 0
    error_count = 0

    for _, result in row_data_items:
        if result.result < 0:
            error_count += 1
        elif result.result > 0:
            warning_count += 1
        else:
            success_count += 1

    dm.WriteLine(
        textwrap.dedent(
            """\

            {success_prefix}{success_count:>6} ({success_percentage:>6.2f}%)
            {error_prefix}  {error_count:>6} ({error_percentage:>6.2f}%)
            {warning_prefix}{warning_count:>6} ({warning_percentage:>6.2f}%)
            Total:   {total:>6} (100.00%)

            """,
        ).format(
            success_prefix=TextwrapEx.CreateSuccessPrefix(dm.capabilities),
            success_count=success_count,
            success_percentage=(success_count / len(row_data_items)) * 100,
            error_prefix=TextwrapEx.CreateErrorPrefix(dm.capabilities),
            error_count=error_count,
            error_percentage=(error_count / len(row_data_items)) * 100,
            warning_prefix=TextwrapEx.CreateWarningPrefix(dm.capabilities),
            warning_count=warning_count,
            warning_percentage=(warning_count / len(row_data_items)) * 100,
            total=len(row_data_items),
        ),
    )
