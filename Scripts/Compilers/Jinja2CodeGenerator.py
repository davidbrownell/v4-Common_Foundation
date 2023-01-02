# ----------------------------------------------------------------------
# |
# |  Jinja2CodeGenerator.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-05 12:02:43
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Compiles Jinja2 template files."""

import os
import textwrap
import uuid

from pathlib import Path
from typing import Any, Callable, Dict, Generator, List as ListType, Optional, Sequence, Tuple, Union

import typer

from jinja2 import Environment, exceptions, FileSystemLoader, StrictUndefined, Undefined
from jinja2.defaults import BLOCK_START_STRING, BLOCK_END_STRING, COMMENT_START_STRING, COMMENT_END_STRING, VARIABLE_START_STRING, VARIABLE_END_STRING

from typer.core import TyperGroup

from Common_Foundation import PathEx
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation.Types import overridemethod

from Common_FoundationEx.CompilerImpl.CodeGenerator import CodeGenerator as CodeGeneratorBase, CreateCleanCommandLineFunc, CreateGenerateCommandLineFunc, CreateListCommandLineFunc, InputType, InvokeReason
from Common_FoundationEx.CompilerImpl.Mixins.InputProcessorMixins.AtomicInputProcessorMixin import AtomicInputProcessorMixin
from Common_FoundationEx.CompilerImpl.Mixins.OutputProcessorMixins.MultipleOutputProcessorMixin import MultipleOutputProcessorMixin

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
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
# |
# |  Public Types
# |
# ----------------------------------------------------------------------
class CodeGenerator(
    AtomicInputProcessorMixin,
    MultipleOutputProcessorMixin,
    CodeGeneratorBase,
):
    """Compiles Jinja2 template files"""

    # ----------------------------------------------------------------------
    def __init__(self):
        CodeGeneratorBase.__init__(
            self,
            self,
            self,
            "Jinja2",
            "Compiles Jinja2 template files.",
            InputType.Files,
            can_execute_in_parallel=True,
        )

        AtomicInputProcessorMixin.__init__(self)
        MultipleOutputProcessorMixin.__init__(self, self)

    # ----------------------------------------------------------------------
    @overridemethod
    def GetCustomCommandLineArgs(self) -> TyperEx.TypeDefinitionsType:
        default_metadata: Dict[str, Any] = {
            k: v
            for k, v in self._EnumerateOptionalMetadata()
        }

        # Ensure that these bool values are the expected values, as the flag names will
        # need to change if the default values change.
        assert default_metadata["force"] is False
        assert default_metadata["preserve_dir_structure"] is True
        assert default_metadata["trim_blocks"] is True
        assert default_metadata["lstrip_blocks"] is True
        assert default_metadata["keep_trailing_newline"] is True

        return {
            "output_data_filename_prefix": (str, typer.Option(None, "--output-data-filename-prefix")),

            "code_gen_header_line_prefix": (str, typer.Option(None, "--code-gen-header-line-prefix", help="Prefix to use for a code generation header added to the template indicating that the file was generated; this prefix will most often be a comment character specific to the generated file type.")),
            "code_gen_header_input_filename": (str, typer.Option(None, "--code-gen-header-input-filename", help="Filename to use in a generated header (if any).")),

            "list_variables": (bool, typer.Option(default_metadata["list_variables"], "--list-variables", help="Lists all variables in the Jinja2 templates.")),
            "force": (bool, typer.Option(default_metadata["force"], "--force", help="Force the generation of content, even when no changes are detected.")),
            "ignore_errors": (bool, typer.Option(default_metadata["ignore_errors"], "--ignore-errors", help="Continue even when errors are encountered.")),
            "jinja2_context": (
                ListType[str],
                TyperEx.TypeDictOption(None, {}, "--jinja2-context", allow_any__=True, help="Additional information to pass to the Jinja2 code generator."),
            ),
            "preserve_dir_structure": (bool, typer.Option(default_metadata["preserve_dir_structure"], "--no-preserve-dir-structure", help="Output all files to the output directory, rather than creating a hierarchy based on the input files encountered.")),

            "variable_start": (str, typer.Option(default_metadata["variable_start"])),
            "variable_end": (str, typer.Option(default_metadata["variable_end"])),

            "block_start": (str, typer.Option(default_metadata["block_start"])),
            "block_end": (str, typer.Option(default_metadata["block_end"])),

            "comment_start": (str, typer.Option(default_metadata["comment_start"])),
            "comment_end": (str, typer.Option(default_metadata["comment_end"])),

            "trim_blocks": (bool, typer.Option(default_metadata["trim_blocks"], "--no-trim-blocks")),
            "lstrip_blocks": (bool, typer.Option(default_metadata["lstrip_blocks"], "--no-lstrip-blocks")),
            "keep_trailing_newline": (bool, typer.Option(default_metadata["keep_trailing_newline"], "--no-keep-trailing-newlines")),
        }

    # ----------------------------------------------------------------------
    @overridemethod
    def IsSupported(
        self,
        filename_or_directory: Path,        # filename if self.input_type == InputType.Files, directory if self.input_type == InputType.Directories
    ) -> bool:
        return (
            filename_or_directory.is_file()
            and (
                filename_or_directory.suffix.lower().startswith(".jinja2")
                or filename_or_directory.stem.lower().endswith(".jinja2")
            )
        )

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    @overridemethod
    def _EnumerateOptionalMetadata(self) -> Generator[Tuple[str, Any], None, None]:
        yield "code_gen_header_line_prefix", None
        yield "code_gen_header_input_filename", None

        yield "list_variables", False
        yield "ignore_errors", False
        yield "jinja2_context", {}
        yield "preserve_dir_structure", True

        yield "variable_start", VARIABLE_START_STRING
        yield "variable_end", VARIABLE_END_STRING

        yield "block_start", BLOCK_START_STRING
        yield "block_end", BLOCK_END_STRING

        yield "comment_start", COMMENT_START_STRING
        yield "comment_end", COMMENT_END_STRING

        yield "trim_blocks", True
        yield "lstrip_blocks", True
        yield "keep_trailing_newline", True

        yield from super(CodeGenerator, self)._EnumerateOptionalMetadata()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredMetadataNames(self) -> ListType[str]:
        return super(CodeGenerator, self)._GetRequiredMetadataNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetRequiredContextNames(self) -> ListType[str]:
        return super(CodeGenerator, self)._GetRequiredContextNames()

    # ----------------------------------------------------------------------
    @overridemethod
    def _CreateContext(
        self,
        dm: DoneManager,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Process jinja2_context
        if isinstance(metadata["jinja2_context"], list):
            metadata["jinja2_context"] = TyperEx.PostprocessDictArgument(metadata["jinja2_context"])

        # Convert the input filename into output filenames
        preserve_dir_structure = metadata.pop("preserve_dir_structure")

        output_dir = metadata["output_dir"]

        if preserve_dir_structure:
            output_filenames: ListType[Path] = []

            if len(metadata[AtomicInputProcessorMixin.ATTRIBUTE_NAME]) == 1:
                output_filenames.append(output_dir / metadata[AtomicInputProcessorMixin.ATTRIBUTE_NAME][0].name)
            else:
                input_root = metadata[AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME]
                input_root_parts_len = len(input_root.parts)

                for input_filename in metadata[AtomicInputProcessorMixin.ATTRIBUTE_NAME]:
                    output_filenames.append(output_dir / Path(*input_filename.parts[input_root_parts_len:]))

        else:
            output_filenames_lookup: Dict[
                Path,                       # output_filename
                Path,                       # input_filename
            ] = {}

            for input_filename in metadata[AtomicInputProcessorMixin.ATTRIBUTE_NAME]:
                output_filename = output_dir / input_filename.name

                existing_input_filename = output_filenames_lookup.get(output_filename, None)

                if existing_input_filename is not None:
                    raise Exception(
                        "The output file '{}' to be generated from the input file '{}' will be overwritten by the output file generated from the input file '{}'.".format(
                            output_filename,
                            existing_input_filename,
                            input_filename,
                        ),
                    )

                output_filenames_lookup[output_filename] = input_filename

            output_filenames = list(output_filenames_lookup.keys())

        # ----------------------------------------------------------------------
        def ConvertOutputFilename(
            value: Path,
        ) -> Path:
            if value.suffix.lower() == ".jinja2":
                name = value.stem
            elif value.stem.lower().endswith(".jinja2"):
                name = "{}{}".format(value.stem[:-(len(".jinja") + 1)], value.suffix)
            else:
                name = value.name

            return value.parent / name

        # ----------------------------------------------------------------------

        metadata[MultipleOutputProcessorMixin.ATTRIBUTE_NAME] = [
            ConvertOutputFilename(output_filename)
            for output_filename in output_filenames
        ]

        return super(CodeGenerator, self)._CreateContext(dm, metadata)

    # ----------------------------------------------------------------------
    @overridemethod
    def _GetNumStepsImpl(
        self,
        context: Dict[str, Any],
    ) -> int:
        return len(context[MultipleOutputProcessorMixin.ATTRIBUTE_NAME])

    # ----------------------------------------------------------------------
    @overridemethod
    def _InvokeImpl(
        self,
        invoke_reason: InvokeReason,        # pylint: disable=unused-argument
        dm: DoneManager,
        context: Dict[str, Any],
        on_progress_func: Callable[
            [
                int,                        # Step (0-based)
                str,                        # Status
            ],
            bool,                           # True to continue, false to terminate
        ],
    ) -> Optional[str]:                     # Optional short description that provides input about the result
        # ----------------------------------------------------------------------
        class RelativeFileSystemLoader(FileSystemLoader):
            # ----------------------------------------------------------------------
            def __init__(
                self,
                input_filename: Path,
                searchpath: Union[str, Path, Sequence[Union[str, Path]]],
                *args,
                **kwargs,
            ):
                super(RelativeFileSystemLoader, self).__init__(
                    searchpath=[input_filename.parent] + (searchpath if isinstance(searchpath, list) else []),
                    *args,
                    **kwargs,
                )

            # ----------------------------------------------------------------------
            def get_source(
                self,
                environment: Environment,
                template: str,
            ) -> Tuple[str, str, Callable[[], bool]]:
                method = super(RelativeFileSystemLoader, self).get_source

                try:
                    return method(environment, template)

                except exceptions.TemplateNotFound:
                    for searchpath in reversed(self.searchpath):
                        potential_template = Path(searchpath) / template
                        if potential_template.is_file():
                            self.searchpath.append(str(potential_template.parent.resolve()))

                            return method(environment, potential_template.name)

                    raise

        # ----------------------------------------------------------------------

        standard_env_args = {
            "variable_start_string": context["variable_start"],
            "variable_end_string": context["variable_end"],
            "block_start_string": context["block_start"],
            "block_end_string": context["block_end"],
            "comment_start_string": context["comment_start"],
            "comment_end_string": context["comment_end"],
            "trim_blocks": context["trim_blocks"],
            "lstrip_blocks": context["lstrip_blocks"],
            "keep_trailing_newline": context["keep_trailing_newline"],
            "undefined": Undefined if context["ignore_errors"] else StrictUndefined,
        }

        input_root = context[AtomicInputProcessorMixin.INPUT_ROOT_ATTRIBUTE_NAME]
        input_root_parts_len = len(input_root.parts)

        for index, (input_filename, output_filename) in enumerate(
            zip(
                context[AtomicInputProcessorMixin.ATTRIBUTE_NAME],
                context[MultipleOutputProcessorMixin.ATTRIBUTE_NAME],
            ),
        ):
            with dm.Nested(
                "Processing '{}' ({} of {})...".format(
                    input_filename,
                    index + 1,
                    len(context[AtomicInputProcessorMixin.ATTRIBUTE_NAME]),
                ),
            ) as this_dm:
                on_progress_func(index, str(Path(*input_filename.parts[input_root_parts_len:])))

                env = Environment(
                    **{
                        **standard_env_args,
                        **{
                            "loader": RelativeFileSystemLoader(input_filename, Path.cwd()),
                        }
                    },
                )

                if context["list_variables"]:
                    from jinja2 import meta

                    with open(input_filename) as f:
                        content = env.parse(f.read())

                    this_dm.WriteInfo(
                        textwrap.dedent(
                            """\
                            Variables:
                            {}
                            """,
                        ).format(
                            "\n".join("    - {}".format(var) for var in meta.find_undeclared_variables(content)),
                        ),
                    )

                    continue

                env.tests["valid_file"] = lambda value: (input_filename.parent / value).is_file()

                env.filters["doubleslash"] = lambda value: value.replace("\\", "\\\\")
                env.filters["env"] = lambda value: os.getenv(value)
                env.filters["format_and_reduce"] = lambda items, template, join_str: join_str.join(template.format(item) for item in items)

                # ----------------------------------------------------------------------
                cached_guids: Dict[str, str] = {}

                def CreateGuid(
                    identifier: Optional[str]=None,
                ) -> str:
                    guid = cached_guids.get(identifier, None) if identifier is not None else None
                    if guid is None:
                        guid = str(uuid.uuid4()).lower()

                        if identifier is not None:
                            cached_guids[identifier] = guid

                    return guid

                # ----------------------------------------------------------------------

                env.globals["guid"] = CreateGuid

                try:
                    with input_filename.open() as f:
                        template_content = f.read()

                    if context["code_gen_header_line_prefix"]:
                        template_content = textwrap.dedent(
                            """\
                            {line_prefix} ----------------------------------------------------------------------
                            {line_prefix} ----------------------------------------------------------------------
                            {line_prefix} ----------------------------------------------------------------------
                            {line_prefix}
                            {line_prefix} This file is the result of a code generation process; any changes made
                            {line_prefix} to this file will be overwritten during the next code generation
                            {line_prefix} invocation. Any changes MUST be made in the source file rather than in
                            {line_prefix} this one.
                            {line_prefix}
                            {line_prefix}     Code Generator:         {name}
                            {line_prefix}     Input Filename:         {input}
                            {line_prefix}
                            {line_prefix} ----------------------------------------------------------------------
                            {line_prefix} ----------------------------------------------------------------------
                            {line_prefix} ----------------------------------------------------------------------

                            {template_content}
                            """,
                        ).format(
                            line_prefix=context["code_gen_header_line_prefix"],
                            name=self.name,
                            input=(
                                context["code_gen_header_input_filename"]
                                or PathEx.CreateRelativePath(context["input_root"], input_filename).as_posix()
                            ),
                            template_content=template_content.rstrip(),
                        )

                    template = env.from_string(template_content)

                    content = template.render(**context["jinja2_context"])
                except Exception as ex:
                    this_dm.WriteError(str(ex))
                    continue

                output_filename.parent.mkdir(parents=True, exist_ok=True)

                with output_filename.open("w") as f:
                    f.write(content)


# ----------------------------------------------------------------------
# |
# |  Public Functions
# |
# ----------------------------------------------------------------------
_code_generator                             = CodeGenerator()

Compile                                     = CreateGenerateCommandLineFunc(app, _code_generator)
Clean                                       = CreateCleanCommandLineFunc(app, _code_generator)
List                                        = CreateListCommandLineFunc(app, _code_generator)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
