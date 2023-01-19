# ----------------------------------------------------------------------
# |
# |  CodeGeneratorPluginHostMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-01-11 15:16:05
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the CodeGeneratorPluginHostMixin object"""

import inspect
import os
import sys
import types

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Generator, Optional, Tuple, Type, Union

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerException, DoneManagerFlags
from Common_Foundation.Types import overridemethod

from .IntrinsicsBase import IntrinsicsBase
from ..Interfaces.IInvoker import IInvoker, InvokeReason
from ..PluginBase import PluginBase


# ----------------------------------------------------------------------
foundation_repo_root = os.getenv("DEVELOPMENT_ENVIRONMENT_FOUNDATION")
if foundation_repo_root:
    foundation_repo_root = Path(foundation_repo_root)
else:
    foundation_repo_root = Path(__file__).parent / "Common_Foundation"

PathEx.EnsureDir(foundation_repo_root)

sys.path.insert(0, str(foundation_repo_root))
with ExitStack(lambda: sys.path.pop(0)):
    from RepositoryBootstrap.SetupAndActivate import DynamicPluginArchitecture  # pylint: disable=import-error

del foundation_repo_root


# ----------------------------------------------------------------------
class CodeGeneratorPluginHostMixin(
    IntrinsicsBase,
    IInvoker,
):
    """Mixin for CodeGenerators that implement functionality using dynamic plugins"""

    # ----------------------------------------------------------------------
    VERBOSE_ENV_VAR_NAME                    = "PLUGIN_HOST_MIXIN_VERBOSE_FLAG"
    DEBUG_ENV_VAR_NAME                      = "PLUGIN_HOST_MIXIN_DEBUG_FLAG"

    # ----------------------------------------------------------------------
    def __init__(
        self,
        dynamic_plugin_architecture_environment_key_or_plugin_dir: Union[str, Path],
    ):
        self._dynamic_plugin_architecture_environment_key_or_plugin_dir     = dynamic_plugin_architecture_environment_key_or_plugin_dir

        self._plugin_cache: Dict[str, PluginBase]                           = {}

    # ----------------------------------------------------------------------
    def LoadPlugin(
        self,
        metadata_or_context: Dict[str, Any],
        dm: Optional[DoneManager],
    ) -> PluginBase:
        # Load the plugin modules
        plugin_name = metadata_or_context.get("plugin", None)
        if plugin_name is None:
            raise DoneManagerException("No plugins were specified.")

        cache_key = plugin_name

        cached_result = self._plugin_cache.get(cache_key, None)
        if cached_result is not None:
            return cached_result

        is_file_input = False

        # ----------------------------------------------------------------------
        def GetEnvironmentKeyOrPath():
            nonlocal is_file_input

            potential_path = Path(plugin_name)
            if potential_path.is_file():
                is_file_input = True
                return potential_path

            return self._dynamic_plugin_architecture_environment_key_or_plugin_dir

        # ----------------------------------------------------------------------

        environment_key_or_path = GetEnvironmentKeyOrPath()

        plugin_modules: List[types.ModuleType] = []

        if isinstance(environment_key_or_path, str):
            plugin_modules += DynamicPluginArchitecture.EnumeratePlugins(environment_key_or_path)

        elif isinstance(environment_key_or_path, Path):
            plugin_filenames: List[Path] = []

            if environment_key_or_path.is_file():
                if environment_key_or_path.suffix != ".py":
                    raise DoneManagerException("'{}' is not a valid python filename.\n".format(environment_key_or_path))

                plugin_filenames.append(environment_key_or_path)
                is_file_input = True

            elif environment_key_or_path.is_dir():
                for filename in environment_key_or_path.iterdir():
                    if filename.suffix == ".py" and filename.stem.endswith("Plugin"):
                        plugin_filenames.append(filename)

            else:
                raise DoneManagerException("'{}' is not a valid filename or directory.".format(environment_key_or_path))

            plugin_modules += [DynamicPluginArchitecture.LoadPlugin(filename) for filename in plugin_filenames]

        else:
            assert False, environment_key_or_path  # pragma: no cover

        # ----------------------------------------------------------------------
        @contextmanager
        def YieldDoneManager() -> Iterator[DoneManager]:
            if dm is not None:
                yield dm
                return

            # Create a diagnostics stream
            is_debug = False

            value = os.getenv(self.__class__.DEBUG_ENV_VAR_NAME)
            if value and value != "0":
                is_debug = True

            is_verbose = False

            value = os.getenv(self.__class__.VERBOSE_ENV_VAR_NAME)
            if value and value != "0":
                is_verbose = True

            with DoneManager.Create(
                sys.stdout,
                "Loading plugins...",
                output_flags=DoneManagerFlags.Create(
                    verbose=is_verbose,
                    debug=is_debug,
                ),
            ) as temp_dm:
                yield temp_dm

        # ----------------------------------------------------------------------

        with YieldDoneManager() as dm:
            # Load the plugin instances
            plugin_infos: Dict[str, Tuple[types.ModuleType, PluginBase]] = {}

            for plugin_module in plugin_modules:
                plugin_class: Optional[Type[PluginBase]] = None

                for potential_class_name in ["Plugin", "CodeGeneratorPlugin"]:
                    plugin_class = getattr(plugin_module, potential_class_name, None)
                    if plugin_class is not None:
                        break

                if plugin_class is None:
                    dm.WriteWarning("The module at '{}' does not contains a 'Plugin' class.\n".format(plugin_module.__file__))
                    continue

                plugin_instance = plugin_class()

                if plugin_instance.name == "None":
                    dm.WriteError("The module  at '{}' contains a plugin with the name 'None'.\n".format(plugin_module.__file__))
                    continue

                validate_environment = plugin_instance.ValidateEnvironment()
                if validate_environment is not None:
                    dm.WriteInfo(
                        "The plugin '{}' defined in '{}' is not valid within this environment: {}\n".format(
                            plugin_instance.name,
                            plugin_module.__file__,
                            validate_environment,
                        ),
                    )
                    continue

                existing_plugin = plugin_infos.get(plugin_instance.name, None)
                if existing_plugin is not None:
                    dm.WriteWarning(
                        "The plugin '{}' defined in '{}' conflicts the a plugin of the same name defined in '{}' and will not be used.\n".format(
                            plugin_instance.name,
                            plugin_module.__file__,
                            existing_plugin[0].__file__,
                        ),
                    )
                    continue

                plugin_infos[plugin_instance.name] = plugin_module, plugin_instance

        if not plugin_infos:
            raise DoneManagerException("No plugins were found.\n")

        if is_file_input:
            assert len(plugin_infos) == 1, plugin_infos
            result = next(iter(plugin_infos.values()))[1]
        else:
            result = plugin_infos.get(plugin_name, None)
            if result is None:
                raise DoneManagerException("The plugin name '{}' is not valid.".format(plugin_name))

            result = result[1]

        self._plugin_cache[cache_key] = result

        return result

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(CodeGeneratorPluginHostMixin, self)._EnumerateOptionalMetadata()
        yield "plugin", "None"

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(CodeGeneratorPluginHostMixin, self)._GetRequiredMetadataNames() + [
            "plugin",
        ]

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(CodeGeneratorPluginHostMixin, self)._GetRequiredContextNames() + [
            "plugin",
        ]

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateGeneratorFiles(
        self,
        context: Dict[str, Any],
    ) -> Generator[Path, None, None]:
        yield from super(CodeGeneratorPluginHostMixin, self)._EnumerateGeneratorFiles(context)

        for base_class in inspect.getmro(type(self.LoadPlugin(context, None))):
            if base_class.__name__ != "object":
                yield Path(inspect.getfile(base_class))

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],
    ) -> int:
        return super(CodeGeneratorPluginHostMixin, self)._GetNumStepsImpl(context) \
            + self.LoadPlugin(context, None).GetNumSteps(context)
