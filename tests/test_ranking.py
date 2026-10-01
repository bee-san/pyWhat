import glob
import io
import json
import math
import os
import re
from decimal import Decimal

import pytest
from click.testing import CliRunner
from rich.console import Console

from pywhat import Filter, Identifier, identifier
from pywhat.helper import FRAGMENT, Keys, likelihood, str_to_key
from pywhat.interactive import NO_MORE, NOTHING_LOADED, InteractiveShell
from pywhat.ranking import (
    SUGGESTED_TOP,
    Top,
    group_by_location,
    inside_word,
    located_matches,
    mark_fragments,
    most_likely_first,
    parse_top,
    select,
    top_matches,
)
from pywhat.regex_identifier import RegexIdentifier
from pywhat.what import main

ETHEREUM = "0x52908400098527886E0F7030069857D2E4169EE7"


def match(name, rarity, fragment=None, matched="x"):
    found = {"Matched": matched, "Regex Pattern": {"Name": name, "Rarity": rarity}}
    if fragment is not None:
        found[FRAGMENT] = fragment
    return found


def names(matches):
    return [found["Regex Pattern"]["Name"] for found in matches]


def cli_runner():
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:  # Click 8.2 always keeps stdout and stderr apart
        return CliRunner()


def run_cli(args, input=None):
    result = cli_runner().invoke(main, args, input=input)
    assert result.exit_code == 0, result.output
    return result


def identify_json(args):
    """The matches that pywhat --json prints for args."""
    return json.loads(run_cli(["--json", *args]).stdout)


def run_shell(*commands, text_input="fixtures/file", **options):
    """
    Run interactive mode with the commands. Returns the shell and the output
    of each command, after the output of starting (and loading text_input).
    """
    stdout = io.StringIO()
    shell = InteractiveShell(
        stdin=io.StringIO("".join(command + "\n" for command in commands)),
        stdout=stdout,
        console=Console(
            file=stdout,
            width=200,
            highlight=False,
            color_system=None,
            force_terminal=False,
        ),
        **options,
    )
    shell.run(text_input)
    return shell, stdout.getvalue().split(InteractiveShell.prompt)


def matched_texts(output):
    return re.findall(r"^Matched on: (.*)$", output, re.MULTILINE)


# Fragments


@pytest.mark.parametrize(
    "text, span, expected",
    [
        ("abc 123 def", (4, 7), False),
        ("abc123def", (3, 6), True),
        ("abc123 def", (3, 6), True),
        ("abc 123def", (4, 7), True),
        ("123", (0, 3), False),
        ("x_123", (2, 5), True),
        ("(123)", (1, 4), False),
        ("THM{hello}", (0, 10), False),
        ("abcdTHM{hello}plze", (4, 14), True),
        # The match does not start or end with a letter or digit
        ("a{b}c", (1, 4), False),
        ("é123", (1, 4), True),
        ("abc", (1, 1), False),
    ],
)
def test_inside_word(text, span, expected):
    assert inside_word(text, span) == expected


def test_mark_fragments():
    text = "email github@skerritt.blog, see skerritt.blog"
    email = match("Email Address", 0.5)
    url_in_email = match("Uniform Resource Locator (URL)", 0.7)
    url = match("Uniform Resource Locator (URL)", 0.7)
    found = [
        (email, (6, 26)),
        (url_in_email, (13, 26)),
        (url, (32, 45)),
    ]
    mark_fragments(text, found)
    assert email[FRAGMENT] is False
    assert url_in_email[FRAGMENT] is True
    assert url[FRAGMENT] is False


def test_mark_fragments_same_start():
    text = "4111111111111111"
    card = match("Visa Card Number", 0.3)
    phone = match("Phone Number", 0.5)
    same = match("American Express Card Number", 0.3)
    mark_fragments(text, [(phone, (0, 13)), (card, (0, 16)), (same, (0, 16))])
    assert phone[FRAGMENT] is True
    # Matches of the same text are not fragments of each other
    assert card[FRAGMENT] is False
    assert same[FRAGMENT] is False


def test_mark_fragments_ignores_rarity_0_matches():
    # Matches with a rarity of 0 match almost anything
    text = "key: github@skerritt.blog"
    key_value = match("Key:Value Pair", 0)
    email = match("Email Address", 0.5)
    mark_fragments(text, [(key_value, (0, 25)), (email, (5, 25))])
    assert email[FRAGMENT] is False
    assert key_value[FRAGMENT] is False


