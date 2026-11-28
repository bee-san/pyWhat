"""fd 0 is closed, so sys.stdin is None: there is no text to search.

Every other way of having no input (a terminal, an empty pipe) reaches
main()'s "Text input expected" and exits with 1. A closed fd 0 must too,
instead of crashing in get_text() with an AttributeError.
"""
import sys

import click
import pytest

from pywhat.what import get_text, main


def test_get_text_without_stdin(monkeypatch):
    monkeypatch.setattr(sys, "stdin", None)
    ctx = click.Context(main)
    ctx.params["interactive"] = False
    assert get_text(ctx, None, ()) == ()


def test_closed_stdin_reports_the_missing_text(monkeypatch):
    monkeypatch.setattr(sys, "stdin", None)
    with pytest.raises(SystemExit) as exit:
        main.main(["-db"], standalone_mode=False)
    assert exit.value.code == "Text input expected. Run 'pywhat --help' for help"
