import json
import re

import pytest

from pywhat.helper import (
    AvailableTags,
    CaseInsensitiveSet,
    available_names,
    get_names,
    join_regexes,
    load_regexes,
    split_tags,
)

database = load_regexes()


@pytest.mark.skip(
    reason="Not all regex have tests now, check https://github.com/bee-san/pyWhat/pull/146#issuecomment-927087231 for info."
)
def test_if_all_tests_exist():
    with open("tests/test_regex_identifier.py", "r", encoding="utf-8") as file:
        tests = file.read()

    for regex in database:
        assert (
            regex["Name"] in tests
        ), "No test for this regex found in 'test_regex_identifier.py'. Note that a test needs to assert the whole name."


def test_name_capitalization():
    # The alternative names too
    for entry_name in (name for entry in database for name in get_names(entry)):
        for word in entry_name.split():
            upper_and_num_count = sum(1 for c in word if c.isupper() or c.isnumeric())
            if upper_and_num_count > 0:
                continue
            cleaned_word = word.translate({ord(c): None for c in "(),."})
            if cleaned_word in ["a", "of", "etc"]:
                continue

            assert word.title() == word, (
                f'Wrong capitalization in regex name: "{entry_name}"\n'
                f'Expected: "{entry_name.title()}"\n'
                "Please capitalize the first letter of each word."
            )


def test_alternative_names_format():
    # "Alternative Names" is optional (issue #184)
    for entry in database:
        if "Alternative Names" not in entry:
            continue
        names = entry["Alternative Names"]
        assert isinstance(names, list) and names, (
            f"'Alternative Names' of {entry['Name']} should be a list of names. "
            "Leave it out if the regex has no other names."
        )
        for name in names:
            assert isinstance(name, str) and name.strip() == name != "", (
                f"Alternative name {name!r} of {entry['Name']} should be a "
                "non-empty string without surrounding whitespace."
            )


def test_names_and_tags_can_be_listed():
    # --include and --exclude take comma separated lists of tags and names
    values = [*AvailableTags().get_tags(), *available_names()]
    for value in values:
        assert split_tags(f"{value},{value}") == [value, value], (
            f'"{value}" cannot be in a comma separated list. Commas are only '
            "allowed in parentheses."
        )


def test_names_are_unique():
    # A name or an alternative name is the name of a single regex, whatever
    # its case
    owners: dict = {}
    for entry in database:
        names = get_names(entry)
        assert len({name.lower() for name in names}) == len(
            names
        ), f'"{entry["Name"]}" has the same name more than once: {names}'
        for name in names:
            owner = owners.setdefault(name.lower(), entry["Name"])
            assert (
                owner == entry["Name"]
            ), f'"{name}" is a name of both "{owner}" and "{entry["Name"]}".'


def test_names_that_are_tags():
    # Names work like tags in filters. A name that is a tag too (such as
    # "Email Address") has to be a tag of its regex, so that filtering by the
    # tag still finds exactly the regexes with the tag.
    tags = CaseInsensitiveSet(AvailableTags().get_tags())
    for entry in database:
        for name in get_names(entry):
            assert name not in tags or name in CaseInsensitiveSet(entry["Tags"]), (
                f'"{name}" is a name of "{entry["Name"]}" and a tag of other regexes. '
                "Add the tag to the regex too, or choose another name."
            )


def test_regex_format():
    # Check the regexes as written in regex.json; "Regex" may be a list
    with open("pywhat/Data/regex.json", "r", encoding="utf-8") as file:
        raw_database = json.load(file)

    for entry in raw_database:
        patterns = entry["Regex"]
        if not isinstance(patterns, list):
            patterns = [patterns]
        for pattern in patterns:
            assert re.findall(
                r"^(?:\(\?i\))?\^\(.*\)\$$", pattern
            ), r"Please use ^(regex)$ regex format. If there is '\n' character, you have to escape it. If there is '(?i)', it is allowed and should be before the '^'."

            assert (
                re.findall(r"\^\||\|\^|\$\|\^|\$\||\|\$", pattern) == []
            ), "Remove in-between boundaries. For example, '^|$' should only be '|'."


@pytest.mark.parametrize(
    "patterns, joined",
    [
        (["^(a)$"], "^(?:(a))$"),
        (["^(a)$", "^(b|c)$"], "^(?:(a)|(b|c))$"),
        (["(?i)^(a)$", "(?i)^(b)$"], "(?i)^(?:(a)|(b))$"),
        (["(?i)^(a)$", "^(B)$"], "^(?:(?i:(a))|(B))$"),
    ],
)
def test_join_regexes(patterns, joined):
    assert join_regexes(patterns) == joined


def test_join_regexes_case_sensitivity():
    regex = join_regexes(["(?i)^(thm{.*})$", "^(FLAG{.*})$"])
    assert re.search(regex, "THM{x}")
    assert re.search(regex, "FLAG{x}")
    assert not re.search(regex, "flag{x}")


def test_join_regexes_rejects_unanchored_regex():
    with pytest.raises(ValueError):
        join_regexes(["^(a)$", "(b)"])


@pytest.mark.parametrize(
    "text, parts",
    [
        ("AWS", ["AWS"]),
        ("", [""]),
        # Like str.split(",") without parentheses
        ("AWS, Bug Bounty,", ["AWS", " Bug Bounty", ""]),
        (
            "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc),UUID",
            ["EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)", "UUID"],
        ),
        ("a (b, (c, d)), e", ["a (b, (c, d))", " e"]),
        ("a), b", ["a)", " b"]),
        ("a (b, c", ["a (b, c"]),
    ],
)
def test_split_tags(text, parts):
    assert split_tags(text) == parts


def test_get_names():
    entry = next(e for e in database if e["Name"] == "Ethereum (ETH) Wallet Address")
    assert get_names(entry) == [
        "Ethereum (ETH) Wallet Address",
        "Ethereum Wallet",
        "ETH Wallet",
    ]
    # "Alternative Names" is optional
    assert get_names({"Name": "Key:Value Pair", "Tags": []}) == ["Key:Value Pair"]


def test_regex_list_is_joined_on_load():
    entry = next(e for e in database if e["Name"] == "TryHackMe Flag Format")
    assert isinstance(entry["Regex"], str)
    assert re.search(entry["Regex"], "thm{a}")
    assert re.search(entry["Regex"], "TryHackMe{a}")
    assert re.search(entry["Boundaryless Regex"], "xx tryhackme{a} yy")


def test_check_keys():
    for entry in database:
        for key in [
            "Name",
            "Regex",
            "plural_name",
            "Description",
            "Rarity",
            "URL",
            "Tags",
            # "Examples", # TODO
        ]:
            assert key in entry, f"{key} is missing in {entry['Name']}"


def test_sorted_by_rarity():
    rarity_num = [regex["Rarity"] for regex in database]

    assert rarity_num == sorted(
        rarity_num, reverse=True
    ), "Regexes should be sorted by rarity in 'regex.json'. Regexes with rarity '1' are at the top of the file and '0' is at the bottom."


def test_no_duplicate_regexes():
    names = [regex["Name"] for regex in database]
    duplicate_names = {name for name in names if names.count(name) > 1}
    assert duplicate_names == set(), (
        ", ".join(duplicate_names) + " present in 'regex.json' more than once."
    )