def test_mark_fragments_of_several_containers():
    # The container that ends last is not the one that starts last
    text = "aaaa bbbb cccc"
    long = match("Long", 0.5)
    short = match("Short", 0.5)
    inside = match("Inside", 0.5)
    mark_fragments(text, [(long, (0, 14)), (short, (5, 9)), (inside, (10, 14))])
    assert [long[FRAGMENT], short[FRAGMENT], inside[FRAGMENT]] == [False, True, True]


def test_identify_marks_fragments():
    out = Identifier(boundaryless=Filter()).identify(ETHEREUM)
    fragments = {
        found["Regex Pattern"]["Name"]: found[FRAGMENT]
        for found in out["Regexes"]["text"]
    }
    assert fragments["Ethereum (ETH) Wallet Address"] is False
    assert fragments["Phone Number"] is True


def test_fragments_of_each_text():
    # A file is searched as several texts (e.g. its UTF-16 strings), the
    # matches of one text are not inside the matches of another one
    found = RegexIdentifier().check(
        ["skerritt.blog", "github@skerritt.blog"], boundaryless=Filter()
    )
    fragments = [
        (found["Matched"], found[FRAGMENT])
        for found in found
        if found["Regex Pattern"]["Name"]
        in ("Uniform Resource Locator (URL)", "Email Address")
    ]
    assert sorted(fragments) == [
        ("github@skerritt.blog", False),
        ("skerritt.blog", False),
        ("skerritt.blog", True),
    ]


def test_boundaries_mean_no_fragments():
    # Without boundaryless mode (the default of the API), every match is a
    # whole line
    out = Identifier().identify(ETHEREUM)
    assert "Ethereum (ETH) Wallet Address" in names(out["Regexes"]["text"])
    assert not any(found[FRAGMENT] for found in out["Regexes"]["text"])


# The order


def test_likelihood():
    assert likelihood(match("A", 0.7)) < likelihood(match("B", 0.5))
    # Fragments are less likely, unless their rarity is 1
    assert likelihood(match("A", 0.3, False)) < likelihood(match("B", 0.5, True))
    assert likelihood(match("A", 1, True)) == likelihood(match("B", 1, False))
    assert likelihood(match("A", 1, True)) < likelihood(match("B", 0.7, False))
    # Matches without the key (e.g. created by a processor) are not fragments
    assert likelihood(match("A", 0.5)) == likelihood(match("B", 0.5, False))


def test_likely_key():
    assert str_to_key("likely") == Keys.LIKELY
    matches = [
        match("Phone Number", 0.5, True),
        match("Ethereum (ETH) Wallet Address", 0.3, False),
        match("TryHackMe Flag Format", 1, True),
        match("Turkish Identification Number", 0.2, True),
        match("Email Address", 0.5, False),
    ]
    assert names(sorted(matches, key=Keys.LIKELY)) == [
        "TryHackMe Flag Format",
        "Email Address",
        "Ethereum (ETH) Wallet Address",
        "Phone Number",
        "Turkish Identification Number",
    ]


def test_identify_with_likely_key():
    out = Identifier(boundaryless=Filter()).identify(ETHEREUM, key=Keys.LIKELY)
    assert out["Regexes"]["text"][0]["Regex Pattern"]["Name"] == (
        "Ethereum (ETH) Wallet Address"
    )


def test_most_likely_first_is_stable():
    found = [
        ("a", match("First", 0.5)),
        ("b", match("Rare", 1)),
        ("a", match("Second", 0.5)),
        ("b", match("Third", 0.5)),
    ]
    assert [pair[1]["Regex Pattern"]["Name"] for pair in most_likely_first(found)] == [
        "Rare",
        "First",
        "Second",
        "Third",
    ]


# How many matches


@pytest.mark.parametrize(
    "top, expected",
    [
        (10, Top(number=10)),
        ("10", Top(number=10)),
        (" 3 ", Top(number=3)),
        ("5%", Top(percent=Decimal("5"))),
        ("0.5%", Top(percent=Decimal("0.5"))),
        (".5 %", Top(percent=Decimal("0.5"))),
        ("100%", Top(percent=Decimal("100"))),
        ("all", Top()),
        ("ALL", Top()),
        (Top(number=2), Top(number=2)),
    ],
)
def test_parse_top(top, expected):
    assert parse_top(top) == expected


