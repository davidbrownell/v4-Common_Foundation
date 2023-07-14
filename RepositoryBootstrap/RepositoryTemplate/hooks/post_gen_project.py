# ----------------------------------------------------------------------
# |
# |  post_gen_project.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-07-13 14:08:11
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Script invoked after cookiecutter project generation"""

import os
import shutil
import textwrap

from pathlib import Path

import typer

from typer.core import TyperGroup

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags
from Common_Foundation import TextwrapEx

from Common_FoundationEx.InflectEx import inflect


# ----------------------------------------------------------------------
class NaturalOrderGrouper(TyperGroup):
    # pylint: disable=missing-class-docstring
    # ----------------------------------------------------------------------
    def list_commands(self, *args, **kwargs):  # pylint: disable=unused-argument
        return self.commands.keys()


# ----------------------------------------------------------------------
app                                         = typer.Typer(
    cls=NaturalOrderGrouper,
    help=__doc__,
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


# ----------------------------------------------------------------------
@app.command(
    "EntryPoint",
    help=__doc__,
    no_args_is_help=False,
)
def EntryPoint(
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
        display=False,
    ) as dm:
        output_dir = Path.cwd()

        step_descriptions: list[str] = [
            # Setup_custom.py
            textwrap.dedent(
                """\
                {}

                Edit this file and add dependencies and any custom setup actions (if necessary). The template copied
                is designed to raise exceptions when these methods are first invoked to ensure that they are customized.
                Remove these exceptions once you have configured all setup activities.
                """,
            ).format(output_dir / "Setup_custom.py"),

            # Activate_custom.py
            textwrap.dedent(
                """\
                {}

                Edit this file and add any custom activation actions (if necessary). The template copied is designed to
                raise exceptions when these methods are first invoked to ensure that they are customized. Remove these
                exceptions once you have configured all activation activities.
                """,
            ).format(output_dir / "Activate_custom.py"),
        ]

        post_commit_fragments: list[str] = [
            textwrap.dedent(
                """\
                ...creating a tag (git) / branch (hg) named:

                 "main_stable"
                """,
            ),
        ]

        with dm.Nested(
            "Finalizing project...",
            suffix="\n",
        ):
            # Repo type
            repo = "{{ cookiecutter.repository_type }}".lower()

            repository_files_dir = output_dir / "repository_files"
            assert repository_files_dir.is_dir(), repository_files_dir

            if repo == "git":
                shutil.copy(repository_files_dir / ".gitignore", output_dir)
            elif repo == "mercurial":
                shutil.copy(repository_files_dir / ".hgignore", output_dir)
            elif repo == "none":
                pass # Nothing to do here
            else:
                assert False, repo  # pragma: no cover

            shutil.rmtree(repository_files_dir)

            # License files
            license = "{{ cookiecutter.license }}".lower()

            license_files_dir = output_dir / "license_files"
            assert license_files_dir.is_dir(), license_files_dir

            for filename in license_files_dir.iterdir():
                assert filename.is_file(), filename

                if filename.name.startswith(license):
                    shutil.move(filename, output_dir / filename.name[len(license) + 1:])

            shutil.rmtree(license_files_dir)

            # README / DEVELOPMENT files
            for file_type_name, file_type in [
                ("README", "{{ cookiecutter.readme_format }}".lower(), ),
                ("DEVELOPMENT", "{{ cookiecutter.development_readme_format }}".lower(), ),
            ]:
                files_dir = output_dir / "{}_files".format(file_type_name.lower())
                assert files_dir.is_dir(), files_dir

                if file_type == "markdown":
                    ext = ".md"
                elif file_type == "restructuredtext":
                    ext = ".rst"
                elif file_type == "none":
                    ext = None
                else:
                    assert False, file_type  # pragma: no cover

                if ext is not None:
                    shutil.copy(files_dir / "{}{}".format(file_type_name, ext), output_dir)

                shutil.rmtree(files_dir)

            # OS-specific files
            support_bootstrap_scripts = _IsTrue("{{ cookiecutter.include_bootstrap_scripts }}")

            for ext, support_value in [
                (".cmd", "{{ cookiecutter.support_windows }}", ),
                (".sh", "{{ cookiecutter.support_linux }}", ),
            ]:
                if _IsTrue(support_value):
                    if not support_bootstrap_scripts:
                        os.remove(output_dir / "Bootstrap{}".format(ext))
                else:
                    os.remove(output_dir / "Setup{}".format(ext))
                    os.remove(output_dir / "Bootstrap{}".format(ext))

            # SCM Plugins
            scm_plugin_filename = output_dir / "SCMPlugins.py"

            if _IsTrue("{{ cookiecutter.include_scm_plugin_script }}"):
                step_descriptions.append(
                    textwrap.dedent(
                        """\
                        {}

                        Edit this file and add any custom Commit, Push, or Pull validation events. The template copied is designed to
                        raise exceptions when these methods are first invoked to ensure that they are customized. Remove these
                        exceptions once you have implemented all the hooks.
                        """,
                    ).format(scm_plugin_filename),
                )
            else:
                os.remove(scm_plugin_filename)

            # pyrightconfig.json
            if not _IsTrue("{{ cookiecutter.include_root_pyright_config }}"):
                os.remove(output_dir / "pyrightconfig.json")

            # GitHub workflows
            github_dir = output_dir / ".github"
            assert github_dir.is_dir(), github_dir

            github_username_and_repo = "{{ cookiecutter.github_username_and_repo }}"
            if github_username_and_repo:
                step_descriptions += [
                    textwrap.dedent(
                        """\
                        {event_on_pr}
                        {validate}
                        {validate_with_dependencies}

                        Customize these files based on the instructions in each one.
                        """,
                    ).format(
                        event_on_pr=github_dir / "workflows" / "event_on_pr.yaml",
                        validate=github_dir / "workflows" / "validate.yaml",
                        validate_with_dependencies=github_dir / "workflows" / "validate_with_dependencies.yaml",
                    ),
                ]

                post_commit_fragments += [
                    textwrap.dedent(
                        """\
                        ...updating the CI tags:

                        `python {create_ci_tags}`

                        After committing these changes, run this script to create tags and push them to GitHub. The generated
                        GitHub workflows rely on these tags to function properly and will fail until they are created.
                        """,
                    ).format(
                        create_ci_tags=output_dir / ".github" / "CreateCITags.py",
                    ),
                ]

            else:
                shutil.rmtree(github_dir)

        # Convert the fragments into a step description
        step_descriptions += [
            textwrap.dedent(
                """\
                After making these changes, consider...

                a) ...adding execute permissions for all .sh files

                   `chomd a+x *.sh`

                b) ...applying copyright noticed to generated files (as needed).

                c) ...committing using the message:

                   "🎉 [started_project] Initial project scaffolding."
                """,
            ),
            textwrap.dedent(
                """\
                After that initial commit, consider...

                {}
                """,
            ).format(
                "".join(
                    "{}) {}\n\n".format(
                        chr(ord("a") + fragment_index),
                        TextwrapEx.Indent(
                            fragment.rstrip(),
                            len("{}) ".format(chr(ord("a") + fragment_index))),
                            skip_first_line=True,
                        ),
                    )
                    for fragment_index, fragment in enumerate(post_commit_fragments)
                ),
            ),
        ]

        dm.WriteLine(
            textwrap.dedent(
                """\
                **********************************************************************
                Repository information has been created at: "{output_dir}"

                To begin using this repository...

                {steps}

                **********************************************************************
                """,
            ).format(
                output_dir=output_dir,
                steps=TextwrapEx.Indent(
                    "\n".join(
                        "{}) {}".format(
                            step_description_index + 1,
                            TextwrapEx.Indent(
                                step_description,
                                len("{}) ".format(step_description_index + 1)),
                                skip_first_line=True,
                            ),
                        )
                        for step_description_index, step_description in enumerate(step_descriptions)
                    ).rstrip(),
                    4),
            ),
        )


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
def _IsTrue(
    value: str,
) -> bool:
    return value.lower() == "true"


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
