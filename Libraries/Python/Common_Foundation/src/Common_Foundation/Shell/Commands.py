# ----------------------------------------------------------------------
# |
# |  Commands.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-08 14:29:09
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains generic Commands decorated for each Shell"""

from dataclasses import dataclass, field, InitVar
from pathlib import Path
from typing import Generator, List, Optional, Union

# pylint: disable=missing-class-docstring


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Command(object):
    pass


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Comment(Command):
    value: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Message(Command):
    value: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Call(Command):
    """Calls a script file, where environment changes are persisted in the calling environment"""

    command_line: str
    exit_on_error: bool                     = field(default=True)
    exit_via_return_statement: bool         = field(default=False, kw_only=True)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert not self.exit_via_return_statement or self.exit_on_error


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Execute(Command):
    """Calls an executable file, where environment changes are not persisted in the calling environment"""

    command_line: str
    exit_on_error: bool                     = field(default=True)
    exit_via_return_statement: bool         = field(default=False, kw_only=True)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert not self.exit_via_return_statement or self.exit_on_error


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class SymbolicLink(Command):
    link_filename: Path
    target: Path
    remove_existing: bool                   = field(default=True)
    relative_path: bool                     = field(default=True)

    is_dir_param: InitVar[Optional[bool]]   = None
    is_dir: bool                            = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self, is_dir_param):
        if is_dir_param is None:
            is_dir_param = self.target.is_dir()

        object.__setattr__(self, "is_dir", is_dir_param)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Set(Command):
    """Sets an environment variable, overwriting any existing value"""

    name: str
    value_or_values: Union[None, str, List[str]]

    # ----------------------------------------------------------------------
    def EnumValues(self) -> Generator[str, None, None]:
        if self.value_or_values is None:
            pass
        elif isinstance(self.value_or_values, str):
            yield self.value_or_values
        else:
            yield from self.value_or_values


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Augment(Command):
    """Updates an environment variable with the provided values"""

    name: str
    value_or_values: Union[str, List[str]]
    is_space_delimited_string: bool         = field(default=False)
    append_values: bool                     = field(default=False)

    # If True, visitors will generate code that looks at the values in memory at code-generation
    # time to determine what should be added. If False, the generated code will look at the
    # content at runtime to determine what should be added.
    simple_format: bool                     = field(default=False)

    # ----------------------------------------------------------------------
    def EnumValues(self) -> Generator[str, None, None]:
        if not isinstance(self.value_or_values, list):
            yield self.value_or_values
        else:
            yield from self.value_or_values


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class SetPath(Set):
    # ----------------------------------------------------------------------
    @classmethod
    def Create(cls, *args, **kwargs):
        return cls("PATH", *args, **kwargs)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class AugmentPath(Augment):
    # ----------------------------------------------------------------------
    @classmethod
    def Create(cls, *args, **kwargs):
        return cls("PATH", *args, **kwargs)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Exit(Command):
    pause_on_success: bool                  = field(default=False, kw_only=True)
    pause_on_error: bool                    = field(default=False, kw_only=True)
    return_code: Optional[int]              = field(default=None, kw_only=True)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class ExitOnError(Command):
    """Exits a script if an error was generated when executing the previous command"""

    variable_name: Optional[str]            = field(default=None)
    return_code: Optional[int]              = field(default=None)
    use_return_statement: Optional[bool]    = field(default=False, kw_only=True)

    # ----------------------------------------------------------------------
    def __post_init__(self):
        assert (
            (self.variable_name is None and self.return_code is None)
            or (self.variable_name is not None and self.return_code is None)
            or (self.variable_name is None and self.return_code is not None)
        ), (self.variable_name, self.return_code)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EchoOff(Command):
    pass


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class CommandPrompt(Command):
    prompt: str
    is_prefix: bool                         = field(kw_only=True, default=True)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Delete(Command):
    path: Path

    is_dir_param: InitVar[Optional[bool]]   = None
    is_dir: bool                            = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self, is_dir_param):
        if is_dir_param is None:
            is_dir_param = self.path.is_dir()

        object.__setattr__(self, "is_dir", is_dir_param)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Copy(Command):
    source: Path
    dest: Path

    is_dir_param: InitVar[Optional[bool]]   = None
    is_dir: bool                            = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self, is_dir_param):
        if is_dir_param is None:
            is_dir_param = self.source.is_dir()

        object.__setattr__(self, "is_dir", is_dir_param)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Move(Command):
    source: Path
    dest: Path

    is_dir_param: InitVar[Optional[bool]]   = None
    is_dir: bool                            = field(init=False)

    # ----------------------------------------------------------------------
    def __post_init__(self, is_dir_param):
        if is_dir_param is None:
            is_dir_param = self.source.is_dir()

        object.__setattr__(self, "is_dir", is_dir_param)


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PersistError(Command):
    """Persists the current error value"""

    variable_name: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PushDirectory(Command):
    value: Optional[Path]


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class PopDirectory(Command):
    pass


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Raw(Command):
    """Raw, shell-specific content that isn't altered during decoration"""
    value: str


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class WindowTitle(Command):
    """Window title for the terminal session"""
    value: str