@pytest.mark.parametrize(
    "top", [0, "0", "-1", "", "abc", "1.5", "0%", "150%", "5%%", "1e3", "%"]
)
def test_parse_invalid_top(top):
    with pytest.raises(ValueError, match="Invalid top"):
        parse_top(top)


@pytest.mark.parametrize(
    "top, total, expected",
    [
        ("10", 157, 10),
        ("10", 3, 3),
        ("5%", 157, 8),
        ("5%", 214, 11),
        ("5%", 1, 1),
        ("1.1%", 1000, 11),
        ("100%", 7, 7),
        ("5%", 0, 0),
        ("all", 157, 157),
    ],
)
def test_top_of(top, total, expected):
    assert parse_top(top).of(total) == expected


@pytest.mark.parametrize("top", ["10", "5%", "0.5%", "all"])
def test_top_str(top):
    assert str(parse_top(top)) == top
    assert parse_top(str(parse_top(top))) == parse_top(top)


def test_top_is_all():
    assert Top().is_all
    assert not Top(number=1).is_all
    assert not Top(percent=Decimal(1)).is_all


# Selecting the top matches

FOUND = [
    ("/a", match("A1", 0.3)),
    ("/b", match("B1", 1)),
    ("/a", match("A2", 0.7)),
    ("/b", match("B2", 0.5, True)),
    ("/a", match("A3", 0.5)),
]


def test_select():
    assert [found["Regex Pattern"]["Name"] for _, found in select(FOUND, Top(3))] == [
        "B1",
        "A2",
        "A3",
    ]
    # The next ones
    assert [
        found["Regex Pattern"]["Name"] for _, found in select(FOUND, Top(3), 3)
    ] == ["A1", "B2"]
    assert select(FOUND, Top(3), 6) == []
    # All of them, in the order they were found
    assert select(FOUND, Top()) == FOUND
    assert select(FOUND, Top(), 2) == FOUND[2:]


def test_located_matches_and_group_by_location():
    identified = {
        "File Signatures": None,
        "Regexes": {"/a": [FOUND[0][1], FOUND[2][1]], "/b": [FOUND[1][1]]},
    }
    assert located_matches(identified) == [FOUND[0], FOUND[2], FOUND[1]]
    assert located_matches({"File Signatures": None, "Regexes": None}) == []
    assert group_by_location(FOUND) == {
        "/a": [FOUND[0][1], FOUND[2][1], FOUND[4][1]],
        "/b": [FOUND[1][1], FOUND[3][1]],
    }
    grouped = group_by_location(FOUND, Keys.NAME, reverse=True)
    assert list(grouped) == ["/a", "/b"]
    assert names(grouped["/a"]) == ["A3", "A2", "A1"]


def test_top_matches():
    identified = {
        "File Signatures": {"/a": {"ISO 8859-1": "x", "Description": "y"}},
        "Regexes": group_by_location(FOUND),
    }
    top = top_matches(identified, 3)
    # The file with the most likely match is first
    assert list(top["Regexes"]) == ["/b", "/a"]
    assert names(top["Regexes"]["/b"]) == ["B1"]
    assert names(top["Regexes"]["/a"]) == ["A2", "A3"]
    assert top["File Signatures"] == identified["File Signatures"]
    # identified is not changed
    assert len(located_matches(identified)) == 5

    assert names(top_matches(identified, "40%")["Regexes"]["/b"]) == ["B1"]
    assert names(top_matches(identified, 2, start=3)["Regexes"]["/a"]) == ["A1"]
    top = top_matches(identified, 3, key=Keys.NAME, reverse=True)
    assert names(top["Regexes"]["/a"]) == ["A3", "A2"]
    assert top_matches(identified, "all") == identified
    assert top_matches(identified, 3, start=5)["Regexes"] is None


def test_top_matches_without_matches():
    identified = {"File Signatures": None, "Regexes": None}
    assert top_matches(identified, 10) == identified


def test_top_matches_of_identify():
    out = Identifier(boundaryless=Filter()).identify(ETHEREUM)
    top = top_matches(out, 1)
    assert names(top["Regexes"]["text"]) == ["Ethereum (ETH) Wallet Address"]


