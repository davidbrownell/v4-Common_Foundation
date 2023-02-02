# ----------------------------------------------------------------------
# |
# |  TyperEx.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-31 08:06:04
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Augments the typer library"""

import re

from dataclasses import dataclass
from types import NoneType
from typing import Any, Callable, cast, ClassVar, Iterable, Optional, Tuple, Type, TypeVar, Union

import typer

from typer import models as typer_models
from typer import main as typer_main

from Common_Foundation import TextwrapEx


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class TypeDefinitionItem(object):
    """Information used to generate a dynamic command line argument"""

    # ----------------------------------------------------------------------
    python_type: Type
    option_info: typer.models.OptionInfo

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        python_type: Type,
        *,
        assume_optional: bool=False,
        **option_info_kwargs,
    ) -> "TypeDefinitionItem":
        is_optional = (
            assume_optional or (
                getattr(python_type, "__origin__", None) is Union
                and any(value is NoneType for value in python_type.__args__)
            )
        )

        typer_option = typer.Option(
            None if is_optional else ...,
            **option_info_kwargs,
        )

        return cls(python_type, typer_option)


# ----------------------------------------------------------------------
TypeDefinitionItemType                      = Union[
    TypeDefinitionItem,

    # Note that the following values are converted into TyperDefinitionItem types
    Type,                                   # Python type annotation
    Tuple[
        Type,                               # Python type annotation
        Union[
            dict[str, Any],                 # Keyword arguments to pass to typer.models.OptionInfo
            typer.models.OptionInfo,        # The OptionInfo itself
        ],
    ],
]


TypeDefinitionsType                         = dict[str, TypeDefinitionItemType]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class DynamicPythonCode(object):
    """\
    Code dynamically generated based on type definitions.

    Example:
        dynamic_python_code = DynamicPythonCode.Create(
            {
                "arg1": TypeDefinitionItem(int, typer.Option(10)),
                "arg2": int,
                "arg3": (int, {"help": "This is the help"}),
                "arg4": (int, typer.Option(20)),
            },
            "custom_types_name",
        )

        # Note that the following var name MUST match the valid provided to
        # TypeDefinitionToPythonFuncArguments.

        custom_types_name = dynamic_python_code.types

        func_code = textwrap.dedent(
            '''\
            @app.command()
            def DynamicFunc(
                {parameters}
            ):
                print({arguments})

            ''',
        ).format(
            parameters=dynamic_python_code.GenerateFuncParameters(),
            arguments=dynamic_python_code.GenerateFuncArguments(single_line=True),
        )

        exec(func_code, globals(), locals())

        DynamicFunc()                       # 10, None, None, 20
        DynamicFunc(arg2=300)               # 10, 300, None, 20
        DynamicFunc(1, 2, 3, 4)             # 1, 2, 3, 4
    """

    DEFAULT_OPTION_TYPES_VAR_NAME: ClassVar[str]        = "default_parameter_types"

    # ----------------------------------------------------------------------
    python_parameters: dict[str, str]
    python_type_values: dict[str, typer.models.OptionInfo]

    # ----------------------------------------------------------------------
    @classmethod
    def Create(
        cls,
        type_definitions: TypeDefinitionsType,
        option_types_var_name: str=DEFAULT_OPTION_TYPES_VAR_NAME,
    ) -> "DynamicPythonCode":
        parameters: dict[str, str] = {}
        types: dict[str, typer.models.OptionInfo] = {}

        for k, v in type_definitions.items():
            option_info: Optional[typer.models.OptionInfo] = None

            if isinstance(v, TypeDefinitionItem):
                python_type = v.python_type
                option_info = v.option_info

            elif isinstance(v, tuple):
                python_type, option_param = v

                if isinstance(option_param, dict):
                    option_info = typer.Option(None, **option_param)
                else:
                    option_info = option_param

            else:
                python_type = v
                option_info = typer.Option(None)

            python_type_name = str(python_type)

            if python_type_name.startswith("typing."):
                python_type_name = python_type_name[len("typing."):]
            elif isinstance(python_type, str):
                python_type_name = python_type
            else:
                python_type_name = python_type.__name__

            assert isinstance(option_info, typer.models.OptionInfo), option_info

            types[k] = option_info

            parameters[k] = '{name}: {python_type_name}={var_name}["{name}"]'.format(
                name=k,
                python_type_name=python_type_name,
                var_name=option_types_var_name,
            )

        return DynamicPythonCode(parameters, types)

    # ----------------------------------------------------------------------
    def GenerateFuncParameters(
        self,
        *,
        single_line: bool=False,
        indentation: int=4,
        skip_first_line: bool=True,
    ) -> str:
        if single_line:
            return ", ".join(parameter for parameter in self.python_parameters.values())

        return TextwrapEx.Indent(
            "\n".join("{},".format(parameter) for parameter in self.python_parameters.values()),
            indentation,
            skip_first_line=skip_first_line,
        )

    # ----------------------------------------------------------------------
    def GenerateFuncArguments(
        self,
        *,
        single_line: bool=False,
        as_dict_args: bool=False,
        as_kwargs: bool=False,
        indentation: int=4,
        skip_first_line: bool=True,
    ) -> str:
        if as_dict_args:
            decorate_parameter_func = lambda value: '"{value}": {value}'.format(value=value)
        elif as_kwargs:
            decorate_parameter_func = lambda value: "{value}={value}".format(value=value)
        else:
            decorate_parameter_func = lambda value: value

        if single_line:
            return ", ".join(decorate_parameter_func(parameter) for parameter in self.python_parameters.keys())

        return TextwrapEx.Indent(
            "\n".join("{},".format(decorate_parameter_func(parameter)) for parameter in self.python_parameters.keys()),
            indentation,
            skip_first_line=skip_first_line,
        )


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
def TyperDictArgument(
    default: Optional[Any],                 # None or ...
    type_definitions: TypeDefinitionsType,
    *,
    allow_any__: bool=False,                # Do not produce errors when key values are provided that are not defined in type_definitions
    **argument_info_kwargs,
) -> Any: # typer_models.ArgumentInfo
    """\
    Creates a typer.models.ArgumentInfo object that is able to process key-value-pairs provided
    on the command line as a string.

    Example:
        CODE:
            def FuncWithRequiredArgs(
                required_key_value_args: List[str] = TyperDictArgument(
                    ...,
                    dict(
                        one=str,
                        two=int,
                        three=List[int],
                        four=Optional[float],
                        five=(Optional[Path], dict(exists=True, resolve_path=True)),
                    ),
                ),
            ):
                required_dict = PostprocessDictArgument(required_key_value_args)

                print(required_dict)


        COMMAND LINE:
            FuncWithRequiredArgs one:1 two:2 three:3 three:33
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": None,
                    "five": None,
                }

            FuncWithRequiredArgs one:1 three:3 three: 33
                -> raises error, two is required

            FuncWithRequiredArgs one:1 two:2 three:3 three:33 four:1.2345 five:.
                -> {
                    "one": "1",
                    "two": 2,
                    "three": [3, 33],
                    "four": 1.2345,
                    "five": Path("<your working directory here>"),
                }
    """

    return _TyperImpl(
        typer_models.ArgumentInfo,
        default,
        type_definitions,
        allow_any__,
        None,
        argument_info_kwargs,
        assume_optional=False,
    )


# ----------------------------------------------------------------------
def TyperDictOption(
    default: Optional[Any],                 # None or ...
    type_definitions: TypeDefinitionsType,
    *option_info_args,
    allow_any__: bool=False,
    **option_info_kwargs,
) -> Any: # typer_models.OptionInfo
    """\
    Creates a typer.models.OptionInfo object that is able to process key-value-pairs provided
    on the command line as a string.

    See `TyperDictArgument` for examples usage.

    See the typer documentation for differences between Arguments and Options:
        https://typer.tiangolo.com/tutorial/first-steps/#what-is-a-cli-argument
    """

    return _TyperImpl(
        typer_models.OptionInfo,
        default,
        type_definitions,
        allow_any__,
        option_info_args,
        option_info_kwargs,
        assume_optional=True,
    )


# ----------------------------------------------------------------------
# TODO: Remove in next major version
def TypeDictOption(*args, **kwargs) -> Any:
    """\
    This method is deprecated and will be removed in the next major version;
    use `TyperDictOption` instead.
    """

    return TyperDictOption(*args, **kwargs)


# ----------------------------------------------------------------------
def PostprocessDictArgument(
    args: Optional[list[Any]],
) -> dict[str, Any]:
    """\
    Converts data that is plumbed through `TyperDictArgument` or `TyperDictOption` into
    a dictionary, as expected.

    This postprocessing step is necessary to ensure that the data (that doesn't look like
    what typer expects it to) makes it through the typer engine mechanics without losing
    anything along the way.

    This function is necessary because this solution is a hack.
    """

    if args is None:
        return {}

    assert len(args) == 1
    assert isinstance(args[0], dict)
    return args[0]


# ----------------------------------------------------------------------
def ProcessDynamicArgs(
    ctx: typer.Context,
    type_definitions: TypeDefinitionsType,
) -> dict[str, Any]:
    """\
    Process arguments dynamically added. This functionality is used when the
    types of some arguments are dynamically dependent upon the value if arguments
    that come before them or plugin architectures where the types of arguments is
    not known by base classes.

    Example:
        app = typer.Typer()

        @app.command(
            name="MyFunc",
            context_settings={"allow_extra_args": True, "ignore_unknown_options": True},
        )
        def MyFunc(
            ctx: typer.Context,
            arg1: int=typer.Argument(...),
            arg2: bool=typer.Option(False, "--arg2"),
        ) -> None:
            extra_args = TyperEx.ProcessDynamicArgs(
                ctx,
                {
                    "extra_arg1": (int, dict(min=10, max=100)),
                    "extra_arg2": str,
                    "extra_args3": (List[int], typer.Option(None, "--extra-arg3"))),
                }
            )
    """

    # Group the arguments
    arguments: list[Tuple[str, Optional[str]]] = []

    for arg in ctx.args:
        if arg.startswith("-"):
            arg = arg.lstrip("-")

            arguments.append((arg, None))
        else:
            # The value should be associated with a keyword encountered prior
            if not arguments or arguments[-1][-1] is not None:
                raise typer.BadParameter("Got unexpected extra argument ({})".format(arg))

            arguments[-1] = (arguments[-1][0], arg)

    # Invoke the dynamic functionality
    return ProcessArguments(
        type_definitions,
        arguments,
        assume_optional=True,
        ctx=ctx,
    )


# ----------------------------------------------------------------------
def ProcessArguments(
    type_definitions: TypeDefinitionsType,
    arguments: Iterable[Tuple[str, Optional[str]]],
    *,
    assume_optional: bool=False,
    ctx: Optional[typer.Context]=None,
) -> dict[str, Any]:
    """\
    Processes arguments dynamically. Use this method when you don't know what the type definitions
    are going to be before the script is invoked.
    """

    return _ProcessArgumentsImpl(
        _TypeDefinitionItemsToClickParams(
            ResolveTypeDefinitions(
                type_definitions,
                assume_optional=assume_optional,
            ),
        ),
        arguments,
        ctx=ctx,
    )


# ----------------------------------------------------------------------
def ResolveTypeDefinitions(
    type_definitions: TypeDefinitionsType,
    *,
    assume_optional: bool,
) -> dict[str, TypeDefinitionItem]:
    results: dict[str, TypeDefinitionItem] = {}

    for k, v in type_definitions.items():
        if isinstance(v, TypeDefinitionItem):
            # No conversion is necessary
            pass

        else:
            if isinstance(v, tuple):
                python_type, option_info_kwargs = v
            else:
                python_type = v
                option_info_kwargs = {}

            v = TypeDefinitionItem.Create(
                python_type,
                **cast(dict[str, Any], option_info_kwargs),
                assume_optional=assume_optional,
            )

        results[k] = v

    return results


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _ProcessArgumentsImpl(
    click_params: dict[str, Tuple[Any, Callable[..., Any]]],
    arguments: Iterable[Tuple[str, Optional[str]]],
    *,
    ctx: Optional[typer.Context],
    allow_unknown: bool=False,
) -> dict[str, Any]:
    # Create information to map from the argument keyword to the result name
    argument_to_result_names: dict[str, str] = {}

    for result_name, (click_param, _) in click_params.items():
        for opt in click_param.opts:
            assert opt.startswith("--"), opt
            opt = opt[2:]

            assert opt not in argument_to_result_names, opt
            argument_to_result_names[opt] = result_name

    results: dict[str, Any] = {}

    # Group the argument values
    for key, value in arguments:
        result_name = argument_to_result_names.get(key, None)
        if result_name is None:
            if not allow_unknown:
                raise typer.BadParameter(
                    "'{}' is not a valid key; {}.".format(
                        key,
                        "custom arguments are not supported"
                            if not click_params
                                else "valid keys are {}".format(
                                    ", ".join(
                                        "'{}'".format(name) for name in argument_to_result_names
                                    ),
                                )
                        ,
                    ),
                )

            result_name = key

        result_value = results.get(result_name, None)

        if result_value is not None:
            if isinstance(result_value, list):
                result_value.append(value)
            else:
                results[result_name] = [result_value, value]
        else:
            results[result_name] = value

    # Convert the values
    does_not_exist = object()

    for param_name, param_info in click_params.items():
        # For some reason, typer uses 2 different techniques to indicate that a type
        # is a list (one technique is used with Arguments, the other is used for Options).
        is_list = param_info[0].nargs == -1 or param_info[0].multiple

        param_results = results.get(param_name, does_not_exist)
        if param_results is does_not_exist:
            if param_info[0].default is None:
                param_results = [] if is_list else None
            else:
                results[param_name] = param_info[0].default

            continue

        if param_results is None:
            if isinstance(param_info[0].default, bool):
                param_results = not param_info[0].default
            else:
                raise typer.BadParameter("A value must be provided for '{}'.".format(param_name))

        if is_list:
            if not isinstance(param_results, list):
                param_results = [param_results, ]
        else:
            if isinstance(param_results, list):
                # Take the last value
                param_results = param_results[-1]

        param_results = param_info[0].process_value(ctx, param_results)

        if param_info[1] is not None:
            param_results = param_info[1](param_results)

        results[param_name] = param_results

    return results


# ----------------------------------------------------------------------
def _TypeDefinitionItemsToClickParams(
    type_definitions: dict[str, TypeDefinitionItem],
) -> dict[str, Tuple[Any, Callable[..., Any]]]:
    return {
        k: typer_main.get_click_param(
            typer_models.ParamMeta(
                name=k,
                default=v.option_info,
                annotation=v.python_type,
            ),
        )
        for k, v in type_definitions.items()
    }


# ----------------------------------------------------------------------
_TyperT                                     = TypeVar("_TyperT", typer_models.ArgumentInfo, typer_models.OptionInfo)

def _TyperImpl(
    typer_type: Type[_TyperT],
    default: Optional[Any],
    type_definitions: TypeDefinitionsType,
    allow_unknown: bool,
    args: Optional[Tuple[str, ...]],
    kwargs: dict[str, Any],
    *,
    assume_optional: bool,
) -> _TyperT:
    assert default is None or default is Ellipsis, default

    click_params = _TypeDefinitionItemsToClickParams(
        ResolveTypeDefinitions(
            type_definitions,
            assume_optional=assume_optional,
        ),
    )

    # Prepare the result
    original_callback = kwargs.pop("callback", None)

    # ----------------------------------------------------------------------
    def Callback(
        ctx: typer.Context,
        param: typer.CallbackParam,
        values: list[str],
    ) -> list[dict[str, Any]]:
        regex = re.compile(
            r"""(?#
            Start of Line                   )^(?#
            Key                             )(?P<key>(?:\\[:=]|[^:=])+)(?#
            Optional Value Begin            )(?:(?#
                Sep                         )\s*[:=]\s*(?#
                Value                       )(?P<value>.+)(?#
            Optional Value End              ))?(?#
            End of Line                     )$(?#
            )""",
        )

        arguments: list[Tuple[str, Optional[str]]] = []

        for value in values:
            match = regex.match(value)
            if not match:
                raise typer.BadParameter(
                    "'{}' is not a valid dictionary parameter; expected '<key>:<value>'.".format(
                        value,
                    ),
                )

            key = match.group("key").replace("\\:", ":").replace("\\=", "=")
            value = (match.group("value") or "").replace("\\:", ":").replace("\\=", "=")

            arguments.append((key, value))

        results = _ProcessArgumentsImpl(
            click_params,
            arguments,
            ctx=ctx,
            allow_unknown=allow_unknown,
        )

        # Invoke the original callback
        if original_callback:
            results = original_callback(ctx, param, results)

        # Convert the results to a list to make it through the typer plumbing
        # unchanged (since the original type was decorated as a list)
        return [results, ]

    # ----------------------------------------------------------------------

    return typer_type(
        **{
            **kwargs,
            **dict(
                default=default,
                callback=Callback,
                param_decls=args,
            ),
        },
    )
