import io
import os
import sys
import time

import pytest
from rich.console import Console
from rich.table import Table

import pywhat.progress
from pywhat.identifier import Identifier, Progress
from pywhat.progress import ProgressBars, progress_bars


def terminal():
    """A console that writes to a string, like to a terminal."""
    return Console(
        file=io.StringIO(),
        force_terminal=True,
        force_interactive=True,
        width=100,
        color_system=None,
        legacy_windows=False,
    )


@pytest.fixture(autouse=True)
def term(monkeypatch):
    # Whatever terminal the tests run in, or none (e.g. TERM=dumb in CI)
    monkeypatch.setenv("TERM", "xterm-256color")


def not_a_terminal():
    return Console(file=io.StringIO(), force_terminal=False)


def render(bars):
    """The progress bars as text."""
    console = Console(
        file=io.StringIO(),
        force_terminal=False,
        width=100,
        color_system=None,
        legacy_windows=False,
    )
    console.print(bars.render())
    return console.file.getvalue()


class FakeTerminal(io.StringIO):
    def isatty(self):
        return True


def test_render_before_the_first_progress():
    assert render(ProgressBars(terminal())).strip() == "Searching..."


def test_render_file():
    bars = ProgressBars(terminal())
    bars(Progress("file", 0, 1, 50, 200, "Uniform Resource Locator (URL)"))
    lines = render(bars).splitlines()
    # No bar for the files, as there is only one
    assert len(lines) == 1
    assert lines[0].startswith("Regexes ")
    assert " 25% " in lines[0]
    assert "Uniform Resource Locator (URL)" in lines[0]


def test_render_files():
    bars = ProgressBars(terminal())
    bars(Progress("/logs/app.log", 2, 8, 137, 137, None))
    files, regexes = render(bars).splitlines()
    assert files.startswith("Files ")
    assert " 2/8 " in files
    assert "/logs/app.log" in files
    assert regexes.startswith("Regexes ")
    assert " 100% " in regexes


def test_render_without_regexes():
    # e.g. if no regex has the tags of --include
    bars = ProgressBars(terminal())
    bars(Progress("text", 0, 1, 0, 0, None))
    assert " 100% " in render(bars)


def test_render_names_literally():
    # Names are not markup, and control characters are left out
    bars = ProgressBars(terminal())
    bars(Progress("[bold]a[/bold]\x1b[2J.txt", 0, 2, 0, 10, "[/]"))
    output = render(bars)
    assert "[bold]a[/bold][2J.txt" in output
    assert "[/]" in output
    assert "\x1b" not in output


def test_render_elapsed_time(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(pywhat.progress, "monotonic", lambda: now[0])
    bars = ProgressBars(terminal())
    bars(Progress("text", 0, 1, 1, 2, "a"))
    now[0] = 165.5
    assert " 0:01:05 " in render(bars)


def test_bars_on_a_terminal():
    console = terminal()
    with ProgressBars(console, delay=0) as bars:
        bars(Progress("file", 0, 1, 1, 4, "Email Address"))
    output = console.file.getvalue()
    assert "Regexes" in output
    assert "Email Address" in output
    # The bars are removed (the line is erased) when the search is done
    assert "\x1b[2K" in output[output.rindex("Email Address") :]


def test_render_long_names():
    # A bar is a line, names that are too long are cut off
    console = terminal()
    console.width = 60
    bars = ProgressBars(console)
    bars(Progress("/a/very/long/path/" * 5, 1, 3, 1, 10, "Regex " * 20))
    console.print(bars._render_lines())
    lines = console.file.getvalue().splitlines()
    assert len(lines) == 2
    assert all(len(line) <= 60 and line.endswith("…") for line in lines)
    assert " 1/3 " in lines[0]
    assert " 10% " in lines[1]


def test_bars_are_rendered_when_refreshed(monkeypatch):
    # Not for every line that is printed above them (e.g. every match with
    # --stream), which would make printing slow
    rendered = []
    render_table = Table.__rich_console__

    def render(table, console, options):
        rendered.append(table)
        return render_table(table, console, options)

    monkeypatch.setattr(Table, "__rich_console__", render)
    console = terminal()
    bars = ProgressBars(console, delay=0)
    bars(Progress("file", 0, 1, 1, 4, "Email Address"))
    with bars:
        for number in range(1000):
            console.print(f"Match {number}")
    output = console.file.getvalue()
    assert "Match 999" in output
    # The bars are below the lines that are printed
    assert output.index("Email Address", output.index("Match 999")) > 0
    # Rendered 10 times a second, not 1000 times
    assert 0 < len(rendered) < 250


def test_bars_appear_after_the_delay():
    console = terminal()
    with ProgressBars(console, delay=0.05) as bars:
        bars(Progress("file", 0, 1, 1, 4, "Email Address"))
        deadline = time.monotonic() + 10
        while not console.file.getvalue() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert "Email Address" in console.file.getvalue()


def test_no_bars_for_quick_searches():
    console = terminal()
    with ProgressBars(console, delay=60) as bars:
        bars(Progress("file", 0, 1, 1, 4, "Email Address"))
    # Nothing at all is written to the terminal
    assert console.file.getvalue() == ""


def test_progress_bars_on_a_terminal():
    console = terminal()
    with progress_bars(console) as bars:
        assert isinstance(bars, ProgressBars)
        assert bars.console is console


def test_progress_bars_not_on_a_terminal():
    with progress_bars(not_a_terminal()) as bars:
        assert bars is None


def test_progress_bars_disabled():
    with progress_bars(terminal(), enabled=False) as bars:
        assert bars is None


def test_progress_bars_dumb_terminal(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    with progress_bars(terminal()) as bars:
        assert bars is None


def test_progress_bars_on_stderr(monkeypatch, tmp_path):
    # When the output is redirected to a file, the bars are on stderr if it is
    # a terminal
    stderr = FakeTerminal()
    monkeypatch.setattr(sys, "stderr", stderr)
    with open(tmp_path / "output.txt", "w") as output:
        to_a_file = Console(file=output)
        with progress_bars(to_a_file, stderr=True) as bars:
            assert bars is not None
            assert bars.console.file is stderr
        with progress_bars(to_a_file) as bars:
            assert bars is None
        with progress_bars(to_a_file, stderr=True, enabled=False) as bars:
            assert bars is None

        monkeypatch.setattr(sys, "stderr", io.StringIO())
        with progress_bars(to_a_file, stderr=True) as bars:
            assert bars is None
        assert output.tell() == 0  # nothing is written to the output


def test_no_progress_bars_on_stderr_for_a_pipe(monkeypatch):
    # The program that reads the output may be writing to the terminal too
    monkeypatch.setattr(sys, "stderr", FakeTerminal())
    read, write = os.pipe()
    try:
        with open(write, "w") as pipe:
            with progress_bars(Console(file=pipe), stderr=True) as bars:
                assert bars is None
    finally:
        os.close(read)
    with progress_bars(not_a_terminal(), stderr=True) as bars:
        assert bars is None


def test_bars_with_a_search():
    # The progress bars are the progress callback of a search
    console = terminal()
    with ProgressBars(console, delay=0) as bars:
        Identifier().identify("fixtures", only_text=False, progress=bars)
        assert bars.progress.files_done == bars.progress.files == 2
    assert "Files" in console.file.getvalue()
