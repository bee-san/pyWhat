"""The Rust engine of RegexIdentifier (pywhat._pywhat) and its fallback to re."""
import re
from importlib.metadata import version

import pytest

import pywhat
from pywhat import regex_identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import load_regexes
from pywhat.regex_identifier import RegexIdentifier

# Text before and after the matches, and in them, that isn't ASCII: the engine
# works on UTF-8 and returns the offsets of characters, as Python counts them
TEXTS = [
    "bee@skerritt.blog thm{flag} 192.168.0.1",
    "é bee@skerritt.blog 😀 192.168.0.1 中文 thm{fläg} https://example.com/ünï\n"
    "4111 1111 1111 1111 ٣ 1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY €\n"
    "😀😀 0x52908400098527886E0F7030069857D2E4169EE7 dQw4w9WgXcQ\n"
    "2021-11-16T20:05:19Z 52.6169586, -1.9779857 ✓",
]

# fancy-regex backtracks 20,000 times at each of the 20,000 positions of the
# first line (where the "c" is preceded by "b") and gives up; Python's re
# finds "ac" on the second line within a second
BACKTRACKING = r"[ab]*c(?<!bc)"
BACKTRACKING_TEXT = "ab" * 10_000 + "c\nac"


@pytest.fixture
def re_searches(monkeypatch):
    """The regexes that Python's re searches for instead of the Rust engine."""
    searched = []
    re_spans = regex_identifier._re_spans

    def counting(regex, string):
        searched.append(regex)
        return re_spans(regex, string)

    monkeypatch.setattr(regex_identifier, "_re_spans", counting)
    return searched


def one_regex(name: str, regex: str) -> Distribution:
    """A distribution of the regex called name, with its regex replaced."""
    dist = Distribution(Filter({"Tags": [name]}))
    (entry,) = dist.get_regexes()
    dist._regexes = [{**entry, "Regex": regex, "Boundaryless Regex": regex}]
    return dist


def test_the_rust_engine_is_used():
    assert regex_identifier._pywhat is not None, (
        "pywhat._pywhat isn't built, so the tests would run on Python's re: "
        "install the package with pip install -e . (or maturin develop)"
    )


@pytest.mark.parametrize("text", TEXTS)
def test_the_engine_finds_what_re_finds(text):
    engine = regex_identifier._pywhat
    encoded = engine.Text(text)
    for entry in load_regexes():
        for key in ["Regex", "Boundaryless Regex"]:
            expected = [m.span() for m in re.finditer(entry[key], text, re.MULTILINE)]
            assert engine.finditer(entry[key], text) == expected, (entry["Name"], key)
            assert engine.finditer(entry[key], encoded) == expected, (
                entry["Name"],
                key,
            )


def test_identify_runs_on_the_engine(re_searches):
    found = RegexIdentifier().check(TEXTS, boundaryless=Filter())
    assert "thm{fläg}" in [match["Matched"] for match in found]
    assert re_searches == []


def test_lone_surrogates_are_searched_with_re(re_searches):
    # surrogateescape gives the bytes of command-line arguments that aren't
    # UTF-8 to Python as lone surrogates, which UTF-8 can't encode
    with pytest.raises(UnicodeEncodeError):
        regex_identifier._pywhat.Text("\udc80")
    with pytest.raises(UnicodeEncodeError):
        regex_identifier._pywhat.finditer("a", "a\udc80")
    dist = Distribution({"Tags": ["TryHackMe Flag Format"]})
    found = RegexIdentifier().check(["\udc80\nthm{a}"], dist=dist)
    assert [match["Matched"] for match in found] == ["thm{a}"]
    assert len(re_searches) == len(dist.get_regexes())


def test_backtracking_limit_falls_back_to_re(re_searches):
    with pytest.raises(regex_identifier._pywhat.MatchError):
        regex_identifier._pywhat.finditer(BACKTRACKING, BACKTRACKING_TEXT)
    dist = one_regex("TryHackMe Flag Format", BACKTRACKING)
    found = RegexIdentifier().check([BACKTRACKING_TEXT], dist=dist)
    assert [match["Matched"] for match in found] == ["ac"]
    assert re_searches == [BACKTRACKING]


def test_patterns_the_engine_cant_compile_fall_back_to_re(re_searches):
    # Python's ASCII-only flag, which the regex crate doesn't have
    pattern = r"(?a)\w+"
    with pytest.raises(ValueError):
        regex_identifier._pywhat.finditer(pattern, "é ab")
    dist = one_regex("TryHackMe Flag Format", pattern)
    found = RegexIdentifier().check(["é ab"], dist=dist)
    assert [match["Matched"] for match in found] == ["ab"]
    assert re_searches == [pattern]


def test_version_is_the_installed_one():
    assert pywhat.__version__ == version("pywhat")
