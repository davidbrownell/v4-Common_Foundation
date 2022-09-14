# ----------------------------------------------------------------------
# |
# |  ScriptsActivateActivity.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 21:10:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the ScriptsActivateActivity object"""

import os
import textwrap

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import inflect as inflect_mod

from rich import print as rich_print
from rich.align import Align
from rich.console import Group
from rich.panel import Panel

from Common_Foundation import JsonEx
from Common_Foundation.Shell import Commands  # type: ignore
from Common_Foundation.Shell.All import CurrentShell  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager  # type: ignore
from Common_Foundation import TextwrapEx  # type: ignore

from .ActivateActivity import ActivateActivity

from ...Configuration import VersionSpecs
from ... import Constants
from ... import DataTypes


# ----------------------------------------------------------------------
inflect                                     = inflect_mod.engine()


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Extractor(object):
    # ----------------------------------------------------------------------
    create_commands_func: Callable[[Path], Optional[List[Commands.Command]]]
    create_documentation_func: Optional[Callable[[Path], str]]
    decorate_script_name_func: Optional[Callable[[Path], str]]


# ----------------------------------------------------------------------
ExtractorMap                                = Dict[
    Tuple[str, ...],                        # file extensions associated with the extractor
    Extractor,
]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class DirGeneratorResult(object):
    path: Path
    should_recurse: bool                    = field(kw_only=True, default=True)


# ----------------------------------------------------------------------
DirGenerator                                = Callable[
    [Path, VersionSpecs],
    Union[None, DirGeneratorResult, List[DirGeneratorResult]],
]


