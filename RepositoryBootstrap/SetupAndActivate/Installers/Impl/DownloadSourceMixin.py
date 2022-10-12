# ----------------------------------------------------------------------
# |
# |  DownloadSourceMixin.py
# |
# |  David Brownell <db@DavidBrownell.com>
# |      2022-10-10 13:33:46
# |
# ----------------------------------------------------------------------
# |
# |  Copyright David Brownell 2022
# |  Distributed under the Boost Software License, Version 1.0. See
# |  accompanying file LICENSE_1_0.txt or copy at
# |  http://www.boost.org/LICENSE_1_0.txt.
# |
# ----------------------------------------------------------------------
"""Contains the DownloadSourceMixin object"""

import hashlib
import ssl

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional
from urllib import request
from urllib.error import URLError

from rich.progress import Progress

from Common_Foundation.ContextlibEx import ExitStack
from Common_Foundation.Shell.All import CurrentShell
from Common_Foundation.Streams.DoneManager import DoneManager
from Common_Foundation import TextwrapEx
from Common_Foundation.Types import overridemethod


# ----------------------------------------------------------------------
class DownloadSourceMixin(object):
    """Mixin that downloads source content to a temporary file"""

    # ----------------------------------------------------------------------
    def __init__(
        self,
        url: str,
        sha256: Optional[str],
    ):
        self.url                            = url
        self.sha256                         = sha256

    # ----------------------------------------------------------------------
    @overridemethod
    @contextmanager
    def _YieldInstallSource(
        self,
        dm: DoneManager,
    ) -> Iterator[Optional[Path]]:
        temp_filename = CurrentShell.CreateTempDirectory() / self.url.rsplit("/", maxsplit=1)[-1]

        with dm.Nested("Downloading '{}'...".format(self.url)) as download_dm:
            with download_dm.YieldStdout() as stdout_context:
                stdout_context.persist_content = False

                with Progress(
                    *Progress.get_default_columns(),
                    "{task.fields[status]}",
                    transient=True,
                ) as progress:
                    total_progress_id = progress.add_task(
                        stdout_context.line_prefix,
                        total=None,
                        status="",
                    )

                    total_completed_size: Optional[str] = None

                    # ----------------------------------------------------------------------
                    def Callback(
                        count: int,
                        block_size: int,
                        total_size: int,
                    ) -> None:
                        nonlocal total_completed_size

                        if count == 0:
                            progress.update(total_progress_id, total=total_size)
                            total_completed_size = TextwrapEx.GetSizeDisplay(total_size)

                        assert total_completed_size is not None

                        task = progress.tasks[0]
                        assert task.id == total_progress_id

                        progress.update(
                            total_progress_id,
                            advance=block_size,
                            status="{} of {} downloaded".format(
                                TextwrapEx.GetSizeDisplay(int(task.completed)),
                                total_completed_size,
                            ),
                        )

                    # ----------------------------------------------------------------------

                    # On older versions of Ubuntu (16.04), attempting to download content will fail SSL
                    # validation for some reason. The following workaround will disable SSL verification
                    # and allow installation to continue. For more information, visit
                    # https://stackoverflow.com/a/49174340.
                    implemented_ssl_workaround = False

                    while True:
                        try:
                            request.urlretrieve(self.url, temp_filename, Callback)
                            break

                        except (ssl.SSLError, URLError):
                            # If we have already tried the ssl workaround, let the error pass
                            if implemented_ssl_workaround:
                                raise

                            ssl._create_default_https_context = ssl._create_unverified_context  # pylint: disable=protected-access
                            implemented_ssl_workaround = True

            if download_dm.result != 0:
                yield None
                return

        with ExitStack(temp_filename.unlink):
            if self.sha256 is not None:
                with dm.Nested("Validating content ({})...".format(TextwrapEx.GetSizeDisplay(temp_filename.stat().st_size))) as validate_dm:
                    hasher = hashlib.sha256()

                    with validate_dm.YieldStdout() as stdout_context:
                        stdout_context.persist_content = False

                        with Progress(
                            transient=True,
                        ) as progress:
                            task_id = progress.add_task(
                                stdout_context.line_prefix,
                                total=temp_filename.stat().st_size,
                            )

                            with temp_filename.open("rb") as f:
                                while True:
                                    block = f.read(4096)
                                    if not block:
                                        break

                                    hasher.update(block)
                                    progress.update(task_id, advance=len(block))

                            hash_value = hasher.hexdigest().lower()

                    if hash_value != self.sha256.lower():
                        validate_dm.WriteError(
                            "The hash values do not match (actual: {}, expected: {}).\n".format(
                                hash_value,
                                self.sha256.lower(),
                            ),
                        )

                        yield None
                        return

            yield temp_filename
