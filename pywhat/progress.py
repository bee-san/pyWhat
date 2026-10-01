"""
Progress bars for searches that take a while (issue #189).

The searches of pywhat.identifier.Identifier call their progress callback
with a pywhat.identifier.Progress before every regex that they search for,
and ProgressBars shows how far the search is on a terminal.
"""
import os
import re
import stat
import sys
import threading
from contextlib import contextmanager
from datetime import timedelta
from time import monotonic
from typing import Any, Iterator, Optional

from rich.console import Console, RenderableType
from rich.live import Live
from rich.progress_bar import ProgressBar
from rich.segment import SegmentLines
from rich.table import Table
from rich.text import Text

from pywhat.identifier import Progress

# The progress bars only appear once a search has taken this long, in seconds,
# so that they do not flicker for the searches that are over in a moment
DELAY = 0.5
BAR_WIDTH = 30
LABEL_STYLE = "bold #D7Afff"
# Control characters, e.g. in file names, would mess up the terminal
_CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def _text(text: str) -> Text:
    # Text, not a str, so that names such as "[a]" are not taken as markup. A
    # name that is too long is cut off, the bars are a line each.
    return Text(_CONTROL_CHARACTERS.sub("", text), no_wrap=True, overflow="ellipsis")


class ProgressBars:
    """
    Progress bars for a search, shown on console while the search runs: a bar
    for the files (if there are several) with the file that is searched, and a
    bar for the regexes of the file with the regex that is searched for. It is
    the progress callback of the search:

        with ProgressBars(Console()) as progress:
            Identifier().identify("big.log", only_text=False, progress=progress)

    The bars appear once the search has taken delay seconds, and are removed
    when it is done.
    """

    def __init__(self, console: Console, delay: float = DELAY):
        self.console = console
        self.delay = delay
        self.progress: Optional[Progress] = None  # the latest progress
        self._start = monotonic()
        self._timer: Optional[threading.Timer] = None
        self._live = Live(
            console=console,
            transient=True,
            refresh_per_second=10,
            # Anything else written to the terminal that the bars are on goes
            # above them. The bars can be on stderr while the output goes to
            # a file on stdout, which must not be redirected then.
            redirect_stdout=console.file is sys.stdout,
            redirect_stderr=console.file is sys.stderr,
            get_renderable=self._render_lines,
        )

    def __call__(self, progress: Progress) -> None:
        # Called for every regex, so it only keeps the progress. The bars are
        # drawn from it 10 times a second.
        self.progress = progress

    def __enter__(self) -> "ProgressBars":
        self._start = monotonic()
        if self.delay > 0:
            # A timer, as the search may be busy with one regex for a while
            self._timer = threading.Timer(
                self.delay, self._live.start, kwargs={"refresh": True}
            )
            self._timer.daemon = True
            self._timer.start()
        else:
            self._live.start(refresh=True)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer.join()  # in case it is showing the bars right now
            self._timer = None
        self._live.stop()

    def render(self) -> RenderableType:
        """The progress bars for the latest progress."""
        progress = self.progress
        if progress is None:
            return Text("Searching...", style=LABEL_STYLE)
        elapsed = str(timedelta(seconds=int(monotonic() - self._start)))
        # Narrower bars on a narrow terminal, to leave room for the names
        bar_width = min(BAR_WIDTH, max(10, self.console.width // 4))

        table = Table.grid(padding=(0, 1))
        table.add_column(style=LABEL_STYLE, no_wrap=True)  # what the bar is for
        table.add_column(no_wrap=True)  # the bar
        table.add_column(justify="right", no_wrap=True)  # how far it is
        table.add_column(no_wrap=True)  # the time since the search started
        # The file or the regex, the only column that is made narrower (cut
        # off with an ellipsis) if the bars are wider than the terminal
        table.add_column()
        if progress.files > 1:
            table.add_row(
                "Files",
                ProgressBar(
                    total=progress.files,
                    completed=progress.files_done,
                    width=bar_width,
                ),
                f"{progress.files_done}/{progress.files}",
                elapsed,
                _text(progress.location),
            )
            elapsed = ""
        # One regex is 1% if there are 100 regexes to search for in the file
        regexes = max(progress.regexes, 1)
        regexes_done = progress.regexes_done if progress.regexes else 1
        table.add_row(
            "Regexes",
            ProgressBar(total=regexes, completed=regexes_done, width=bar_width),
            f"{100 * regexes_done // regexes}%",
            elapsed,
            _text(progress.regex or ""),
        )
        return table

    def _render_lines(self) -> RenderableType:
        """
        The progress bars, rendered. The bars are drawn below every line that
        is printed while they are shown, e.g. every match with --stream, but
        they are only rendered when they are refreshed, 10 times a second.
        """
        lines = self.console.render_lines(self.render(), pad=False)
        return SegmentLines(lines, new_lines=True)


def _writes_to_a_file(console: Console) -> bool:
    """Whether console writes to a regular file, e.g. pywhat ... > output.txt"""
    try:
        return stat.S_ISREG(os.fstat(console.file.fileno()).st_mode)
    except (AttributeError, OSError, ValueError):  # e.g. io.UnsupportedOperation
        return False


def _is_a_terminal(console: Console) -> bool:
    """
    Whether console writes to a terminal that the progress bars can be drawn
    on. console.is_terminal is not enough: rich also takes a pipe or a file for
    a terminal if FORCE_COLOR or TTY_COMPATIBLE=1 is set, to write colours to
    it, and the bars would break the output there, e.g. the JSON of
    pywhat --json ... | jq (issue #264).
    """
    if not console.is_terminal or console.is_dumb_terminal:
        return False
    isatty = getattr(console.file, "isatty", None)
    try:
        return isatty is not None and bool(isatty())
    except ValueError:  # the file is closed
        return False


@contextmanager
def progress_bars(
    console: Console, *, enabled: bool = True, stderr: bool = False
) -> Iterator[Optional[ProgressBars]]:
    """
    Show ProgressBars on console while the with block runs, if console is a
    terminal. With stderr, they are shown on stderr instead if console writes
    to a file and stderr is a terminal, e.g. for pywhat ... > output.txt. Not
    if it writes to a pipe, as the program that reads it may be writing to the
    terminal too, e.g. for pywhat --stream --json ... | jq.

    Yields the ProgressBars, the progress callback for the search, or None if
    the bars are not shown because there is no terminal or they are disabled.
    """
    if enabled and stderr and _writes_to_a_file(console):
        console = Console(stderr=True, highlight=False)
    if not enabled or not _is_a_terminal(console):
        yield None
        return
    with ProgressBars(console) as bars:
        yield bars
