"""
Test cases for URL identification.

The URL regex has to match the whole URL and nothing around it, in boundaryless
mode (the default of the CLI) too (issue #117).
"""
import re
import time

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes
from pywhat.what import main

URL = "Uniform Resource Locator (URL)"
r = identifier.Identifier(boundaryless=Filter())


def _urls(text):
    out = r.identify(text)
    if out["Regexes"] is None:
        return []
    return [
        match["Matched"]
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == URL
    ]


@pytest.mark.parametrize(
    "url",
    [
        "google.com/help",
        "https://www.google.com",
        "https://google.co.uk/search?q=a",
        "https://github.com/bee-san/pyWhat/issues/117#issuecomment-881348890",
        # port with one digit
        "https://example.com:8/x",
        # user without a password, and characters like "-" and "_" in it
        "https://user@bitbucket.org/team/repo.git",
        "https://deploy-bot:s3cr3t_t0ken@github.com/org/repo.git",
        # user and password with an IP address
        "https://user:pass@10.0.0.1:8080/admin",
        # domains starting with an IP address
        "http://10.1.1.1.nip.io/",
        # punycode subdomain
        "https://xn--d1acufc.xn--80aaxitdbjk.xn--p1ai/",
        # brackets and braces in the path and query
        "https://example.com/?a[]=1&a[]=2",
        "https://example.com/?filter[name]=x&page[size]=10",
        "https://api.github.com/repos/{owner}/{repo}",
        "https://example.com/api/${id}",
        "https://en.wikipedia.org/wiki/Swiss_cheese_(North_America)#Production",
        "https://en.wikipedia.org/wiki/Ender's_Game",
        # non-ASCII characters in the path
        "https://de.wikipedia.org/wiki/K\u00f6ln",
        "https://ja.wikipedia.org/wiki/\u6771\u4eac\u90fd",
        "https://www.google.com/maps/@51.5,-0.12,15z",
        "https://example.com/#!/route",
        "http://d.com/#@.s?h/",
        "https://example.com/?token=abc==",
    ],
)
def test_url_is_fully_matched(url):
    assert _urls(f"Visit {url} today") == [url]


def test_url_with_longest_tld_is_matched():
    assert _urls("google.co google.com google.coffee") == [
        "google.co",
        "google.com",
        "google.coffee",
    ]


@pytest.mark.parametrize(
    "text, urls",
    [
        ("Go to https://example.com/path.", ["https://example.com/path"]),
        ("Go to https://example.com.", ["https://example.com"]),
        ("Is it https://example.com/?q=1?", ["https://example.com/?q=1"]),
        ("Did you see https://example.com/?", ["https://example.com/"]),
        (
            "Visit https://www.google.com:443/search?q=hello!",
            ["https://www.google.com:443/search?q=hello"],
        ),
        ("URL: https://example.com/a/b/c/: done", ["https://example.com/a/b/c/"]),
        ("https://example.com/a...", ["https://example.com/a"]),
        ("url=https://example.com/a;", ["https://example.com/a"]),
        ("(see https://example.com/path)", ["https://example.com/path"]),
        ("[link](https://example.com/a)", ["https://example.com/a"]),
        (
            "[x](https://en.wikipedia.org/wiki/Swiss_cheese_(North_America))",
            ["https://en.wikipedia.org/wiki/Swiss_cheese_(North_America)"],
        ),
        ("[url=https://example.com/a]x[/url]", ["https://example.com/a"]),
        ("background: url(https://example.com/a.png);", ["https://example.com/a.png"]),
        ("<https://example.com/a>", ["https://example.com/a"]),
        ('<a href="https://example.com?q=1">x</a>', ["https://example.com?q=1"]),
        ('{"url":"https://example.com/a","b":1}', ["https://example.com/a"]),
        ("requests.get('https://example.com/a')", ["https://example.com/a"]),
        ("fetch(`https://example.com/api/${id}`)", ["https://example.com/api/${id}"]),
        ("\u201chttps://example.com/a\u201d", ["https://example.com/a"]),
        (
            "'https://example.com/a', 'https://example.org/b'",
            ["https://example.com/a", "https://example.org/b"],
        ),
        (
            "https://example.com/a, https://example.org/b",
            ["https://example.com/a", "https://example.org/b"],
        ),
    ],
)
def test_url_does_not_include_surrounding_punctuation(text, urls):
    assert _urls(text) == urls


@pytest.mark.parametrize(
    "text",
    [
        "tryhackme.comm",
        "https://example.comfoo",
        "x = self.items[0]",
        "df.to_csv(path)",
        "response.status_code",
        "org.apache.commons.lang3.builder.ToStringBuilder.reflectionToString",
    ],
)
def test_url_is_not_matched_in_the_middle_of_a_word(text):
    assert _urls(text) == []


def test_cli_prints_the_full_url():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--include", "URL", "Visit https://www.google.com/search?q=hello."]
    )
    assert result.exit_code == 0
    assert "Matched on: https://www.google.com/search?q=hello\n" in result.output


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 50000, id="long word"),
        pytest.param("0x" + "6080604052" * 5000, id="long hex string"),
        pytest.param("http://" + "a" * 50000, id="scheme and long word"),
        pytest.param("a." * 2000, id="long dotted name"),
        pytest.param("xn--" * 12500, id="repeated punycode prefix"),
        pytest.param("https://example.com/a" + "." * 50000, id="trailing dots"),
        pytest.param("https://example.com/(" + "a" * 50000, id="unclosed bracket"),
    ],
)
def test_url_regex_does_not_backtrack_catastrophically(text):
    entry = next(regex for regex in load_regexes() if regex["Name"] == URL)
    start = time.perf_counter()
    list(re.finditer(entry["Boundaryless Regex"], text))
    assert time.perf_counter() - start < 2
