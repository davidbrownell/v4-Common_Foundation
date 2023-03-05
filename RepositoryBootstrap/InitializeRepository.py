# ----------------------------------------------------------------------
# |
# |  InitializeRepository.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 21:30:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022-23
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Interactive script used to initialize a new repository"""

import os
import shutil
import sys
import textwrap
import types
import uuid

from enum import auto, Enum
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import typer

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation import PathEx
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import SubprocessEx
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect

sys.path.insert(0, str(Path(__file__).parent))
with ExitStack(lambda: sys.path.pop(0)):
    import Constants  # pylint: disable=import-error


# ----------------------------------------------------------------------
class ReadmeFormat(Enum):
    Markdown                                = auto()
    Rst                                     = auto()


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Configuration(object):
    root: Path
    friendly_name: str

    readme_format: Optional[ReadmeFormat]
    developer_readme_format: Optional[ReadmeFormat]

    support_git: bool                       = field(kw_only=True)
    support_hg: bool                        = field(kw_only=True)
    support_windows: bool                   = field(kw_only=True)
    support_linux: bool                     = field(kw_only=True)

    include_boost_license: bool             = field(kw_only=True)
    include_bootstrap: bool                 = field(kw_only=True)
    include_scm_hook: bool                  = field(kw_only=True)
    include_pyright_config: bool            = field(kw_only=True)

    include_github_workflows: bool          = field(kw_only=True)


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)

# ----------------------------------------------------------------------
@app.command("EntryPoint", no_args_is_help=False)
def EntryPoint(
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        # Repo dir
        repo_dir = Path(
            _Prompt(
                textwrap.dedent(
                    """\

                    Enter the destination repository directory (this directory should exist
                    and be initialized with your preferred source control management system)
                    """,
                ),
                os.getcwd(),
            ),
        ).resolve()

        if not repo_dir.is_dir():
            raise Exception("The directory '{}' does not exist.".format(repo_dir))

        dm.WriteLine("")

        friendly_name = _Prompt("Enter the friendly name of this repository: ", repo_dir.name)

        # Files to copy
        dm.WriteLine(
            textwrap.dedent(
                """\

                **********************************************************************
                Answers to the following questions will be used to copy template files
                to '{}'.

                The contents of the generated template files will not be modified by
                this process.
                **********************************************************************

                """,
            ).format(repo_dir),
        )

        support_git = _Prompt("Include '.gitignore' for Git support? ", "yes").lower() in ["yes", "y"]
        support_hg = _Prompt("Include '.hgignore' for Mercurial support? ", "no").lower() in ["yes", "y"]
        dm.WriteLine("")

        support_windows = _Prompt("Support development on Windows? ", "yes").lower() in ["yes", "y"]
        support_linux = _Prompt("Support development on Linux? ", "yes").lower() in ["yes", "y"]
        include_bootstrap = _Prompt("Include bootstrap scripts for automated environment setup? ", "yes").lower() in ["yes", "y"]
        dm.WriteLine("")

        include_boost_license = _Prompt("Include the Boost Software License? ", "no").lower() in ["yes", "y"]
        include_scm_hook = _Prompt("Include source control commit hooks? ", "no").lower() in ["yes", "y"]
        include_pyright_config = _Prompt("Include 'pyrightconfig.json' to limit the scope of pylint scanning? ", "no").lower() in ["yes", "y"]
        dm.WriteLine("")

        readmes = types.SimpleNamespace(
            standard=None,
            developer=None,
        )

        for attribute_name, desc in [
            ("standard", ""),
            ("developer", "Developer "),
        ]:
            doc_format = _Prompt(
                "{}Readme format (Markdown, None, Rst)? ".format(desc),
                "Markdown",
                lambda value: value.lower() in ["markdown", "none", "rst"],
            ).lower()

            if doc_format == "none":
                doc_format = None
            elif doc_format == "markdown":
                doc_format = ReadmeFormat.Markdown
            elif doc_format == "rst":
                doc_format = ReadmeFormat.Rst
            else:
                assert False, doc_format  # pragma: no cover

            setattr(readmes, attribute_name, doc_format)

        dm.WriteLine("")

        include_github_workflows = False

        if _Prompt("With this repository be hosted on Github? ", "yes").lower() in ["yes", "y"]:
            include_github_workflows = _Prompt("Include Github Continuous Integration workflows? ", "yes").lower() in ["yes", "y"]

            if include_github_workflows:
                if not support_git:
                    dm.WriteInfo("Git support is required by Github workflows and will be added.\n")
                    support_git = True

                if not include_bootstrap:
                    dm.WriteInfo("Bootstrap files are required by Github workflows and will be added.\n")
                    include_bootstrap = True

        return Execute(
            dm,
            Configuration(
                repo_dir,
                friendly_name,
                readmes.standard,
                readmes.developer,
                support_git=support_git,
                support_hg=support_hg,
                support_windows=support_windows,
                support_linux=support_linux,
                include_boost_license=include_boost_license,
                include_bootstrap=include_bootstrap,
                include_scm_hook=include_scm_hook,
                include_pyright_config=include_pyright_config,
                include_github_workflows=include_github_workflows,
            ),
        )


# ----------------------------------------------------------------------
def Execute(
    dm: DoneManager,
    config: Configuration,
) -> None:
    template_path = Path(__file__).parent / "Templates"

    # Get a list of files to copy and todo actions
    files_to_copy: List[str] = [
        "Setup_custom.py",
        "Activate_custom.py",
    ]

    actions: List[str] = [
        textwrap.dedent(
            """\
            "{}"

            Edit this file and add dependencies and any custom setup actions (if necessary). The template copied
            is designed to raise exceptions when these methods are first invoked to ensure that they are customized.
            Remove these exceptions once you have configured all setup activities.
            """,
        ).format(str(config.root / files_to_copy[0])),
        textwrap.dedent(
            """\
            "{}"

            Edit this file and add any custom activation actions (if necessary). The template copied is designed to
            raise exceptions when these methods are first invoked to ensure that they are customized. Remove these
            exceptions once you have configured all activation activities.
            """,
        ).format(str(config.root / files_to_copy[1])),
    ]

    if config.support_git:
        files_to_copy += [
            ".gitignore",
        ]

    if config.support_hg:
        files_to_copy += [
            ".hgignore",
        ]

    if not config.support_windows and not config.support_linux:
        raise Exception("Windows and/or Linux must be supported.")

    if config.support_windows:
        files_to_copy += [
            "Setup.cmd",
        ]

    if config.support_linux:
        files_to_copy += [
            "Setup.sh",
        ]

    if config.include_boost_license:
        files_to_copy.append("LICENSE_1_0.txt")

    if config.include_bootstrap:
        if config.support_windows:
            files_to_copy.append("Bootstrap.cmd")
        if config.support_linux:
            files_to_copy.append("Bootstrap.sh")

    if config.include_scm_hook:
        files_to_copy.append("ScmHook_custom.py")

        actions.append(
            textwrap.dedent(
                """\
                "{}"

                Edit this file and add any custom Commit, Push, or Pull validations event. The template copied is designed to
                raise exceptions when these methods are first invoked to ensure that they are customized. Remove these
                exceptions once you have implemented all the hooks.
                """,
            ).format(
                str(config.root / files_to_copy[-1]),
            ),
        )

    if config.include_pyright_config:
        files_to_copy.append("pyrightconfig.json")

    for stem, doc_format in [
        ("README", config.readme_format),
        ("DEVELOPMENT", config.developer_readme_format),
    ]:
        if doc_format is None:
            continue

        if doc_format == ReadmeFormat.Markdown:
            files_to_copy.append("{}.md".format(stem))
        elif doc_format == ReadmeFormat.Rst:
            files_to_copy.append("{}.rst".format(stem))
        else:
            assert False, doc_format

        actions.append(
            textwrap.dedent(
                """\
                "{}"

                Edit the contents of this file.
                """,
            ).format(
                str(config.root / files_to_copy[-1]),
            ),
        )

    dm.WriteLine("")

    with dm.Nested(
        "Copying {}...".format(inflect.no("file", len(files_to_copy))),
        suffix="\n",
    ):
        for file_to_copy in files_to_copy:
            source = template_path / file_to_copy
            dest = config.root / file_to_copy

            if dest.is_file():
                continue

            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(dest))

        # Create the repo id
        dest_filename = config.root / Constants.REPOSITORY_ID_FILENAME

        with dest_filename.open("w") as f:
            f.write(
                Constants.REPOSITORY_ID_CONTENT_TEMPLATE.format(
                    name=config.friendly_name,
                    id=str(uuid.uuid4()),
                ),
            )

    post_commit_messages: list[str] = [
        textwrap.dedent(
            """\
            ...creating a tag (git) / branch (hg) named:

            "main_stable"
            """,
        ),
    ]

    if config.include_github_workflows:
        github_workflow_result = _InitGithubWorkflows(dm, config)

        if dm.result != 0:
            return

        assert github_workflow_result is not None

        actions += github_workflow_result.actions
        post_commit_messages += github_workflow_result.post_commit_messages

    actions.append(
        textwrap.dedent(
            """\
            After making these changes, consider...

            a) ...adding execution permissions for all .sh files:

               `chmod a+x *.sh`

            b) ...applying copyright notices to generated files (as needed).

            c) ...committing using the message:

               "🎉 [started_project] Initial project scaffolding."
            """,
        ),
    )

    actions.append(
        textwrap.dedent(
            """\
            After that initial commit, consider...

            {}

            """,
        ).format(
            "".join(
                "{}) {}\n\n".format(
                    chr(ord("a") + message_index),
                    TextwrapEx.Indent(
                        message.rstrip(),
                        len("{}) ".format(chr(ord("a") + message_index))),
                        skip_first_line=True,
                    ),
                )
                for message_index, message in enumerate(post_commit_messages)
            ),
        ),
    )

    dm.WriteLine(
        textwrap.dedent(
            """\


            **********************************************************************
            Repository information has been created at: "{repo_dir}"

            To begin using this repository...

            {steps}

            **********************************************************************
            """,
        ).format(
            repo_dir=config.root,
            steps=TextwrapEx.Indent(
                "\n".join(
                    "{}) {}".format(
                        action_index + 1,
                        TextwrapEx.Indent(
                            action,
                            len("{}) ".format(action_index + 1)),
                            skip_first_line=True,
                        ),
                    )
                    for action_index, action in enumerate(actions)
                ).rstrip(),
                4,
            ),
        ),
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _Prompt(
    prompt: str,
    default_value: Optional[str]=None,
    is_valid_func: Optional[Callable[[str], bool]]=None,
) -> str:
    if default_value is not None:
        prompt += "[{}] ".format(default_value)

    while True:
        result = input(prompt).strip()
        if not result and default_value is not None:
            result = default_value

        if (
            result
            and (
                not is_valid_func or is_valid_func(result)
            )
        ):
            return result


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class _InitGithubWorkflowsResult(object):
    actions: list[str]
    post_commit_messages: list[str]


def _InitGithubWorkflows(
    dm: DoneManager,
    config: Configuration,
) -> Optional[_InitGithubWorkflowsResult]:

    dm.WriteLine("")

    git_username = _Prompt("What is the github username or organization that will host this repository? ")
    repo_name = _Prompt("What is the repository name? ", config.friendly_name)
    dm.WriteLine("")

    is_mixin_repository = _Prompt("Is this repository a mixin repository (answer 'no' unless you are absolutely certain that it is)? ", "no").lower() in ["yes", "y"]

    repo_url = "https://github.com/{git_username}/{repo_name}".format(
        git_username=git_username,
        repo_name=repo_name,
    )

    dm.WriteLine("")

    with dm.Nested("Generating GitHub workflows...") as this_dm:
        template_dir = Path(__file__).parent / "Templates" / "github_workflows"
        assert template_dir.is_dir(), template_dir

        # We are invoking the code generator from the command line rather than using the code
        # generator instance calculated in `GetNumBuildSteps` to encapsulate the surprisingly
        # subtle logic associated with how a `CodeGenerator` coverts metadata to context.
        command_line_flags: List[str] = [
            "--variable-start", '"<<<"',
            "--variable-end", '">>>"',
            "--block-start", '"<<%"',
            "--block-end", '"%>>"',
            "--comment-start", '"<<#"',
            "--comment-end", '"#>>"',
            "--jinja2-context", '"git_username:{}"'.format(git_username),
            "--jinja2-context", '"git_repo:{}"'.format(repo_name),
            "--jinja2-context", '"friendly_repo_name:{}"'.format(config.friendly_name),
            "--jinja2-context", '"is_mixin_repository:{}"'.format(str(is_mixin_repository).lower()),
            "--single-task",
        ]

        command_line = 'Jinja2CodeGenerator{script_extension} Generate "{input_dir}" "{output_dir}" {flags}'.format(
            script_extension=CurrentShell.script_extensions[0],
            input_dir=template_dir,
            output_dir=config.root,
            flags=" ".join(command_line_flags),
        )

        this_dm.WriteVerbose("Command Line: {}\n\n".format(command_line))

        result = SubprocessEx.Run(command_line)

        this_dm.result = result.returncode

        if this_dm.result != 0:
            this_dm.WriteError(result.output)
            return None

        with this_dm.YieldVerboseStream() as stream:
            stream.write(result.output)

        # Remove the conditional compilation file
        for item in config.root.iterdir():
            if item.is_file() and item.suffix == ".data" and item.stem.endswith(".ConditionalInvocationQueryMixin"):
                item.unlink()
                break

    return _InitGithubWorkflowsResult(
        [
            textwrap.dedent(
                """\
                "{event_on_pr}"
                "{validate}"
                "{validate_with_dependencies}"

                Customize these files based on the instructions in each one.
                """,
            ).format(
                event_on_pr=PathEx.EnsureFile(config.root / ".github" / "workflows" / "event_on_pr.yaml"),
                validate_with_dependencies=PathEx.EnsureFile(config.root / ".github" / "workflows" / "validate_with_dependencies.yaml"),
                validate=PathEx.EnsureFile(config.root / ".github" / "workflows" / "validate.yaml"),

            ),
        ],
        [
            textwrap.dedent(
                """\
                ...updating the CI tags:

                'python {create_ci_tags}'

                After committing these changes, run this script to create tags and push them to GitHub. The generated
                GitHub workflows rely on these tags to function properly and will fail until they are created.
                """,
            ).format(
                create_ci_tags=PathEx.EnsureFile(config.root / ".github" / "CreateCITags.py"),
            ),
            textwrap.dedent(
                """\
                ...adding a CodeQL.yaml configuration file:

                1) Visit {repo_url}/settings/security_analysis
                2) Navigate to the section "Code scanning -> CodeQL analysis"
                3) Click "Set up"
                4) Select "Advanced"
                5) Copy the contents of the generated file by Github
                6) Copy the contents to a local file named "{local_file}"
                7) Edit "{local_file}" with these changes:

                    * Change `name: "CodeQL"` to `name: "[static code analysis] CodeQL"`
                    * [Optional] Remove the emojis on lines 63 and 64 (these can cause problems with Jinja2)

                8) Save the file
                """,
            ).format(
                repo_url=repo_url,
                local_file=config.root / ".github" / "workflows" / "sca_CodeQL.yaml",
            ),
            textwrap.dedent(
                """\
                ...updating the GitHub repository settings:

                - Enable "Secret scanning" at {repo_url}/settings/security_analysis

                - Enable Github write permissions at {repo_url}/settings/actions

                    1) Navigate to the section "Workflow permissions"
                    2) Select "Read and write permissions"
                    3) Click "Save"

                  Write permissions are necessary so that the CI workflows are able to update
                  the tag "main_stable" once a change has been validated.
                """,
            ).format(repo_url=repo_url),
        ],
    )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
