# ----------------------------------------------------------------------
# |
# |  Build.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-03-29 12:57:29
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Builds AutoSemVer"""

import os
import textwrap
import uuid

from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any, Callable, Iterator, Optional, TextIO, Tuple, Union

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Streams.StreamDecorator import StreamDecorator
from Common_Foundation import SubprocessEx
from Common_Foundation import Types
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.BuildImpl import BuildInfoBase
from Common_FoundationEx import TyperEx

try:
    from Common_PythonDevelopment.BuildPythonExecutable import Build, BuildSteps, Clean

    _working_dir = PathEx.EnsureDir(Path(__file__).parent / "..")
    PathEx.EnsureFile(_working_dir / "setup.py")

    _clean_func = Clean

    _build_func = lambda *args, **kwargs: Build(
        *args,
        **{
            **kwargs,
            **{
                "working_dir": _working_dir,
            },
        },
    )

except ModuleNotFoundError:
    # ----------------------------------------------------------------------
    def CleanImpl(*args, **kwargs):  # pylint: disable=unused-argument
        return 0

    # ----------------------------------------------------------------------
    def BuildImpl(*args, **kwargs):  # pylint: disable=unused-argument
        return 0

    # ----------------------------------------------------------------------

    _clean_func = CleanImpl
    _build_func = BuildImpl

    BuildSteps = []


# ----------------------------------------------------------------------
class BuildInfo(BuildInfoBase):
    # ----------------------------------------------------------------------
    def __init__(self):
        super(BuildInfo, self).__init__(
            name="AutoSemVer",
            requires_output_dir=True,
            disable_if_dependency_environment=True,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def Clean(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return _clean_func(
            output_dir,
            output_stream,
            is_verbose=is_verbose,
            is_debug=is_debug,
        )

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomBuildArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return argument descriptions for any custom args that can be passed to the Build func on the command line"""

        # No custom args by default
        return {}

    # ----------------------------------------------------------------------
    @overridemethod
    def GetNumBuildSteps(
        self,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        return len(BuildSteps)

    # ----------------------------------------------------------------------
    @overridemethod
    def Build(                              # pylint: disable=arguments-differ
        self,
        configuration: Optional[str],       # pylint: disable=unused-argument
        output_dir: Path,
        output_stream: TextIO,
        on_progress_update: Callable[       # pylint: disable=unused-argument
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
        *,
        is_verbose: bool,
        is_debug: bool,
        force: bool=False,
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        return _build_func(
            output_dir,
            output_stream,
            on_progress_update,
            is_verbose=is_verbose,
            is_debug=is_debug,
            force=force,
        )


# ----------------------------------------------------------------------
def CreateBinary(
    output_dir: Path=TyperEx.typer.Argument(..., file_okay=False, help="Binary output directory."),
    docker_base_image: str=TyperEx.typer.Option("ubuntu:latest", "--base-image", help="Name of the docker image used to build the binary."),
    verbose: bool=TyperEx.typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=TyperEx.typer.Option(False, "--verbose", help="Write debug information to the terminal."),
) -> int:
    """Creates a binary that can be used to run AutoSemVer without installing all python dependencies."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        if not os.getenv("DEVELOPMENT_ENVIRONMENT_DOCKER_DEVELOPMENT_MIXIN_ACTIVE"):
            dm.WriteError(
                textwrap.dedent(
                    """\
                    This build relies on the repository 'Common_DockerDevelopmentMixin', which does
                    not appear to be activated.

                    This repository is available at: https://github.com/davidbrownell/v4-Common_DockerDevelopmentMixin
                    """,
                ),
            )

            return dm.result

        source_root = PathEx.EnsureDir(Path(__file__).parent.parent)

        working_dir = CurrentShell.CreateTempDirectory()
        with ExitStack(lambda: PathEx.RemoveTree(working_dir)):
            unique_id = str(uuid.uuid4()).replace("-", "")

            # Calculate the current version
            version: Optional[str] = None

            with dm.Nested(
                "Calculating version...",
                lambda: version,
            ):
                result = SubprocessEx.Run(
                    "AutoSemVer{} --quiet".format(CurrentShell.script_extensions[0]),
                    cwd=source_root,
                )

                assert result.returncode == 0, result
                version = result.output.strip()

            # Create the docker file
            docker_filename = working_dir / "Dockerfile"

            with dm.Nested("Creating dockerfile..."):
                with docker_filename.open("w") as f:
                    f.write(
                        textwrap.dedent(
                            """\
                            FROM {base_image}

                            RUN apt update && apt install -y git

                            RUN mkdir code
                            WORKDIR /code

                            COPY . .

                            RUN bash -c "src/AutoSemVer/BuildEnvironment/Bootstrap.sh /tmp/code_dependencies --debug"

                            WORKDIR /code/src/AutoSemVer/BuildEnvironment

                            RUN bash -c "source ./Activate.sh \\
                                && python Build.py Build /tmp/AutoSemVer"

                            RUN bash -c "mkdir /tmp/AutoSemVer_binary \\
                                && cd /tmp/AutoSemVer \\
                                && tar -czvf /tmp/AutoSemVer_binary/{version}-{os}.tgz *"
                            """,
                        ).format(
                            base_image=docker_base_image,
                            version=version,
                            os=docker_base_image.split(":")[0],
                        ),
                    )

            # Build the image
            with dm.Nested("Building archive...") as build_dm:
                command_line = 'docker build --tag {tag} -f {dockerfile} .'.format(
                    tag=unique_id,
                    dockerfile=docker_filename,
                )

                build_dm.WriteVerbose("Command line: {}\n\n".format(command_line))

                with _GenerateStreamAndSink(build_dm) as (stream, sink):
                    build_dm.result = SubprocessEx.Stream(
                        command_line,
                        stream,
                        cwd=PathEx.EnsureDir(source_root.parent.parent),
                    )

                    if build_dm.result != 0:
                        if build_dm.is_verbose:
                            build_dm.WriteError(sink.getvalue())

                        return build_dm.result

            with dm.Nested("Extracting archive...") as extract_dm:
                output_dir.mkdir(parents=True, exist_ok=True)

                command_line = 'docker run --rm -v "{output_dir}:/local" {tag} bash -c "cp /tmp/AutoSemVer_binary/* /local"'.format(
                    tag=unique_id,
                    output_dir=output_dir,
                )

                extract_dm.WriteVerbose("Command line: {}\n\n".format(command_line))

                with _GenerateStreamAndSink(extract_dm) as (stream, sink):
                    extract_dm.result = SubprocessEx.Stream(command_line, stream)
                    if extract_dm.result != 0:
                        if not extract_dm.is_verbose:
                            extract_dm.WriteError(sink.getvalue())

                        return extract_dm.result

            with dm.Nested("Removing image...") as remove_dm:
                command_line = 'docker image rm {}'.format(unique_id)

                remove_dm.WriteVerbose("Command line: {}\n\n".format(command_line))

                with _GenerateStreamAndSink(remove_dm) as (stream, sink):
                    remove_dm.result = SubprocessEx.Stream(command_line, stream)
                    if remove_dm.result != 0:
                        if not remove_dm.is_verbose:
                            remove_dm.WriteError(sink.getvalue())

                        return remove_dm.result

            return 0


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
@contextmanager
def _GenerateStreamAndSink(
    dm: DoneManager,
) -> Iterator[tuple[Any, StringIO]]:
    sink = StringIO()

    if dm.is_verbose:
        with dm.YieldVerboseStream() as stream:
            yield stream, sink
    else:
        yield sink, sink


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    BuildInfo().Run()
