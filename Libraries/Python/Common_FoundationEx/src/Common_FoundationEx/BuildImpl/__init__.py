# ----------------------------------------------------------------------
# |
# |  __init__.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-15 13:51:00
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""\
Provides functionality for files that implement or consume build functionality.
A build file is a python script that is capable of building or cleaning one or more
artifacts, where the mechanics associated with the implementation of that functionality
is opaque to the user. With these semantics in place, build files provide a consist way
of building functionality regardless of the underlying technical details.
"""

import inspect
import os
import re
import sys
import textwrap

from abc import abstractmethod, ABC
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Callable, Dict, List, Optional, Pattern, TextIO, Tuple, Union

try:
    import typer

    from rich.progress import Progress

    from typer.core import TyperGroup
    from typer.models import CommandInfo, OptionInfo

except ModuleNotFoundError:
    sys.stdout.write("\nERROR: This script is not available in a 'nolibs' environment.\n")
    sys.exit(-1)

from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx
from Common_Foundation import Types

from Common_FoundationEx.InflectEx import inflect
from Common_FoundationEx import TyperEx


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
)


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class Mode(str, Enum):
    Clean                                   = "Clean"
    Build                                   = "Build"


# ----------------------------------------------------------------------
class BuildInfoBase(ABC):
    """Abstract base class for BuildInfo objects exported by Build.py files"""

    # ----------------------------------------------------------------------
    # Lower values indicate higher priority
    STANDARD_PRIORITY                       = 10000

    COMPLETE_CONFIGURATION_NAME             = "Complete"
    STANDARD_CONFIGURATION_NAMES            = ["Debug", "Release"]

    # ----------------------------------------------------------------------
    def __init__(
        self,
        name: str,

        *,
        priority: int=STANDARD_PRIORITY,

        configurations: Optional[List[str]]=None,
        configuration_is_required_on_clean: Optional[bool]=None,

        requires_output_dir: Optional[bool]=None,
        suggested_output_dir_location: Optional[Path]=None,

        # The name of an environment that must be active in order to
        # invoke the build functionality.
        required_development_environment: Optional[str]=None,

        # The names of environment configurations that must be active in order to
        # invoke the build functionality.
        required_development_configurations: Optional[List[Pattern]]=None,

        # Disable this functionality if the current environment has been activated as a
        # dependency environment.
        disable_if_dependency_environment: bool=False,
    ):
        assert configurations is None or configurations, configurations

        assert (
            (configurations is None and configuration_is_required_on_clean is None)
            or (configurations is not None and configuration_is_required_on_clean is not None)
        ), (configurations, configuration_is_required_on_clean)

        assert (
            (requires_output_dir is None and suggested_output_dir_location is None)
            or requires_output_dir is not None
        ), (requires_output_dir, configuration_is_required_on_clean)

        assert required_development_configurations is None or required_development_configurations, required_development_configurations

        self.name                                       = name
        self.priority                                   = priority

        self.configurations                             = configurations
        self.configuration_is_required_on_clean         = configuration_is_required_on_clean

        self.requires_output_dir                        = requires_output_dir
        self.suggested_output_dir_location              = suggested_output_dir_location

        self.required_development_environment           = required_development_environment
        self.required_development_configurations        = required_development_configurations
        self.disable_if_dependency_environment          = disable_if_dependency_environment

    # ----------------------------------------------------------------------
    def GetTableInfo(self) -> Dict[str, str]:
        return {
            "Name": self.name,
            "Priority": str(self.priority),
            "Configurations": "<None>" if self.configurations is None else ", ".join(self.configurations),
            "Configuration Required on Clean": "<N/A>" if self.configuration_is_required_on_clean is None else str(self.configuration_is_required_on_clean),
            "Requires Output Dir": str(self.requires_output_dir),
            "Suggested Output Dir Location": "<N/A>" if self.suggested_output_dir_location is None else str(self.suggested_output_dir_location),
            "Required Development Environment": self.required_development_environment or "<None>",
            "Required Development Configurations": "<None>" if self.required_development_configurations is None else ", ".join(config_regex.pattern for config_regex in self.required_development_configurations),
            "Disable If Dependency Environment": str(self.disable_if_dependency_environment),
        }

    # ----------------------------------------------------------------------
    def GetNumCleanSteps(
        self,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        """\
        Return the number of steps involved in cleaning.

        This information is used to create progress bars and other visual indicators of progress
        and should be implemented by derived classes if it is possible to extract more information.
        """

        return 1

    # ----------------------------------------------------------------------
    @Types.extensionmethod
    def GetCustomCleanArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return argument descriptions for any custom args that can be passed to the Clean func on the command line"""

        # No custom args by default
        return {}

    # ----------------------------------------------------------------------
    def GetNumBuildSteps(
        self,
        configuration: Optional[str],  # pylint: disable=unused-argument
    ) -> int:
        """\
        Return the number of steps involved in building.

        This information is used to create progress bars and other visual indicators of progress
        and should be implemented by derived classes if it is possible to extract more information.
        """

        return 1

    # ----------------------------------------------------------------------
    @Types.extensionmethod
    def GetCustomBuildArgs(self) -> TyperEx.TypeDefinitionsType:
        """Return argument descriptions for any custom args that can be passed to the Build func on the command line"""

        # No custom args by default
        return {}

    # ----------------------------------------------------------------------
    @abstractmethod
    def Clean(
        self,
        configuration: Optional[str],
        output_dir: Optional[Path],
        output_stream: TextIO,
        on_progress_update: Callable[
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    @abstractmethod
    def Build(
        self,
        configuration: Optional[str],
        output_dir: Optional[Path],
        output_stream: TextIO,
        on_progress_update: Callable[
            [
                int,                        # Step ID
                str,                        # Status info
            ],
            bool,                           # True to continue, False to terminate
        ],
    ) -> Union[
        int,                                # Error code
        Tuple[int, str],                    # Error code and short text that provides info about the result
    ]:
        raise Exception("Abstract method")

    # ----------------------------------------------------------------------
    def Run(self) -> None:
        verbose_option = typer.Option(False, "--verbose", help="Write verbose information to the terminal.")        # pylint: disable=possibly-unused-variable
        debug_option = typer.Option(False, "--debug", help="Write additional debug information to the terminal.")   # pylint: disable=possibly-unused-variable

        # Dynamically create the Build, Clean, and Rebuild func
        build_parameters: Dict[str, str] = {}
        build_option_types: Dict[str, OptionInfo] = {}

        for k, v in self.GetCustomBuildArgs().items():
            if isinstance(v, tuple):
                annotation, v = v

                if isinstance(v, dict):
                    v = typer.Option(None, **v)

                assert isinstance(v, OptionInfo), v
                build_option_types[k] = v

                default = '=build_option_types["{}"]'.format(k)
            else:
                annotation = v
                default = ""

            build_parameters[k] = '{name}: {annotation}{default}'.format(
                name=k,
                annotation=annotation.__name__,
                default=default,
            )

        clean_parameters: Dict[str, str] = {}
        clean_option_types: Dict[str, OptionInfo] = {}

        for k, v in self.GetCustomCleanArgs().items():
            if isinstance(v, tuple):
                annotation, v = v

                if isinstance(v, dict):
                    v = typer.Option(None, **v)

                assert isinstance(v, OptionInfo), v
                clean_option_types[k] = v

                default= '=clean_option_types["{}"]'.format(k)
            else:
                annotation = v
                default = ""

            clean_parameters[k] = '{name}: {annotation}{default}'.format(
                name=k,
                annotation=annotation.__name__,
                default=default,
            )

        build_configuration_parameter = ""
        clean_configuration_parameter = ""
        build_configuration_argument = "None"
        clean_configuration_argument = "None"

        if self.configurations:
            configuration_enum = Types.StringsToEnum("ConfigurationEnum", self.configurations)  # pylint: disable=possibly-unused-variable

            build_configuration_parameter = 'configuration: configuration_enum=typer.Argument(..., help="Configuration to build."),'
            build_configuration_argument = "configuration.value"

            if self.configuration_is_required_on_clean:
                clean_configuration_parameter = 'configuration: configuration_enum=typer.Argument(..., help="Configuration to clean."),'
                clean_configuration_argument = "configuration.value"

        build_output_dir_parameter = ""
        clean_output_dir_parameter = ""
        output_dir_argument = "None"

        if self.requires_output_dir:
            build_output_dir_parameter = 'output_dir: Path=typer.Argument({}, file_okay=False, resolve_path=True, help="Build output directory."),'.format(
                self.suggested_output_dir_location or "...",
            )
            clean_output_dir_parameter = 'output_dir: Path=typer.Argument(..., exists=True, file_okay=False, resolve_path=True, help="Output directory used with Build."),'

            output_dir_argument = "output_dir"

        funcs = textwrap.dedent(
            """\
            # ----------------------------------------------------------------------
            @app.command("Build", no_args_is_help={build_no_args_is_help})
            def Build(
                {build_configuration_parameter}
                {build_output_dir_parameter}
                {build_parameters}
                verbose: bool=verbose_option,
                debug: bool=debug_option,
            ) -> None:
                '''Builds '{name}'.'''

                with DoneManager.CreateCommandLine(
                    output_flags=DoneManagerFlags.Create(
                        verbose=verbose,
                        debug=debug,
                    ),
                ) as dm:
                    self._Execute(
                        dm,
                        {build_configuration_argument},
                        {build_output_dir_argument},
                        "Building",
                        self.GetNumBuildSteps,
                        lambda *args, **kwargs: self.Build(
                            *args,
                            **{{
                                **kwargs,
                                **{{{build_arguments}}}
                            }},
                        ),
                    )

            # ----------------------------------------------------------------------
            @app.command("Clean", no_args_is_help={clean_no_args_is_help})
            def Clean(
                {clean_configuration_parameter}
                {clean_output_dir_parameter}
                {clean_parameters}
                verbose: bool=verbose_option,
                debug: bool=debug_option,
            ) -> None:
                '''Cleans '{name}'.'''

                with DoneManager.CreateCommandLine(
                    output_flags=DoneManagerFlags.Create(
                        verbose=verbose,
                        debug=debug,
                    ),
                ) as dm:
                    self._Execute(
                        dm,
                        {clean_configuration_argument},
                        {clean_output_dir_argument},
                        "Cleaning",
                        self.GetNumCleanSteps,
                        lambda *args, **kwargs: self.Clean(
                            *args,
                            **{{
                                **kwargs,
                                **{{{clean_arguments}}}
                            }},
                        ),
                    )

            # ----------------------------------------------------------------------
            @app.command("Rebuild", no_args_is_help={rebuild_no_args_is_help})
            def Rebuild(
                {rebuild_configuration_parameter}
                {rebuild_output_dir_parameter}
                {rebuild_parameters}
                verbose: bool=verbose_option,
                debug: bool=debug_option,
            ) -> None:
                '''Rebuilds '{name}'.'''

                with DoneManager.CreateCommandLine(
                    output_flags=DoneManagerFlags.Create(
                        verbose=verbose,
                        debug=debug,
                    ),
                ) as dm:
                    self._Execute(
                        dm,
                        {clean_configuration_argument},
                        {clean_output_dir_argument},
                        "Cleaning",
                        self.GetNumCleanSteps,
                        lambda *args, **kwargs: self.Clean(
                            *args,
                            **{{
                                **kwargs,
                                **{{{clean_arguments}}}
                            }},
                        ),
                    )

                    self._Execute(
                        dm,
                        {build_configuration_argument},
                        {build_output_dir_argument},
                        "Building",
                        self.GetNumBuildSteps,
                        lambda *args, **kwargs: self.Build(
                            *args,
                            **{{
                                **kwargs,
                                **{{{build_arguments}}}
                            }},
                        ),
                    )
            """,
        ).format(
            name=self.name,
            # Build
            build_no_args_is_help="True" if (build_configuration_parameter or build_output_dir_parameter or build_parameters) else "False",
            build_configuration_parameter=build_configuration_parameter,
            build_configuration_argument=build_configuration_argument,
            build_output_dir_parameter=build_output_dir_parameter,
            build_output_dir_argument=output_dir_argument,
            build_parameters=TextwrapEx.Indent(
                "\n".join("{},".format(parameter) for parameter in build_parameters.values()),
                4,
                skip_first_line=True,
            ),
            build_arguments=", ".join('"{k}": {k}'.format(k=k) for k in build_parameters),
            # Clean
            clean_no_args_is_help="True" if (clean_configuration_parameter or clean_output_dir_parameter or clean_parameters) else "False",
            clean_configuration_parameter=clean_configuration_parameter,
            clean_configuration_argument=clean_configuration_argument,
            clean_output_dir_parameter=clean_output_dir_parameter,
            clean_output_dir_argument=output_dir_argument,
            clean_parameters=TextwrapEx.Indent(
                "\n".join("{},".format(parameter) for parameter in clean_parameters.values()),
                4,
                skip_first_line=True,
            ),
            clean_arguments=", ".join('"{k}": {k}'.format(k=k) for k in clean_parameters),
            # Rebuild
            rebuild_no_args_is_help="True" if (
                build_configuration_parameter
                or build_output_dir_parameter
                or build_parameters
                or clean_configuration_parameter
                or clean_output_dir_parameter
                or clean_parameters
            ) else "False",
            rebuild_configuration_parameter=build_configuration_parameter or clean_configuration_parameter,
            rebuild_output_dir_parameter=build_output_dir_parameter or clean_output_dir_parameter,
            rebuild_parameters=TextwrapEx.Indent(
                "\n".join(
                    "{},".format(parameter) for parameter in {
                        **clean_parameters,
                        **build_parameters,
                    }.values()
                ),
                4,
                skip_first_line=True,
            ),
        )

        exec(  # pylint: disable=exec-used
            funcs,
            {
                **globals(),
                **{
                    "self": self,
                },
            },
            locals(),
        )

        # ----------------------------------------------------------------------
        @app.command("Metadata", help="Displays metadata about the build.")
        def Metadata() -> None:
            with DoneManager.CreateCommandLine() as dm:
                table_info = self.GetTableInfo()

                with dm.YieldStream() as stream:
                    stream.write(
                        TextwrapEx.CreateTable(
                            list(table_info.keys()),
                            [list(table_info.values()), ],
                            is_vertical=True,
                        ),
                    )

        # ----------------------------------------------------------------------

        # Add any custom functionality exposed by the build file
        frame = inspect.stack()[1]
        mod = inspect.getmodule(frame[0])

        for func_name, func in inspect.getmembers(mod, inspect.isfunction):
            if inspect.getmodule(func) is not mod:
                continue

            if func_name.startswith("_"):
                continue

            if func_name in ["Build", "Clean", "Rebuild", "Metadata"]:
                raise Exception("'{}' is a reserved name and can't be used to implement custom functionality.".format(func_name))

            try:
                app.registered_commands.append(
                    CommandInfo(
                        name=func_name,
                        callback=func,
                    ),
                )
            except Exception:
                sys.stdout.write("Typer doesn't like '{}'.\n\n\n".format(func_name))
                raise

        app()

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _BuildImpl(
        self,
        ctx: typer.Context,
        dm: DoneManager,
        configuration: Optional[str],
        output_dir: Optional[Path],
    ) -> None:
        return self._Execute(
            dm,
            configuration,
            output_dir,
            "Building",
            self.GetNumBuildSteps,
            lambda *args, **kwargs: self.Build(
                *args,
                **{
                    **kwargs,
                    **TyperEx.ProcessDynamicArgs(
                        ctx,
                        self.GetCustomBuildArgs(),
                    ),
                },
            ),
        )

    # ----------------------------------------------------------------------
    def _CleanImpl(
        self,
        ctx: typer.Context,
        dm: DoneManager,
        configuration: Optional[str],
        output_dir: Optional[Path],
    ) -> None:
        return self._Execute(
            dm,
            configuration,
            output_dir,
            "Cleaning",
            self.GetNumCleanSteps,
            lambda *args, **kwargs: self.Clean(
                *args,
                **{
                    **kwargs,
                    **TyperEx.ProcessDynamicArgs(
                        ctx,
                        self.GetCustomCleanArgs(),
                    ),
                },
            ),
        )

    # ----------------------------------------------------------------------
    def _Execute(
        self,
        dm: DoneManager,
        configuration: Optional[str],
        output_dir: Optional[Path],
        desc: str,
        get_num_steps_func: Callable[[Optional[str]], int],
        execute_func: Callable[
            [Optional[str], Optional[Path], TextIO, Callable[[int, str], bool]],
            Union[int, Tuple[int, str]],
        ],
    ) -> None:
        if not self._ValidateEnvironment(dm):
            return

        with dm.Nested("{}...".format(desc)) as execute_dm:
            output: Optional[str] = None

            # TODO: Covert this to use ExecuteTasks
            with execute_dm.YieldStdout() as stdout_context:
                stdout_context.persist_content = False

                with Progress(
                    *Progress.get_default_columns(),
                    "{task.fields[status]}",
                    transient=True,
                ) as progress:
                    task_id = progress.add_task(
                        stdout_context.line_prefix,
                        status=desc,
                    )

                    num_steps = get_num_steps_func(configuration)
                    current_step = 0

                    progress.update(task_id, total=num_steps)

                    # ----------------------------------------------------------------------
                    def OnProgress(
                        step: int,
                        status: str,
                    ) -> bool:
                        nonlocal current_step

                        advance = step - current_step
                        current_step = step

                        progress.update(
                            task_id,
                            advance=advance,
                            status="({} of {}) {}".format(
                                current_step + 1,
                                num_steps,
                                status,
                            ),
                        )

                        return True

                    # ----------------------------------------------------------------------

                    sink = StringIO()
                    result = execute_func(configuration, output_dir, sink, OnProgress)
                    output = sink.getvalue()

                    if isinstance(result, tuple):
                        result = result[0]

                    execute_dm.result = result

            assert output is not None

            if execute_dm.result != 0:
                with execute_dm.YieldStream() as stream:
                    stream.write(output)
            else:
                with execute_dm.YieldVerboseStream() as stream:
                    stream.write(output)

    # ----------------------------------------------------------------------
    def _ValidateEnvironment(
        self,
        dm: DoneManager,
    ) -> bool:
        if (
            self.required_development_environment
            and self.required_development_environment.lower() not in [
                CurrentShell.name.lower(),
                CurrentShell.family_name.lower(),
            ]
        ):
            dm.WriteInfo("This build can only be run on '{}'.\n".format(self.required_development_environment))
            return False

        if self.required_development_configurations:
            current_configuration = os.getenv("DEVELOPMENT_ENVIRONMENT_REPOSITORY_CONFIGURATION")
            assert current_configuration is not None

            if not any(re.match(config_regex, current_configuration) for config_regex in self.required_development_configurations):
                dm.WriteInfo(
                    "This build can only be run in development environments activated with the {} {}; the current configuration is '{}'.".format(
                        inflect.plural("configuration", len(self.required_development_configurations)),
                        ", ".join("'{}'".format(config) for config in self.required_development_configurations),
                        current_configuration,
                    ),
                )

                return False

        if self.disable_if_dependency_environment and not __file__.startswith(Types.EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_REPOSITORY"))):
            dm.WriteInfo("This build can not be used when its repository is activated as a dependency repository.")
            return False

        return True
