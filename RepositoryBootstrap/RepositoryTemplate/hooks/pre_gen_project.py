# ----------------------------------------------------------------------
# |
# |  pre_gen_project.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2023-07-13 13:56:44
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2023
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Script invoked before cookiecutter project generation"""

import typer

from typer.core import TyperGroup

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags


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
        with dm.Nested("Running pre-project validation...") as validation_dm:
            if not "{{ cookiecutter.name }}":
                validation_dm.WriteError("A name must be provided.")

            if not "{{ cookiecutter.repo_friendly_name }}":
                validation_dm.WriteError("A friendly name must be provided for the repository.")

            if (
                "{{ cookiecutter.support_windows }}".lower() != "true"
                and "{{ cookiecutter.support_linux }}".lower() != "true"
            ):
                validation_dm.WriteError("Windows and/or Linux must be supported.")

            if "{{ cookiecutter.github_username_and_repo }}":
                if "{{ cookiecutter.repository_type }}".lower() != "git":
                    validation_dm.WriteError("The repository type must be 'git' when providing a GitHub username and repo.")

                if not _IsTrue("{{ cookiecutter.include_bootstrap_scripts }}"):
                    validation_dm.WriteError("GitHub workflows require bootstrap scripts.")


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
