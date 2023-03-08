# ----------------------------------------------------------------------
# |
# |  ScmPlugins.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-25 09:53:22
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Customizations for SCM plugins"""

import importlib
import itertools
import re
import textwrap
import sys

from functools import cached_property
from pathlib import Path
from typing import ClassVar, Dict, List, Optional, Pattern

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import PathEx
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.InflectEx import inflect

from RepositoryBootstrap.DataTypes import ChangeInfo, SCMPlugin


# ----------------------------------------------------------------------
sys.path.insert(0, str(PathEx.EnsureDir(Path(__file__).parent / "Scripts" / "AutoSemVer")))
with ExitStack(lambda: sys.path.pop(0)):
    import AutoSemVer  # type: ignore


# ----------------------------------------------------------------------
def GetPlugins() -> list[SCMPlugin]:
    return [
        _CommitMessageDecorator(),
        _ValidateCommitMessage(),
        _ValidateValidTitleLength(),
        _ValidateGitmoji(),
        _ValidateBannedText(),
        _ValidateAutoSemVerUsage(),
        _ValidateDistinctAutoSemVerConfigurations(),
        _ValidatePythonLibraryVersions(),
    ]


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
class _CommitMessageDecorator(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Commit Message Decorator"

    flags: ClassVar[SCMPlugin.Flag]        = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
    )

    # This has to happen early in the process as it decorates the title and description
    priority: ClassVar[int]                 = SCMPlugin.DEFAULT_PRIORITY // 2

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=protected-access
        change: ChangeInfo,
    ) -> None:
        # We have to get creative in how we invoke CommitEmojis because this script isn't running in a
        # fully activated environment. However, we are guaranteed that the working directory is set
        # to the root of Common_Foundation.
        commit_emojis_dir = PathEx.EnsureDir(Path.cwd() / "Scripts" / "CommitEmojis")

        # ----------------------------------------------------------------------
        def Transform(
            value: Optional[str],
        ) -> Optional[str]:
            if value is None:
                return None

            temp_filename = CurrentShell.CreateTempFilename()

            with temp_filename.open(
                "w",
                encoding="UTF-8",
            ) as f:
                f.write(value)

            with ExitStack(lambda: PathEx.RemoveFile(temp_filename)):
                command_line = 'python {} Transform "{}"'.format(
                    commit_emojis_dir,
                    temp_filename,
                )

                result = SubprocessEx.Run(command_line)
                result.RaiseOnError()

                return result.output

        # ----------------------------------------------------------------------

        new_title = Transform(change.title)
        assert new_title is not None

        new_description = Transform(change.description)

        if new_title != change.title or new_description != change.description:
            # ----------------------------------------------------------------------
            def ToText(
                title: str,
                description: Optional[str],
            ) -> str:
                return "{}{}{}".format(
                    title,
                    "\n\n" if description else "",
                    description or "",
                )

            # ----------------------------------------------------------------------

            dm.WriteLine(
                textwrap.dedent(
                    """\
                    The message has been changed from:

                        {}

                    to:

                        {}

                    """,
                ).format(
                    ToText(change.title, change.description),
                    ToText(new_title, new_description),
                ),
            )

            change.title = new_title
            change.description = new_description


# ----------------------------------------------------------------------
class _ValidateCommitMessage(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Validate Commit Message"

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
        | SCMPlugin.Flag.ValidatePullRequest
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=unused-argument
        change: ChangeInfo,
    ) -> None:
        if not change.title:
            dm.WriteError(
                "The commit message for '{} <{}>' is empty.".format(
                    change.change_info.id,
                    change.change_info.author_date,
                ),
            )

        if dm.result == 0:
            dm.WriteVerbose("A commit message is present.")


# ----------------------------------------------------------------------
class _ValidateValidTitleLength(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Validate Commit Title Length"

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
        | SCMPlugin.Flag.ValidatePullRequest
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=unused-argument
        change: ChangeInfo,
    ) -> None:
        # Longest title length that can be displayed on GitHub.com without introducing an ellipsis
        # (rounded down to a slightly-less specific value that is hopefully easy to remember).
        max_title_length = 65

        if len(change.title) > max_title_length:
            dm.WriteError(
                textwrap.dedent(
                    """\
                    The commit title '{}' for '{} <{}>' is too long.

                        Maximum length:  {}
                        Current length:  {}

                    """,
                ).format(
                    change.title,
                    change.change_info.id,
                    change.change_info.author_date,
                    max_title_length,
                    len(change.title),
                ),
            )

        if dm.result == 0:
            dm.WriteVerbose("The title length is valid.")


# ----------------------------------------------------------------------
class _ValidateGitmoji(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Validate Gitmoji Conventions"

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
        | SCMPlugin.Flag.ValidatePullRequest
    )

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,  # pylint: disable=unused-argument
        change: ChangeInfo,
    ) -> None:
        # This won't work in all cases, but consider a 32 bit char an emoji
        title_bytes = change.title.encode("UTF-8")

        if not (
            (len(title_bytes) >= 2 and (title_bytes[0] >> 5) == 0b110)
            or (len(title_bytes) >= 3 and (title_bytes[0] >> 4) == 0b1110)
            or (len(title_bytes) >= 4 and (title_bytes[0] >> 3) == 0b11110)
        ):
            dm.WriteError(
                textwrap.dedent(
                    """\
                    The commit message '{}' does not adhere to Gitmoji conventions (it does not begin with an emoji).

                    For a list of available Gitmoji values, run `CommitEmojis Display` within an activated environment.

                    Visit https://gitmoji.dev/ for more information about Gitmoji and its benefits.

                    """,
                ).format(change.title),
            )

        if dm.result == 0:
            dm.WriteVerbose("The commit message adheres to Gitmoji conventions.")


# ----------------------------------------------------------------------
class _ValidateBannedText(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Validate Banned Text"

    flags: ClassVar[SCMPlugin.Flag]         = (
        SCMPlugin.Flag.OnCommit
        | SCMPlugin.Flag.OnCommitCanBeDisabled
        | SCMPlugin.Flag.ValidatePullRequest
    )

    has_verbose_output: ClassVar[bool]      = True

    _banned_regex: ClassVar[Pattern]        = re.compile(
        r"(?P<phrase>{})".format(
            "|".join(
                [
                    # Note that these are written in an odd way as to not trigger errors when
                    # changes are made to this file
                    "{}ugBug".format("B"),
                ],
            ),
        ),
        re.IGNORECASE,
    )

    # ----------------------------------------------------------------------
    @cached_property
    def disable_commit_messages(self) -> list[str]:
        return super(_ValidateBannedText, self).disable_commit_messages + ["Allow banned text", ]

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,
        change: ChangeInfo,
    ) -> None:
        # ----------------------------------------------------------------------
        def GetDisplayName(
            filename: Path,
        ) -> str:
            return str(PathEx.CreateRelativePath(repository.repo_root, filename))

        # ----------------------------------------------------------------------

        filenames = list(
            itertools.chain(
                change.change_info.files_added or [],
                change.change_info.files_modified or [],
            ),
        )

        errors: List[str] = []

        for filename_index, filename in enumerate(filenames):
            display_name = GetDisplayName(filename)
            status: Optional[str] = None

            with dm.Nested(
                "'{}' ({} of {})...".format(
                    display_name,
                    filename_index + 1,
                    len(filenames),
                ),
                lambda: status or "errors were encountered",
            ) as file_dm:
                if not filename.is_file:
                    status = "the file no longer exists"
                else:
                    try:
                        with filename.open() as f:
                            filename_content = f.read()

                        results: Dict[str, int] = {}
                        num_phrases = 0

                        for match in self.__class__._banned_regex.finditer(filename_content):
                            phrase = match.group("phrase")

                            if phrase not in results:
                                results[phrase] = 0

                            results[phrase] += 1
                            num_phrases += 1

                        if results:
                            errors.append(
                                TextwrapEx.Indent(
                                    textwrap.dedent(
                                        """\
                                        {}
                                        {}
                                        """,
                                    ).format(
                                        display_name,
                                        TextwrapEx.Indent(
                                            "\n".join(
                                                '"{}": {}'.format(phrase, inflect.no("time", num_times))
                                                for phrase, num_times in results.items()
                                            ),
                                            4,
                                        ),
                                    ),
                                    4,
                                ),
                            )

                            file_dm.result = -1

                        status = "{} found".format(inflect.no("banned phrase", num_phrases))

                    except UnicodeDecodeError:
                        status = "this appears to be a binary file"

                assert status is not None

        if errors:
            dm.WriteError(
                textwrap.dedent(
                    """\

                    Banned text was found in these files:

                    {}

                    """,
                ).format("\n".join(errors).rstrip()),
            )
        else:
            dm.WriteVerbose("\nNo banned text was found.")


# ----------------------------------------------------------------------
class _ValidateAutoSemVerUsage(SCMPlugin):
    # ----------------------------------------------------------------------
    name: ClassVar[str]                     = "Validate AutoSemVer Usage"
    flags: ClassVar[SCMPlugin.Flag]         = SCMPlugin.Flag.ValidatePullRequest

    # ----------------------------------------------------------------------
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,
        change: ChangeInfo,
    ) -> None:
        has_major = any("+major" in value for value in [change.title, change.description or ""])
        has_minor = any("+minor" in value for value in [change.title, change.description or ""])

        if has_major or has_minor:
            if has_major and has_minor:
                dm.WriteError(
                    "Both major and minor AutoSemVer increments were specified in '{} <{}>'.".format(
                        change.change_info.id,
                        change.change_info.author_date,
                    ),
                )

            elif not any(
                AutoSemVer.GetConfigurationFilename(filename, repository.repo_root)
                for filename in itertools.chain(
                    change.change_info.files_added,
                    change.change_info.files_removed,
                    change.change_info.files_modified,
                    change.change_info.working_files,
                )
            ):
                dm.WriteError(
                    "The change '{} <{}>' increments a major or minor version but the files in the change are not associated with an AutoSemVer configuration file.".format(
                        change.change_info.id,
                        change.change_info.author_date,
                    ),
                )

        if dm.result == 0:
            dm.WriteVerbose("AutoSemVer usage is valid.")


# ----------------------------------------------------------------------
class _ValidateDistinctAutoSemVerConfigurations(SCMPlugin):
    name: ClassVar[str]                     = "Validate Distinct AutoSemVer Configurations"
    flags: ClassVar[SCMPlugin.Flag]         = SCMPlugin.Flag.ValidatePullRequest

    has_verbose_output: ClassVar[bool]      = True

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,
        change: ChangeInfo,
    ) -> None:
        configuration_files: dict[Path, list[Path]] = {}

        for filename in itertools.chain(
            change.change_info.files_added,
            change.change_info.files_removed,
            change.change_info.files_modified,
        ):
            configuration_file = AutoSemVer.GetConfigurationFilename(
                filename.parent,
                repository.repo_root,
            )

            if configuration_file is None:
                configuration_file = Path("<No Configuration File>")

            configuration_files.setdefault(configuration_file, []).append(filename)

        if len(configuration_files) > 1:
            keys = list(configuration_files.keys())
            keys.sort()

            dm.WriteError(
                textwrap.dedent(
                    """\
                    This spans multiple AutoSemVer configuration files and  must be split
                    into multiple changes so that AutoSemVer increments each independently.

                    {}

                    """,
                ).format(
                    "".join(
                        TextwrapEx.Indent(
                            textwrap.dedent(
                                """\
                                {}:
                                {}

                                """,
                            ).format(
                                (
                                    configuration_file
                                    if configuration_file.name.startswith("<") and configuration_file.name.endswith(">")
                                    else PathEx.CreateRelativePath(repository.repo_root, configuration_file)
                                ),
                                "\n".join(
                                    "    {}".format(PathEx.CreateRelativePath(repository.repo_root, filename))
                                    for filename in configuration_files[configuration_file]
                                ),
                            ),
                            4,
                            skip_first_line=False,
                        )
                        for configuration_file in keys
                    ).rstrip(),
                ),
            )

        if dm.result == 0:
            dm.WriteVerbose("The files are distinct.")


# ----------------------------------------------------------------------
class _ValidatePythonLibraryVersions(SCMPlugin):
    name: ClassVar[str]                     = "Validate Python Library Versions"
    flags: ClassVar[SCMPlugin.Flag]         = SCMPlugin.Flag.ValidatePullRequest

    has_verbose_output: ClassVar[bool]      = True

    # ----------------------------------------------------------------------
    @overridemethod
    def Execute(
        self,
        dm: DoneManager,
        repository: Repository,
        change: ChangeInfo,  # pylint: disable=unused-argument
    ) -> None:
        python_libraries: list[Path] = []

        with dm.Nested(
            "Calculating Python libraries",
            lambda: "{} found".format(inflect.no("library", len(python_libraries))),
            suffix="\n",
        ):
            python_libraries_dir = repository.repo_root / "Libraries" / "Python"
            if not python_libraries_dir.is_dir():
                return

            for child in python_libraries_dir.iterdir():
                if not child.is_dir():
                    continue

                python_libraries.append(child)

        with dm.Nested("Processing {}...".format(inflect.no("library", len(python_libraries)))) as processing_dm:
            for python_library_index, python_library in enumerate(python_libraries):
                with processing_dm.Nested(
                    "'{}' ({} of {})...".format(
                        python_library.stem,
                        python_library_index + 1,
                        len(python_libraries),
                    ),
                    suffix="\n",
                ) as library_dm:
                    # Get the specified version
                    specified_version: Optional[str] = None

                    with library_dm.Nested(
                        "Loading specified version...",
                        lambda: specified_version or "errors were encountered",
                    ) as version_dm:
                        version_filename = python_library / "src" / "__version__.py"

                        if not version_filename.is_file():
                            version_dm.WriteWarning("The filename '{}' does not exist.".format(version_filename))
                            continue

                        sys.path.insert(0, str(version_filename.parent))
                        with ExitStack(lambda: sys.path.pop(0)):
                            mod = importlib.import_module(version_filename.stem)

                            with ExitStack(lambda: sys.modules.pop(version_filename.stem)):
                                specified_version = getattr(mod, "VERSION", None)
                                if specified_version is None:
                                    version_dm.WriteError("'VERSION' was not defined in '{}'.".format(version_filename))
                                    continue

                    # Calculate the version
                    calculated_version: Optional[AutoSemVer.GetSemanticVersionResult] = None

                    with library_dm.Nested(
                        "Calculating actual version...",
                        lambda: calculated_version.version if calculated_version is not None else "errors were encountered",
                    ) as version_dm:
                        calculated_version = AutoSemVer.GetSemanticVersion(
                            version_dm,
                            path=python_library,
                            include_branch_name_when_necessary=False,
                            no_metadata=True,
                        )

                    assert specified_version is not None
                    assert calculated_version is not None

                    # Python libraries are only defined in terms of major/minor/patch, so we need
                    # to compare as a semver string.
                    calculated_version_str = str(calculated_version.semantic_version)

                    if calculated_version_str != specified_version:
                        library_dm.WriteError(
                            textwrap.dedent(
                                """\

                                The calculated version and the specified versions do not match. Unfortunately,
                                python library versions cannot be specified dynamically as python libraries are
                                installed as a part of the python activation process. AutoSemVer (which is
                                used to calculate semantic versions) cannot be used at this time as it relies
                                on functionality only available after activation is complete.

                                We are therefore left with this process, which verifies that the specified
                                semantic version matches the calculated semantic version.

                                To resolve this error, either...

                                    ...update the specified version so that it matches the calculated version:

                                        '{filename}':
                                            VERSION = "{calculated}"

                                    ...update the calculated version so that it matches the specified version:

                                        Include '+major' or '+minor' in your change description upon checkin.

                                Specified Version:   {specified}
                                Calculated Version:  {calculated}

                                """,
                            ).format(
                                filename=version_filename,
                                specified=specified_version,
                                calculated=calculated_version_str,
                            ),
                        )

        if dm.result == 0:
            dm.WriteVerbose("\nAll versions match.")
