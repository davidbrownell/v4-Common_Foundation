# ----------------------------------------------------------------------
# |
# |  DynamicFunctions.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 15:17:04
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains functionality useful when dynamically invoking functions"""

import importlib
import inspect
import sys
import types

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from .ContextlibEx import ExitStack


# ----------------------------------------------------------------------
@contextmanager
def GetCustomizationMod(
    path: Path,
) -> Iterator[Optional[types.ModuleType]]:
    if not path.is_file():
        yield None
        return

    sys.path.insert(0, str(path.parent.resolve()))
    with ExitStack(lambda: sys.path.pop(0)):
        module_name = path.stem

        module = importlib.import_module(module_name)
        del sys.modules[module_name]

        yield module


# ----------------------------------------------------------------------
def CreateInvocationWrapper(func):
    """\
    Returns a function that can be invoked with a subset of all possible arguments.

    Example:
        def MyFunc(a, b):
            return a + b

        MyFunc(10, 20, 3)                  # Error
        MyFunc(a=10, b=20, c=3)            # Error
        MyFunc(**{'a':10, 'b':20, 'c':3})  # Error

        wrapper = CreateInvocationWrapper(MyFunc)

        wrapper({'a':10, 'b':20, 'c':3}) == 30
    """

    arg_spec = inspect.getfullargspec(func)

    arg_names = {arg for arg in arg_spec.args}
    positional_arg_names = arg_spec.args[:len(arg_spec.args) - len(arg_spec.defaults or [])]

    # Handle perfect forwarding scenarios
    if not arg_names and not positional_arg_names:
        if getattr(arg_spec, "varkw", None) is not None:
            # ----------------------------------------------------------------------
            def Invoke(kwargs):
                return func(**kwargs)

            # ----------------------------------------------------------------------

            return Invoke

        elif arg_spec.varargs is not None:
            # ----------------------------------------------------------------------
            def Invoke(kwargs):
                return func(*tuple(kwargs.values()))

            # ----------------------------------------------------------------------

            return Invoke

        else:
            # ----------------------------------------------------------------------
            def Invoke(kwargs):
                return func()

            # ----------------------------------------------------------------------

            return Invoke

    else:
        # ----------------------------------------------------------------------
        def Invoke(kwargs):
            potential_positional_args = []
            invoke_kwargs = {}

            for k in list(kwargs.keys()):
                if k in arg_names:
                    invoke_kwargs[k] = kwargs[k]
                else:
                    potential_positional_args.append(kwargs[k])

            for positional_arg_name in positional_arg_names:
                if positional_arg_name not in kwargs and potential_positional_args:
                    invoke_kwargs[positional_arg_name] = potential_positional_args.pop(0)

            return func(**invoke_kwargs)

        # ----------------------------------------------------------------------

        return Invoke
