# ----------------------------------------------------------------------
# |
# |  CreateTags.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-10 15:47:54
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Creates Source Control Management Tags."""

import datetime
import re
import textwrap

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer

from semantic_version import Version as SemVer
from typer.core import TyperGroup

from Common_Foundation.SourceControlManagers.All import ALL_SCMS
from Common_Foundation.SourceControlManagers.GitSourceControlManager import GitSourceControlManager
from Common_Foundation.SourceControlManagers.SourceControlManager import Repository
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
class ReleaseType(str, Enum):
                                                                            # Note that these are intentionally placed in descending order
    official                                = "official"                    # [<prefix>-]v1.2.3
    prerelease                              = "prerelease"                  # [<prefix>-]v1.2.3-prerelease[.<suffix>]
    ci_build                                = "ci_build"                    # [<prefix>-]v1.2.3-machine[.<suffix>]
    local_build                             = "local_build"                 # [<prefix>-]v1.2.3-local[.<suffix>]


# ----------------------------------------------------------------------
@app.command("EntryPoint", no_args_is_help=True)
def EntryPoint(
    semantic_version: str=typer.Argument(..., help="Semantic version to apply; can be the Semantic version or a filename whose contents contain a semantic version."),
    description: str=typer.Argument(..., help="Description used when creating the tag(s)."),
    prefix: Optional[str]=typer.Option(None, help="Prefix applied when creating the tag(s)."),
    release_type: ReleaseType=typer.Option(ReleaseType.local_build, "--release-type", case_sensitive=False, help="Specifies the type of the new tag(s)."),
    suffix: Optional[str]=typer.Option(None, help="Suffix applied when creating the tag(s)."),
    commit_id: Optional[str]=typer.Option(None, help="Commit id associated with the created tag(s)."),
    include_latest: bool=typer.Option(False, "--include-latest", help="Include a 'latest' variation of the tag."),
    push: bool=typer.Option(False, "--push", help="Push the created tag(s) to the remote repository."),
    force: bool=typer.Option(False, "--force", help="Update the tag(s) if they already exist."),
    dry_run: bool=typer.Option(False, "--dry-run", help="Show what would be done, but do not actually create/push the tag(s)."),
    working_dir: Path=typer.Option(Path.cwd(), "--working-dir", file_okay=False, exists=True, resolve_path=True, help="Working directory of the repository to update."),
    force_unsigned_tags: bool=typer.Option(False, "--force-unsigned-tags", help="Disable errors associated with unsigned tags and continue; this is not recommended."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Creates tags."""

    # ----------------------------------------------------------------------
    @dataclass(frozen=True)
    class VersionInfo(object):
        # ----------------------------------------------------------------------
        prefix: Optional[str]
        semantic_version: SemVer
        suffix: Optional[str]  # Can be an empty string

        # ----------------------------------------------------------------------
        @classmethod
        def Create(
            cls,
        ) -> "VersionInfo":
            nonlocal semantic_version

            potential_file = Path(semantic_version)
            if potential_file.is_file():
                with potential_file.open() as f:
                    semantic_version = f.read().strip()

            match = re.match(
                r"""(?#
                    Start of string         )^(?#
                    Prefix                  )(?P<prefix>.*?)(?#
                    Major                   )(?P<major>\d+)\.(?#
                    Minor                   )(?P<minor>\d+)\.(?#
                    Patch                   )(?P<patch>\d+)(?#
                    Suffix                  )(?P<suffix>.*)(?#
                    End of string           )$(?#
                )""",
                semantic_version,
            )

            if not match:
                raise Exception("'{}' is not an expected semantic version.".format(semantic_version))

            prefix_value = match.group("prefix") or ""
            suffix_value = match.group("suffix") or ""

            if prefix:
                if prefix_value is not None:
                    raise typer.BadParameter(
                        "'--prefix' cannot be provided when the semantic version '{}' has a prefix.".format(
                            semantic_version,
                        ),
                    )

                prefix_value = prefix

            if suffix:
                if suffix_value:
                    raise typer.BadParameter(
                        "'--suffix' cannot be provided when the semantic version '{}' has a prefix or suffix.".format(
                            semantic_version,
                        ),
                    )

                suffix_value = suffix

            if release_type == ReleaseType.official:
                if suffix:
                    raise typer.BadParameter("Suffixes are not supported with official releases.")
            else:
                if include_latest:
                    raise typer.BadParameter("'latest'-tags can only be created for official release types.")

                if not suffix_value:
                    if release_type == ReleaseType.prerelease:
                        release_type_decorator = "prerelease"
                    elif release_type == ReleaseType.ci_build:
                        release_type_decorator = "machine"
                    elif release_type == ReleaseType.local_build:
                        release_type_decorator = "local"
                    else:
                        assert False, release_type  # pragma: no cover

                    suffix_value = "-{}.{}".format(
                        release_type_decorator,
                        datetime.datetime.now().strftime("%Y.%M.%d.%H.%M.%S"),
                    )

            if suffix_value and not suffix_value.startswith("-"):
                suffix_value = "-{}".format(suffix_value)

            return VersionInfo(
                prefix_value,
                SemVer(
                    major=int(match.group("major")),
                    minor=int(match.group("minor")),
                    patch=int(match.group("patch")),
                ),
                suffix_value,
            )

    # ----------------------------------------------------------------------

    version_info = VersionInfo.Create()

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        repo: Optional[Repository] = None

        for scm in ALL_SCMS:
            repo_path = scm.IsActive(working_dir)
            if repo_path is None:
                continue

            repo = scm.Open(repo_path)
            break

        if repo is None:
            raise typer.BadParameter("'{}' is not associated with a Source Control Manager.".format(working_dir))

        versions: List[str] = [
            "{}{}{}".format(version_info.prefix, version_info.semantic_version, version_info.suffix),
        ]

        if not version_info.suffix:
            versions += [
                "{}{}.{}".format(
                    version_info.prefix,
                    version_info.semantic_version.major,
                    version_info.semantic_version.minor,
                ),
                "{}{}".format(version_info.prefix, version_info.semantic_version.major),
            ]

        if include_latest:
            versions.append("{}latest".format((version_info.prefix or "").rstrip("v")))

        if repo.scm.name != "Git":
            raise Exception("Git is the only SCM supported at this time.")

        # Ensure that tags are signed if other content is signed
        if not force_unsigned_tags:
            git_output = GitSourceControlManager.Execute("git config --get commit.gpgSign").output.strip().lower()

            if git_output == "true":
                git_output = GitSourceControlManager.Execute("git config --get tag.gpgSign").output.strip().lower()

                if git_output != "true":
                    dm.WriteError(
                        textwrap.dedent(
                            """\
                            Git commits are configured to be signed, but git tags are not.

                            To enable tag signing, run:

                                'git config --global tag.gpgSign true'

                            To disable this error and continue with unsigned tags, specify "--force-unsigned-tags" on
                            the command line when invoking this script.
                            """,
                        ),
                    )

                    return

        # ----------------------------------------------------------------------
        def ProcessVersions(
            desc: str,
            command_line_template: str,
        ) -> None:
            with dm.Nested(desc, suffix="\n") as this_dm:
                for version_index, version in enumerate(versions):
                    with this_dm.Nested(
                        "'{}' ({} of {})...".format(version, version_index + 1, len(versions)),
                    ) as version_dm:
                        command_line = command_line_template.format(version)

                        version_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

                        if dry_run:
                            continue

                        result = SubprocessEx.Run(command_line)

                        version_dm.result = result.returncode

                        if version_dm.result != 0:
                            version_dm.WriteError(result.output)
                            return

                        with version_dm.YieldVerboseStream() as stream:
                            stream.write(result.output)

        # ----------------------------------------------------------------------

        ProcessVersions(
            "Creating local tags...",
            'git tag --annotate -m "{message}"{force} "{{}}" {commit_id}'.format(
                message=description,
                force=" --force" if force else "",
                commit_id=commit_id or "",
            ),
        )

        if dm.result != 0:
            return

        if push:
            ProcessVersions(
                "Pushing tags...",
                'git push origin "{{}}"{force}'.format(
                    force=" --force" if force else "",
                ),
            )

            if dm.result != 0:
                return


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
