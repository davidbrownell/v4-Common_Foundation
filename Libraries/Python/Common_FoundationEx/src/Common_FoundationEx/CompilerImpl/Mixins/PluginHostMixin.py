# ----------------------------------------------------------------------
# |
# |  PluginHostMixin.py
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
"""Contains the PluginHostMixin object"""

import importlib
import inspect
import os
import sys

from pathlib import Path
from typing import Any, Dict, List, Generator, Tuple, Union

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerException
from Common_Foundation.Types import overridemethod, EnsureValid

from .IntrinsicsBase import IntrinsicsBase
from ..Interfaces.IInvoker import IInvoker, InvokeReason
from ..PluginBase import PluginBase


# ----------------------------------------------------------------------
class PluginHostMixin(
    IntrinsicsBase,
    IInvoker,
):
    """Mixin for CodeGenerators that implement functionality using dynamic plugins"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        dynamic_plugin_architecture_environment_key_or_plugin_dir: Union[str, Path],
    ):
        plugin_modules: List[Any] = [] # BugBUg: Type

        if isinstance(dynamic_plugin_architecture_environment_key_or_plugin_dir, str) and os.getenv(dynamic_plugin_architecture_environment_key_or_plugin_dir):
            fundamental_repo_root = PathEx.EnsureDir(Path(EnsureValid(os.getenv("DEVELOPMENT_ENVIRONMENT_FUNDAMENTAL"))))

            sys.path.insert(0, str(fundamental_repo_root))
            with ExitStack(lambda: sys.path.pop(0)):
                from RepositoryBootstrap.SetupAndActivate import DynamicPluginArchitecture

            plugin_modules = list(DynamicPluginArchitecture.EnumeratePlugins(dynamic_plugin_architecture_environment_key_or_plugin_dir))

        elif isinstance(dynamic_plugin_architecture_environment_key_or_plugin_dir, Path):
            if not dynamic_plugin_architecture_environment_key_or_plugin_dir.is_dir():
                raise DoneManagerException(
                    "'{}' is not a valid path.".format(dynamic_plugin_architecture_environment_key_or_plugin_dir),
                )

            sys.path.insert(0, str(dynamic_plugin_architecture_environment_key_or_plugin_dir))
            with ExitStack(lambda: sys.path.pop(0)):
                for filename in dynamic_plugin_architecture_environment_key_or_plugin_dir.iterdir():
                    if filename.suffix == ".py" and filename.stem.endswith("Plugin"):
                        plugin_modules.append(importlib.import_module(filename.stem))

        else:
            raise DoneManagerException(
                "'{}' is not a valid environment variable or path.".format(dynamic_plugin_architecture_environment_key_or_plugin_dir),
            )

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield from super(PluginHostMixin, self)._EnumerateOptionalMetadata()
        yield "plugin", "None"

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> List[str]:
        return super(PluginHostMixin, self)._GetRequiredMetadataNames() + [
            "plugin",
        ]

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> List[str]:
        return super(PluginHostMixin, self)._GetRequiredContextNames() + [
            "plugin",
        ]

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,  # pylint: disable=unused-argument
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        plugin = self._GetPlugin(metadata)

        metadata = plugin.PostprocessMetadata(metadata)

        context = super(PluginHostMixin, self)._CreateContext(dm, metadata)

        return plugin.PreprocessContext(dm, context)

    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateGeneratorFiles(
        self,
        context: Dict[str, Any],
    ) -> Generator[Path, None, None]:
        yield from super(PluginHostMixin, self)._EnumerateGeneratorFiles(context)

        for base_class in inspect.getmro(type(self._GetPlugin(context))):
            if base_class.__name__ != "object":
                yield Path(inspect.getfile(base_class))

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],
    ) -> int:
        return super(PluginHostMixin, self)._GetNumStepsImpl(context) + self._GetPlugin(context).GetNumSteps(context)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    def _GetPlugin(
        self,
        metadata_or_context: Dict[str, Any],
    ) -> PluginBase:
        assert False, "BugBug"
