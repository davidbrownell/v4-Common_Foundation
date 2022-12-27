# ----------------------------------------------------------------------
# |
# |  update_data.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-11-01 09:59:32
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Updates the Gitmoji data"""

from pathlib import Path
from typing import List

import requests
import typer

from typer.core import TyperGroup

from Common_Foundation.Streams.DoneManager import DoneManager, DoneManagerFlags


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
@app.command("Update", no_args_is_help=False)
def Update(
    url_base: str=typer.Option("https://raw.githubusercontent.com/carloscuesta/gitmoji/master/packages/gitmojis/src", "--url-base", help="Base url of the gitmoji data."),
    filenames: List[str]=typer.Option(["gitmojis.json", "schema.json"], "--filename", help="gitmoji files to download."),
    verbose: bool=typer.Option(False, "--verbose", help="Write verbose information to the terminal."),
    debug: bool=typer.Option(False, "--debug", help="Write debug information to the terminal."),
) -> None:
    """Updates the Gitmoji data."""

    with DoneManager.CreateCommandLine(
        output_flags=DoneManagerFlags.Create(verbose=verbose, debug=debug),
    ) as dm:
        this_dir = Path(__file__).parent

        for filename_index, filename in enumerate(filenames):
            with dm.Nested(
                "Downloading '{}' ({} of {})...".format(
                    filename,
                    filename_index + 1,
                    len(filenames),
                ),
            ):
                response = requests.get("{}/{}".format(url_base, filename))
                response.raise_for_status()

                content = response.text

                with (this_dir / filename).open(
                    "w",
                    encoding="UTF-8",
                ) as f:
                    f.write(content)


# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
# ----------------------------------------------------------------------
if __name__ == "__main__":
    app()