# ----------------------------------------------------------------------
class ScriptsActivateActivity(ActivateActivity):
    # ----------------------------------------------------------------------
    # |
    # |  Properties
    # |
    # ----------------------------------------------------------------------
    @property
    def name(self) -> str:
        return "Scripts"

    # ----------------------------------------------------------------------
    # |
    # |  Private Types
    # |
    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class _ExtractorEx(Extractor):
        # ----------------------------------------------------------------------
        repository: DataTypes.ConfiguredRepoDataWithPath

    # ----------------------------------------------------------------------
    # |
    # |  Private Methods
    # |
    # ----------------------------------------------------------------------
    # Update the comments in ../../Constants.py if this method name changes
    def _CreateCommandsImpl(
        self,
        dm: DoneManager,
        configuration: Optional[str],
        repositories: List[DataTypes.ConfiguredRepoDataWithPath],
        version_specs: VersionSpecs,
        generated_dir: Path,
        *,
        force: bool,
    ) -> List[Commands.Command]:
        script_dir = generated_dir / self.name

        with dm.VerboseNested(
            "Cleaning previous content...",
            suffix="\n",
            display_exceptions=False,
        ):
            CurrentShell.RemoveDir(script_dir)

        script_dir.mkdir(parents=True, exist_ok=True)

        commands: List[Commands.Command] = []

        # As a convenience, generate links without file extensions that point to the file-extension
        # versions on some systems
        should_generate_extensionless_links = (
            CurrentShell.family_name == "Linux" and CurrentShell.script_extensions
        )

        # Scripts come in a variety of different forms; customization methods may return new ways to
        # traverse a directory. Maintain a list of all potential dir generators to use when parsing
        # script directories.
        dir_generators: List[Callable[[Path, VersionSpecs], DirGeneratorResult]] = [
            (lambda directory, version_specs: DirGeneratorResult(directory / self.name, should_recurse=True)),
        ]

        extractors: Dict[str, ScriptsActivateActivity._ExtractorEx] = {}

        with dm.VerboseNested(
            "Preparing dynamic functionality...",
            [
                lambda: "{} found".format(inflect.no("custom extractor", len(extractors))),
                lambda: "{} found".format(inflect.no("custom generator", len(dir_generators) - 1)),
            ],
            suffix="\n",
            display_exceptions=False,
        ) as prep_dm:
            args = {
                "repositories": repositories,
                "version_specs": version_specs,
            }

            for repository_index, repository in enumerate(repositories):
                original_num_extractors = len(extractors)
                original_num_generators = len(dir_generators)

                with prep_dm.Nested(
                    "'{}' ({} of {})...".format(
                        repository.root,
                        repository_index + 1,
                        len(repositories),
                    ),
                    [
                        lambda: "{} added".format(inflect.no("custom extractor", len(extractors) - original_num_extractors)),
                        lambda: "{} added".format(inflect.no("custom generator", len(dir_generators) - original_num_generators)),
                    ],
                    display_exceptions=False,
                ):
                    result = self.CallCustomMethod(
                        repository.root / Constants.ACTIVATE_ENVIRONMENT_CUSTOMIZATION_FILENAME,
                        Constants.ACTIVATE_ENVIRONMENT_CUSTOM_SCRIPT_EXTRACTOR_METHOD_NAME,
                        args,
                        result_is_list=False,
                    )

                    if result is None:
                        continue

                    # The result can be:
                    #   - (ExtractorMap, DirGenerators)
                    #   - (ExtractorMap, DirGenerator)
                    #   - ExtractorMap

                    if isinstance(result, tuple):
                        these_extractors, generator_or_generators = result

                        if not isinstance(generator_or_generators, list):
                            dir_generators.append(generator_or_generators)
                        else:
                            dir_generators += generator_or_generators
                    else:
                        these_extractors = result

                    for file_extensions, extractor in these_extractors.items():
                        for file_extension in file_extensions:
                            existing_extractor = extractors.get(file_extension, None)
                            if existing_extractor is not None:
                                raise Exception(
                                    textwrap.dedent(
                                        """\
                                        An extractor for '{ext}' was already defined.

                                        New:            {new_name} <{new_id}> [{new_root}]
                                        Original:       {original_name} <{original_id}> [{original_root}]

                                        """,
                                    ).format(
                                        ext=file_extension,
                                        new_name=repository.name,
                                        new_id=repository.id,
                                        new_root=repository.root,
                                        original_name=existing_extractor.repository.name,
                                        original_id=existing_extractor.repository.id,
                                        original_root=existing_extractor.repository.root,
                                    ),
                                )

                            extractors[file_extension] = extractor

        if extractors:
            # ----------------------------------------------------------------------
            @dataclass(frozen=True)
            class ScriptInfo(object):
                # ----------------------------------------------------------------------
                repository: DataTypes.ConfiguredRepoDataWithPath
                extractor: Extractor
                filename: Path

            # ----------------------------------------------------------------------

            script_infos: List[ScriptInfo] = []

            with dm.VerboseNested(
                "Searching for content...",
                lambda: "{} found".format(inflect.no("script", len(script_infos))),
                suffix="\n",
                display_exceptions=False,
            ) as search_dm:
                for repository_index, repository in enumerate(repositories):
                    original_num_scripts = len(script_infos)

                    with search_dm.Nested(
                        "'{}' ({} of {})...".format(
                            repository.root,
                            repository_index + 1,
                            len(repositories),
                        ),
                        lambda: "{} added".format(inflect.no("script", len(script_infos) - original_num_scripts)),
                        display_exceptions=False,
                    ):
                        for dir_generator in dir_generators:
                            result_or_results = dir_generator(repository.root, version_specs)
                            if result_or_results is None:
                                continue

                            if isinstance(result_or_results, list):
                                results = result_or_results
                            else:
                                results = [result_or_results, ]

                            for result in results:
                                if not result.path.is_dir():
                                    continue

                                if result.should_recurse:
                                    # ----------------------------------------------------------------------
                                    def EnumFilenamesRecursive():
                                        for root, _, filenames in os.walk(result.path):
                                            root = Path(root)

                                            for filename in filenames:
                                                yield root / filename

                                    # ----------------------------------------------------------------------

                                    enum_filenames_func = EnumFilenamesRecursive

                                else:
                                    # ----------------------------------------------------------------------
                                    def EnumFilenamesStandard():
                                        yield from result.path.iterdir()

                                    # ----------------------------------------------------------------------

                                    enum_filenames_func = EnumFilenamesStandard

                                for filename in enum_filenames_func():
                                    extractor = extractors.get(filename.suffix, None)
                                    if extractor is None:
                                        continue

                                    script_infos.append(
                                        ScriptInfo(repository, extractor, filename.resolve()),
                                    )

            if script_infos:
                # ----------------------------------------------------------------------
                @dataclass(frozen=True)
                class WrappedInfo(object):
                    # ----------------------------------------------------------------------
                    name: str
                    documentation: Optional[str]
                    script_info: ScriptInfo

                # ----------------------------------------------------------------------

                wrappers: List[WrappedInfo] = []
                rename_warnings: List[str] = []

                with dm.VerboseNested(
                    "Creating script wrappers...",
                    lambda: "{} written".format(inflect.no("wrapper", len(wrappers))),
                    suffix="\n",
                    display_exceptions=False,
                ):
                    # We have a list of script files and the functions used to extract information
                    # from them. Files were extracted based on repositories ordered from the lowest
                    # to highest level. However, it is likely that the user will want to use scripts
                    # from high-level repositories more often than lower-level ones when names collide.
                    # Reverse the order of the higher-level scripts get the standard name while conflicts
                    # in lower-level libraries are renamed.
                    script_infos.reverse()

                    for script_info in script_infos:
                        script_commands = script_info.extractor.create_commands_func(script_info.filename)
                        if script_commands is None:
                            continue

                        # Create a unique name for the wrapper
                        if script_info.extractor.decorate_script_name_func is not None:
                            name = script_info.extractor.decorate_script_name_func(script_info.filename)
                        else:
                            name = script_info.filename.stem

                        conflicts: List[Path] = []

                        while True:
                            potential_filename = script_dir / "{}{}{}".format(
                                name,
                                len(conflicts) if conflicts else "",
                                CurrentShell.script_extensions[0],
                            )

                            if not potential_filename.is_file():
                                break

                            conflicts.append(potential_filename)

                        if potential_filename.stem != name:
                            rename_warnings.append(
                                textwrap.dedent(
                                    """\
                                    The wrapper script for '{}' has been renamed '{}' to avoid conflicts with:
                                    {}
                                    """,
                                ).format(
                                    str(script_info.filename.resolve()),
                                    potential_filename.name,
                                    "\n".join("    - {}".format(str(conflict.resolve())) for conflict in conflicts),
                                ),
                            )

                        # Create the wrapper
                        with potential_filename.open("w") as f:
                            f.write(CurrentShell.GenerateCommands(script_commands))

                        CurrentShell.MakeFileExecutable(potential_filename)

                        # Create the information that will be used for additional help
                        wrappers.append(
                            WrappedInfo(
                                potential_filename.name,
                                script_info.extractor.create_documentation_func(script_info.filename)
                                    if script_info.extractor.create_documentation_func is not None
                                    else None,
                                script_info,
                            ),
                        )

                        if should_generate_extensionless_links:
                            extensionless_filename = potential_filename.with_suffix("")

                            extensionless_filename.hardlink_to(potential_filename)
                            CurrentShell.MakeFileExecutable(extensionless_filename)

                if wrappers:
                    # Above, we reversed the items so we could order from most-specific to least-specific.
                    # Here, we want to order the other way around.
                    wrappers.reverse()

                    with dm.VerboseNested(
                        "Preserving script data...",
                        display_exceptions=False,
                    ):
                        # Group the scripts by repository
                        repos: Dict[str, Tuple[str, Path, List[Any]]] = {}

                        for wrapper in wrappers:
                            repos.setdefault(
                                str(wrapper.script_info.repository.id),
                                (
                                    wrapper.script_info.repository.name,
                                    wrapper.script_info.repository.root,
                                    [],
                                ),
                            )[-1].append(
                                {
                                    "name": wrapper.name,
                                    "documentation": wrapper.documentation,
                                    "filename": str(wrapper.script_info.filename),
                                },
                            )

                        with (script_dir / Constants.SCRIPT_DATA_NAME).open("w") as f:
                            JsonEx.Dump(repos, f)

                # Wait until the verbose stream is done writing content before writing warnings
                if rename_warnings:
                    dm.WriteWarning.write(
                        TextwrapEx.Indent("\n\n{}".format("\n".join(rename_warnings)), 2),
                    )

                if wrappers:
                    # Write the final output
                    with dm.YieldStream() as stream:
                        stream.write("\n")

                        rich_print(
                            Panel(
                                Group(
                                    textwrap.dedent(
                                        """\
                                        Shell wrappers have been created for all recognized scripts with the directory
                                        '{script_dir}' across all repositories. For a complete list of these wrappers, run:
                                        """,
                                    ).format(script_dir=self.name),
                                    Align(
                                        Constants.SCRIPT_LIST_NAME + CurrentShell.script_extensions[0],
                                        "center",
                                        style="bold white",
                                    ),
                                ),
                                expand=False,
                                padding=(1, 2),
                            ),
                            end="",
                            file=stream,  # type: ignore
                        )

                        stream.write("\n")

        commands.append(
            Commands.AugmentPath.Create(str(script_dir.resolve())),
        )

        return commands
