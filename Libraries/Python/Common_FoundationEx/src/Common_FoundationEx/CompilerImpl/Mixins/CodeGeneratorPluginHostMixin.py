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
from typing import Any, Dict, Iterator, List, Generator, Optional, Tuple, Type, Union

from Common_Foundation import DynamicPluginArchitecture
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation.Types import overridemethod

from .IntrinsicsBase import IntrinsicsBase
from ..Interfaces.IInvoker import IInvoker
from ..PluginBase import PluginBase


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
        all_plugins = self.__class__._LoadAllPlugins(dynamic_plugin_architecture_environment_key_or_plugin_dir)  # pylint: disable=protected-access

        self._all_plugins: list[PluginBase]             = all_plugins
        self._plugin_cache: dict[str, PluginBase]       = {}

    # ----------------------------------------------------------------------
    def EnumPlugins(self) -> Generator[PluginBase, None, None]:
        yield from self._all_plugins

    # ----------------------------------------------------------------------
    def GetPlugin(
        self,
        metadata_or_context: dict[str, Any],
    ) -> PluginBase:
        plugin_name = metadata_or_context.get("plugin", None)
        if plugin_name is None:
            raise Exception("No plugins were specified.")

        if plugin_name == "None":
            raise Exception("A plugin name was not provided on the command line.")

        cached_plugin = self._plugin_cache.get(plugin_name, None)
        if cached_plugin is not None:
            return cached_plugin

        potential_path = Path(plugin_name)
        if potential_path.is_file():
            plugins = self.__class__._LoadAllPlugins(
                potential_path,
                heading="Loading explicit plugin...",
            )

            if not plugins:
                raise Exception("The plugin could not be loaded.")

            assert len(plugins) == 1
            plugin = plugins[0]

        else:
            plugin = next(
                (plugin for plugin in self._all_plugins if plugin.name == plugin_name),
                None,
            )

            if plugin is None:
                raise Exception("The plugin name '{}' is not valid.".format(plugin_name))

        self._plugin_cache[plugin_name] = plugin
        return plugin

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

        for base_class in inspect.getmro(type(self.GetPlugin(context))):
            if base_class.__name__ != "object":
                yield Path(inspect.getfile(base_class))

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],
    ) -> int:
        return super(CodeGeneratorPluginHostMixin, self)._GetNumStepsImpl(context) \
            + self.GetPlugin(context).GetNumAdditionalSteps(context)

    # ----------------------------------------------------------------------
    @classmethod
    def _LoadAllPlugins(
        cls,
        environment_key_plugin_dir_or_file: Union[str, Path],
        *,
        heading: str="Loading Plugins...",
    ) -> list[PluginBase]:
        with cls._YieldGlobalDoneManager(heading) as dm:
            modules: list[types.ModuleType] = []

            if isinstance(environment_key_plugin_dir_or_file, str):
                modules += DynamicPluginArchitecture.EnumeratePlugins(environment_key_plugin_dir_or_file)

            elif isinstance(environment_key_plugin_dir_or_file, Path):
                plugin_filenames: list[Path] = []

                if environment_key_plugin_dir_or_file.is_file():
                    if environment_key_plugin_dir_or_file.suffix != ".py":
                        raise Exception("'{}' is not a valid python filename.".format(environment_key_plugin_dir_or_file))

                    plugin_filenames.append(environment_key_plugin_dir_or_file)

                elif environment_key_plugin_dir_or_file.is_dir():
                    for child in environment_key_plugin_dir_or_file.iterdir():
                        if (
                            child.is_file()
                            and child.suffix == ".py"
                            and child.stem.endswith("Plugin")
                        ):
                            plugin_filenames.append(child)

                else:
                    raise Exception("'{}' is not a valid filename or directory.".format(environment_key_plugin_dir_or_file))

                modules += [DynamicPluginArchitecture.LoadPlugin(filename) for filename in plugin_filenames]

            else:
                assert False, environment_key_plugin_dir_or_file  # pragma: no cover

            # Load the instances
            plugin_infos: dict[str, Tuple[types.ModuleType, PluginBase]] = {}

            for module in modules:
                plugin_class: Optional[Type[PluginBase]] = None

                for potential_class_name in ["Plugin", "CodeGeneratorPlugin"]:
                    plugin_class = getattr(module, potential_class_name, None)
                    if plugin_class is not None:
                        break

                if plugin_class is None:
                    dm.WriteWarning("The module at '{}' does not contain a 'Plugin' class.\n".format(module.__file__))
                    continue

                plugin_instance = plugin_class()

                if plugin_instance.name == "None":
                    dm.WriteError("The module at '{}' contains a plugin with the reserved name 'None'.\n".format(module.__file__))
                    continue

                validate_environment = plugin_instance.ValidateEnvironment()
                if validate_environment is not None:
                    dm.WriteInfo(
                        "The plugin '{}' (defined at '{}') is not valid within this environment: {}\n".format(
                            plugin_instance.name,
                            module.__file__,
                            validate_environment,
                        ),
                    )
                    continue

                existing_plugin = plugin_infos.get(plugin_instance.name, None)
                if existing_plugin is not None:
                    dm.WriteWarning(
                        "The plugin '{}' (defined at '{}') conflicts with the plugin of the same name defined at '{}' and will not be used.\n".format(
                            plugin_instance.name,
                            module.__file__,
                            existing_plugin[0].__file__,
                        ),
                    )
                    continue

                plugin_infos[plugin_instance.name] = module, plugin_instance

            return [value[1] for value in plugin_infos.values()]

    # ----------------------------------------------------------------------
    @classmethod
    @contextmanager
    def _YieldGlobalDoneManager(
        cls,
        heading: str,
    ) -> Iterator[DoneManager]:
        # Create a diagnostics stream
        is_debug = False

        value = os.getenv(cls.DEBUG_ENV_VAR_NAME)
        if value and value != "0":
            is_debug = True

        is_verbose = False

        value = os.getenv(cls.VERBOSE_ENV_VAR_NAME)
        if value and value != "0":
            is_verbose = True

        with DoneManager.Create(
            sys.stdout,
            heading,
            output_flags=DoneManagerFlags.Create(
                verbose=is_verbose,
                debug=is_debug,
            ),
        ) as temp_dm:
            yield temp_dm
