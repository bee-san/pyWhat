"""
Tests for the regexes based on the regex101.com community library (issue #37).

The "Examples" in regex.json test each regex on its own. These tests cover
how the regexes behave inside longer text (boundaryless mode, the CLI
default), the false positives they are designed to avoid, the operating
system and browser detection of user agents, and that none of them
backtracks catastrophically.
"""
import re
import time

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes
from pywhat.what import main

CRON = "Cron Schedule"
USER_AGENT = "Browser User Agent"
ISO_8601 = "ISO 8601 Timestamp"
POSTCODE = "United Kingdom (UK) Postcode"
REGEX101 = "Regex101 Permalink"
NEW_REGEXES = [CRON, USER_AGENT, ISO_8601, POSTCODE, REGEX101]

r = identifier.Identifier(boundaryless=Filter({"MinRarity": 0}))


def matches(name: str, text: str) -> list:
    """Everything that the regex called `name` matches in `text` (boundaryless)."""
    out = r.identify(text)
    if out["Regexes"] is None:
        return []
    return [
        match["Matched"]
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == name
    ]


def description(name: str, text: str):
    out = r.identify(text, boundaryless=Filter({"Tags": []}))
    return next(
        match["Regex Pattern"]["Description"]
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == name
    )


@pytest.mark.parametrize(
    "name, text, expected",
    [
        (CRON, 'schedule: "*/5 * * * *"', ["*/5 * * * *"]),
        (CRON, "  - cron: '30 5 * * 1,3'", ["30 5 * * 1,3"]),
        (CRON, "Runs at 0 0 * * *. Every day.", ["0 0 * * *"]),
        (
            CRON,
            "# m h dom mon dow command\n"
            "0 5 * * 1 tar -zcf /var/backups/home.tgz /home/\n"
            "*/15 * * * * root /usr/local/bin/poll >/dev/null 2>&1\n",
            [
                "0 5 * * 1 tar -zcf /var/backups/home.tgz /home/",
                "*/15 * * * * root /usr/local/bin/poll >/dev/null 2>&1",
            ],
        ),
        (
            USER_AGENT,
            '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.1" 200 2326 "-" '
            '"Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"',
            ["Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0"],
        ),
        (
            USER_AGENT,
            "User-Agent: Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko\r\n",
            ["Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko"],
        ),
        (
            ISO_8601,
            '{"created_at": "2021-06-26T16:50:36Z", "id": 1}',
            ["2021-06-26T16:50:36Z"],
        ),
        (
            POSTCODE,
            "Buckingham Palace, London SW1A 1AA, United Kingdom",
            ["SW1A 1AA"],
        ),
        (
            REGEX101,
            "See https://regex101.com/r/wY0rM7/3, it explains the regex.",
            ["https://regex101.com/r/wY0rM7/3"],
        ),
    ],
)
def test_matches_in_longer_text(name, text, expected):
    assert matches(name, text) == expected


@pytest.mark.parametrize(
    "name, text",
    [
        # Products and number tables are not cron schedules
        (CRON, "volume = 2 * 3 * 4"),
        (CRON, "print(2 * 3 * 4 * 5 * 6)"),
        (CRON, "seconds = 24 * 60 * 60"),
        (CRON, "1 2 3 4 5 6 7 8 9 10"),
        # A line of stars, e.g. a separator in a comment
        (CRON, "* * * * * * * * * * * * * * * * * * * *"),
        # A C comment drawing a bit layout
        (CRON, " *  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5\n"),
        # Inside of other tokens
        (CRON, "a/1 * * * *"),
        (CRON, "0 2 * * *x"),
        # Hex colours and other short uppercase tokens
        (POSTCODE, "color: #FF00AA; background: #AB12EF;"),
        (POSTCODE, "S16LE S32BE E11HD"),
        # The postcode has to be written with a space
        (POSTCODE, "SW1A1AA"),
        # A date or a date and time without the "T" is not ISO 8601
        (ISO_8601, "2016-01-19"),
        (ISO_8601, "2016-01-19 15:21:32"),
        (USER_AGENT, "Mozilla/5.0 and/or later"),
        (REGEX101, "https://regex101.com/r/abcdefgh"),
    ],
)
def test_no_false_positives(name, text):
    assert matches(name, text) == []


@pytest.mark.parametrize(
    "user_agent, detected",
    [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Windows, Chrome",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
            "Windows, Microsoft Edge",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/105.0.0.0",
            "Windows, Opera",
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Linux, Firefox",
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "macOS, Safari",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
            "iOS, Safari",
        ),
        (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
            "iOS, Chrome",
        ),
        (
            "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Android, Chrome",
        ),
        (
            "Mozilla/5.0 (Linux; Android 13; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/23.0 Chrome/115.0.0.0 Mobile Safari/537.36",
            "Android, Samsung Internet",
        ),
        (
            "Mozilla/5.0 (X11; CrOS x86_64 14541.0.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "ChromeOS, Chrome",
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko",
            "Windows, Internet Explorer",
        ),
        (
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Bot",
        ),
    ],
)
def test_user_agent_detection(user_agent, detected):
    assert description(USER_AGENT, user_agent) == "Detected: " + detected


def test_cli_output():
    runner = CliRunner()
    result = runner.invoke(main, ["*/10 * * * * root /usr/local/bin/backup"])
    assert result.exit_code == 0
    assert CRON in result.output

    result = runner.invoke(
        main,
        [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ],
    )
    assert result.exit_code == 0
    assert USER_AGENT in result.output
    assert "Detected: Windows, Chrome" in result.output


ADVERSARIAL_INPUTS = {
    "numbers": "1 " * 20000,
    "stars": "* " * 20000,
    "steps": "*/" * 20000,
    "list": "1," * 20000 + "x",
    "ranges": "1-" * 20000,
    "products": "2 * 3 * 4 " * 5000,
    "tabs": "1\t" * 20000,
    "spaces": " " * 40000 + "x",
    "pluses": "a+" * 20000,
    "user agent starts": "Mozilla/5.0 (" * 5000,
    "user agent products": "Mozilla/5.0 (x)" + " a/b" * 10000 + '"',
    "user agent mobile": "Mozilla/5.0 (x)" + " Mobile" * 10000 + "!",
    "unclosed comment": "Mozilla/5.0 (" + "a" * 40000,
    "postcodes": "SW1A " * 10000,
    "dates": "2016-01-19T" * 5000,
    "long fraction": "2016-01-19T15:21:32." + "1" * 40000 + "x",
    "permalinks": "regex101.com/r/" * 5000,
}


@pytest.mark.parametrize(
    "text", ADVERSARIAL_INPUTS.values(), ids=ADVERSARIAL_INPUTS.keys()
)
def test_no_catastrophic_backtracking(text):
    database = {regex["Name"]: regex for regex in load_regexes()}
    start = time.perf_counter()
    for name in NEW_REGEXES:
        for key in ("Regex", "Boundaryless Regex"):
            for _ in re.finditer(database[name][key], text, re.MULTILINE):
                pass
    # Linear time takes milliseconds, catastrophic backtracking would take ages
    assert time.perf_counter() - start < 5