def test_top_matches_of_a_directory():
    # The most likely matches of all files
    out = Identifier().identify("fixtures", only_text=False)
    found = located_matches(out)
    assert len(out["Regexes"]) == 2
    for top in (1, 5, len(found) - 1):
        shown = located_matches(top_matches(out, top))
        assert sorted(id(pair[1]) for pair in shown) == sorted(
            id(pair[1]) for pair in most_likely_first(found)[:top]
        )


# Sorting with --key (issue #232)


def test_sorting_without_matches():
    # Used to raise TypeError: 'NoneType' object is not subscriptable
    out = Identifier().identify("nothing to see here", key=Keys.NAME)
    assert out == {"File Signatures": None, "Regexes": None}


def write_directory(tmp_path, empty_file=True):
    # The found order is not sorted by name
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_text("THM{hello} github@skerritt.blog 10.0.0.1\n")
    if empty_file:
        (tmp_path / "z.txt").write_text("nothing to see here\n")


@pytest.fixture
def sorted_glob(monkeypatch):
    """Find the files of a directory in alphabetical order."""
    iglob = glob.iglob

    def sorted_iglob(*args, **kwargs):
        return iter(sorted(iglob(*args, **kwargs)))

    monkeypatch.setattr(identifier.glob, "iglob", sorted_iglob)


@pytest.mark.usefixtures("sorted_glob")
@pytest.mark.parametrize("empty_file", [True, False])
def test_sorting_every_file(tmp_path, empty_file):
    # Only the matches of the last file used to be sorted, and if the last
    # file (z.txt) has none: KeyError
    write_directory(tmp_path, empty_file)
    out = Identifier(boundaryless=Filter()).identify(
        str(tmp_path), only_text=False, key=Keys.NAME
    )
    assert sorted(out["Regexes"]) == [os.sep + "a.txt", os.sep + "b.txt"]
    for matches in out["Regexes"].values():
        assert names(matches) == sorted(names(matches))
        assert len(matches) > 2


@pytest.mark.usefixtures("sorted_glob")
def test_cli_sorting_every_file(tmp_path):
    write_directory(tmp_path)
    result = run_cli(["-k", "name", "--format", "%n", str(tmp_path)])
    found = result.stdout.splitlines()
    assert len(found) % 2 == 0
    half = len(found) // 2
    assert found[:half] == sorted(found[:half])
    assert found[half:] == found[:half]


# The command line


def test_cli_top():
    result = run_cli(["--top", "1", ETHEREUM])
    assert matched_texts(result.stdout) == [ETHEREUM]
    assert "Ethereum (ETH) Wallet Address" in result.stdout
    assert "Phone Number" not in result.stdout
    total = len(identify_json([ETHEREUM])["Regexes"]["text"])
    assert f"Showing the 1 most likely of {total} matches." in result.stderr


def test_cli_top_percent():
    total = len(located_matches(identify_json(["fixtures/file"])))
    top = identify_json(["--top", "5%", "fixtures/file"])
    assert len(top["Regexes"]["file"]) == math.ceil(total * 5 / 100)
    assert top["Regexes"]["file"] == sorted(top["Regexes"]["file"], key=likelihood)


def test_cli_top_json():
    result = run_cli(["--top", "3", "--json", "fixtures"])
    # Only the matches are on stdout
    top = json.loads(result.stdout)
    assert len(located_matches(top)) == 3
    # The most likely matches of all files
    assert list(top["Regexes"]) == [os.sep + "file"]
    for found in top["Regexes"][os.sep + "file"]:
        assert found["Regex Pattern"]["Rarity"] == 1
    assert "Showing the 3 most likely of" in result.stderr


def test_cli_top_and_key():
    top = identify_json(["--top", "5", "fixtures/file"])["Regexes"]["file"]
    by_name = identify_json(["--top", "5", "-k", "name", "fixtures/file"])
    assert by_name["Regexes"]["file"] == sorted(top, key=Keys.NAME)


def test_cli_top_without_matches():
    result = run_cli(["--top", "10", "nothing to see here"])
    assert "Nothing found!" in result.stdout
    assert result.stderr == ""


