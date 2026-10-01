"""
Test cases for YouTube videos (issue #255).

A YouTube video link is identified in all of its common formats, with or
without "https://", as the whole link and nothing around it. A video ID on its
own, such as dQw4w9WgXcQ, could be any 11 random characters, so it has a rarity
of 0 and is only shown with --rarity 0:.
"""
import re
import time

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes
from pywhat.what import main

VIDEO = "YouTube Video"
VIDEO_LINKS = next(regex for regex in load_regexes() if regex["Name"] == VIDEO)[
    "Examples"
]["Valid"]
# Boundaryless mode, the default of the CLI
r = identifier.Identifier(boundaryless=Filter())


def _videos(text, identifier_=r):
    out = identifier_.identify(text)
    if out["Regexes"] is None:
        return []
    return [
        match["Matched"]
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == VIDEO
    ]


@pytest.mark.parametrize("link", VIDEO_LINKS)
def test_video_link_is_fully_matched(link):
    assert _videos(f"Watch {link} now") == [link]


@pytest.mark.parametrize(
    "link",
    [
        "https://youtu.be/dQw4w9WgXcQ?si=Ab_cD-eF0123gHiJ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
        "https://www.youtube.com/watch?app=desktop&v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
        "youtu.be/dQw4w9WgXcQ",
    ],
)
def test_video_link_is_matched_by_default_api(link):
    # The API is not in boundaryless mode by default
    assert _videos(link, identifier.Identifier()) == [link]


@pytest.mark.parametrize(
    "text, links",
    [
        ("(see https://youtu.be/dQw4w9WgXcQ)", ["https://youtu.be/dQw4w9WgXcQ"]),
        (
            "[Rick](https://youtu.be/dQw4w9WgXcQ?t=42).",
            ["https://youtu.be/dQw4w9WgXcQ?t=42"],
        ),
        ("Have you seen youtu.be/dQw4w9WgXcQ?", ["youtu.be/dQw4w9WgXcQ"]),
        (
            "Watch https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s!",
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=42s"],
        ),
        (
            "https://youtu.be/dQw4w9WgXcQ, https://youtu.be/ScOAntcCa78",
            ["https://youtu.be/dQw4w9WgXcQ", "https://youtu.be/ScOAntcCa78"],
        ),
        (
            '<iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ?si=abc">',
            ["https://www.youtube.com/embed/dQw4w9WgXcQ?si=abc"],
        ),
        (
            '<iframe src="//www.youtube.com/embed/dQw4w9WgXcQ">',
            ["//www.youtube.com/embed/dQw4w9WgXcQ"],
        ),
        (
            '<a href="https://www.youtube.com/watch?v=dQw4w9WgXcQ&amp;t=1">',
            ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&amp;t=1"],
        ),
        ('{"url":"https://youtu.be/dQw4w9WgXcQ"}', ["https://youtu.be/dQw4w9WgXcQ"]),
        (
            "\u52d5\u753bhttps://youtu.be/dQw4w9WgXcQ\u3067\u3059",
            ["https://youtu.be/dQw4w9WgXcQ"],
        ),
    ],
)
def test_video_link_does_not_include_surrounding_text(text, links):
    assert _videos(text) == links


@pytest.mark.parametrize(
    "text",
    [
        "dQw4w9WgXcQ",
        "notyoutube.com/watch?v=dQw4w9WgXcQ",
        "my-youtube.com/watch?v=dQw4w9WgXcQ",
        "youtube.com.example.org/watch?v=dQw4w9WgXcQ",
        "ayoutu.be/dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQxyz",
        "https://www.youtube.com/watch?v=trj15fjXWDwasdasdasd",
        "https://www.youtube.com/watch?v=dQw4w9WgXc&t=42s",
        "https://www.youtube.com/watch?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG",
        "https://www.youtube.com/channel/UCjXfkj5iapKHJrhYfAF9ZGg",
        "https://www.youtube.com/@RickAstleyYT",
        "https://www.youtube.com/embed/videoseries?list=PLx0sYbCqOb8TBPRdmBHs5Iftvv9TPboYG",
        "https://www.youtube.com/embed/live_stream?channel=UCjXfkj5iapKHJrhYfAF9ZGg",
    ],
)
def test_not_a_video_link(text):
    assert _videos(f"Watch {text} now") == []


def test_cli_prints_the_full_video_link():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--include", "YouTube", "Watch https://youtu.be/dQw4w9WgXcQ?t=42."]
    )
    assert result.exit_code == 0
    assert (
        "Matched on: https://youtu.be/dQw4w9WgXcQ?t=42\nName: YouTube Video\n"
        in result.output
    )


def test_cli_video_id_is_only_shown_with_rarity_0():
    # A video ID on its own has a rarity of 0, it could be any 11 characters
    runner = CliRunner()
    result = runner.invoke(main, ["dQw4w9WgXcQ"])
    assert result.exit_code == 0
    assert "YouTube" not in result.output

    result = runner.invoke(main, ["--rarity", "0:", "dQw4w9WgXcQ"])
    assert result.exit_code == 0
    assert "Name: YouTube Video ID" in result.output
    assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in result.output


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 50000, id="long word"),
        pytest.param("youtube." * 7000, id="repeated host"),
        pytest.param("youtu.be/" * 6000, id="repeated short host"),
        pytest.param("youtube.com/watch?" + "a&" * 25000, id="many parameters"),
        pytest.param("youtube.com/watch?" + "v=a&" * 12500, id="many short v"),
        pytest.param(("youtube.com/watch?" + "a=b&" * 25) * 500, id="many links"),
        pytest.param("https://youtu.be/dQw4w9WgXcQ?" + "." * 50000, id="dots"),
        pytest.param("https://youtu.be/dQw4w9WgXcQ?t=1" + "!" * 50000, id="bangs"),
    ],
)
def test_video_regex_does_not_backtrack_catastrophically(text):
    entry = next(regex for regex in load_regexes() if regex["Name"] == VIDEO)
    for regex in (entry["Regex"], entry["Boundaryless Regex"]):
        start = time.perf_counter()
        list(re.finditer(regex, text, re.MULTILINE))
        assert time.perf_counter() - start < 2
