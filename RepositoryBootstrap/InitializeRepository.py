# ----------------------------------------------------------------------
# |
# |  InitializeRepository.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-08-10 21:30:20
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
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

from Common_Foundation.ContextlibEx import ExitStack  # type: ignore
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import TextwrapEx  # type: ignore

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
def EntryPoint():
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

    sys.stdout.write("\n")

    friendly_name = _Prompt("Enter the friendly name of this repository: ")

    # Files to copy
    sys.stdout.write(
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
    sys.stdout.write("\n")

    support_windows = _Prompt("Support development on Windows? ", "yes").lower() in ["yes", "y"]
    support_linux = _Prompt("Support development on Linux? ", "yes").lower() in ["yes", "y"]
    sys.stdout.write("\n")

    include_boost_license = _Prompt("Include the Boost Software License? ", "no").lower() in ["yes", "y"]
    include_bootstrap = _Prompt("Include bootstrap scripts for automated environment setup? ", "yes").lower() in ["yes", "y"]
    include_scm_hook = _Prompt("Include source control commit hooks? ", "no").lower() in ["yes", "y"]
    include_pyright_config = _Prompt("Include 'pyrightconfig.json' to limit the scope of pylint scanning? ", "no").lower() in ["yes", "y"]
    sys.stdout.write("\n")

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

    sys.stdout.write("\n")

    include_github_workflows = False

    if _Prompt("With this repository be hosted on Github? ", "yes").lower() in ["yes", "y"]:
        include_github_workflows = _Prompt("Include Github Continuous Integration workflows? ", "yes").lower() in ["yes", "y"]

        if include_github_workflows:
            if not support_git:
                sys.stdout.write("NOTE: Git support is required by Github workflows and will be added.\n")
                support_git = True

            if not include_bootstrap:
                sys.stdout.write("NOTE: Bootstrap files are required by Github workflows and will be added.\n")
                include_bootstrap = True

    return Execute(
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

    if config.include_github_workflows:
        workflow_files = [
            os.path.join(".github", "workflows", filename)
            for filename in [
                "build_and_test.yaml",
                "exercise_main.yaml",
                "main.yaml",
                "on_pr_to_main.yaml",
            ]
        ]

        files_to_copy += workflow_files

        actions.append(
            textwrap.dedent(
                """\
                Github workflow files:

                {}

                Search for instances of "<< Populate (github_workflow): ... >>" in these files and make updates
                following the instructions provided with each using information specific to this repository being
                initialized.

                    Friendly Name of this repo: {}
                """,
            ).format(
                "\n".join('    - "{}"'.format(filename) for filename in workflow_files),
                config.friendly_name,
            ),
        )

    actions.append(
        textwrap.dedent(
            """\
            After making these changes, consider...

                a) Adding execution permissions for all .sh files:

                    `chmod a+x *.sh`

                b) Committing using the message:

                    "🎉 [started_project] Initial project scaffolding."

                c) Creating a tag (git) / branch (hg) based on that commit named

                    "main_stable"
            """,
        ),
    )

    # Copy the files
    with DoneManager.Create(
        sys.stdout,
        "\nCopying {} ...".format(
            inflect.no("file", len(files_to_copy)),
        ),
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

    sys.stdout.write(
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
                    "{}) {}".format(action_index + 1, action)
                    for action_index, action in enumerate(actions)
                ),
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
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    sys.exit(EntryPoint())