@pytest.mark.parametrize("top", ["all", "100000"])
def test_cli_top_of_all_matches(top):
    # Nothing is left out, and the output is the same as without --top
    # (the matches of --top 100000 are most likely first)
    result = run_cli(["--top", top, "--json", "fixtures"])
    assert result.stderr == ""
    expected = identify_json(["fixtures"])
    if top == "all":
        assert json.loads(result.stdout) == expected
    else:
        assert len(located_matches(json.loads(result.stdout))) == len(
            located_matches(expected)
        )


@pytest.mark.parametrize("top", ["0", "150%", "abc"])
def test_cli_invalid_top(top):
    result = cli_runner().invoke(main, ["--top", top, "THM{hello}"])
    assert result.exit_code == 1
    assert f"Invalid top '{top}'" in result.stdout


def test_cli_likely_key():
    result = run_cli(["-k", "likely", "--format", "%n", ETHEREUM])
    assert result.stdout.splitlines()[0] == "Ethereum (ETH) Wallet Address"


def test_cli_default_order_is_unchanged():
    # Without --top or --key, the matches are in the order they were found
    out = Identifier(dist=None, boundaryless=Filter()).identify(ETHEREUM)
    result = run_cli(["--format", "%n", ETHEREUM])
    assert result.stdout.splitlines() == names(out["Regexes"]["text"])


def test_cli_sorting_without_matches():
    result = run_cli(["-k", "rarity", "nothing to see here"])
    assert "Nothing found!" in result.stdout


def test_cli_help():
    result = run_cli(["--help"])
    assert "--top N" in result.stdout
    assert "Top matches:" in result.stdout
    assert "likely - Sort the most likely matches first" in result.stdout


# Interactive mode


def test_interactive_top_and_more():
    shell, outputs = run_shell('include:"CTF Flag"', "top 2", "more", "more", "more")
    found = len(shell.search())
    assert found == len(matched_texts(outputs[1])) > 4
    assert f"Showing the 2 most likely of {found} matches." in outputs[2]
    assert "Type 'more' to see the next 2." in outputs[2]
    assert len(matched_texts(outputs[2])) == 2
    assert f"Showing matches 3 to 4 of {found}." in outputs[3]
    assert len(matched_texts(outputs[3])) == 2
    # Every match is shown once
    shown = []
    output = 2
    while NO_MORE not in outputs[output]:
        shown += matched_texts(outputs[output])
        output += 1
    assert sorted(shown) == sorted(matched_texts(outputs[1]))


def test_interactive_top_shows_the_most_likely_matches():
    shell, outputs = run_shell("top 3")
    likely = sorted((found for _, found in shell.search()), key=likelihood)
    shown = re.findall(r"^Name: (.*)$", outputs[1], re.MULTILINE)
    assert shown == names(likely[:3])
    assert "Search: " in outputs[1]


def test_interactive_more_shows_the_rest():
    shell, outputs = run_shell("include:Email", "top 2", "more", "more")
    found = len(shell.search())
    assert found == 3
    assert f"Showing matches 3 to 3 of {found}." in outputs[3]
    assert "Type 'more'" not in outputs[3]
    assert NO_MORE in outputs[4]


def test_interactive_top_percent():
    shell, outputs = run_shell("top 5%")
    found = len(shell.search())
    shown = math.ceil(found * 5 / 100)
    assert len(matched_texts(outputs[1])) == shown
    assert f"Showing the {shown} most likely of {found} matches." in outputs[1]


def test_interactive_top_of_a_directory():
    shell, outputs = run_shell("top 1", "rarity:0.7", text_input="fixtures")
    # The most likely matches of all files
    assert "File: " + os.sep + "file" in outputs[1]
    assert "File: " + os.sep + os.path.join("test", "file") not in outputs[1]
    assert len(matched_texts(outputs[2])) == 1


def test_interactive_new_search_starts_again():
    _, outputs = run_shell("top 1", "more", "include:Email")
    assert "Showing matches 2 to 2" in outputs[2]
    assert "Showing the 1 most likely of 3 matches." in outputs[3]


def test_interactive_top_all():
    shell, outputs = run_shell("top 2", "top all", "more", "top")
    assert len(matched_texts(outputs[2])) == len(shell.search())
    assert "Showing" not in outputs[2]
    assert "All matches of the search are shown." in outputs[3]
    assert "Searches show all of their matches." in outputs[4]


