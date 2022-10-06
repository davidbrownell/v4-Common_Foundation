# ----------------------------------------------------------------------
# |
# |  InstallHelpers.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-05 08:34:45
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Functionality useful when Installing tools"""

import hashlib
import math
import os
import shutil
import ssl
import textwrap
import time

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union
from urllib import request
from urllib.error import URLError

from rich.progress import Progress
from semantic_version import Version as SemVer

from Common_Foundation import PathEx
from Common_Foundation import RegularExpression
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from .. import Constants


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class InstallBinaryToolInfo(object):
    tool_name: str
    version_directory: str
    required_version: Optional[SemVer]

    force: bool                             = field(kw_only=True, default=False)
    write_sentinel_in_tool_root: bool       = field(kw_only=True, default=False)
    archive_name: str                       = field(default="install.7z")


# ----------------------------------------------------------------------
def InstallBinaries(
    dm: DoneManager,
    repo_root: Path,
    tool_info_items: List[InstallBinaryToolInfo],
    *,
    force_all: bool,
) -> None:
    """Installs an archive if the tool does not exist or is the wrong version."""

    tools_dir = repo_root / Constants.TOOLS_SUBDIR
    assert tools_dir.is_dir(), tools_dir

    for index, tool_info in enumerate(tool_info_items):
        with dm.Nested(
            "Processing '{}' [{}] ({} of {})...".format(
                tool_info.tool_name,
                tool_info.version_directory,
                index + 1,
                len(tool_info_items),
            ),
            suffix="\n" if dm.is_verbose else "",
        ) as this_dm:
            fullpath = tools_dir / tool_info.tool_name / tool_info.version_directory
            assert fullpath.is_dir(), fullpath

            fullpath /= CurrentShell.family_name
            assert fullpath.is_dir(), fullpath

            potential_fullpath = fullpath / "x64"
            if potential_fullpath.is_dir():
                fullpath = potential_fullpath

            archive_filename = fullpath / tool_info.archive_name

            if not archive_filename.is_file():
                this_dm.WriteError("The file '{}' does not exist.\n".format(archive_filename))
                continue

            if (
                not force_all
                and not tool_info.force
                and CheckInstalledSentinel(
                    this_dm,
                    fullpath,
                    tool_info.required_version,
                    sentinel_in_tool_root=tool_info.write_sentinel_in_tool_root,
                )
            ):
                this_dm.WriteVerbose("'{}' exists and is up-to-date.\n".format(fullpath))
                continue

            sentinel_filename = GetSentinelFilename(fullpath, sentinel_in_tool_root=tool_info.write_sentinel_in_tool_root)

            if sentinel_filename.is_file():
                with this_dm.Nested("Removing '{}'...".format(sentinel_filename)):
                    sentinel_filename.unlink()

            install_root = fullpath / Types.EnsureValid(os.getenv(Constants.DE_ENVIRONMENT_NAME))

            if install_root.is_dir():
                with this_dm.Nested("Removing '{}'...".format(install_root)):
                    PathEx.RemoveTree(install_root)

            with this_dm.Nested("Installing '{}'...".format(archive_filename)) as install_dm:
                if CurrentShell.family_name == "Windows":
                    command_line = '7z x -y "-o{}" {}'.format(install_root, tool_info.archive_name)
                else:
                    command_line = '7zz x -y "-o{}" {}'.format(install_root, tool_info.archive_name)

                result = SubprocessEx.Run(
                    command_line,
                    cwd=fullpath,
                )

                install_dm.result = result.returncode

                if install_dm.result != 0:
                    install_dm.WriteError(result.output)
                    continue

                with install_dm.YieldVerboseStream() as stream:
                    stream.write(result.output)

            WriteInstalledSentinel(
                this_dm,
                fullpath,
                tool_info.required_version,
                write_sentinel_in_tool_root=tool_info.write_sentinel_in_tool_root,
            )


# ----------------------------------------------------------------------
def WriteInstalledSentinel(
    dm: DoneManager,
    tool_root: Path,
    required_version: Optional[SemVer],
    *,
    write_sentinel_in_tool_root: bool=False,            # Write the installed sentinel in the tool root (which is the parent of installed_root) rather than the install dir.
                                                        # Set this to True when the installed root is read-only.
) -> None:
    sentinel_filename = GetSentinelFilename(tool_root, sentinel_in_tool_root=write_sentinel_in_tool_root)
    assert sentinel_filename.parent.is_dir(), sentinel_filename

    with dm.Nested("Writing '{}'...".format(sentinel_filename)):
        with sentinel_filename.open("w") as f:
            if required_version is None:
                f.write("Installation was successful.\n")
            else:
                f.write(_versioned_sentinel_content.format(version=str(required_version)))


# ----------------------------------------------------------------------
def CheckInstalledSentinel(
    dm: DoneManager,
    tool_root: Path,
    required_version: Union[None, SemVer, str],
    *,
    sentinel_in_tool_root: bool=False,
) -> bool:
    sentinel_filename = GetSentinelFilename(tool_root, sentinel_in_tool_root=sentinel_in_tool_root)

    if not sentinel_filename.is_file():
        dm.WriteVerbose("'{}' does not exist.\n".format(sentinel_filename))
        return False

    if required_version:
        with sentinel_filename.open() as f:
            content = f.read()

        match = RegularExpression.TemplateStringToRegex(_versioned_sentinel_content).match(content)
        if not match:
            dm.WriteInfo("'{}' was not versioned.\n".format(sentinel_filename))
            return False

        previous_version = match.group("version")
        required_version_string = str(required_version)

        if previous_version != required_version_string:
            dm.WriteInfo("The version '{}' does not match the required version '{}'.\n".format(previous_version, required_version_string))
            return False

    return True


# ----------------------------------------------------------------------
def GetSentinelFilename(
    tool_root: Path,
    *,
    sentinel_in_tool_root: bool=False,
) -> Path:
    environment_name = Types.EnsureValid(os.getenv(Constants.DE_ENVIRONMENT_NAME))

    if sentinel_in_tool_root:
        return tool_root / "SuccessfulInstallation.{}.txt".format(environment_name)

    return tool_root / environment_name / "SuccessfulInstallation.txt"


# ----------------------------------------------------------------------
def DownloadBinary(
    dm: DoneManager,
    uri: str,
    output_filename: Path,
    sha256: Optional[str],
) -> None:
    temp_filename = CurrentShell.CreateTempFilename()

    with dm.Nested("Downloading '{}'...".format(uri)) as download_dm:
        with download_dm.YieldStdout() as stdout_context:
            stdout_context.persist_content = False

            with Progress(
                *Progress.get_default_columns(),
                "{task.fields[status]}",
                transient=True,
            ) as progress:
                total_progress_id = progress.add_task(
                    stdout_context.line_prefix,
                    total=None,
                    status="",
                )

                total_completed_size: Optional[str] = None

                # ----------------------------------------------------------------------
                def Callback(
                    count: int,
                    block_size: int,
                    total_size: int,
                ):
                    nonlocal total_completed_size

                    if count == 0:
                        progress.update(total_progress_id, total=total_size)
                        total_completed_size = TextwrapEx.GetSizeDisplay(total_size)

                    assert total_completed_size is not None

                    task = progress.tasks[0]
                    assert task.id == total_progress_id

                    progress.update(
                        total_progress_id,
                        advance=block_size,
                        status="{} of {} downloaded".format(
                            TextwrapEx.GetSizeDisplay(int(task.completed)),
                            total_completed_size,
                        ),
                    )

                # ----------------------------------------------------------------------

                # On older versions of Ubuntu (16.04), attempting to download content will fail SSL
                # validation for some reason. The following workaround will disable SSL verification
                # and allow installation to continue. For more information, visit
                # https://stackoverflow.com/a/49174340.
                implemented_ssl_workaround = False

                while True:
                    try:
                        request.urlretrieve(uri, temp_filename, Callback)
                        break

                    except (ssl.SSLError, URLError):
                        # If we have already tried the ssl workaround, let the error pass
                        if implemented_ssl_workaround:
                            raise

                        ssl._create_default_https_context = ssl._create_unverified_context
                        implemented_ssl_workaround = True

        if download_dm.result != 0:
            return

    if sha256:
        CalculateHash(dm, temp_filename, sha256)
        if dm.result != 0:
            return

    with dm.Nested("Saving '{}'...".format(output_filename)):
        if output_filename.is_file():
            output_filename.unlink()

        output_filename.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(temp_filename, output_filename)


# ----------------------------------------------------------------------
def CalculateHash(
    dm: DoneManager,
    filename: Path,
    sha256: str,
) -> None:
    with dm.Nested(
        "Validating content ({})...".format(TextwrapEx.GetSizeDisplay(filename.stat().st_size)),
    ) as validate_dm:
        hash = hashlib.sha256()

        with validate_dm.YieldStdout() as stdout_context:
            stdout_context.persist_content = False

            with Progress(
                transient=True,
            ) as progress:
                task_id = progress.add_task(
                    stdout_context.line_prefix,
                    total=filename.stat().st_size,
                )

                with filename.open("rb") as f:
                    while True:
                        block = f.read(4096)
                        if not block:
                            break

                        hash.update(block)
                        progress.update(task_id, advance=len(block))

                hash = hash.hexdigest().lower()

        if hash != sha256.lower():
            validate_dm.WriteError(
                "The hash values do not match (actual: {}, expected: {})\n".format(
                    hash,
                    sha256.lower(),
                ),
            )


# ----------------------------------------------------------------------
def IsInteractivePrompt(
    dm: DoneManager,
    wait_seconds: int=5,
    prompt: str="Press any key to enable an interactive experience",
) -> bool:
    # By default, the tools will install without user intervention, but this becomes
    # problematic when there are errors during install as the UX goes away and the
    # error information is only available by perusing the setup log files. Create
    # an experience where the install will proceeded without intervention by default,
    # but let's the user select an interactive installation if they want it within
    # a relatively short period of time.
    interactive_install = False

    with dm.YieldStdout() as stdout_content:
        stdout_content.persist_content = False

        # Importing msvcrt here, as it is only available on Windows and we don't want to
        # see an import error when attempting to activate the environment on Windows;
        # we want to see other, more informative errors in that scenario.
        import msvcrt

        # ----------------------------------------------------------------------
        def GetDisplayString(
            time_remaining: float,
        ) -> str:
            seconds_remaining = int(math.ceil(time_remaining))

            return "\r{}{} ({} remaining)  ".format(
                stdout_content.line_prefix,
                prompt,
                "{} {}".format(
                    seconds_remaining,
                    "seconds" if seconds_remaining != 1 else "second",
                ),
            )

        # ----------------------------------------------------------------------

        wait_seconds = 5
        start_time = time.perf_counter()

        while True:
            if msvcrt.kbhit():
                msvcrt.getch()

                interactive_install = True
                break

            elapsed_time = time.perf_counter() - start_time
            if elapsed_time > wait_seconds:
                break

            stdout_content.stream.write(GetDisplayString(wait_seconds - elapsed_time))

        stdout_content.stream.write(
            "\r{}\r".format(" " * len(GetDisplayString(0))),
        )

    return interactive_install


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
_versioned_sentinel_content                 = textwrap.dedent(
    """\
    Installation of '{version}' was successful.
    """,
)