def test_interactive_describe_top():
    _, outputs = run_shell("top", "top 10", "top", "top 5%", "top", text_input=None)
    assert "Searches show all of their matches." in outputs[1]
    assert "Searches show the most likely 10 matches" in outputs[3]
    assert "Searches show the most likely 5% of their matches" in outputs[5]


def test_interactive_invalid_top():
    shell, outputs = run_shell("top 2", "top 0", "more")
    assert "Invalid top '0'" in outputs[2]
    # The top is not changed
    assert shell.top == Top(2)
    assert "Showing matches 3 to 4" in outputs[3]


def test_interactive_more_when_nothing_is_loaded():
    _, outputs = run_shell("more", "top 1", "more", text_input=None)
    assert NOTHING_LOADED in outputs[1]
    assert NOTHING_LOADED in outputs[3]


def test_interactive_more_without_top():
    _, outputs = run_shell("more")
    assert "All matches of the search are shown." in outputs[1]


def test_interactive_suggests_top():
    # "There are 157 results, would you like to only show the top 10?"
    shell, outputs = run_shell("search", "search", 'include:"CTF Flag"')
    found = len(shell.search())
    suggestion = (
        f"Type 'top {SUGGESTED_TOP}' to only see the {SUGGESTED_TOP} most likely"
    )
    assert suggestion in outputs[1]
    # Only once
    assert suggestion not in outputs[2]
    assert found < 20
    assert suggestion not in outputs[3]


def test_interactive_does_not_suggest_top_for_few_matches():
    _, outputs = run_shell('include:"CTF Flag"')
    assert "Type 'top" not in outputs[1]


def test_interactive_top_option():
    shell, outputs = run_shell("search", "more", top="2")
    assert shell.top == Top(2)
    assert len(matched_texts(outputs[1])) == 2
    assert "Showing matches 3 to 4" in outputs[2]


def test_interactive_more_does_not_show_file_signatures_again(tmp_path):
    image = tmp_path / "flags.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n\nTHM{a}\nTHM{b}\nTHM{c}\n")
    _, outputs = run_shell("top 1", "more", text_input=str(image))
    assert "File Identified: flags.png" in outputs[1]
    assert matched_texts(outputs[1]) == ["THM{a}"]
    assert "File Identified" not in outputs[2]
    assert matched_texts(outputs[2]) == ["THM{b}"]


def test_interactive_load_starts_again():
    shell, outputs = run_shell("top 1", "more", "load fixtures/file", "more")
    assert "Showing matches 2 to 2" in outputs[2]
    assert "Showing the 1 most likely of" in outputs[4]


def test_interactive_top_json():
    _, outputs = run_shell("top 2", json_output=True)
    identified = json.loads(
        next(line for line in outputs[1].splitlines() if line.startswith("{"))
    )
    assert len(identified["Regexes"]["file"]) == 2


def test_interactive_top_and_key():
    shell, outputs = run_shell("top 4", key=Keys.NAME)
    likely = sorted((found for _, found in shell.search()), key=likelihood)[:4]
    shown = re.findall(r"^Name: (.*)$", outputs[1], re.MULTILINE)
    assert shown == sorted(names(likely))


def test_interactive_top_completion():
    shell, _ = run_shell()
    assert shell.complete_top("", "top ", 4, 4) == [str(SUGGESTED_TOP), "5%", "all"]
    assert shell.complete_top("a", "top a", 4, 5) == ["all"]
    assert "top" in shell.completenames("to", "to", 0, 2)
    assert "more" in shell.completenames("mo", "mo", 0, 2)


def test_interactive_help():
    _, outputs = run_shell("help", "help top", "help more")
    assert "top" in outputs[1] and "more" in outputs[1]
    assert outputs[2].startswith("top [N, N% or all]\n")
    assert outputs[3].startswith("more\n")


def test_cli_interactive_top():
    result = run_cli(
        ["--interactive", "--top", "1", "fixtures/file"],
        input='include:"CTF Flag"\nmore\n',
    )
    assert "Showing the 1 most likely of" in result.stdout
    assert "Showing matches 2 to 2 of" in result.stdout


def test_cli_interactive_invalid_top():
    result = cli_runner().invoke(main, ["--interactive", "--top", "0", "fixtures"])
    assert result.exit_code == 1
    assert "Invalid top '0'" in result.stdout
