import re
from typing import List, Tuple

import pytest

from pywhat import regex_identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import load_regexes

database = load_regexes()
r = regex_identifier.RegexIdentifier()
dist = Distribution(Filter({"MinRarity": 0.0}))


def _assert_match_first_item(name, res):
    assert name in res[0]["Regex Pattern"]["Name"]
    # TODO:
    # - http://10.1.1.1 == ip


def _assert_match_exploit_first_item(search, res):
    assert search in res[0]["Regex Pattern"]["Exploit"]


def test_regex_successfully_parses():
    regexes = r.distribution.get_regexes()
    assert type(regexes) == list
    assert len(regexes) != 0
    regex = regexes[0]
    assert type(regex) == dict
    for key in [
        "Name",
        "Regex",
        "plural_name",
        "Description",
        "Rarity",
        "URL",
        "Tags",
        "Examples",
    ]:
        assert key in regex


def _assert_match_in_items(name, res):
    assert any(name in i["Regex Pattern"]["Name"] for i in res)


def regex_valid_match(name: str, match: str) -> bool:
    return any(
        name in matched["Regex Pattern"]["Name"]
        for matched in r.check([match], dist=dist)
    )


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


@pytest.mark.parametrize(
    "name,match",
    [
        (regex["Name"], match)
        for regex in database
        for match in regex.get("Examples", {}).get("Valid", [])  # not in all entries
    ],
)
def test_regex_valid_match(name: str, match: str):
    assert regex_valid_match(name, match)


@pytest.mark.parametrize(
    "name,match",
    [
        (regex["Name"], match)
        for regex in database
        for match in regex.get("Examples", {}).get("Invalid", [])  # not in all entries
    ],
)
def test_regex_invalid_match(name: str, match: str):
    assert not regex_valid_match(name, match)


def test_ip():
    res = r.check(
        ["http://10.1.1.1/just/a/test"],
        boundaryless=Filter({"Tags": ["Identifiers"]}),
    )
    _assert_match_first_item("Uniform Resource Locator (URL)", res)
    assert "Internet Protocol (IP) Address Version 4" in res[1]["Regex Pattern"]["Name"]


@pytest.mark.parametrize(
    "match", ["00:00:00:00:00:00", "00-00-00-00-00-00", "0000.0000.0000"]
)
def test_mac(match: str):
    res = r.check([match])
    assert (
        res
        and match in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
        and "Xerox Corp" in res[0]["Regex Pattern"]["Description"]
    )


@pytest.mark.parametrize(
    "match", ["00-00-00-00.00-00", "00:00-00-00-00-00", "00:00:0G:00:00:00"]
)
def test_mac4(match: str):
    res = r.check([match])
    assert (
        not res
        or res[0]["Regex Pattern"]["Name"]
        != "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


@pytest.mark.skip(
    reason="Fails because not a valid TLD. If presented in punycode, it works."
)
def test_international_url():
    res = r.check(["http://папироска.рф"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


@pytest.mark.parametrize("match", ["5409010000000004", "5409 0100 0000 0004"])
def test_master_card(match: str):
    res = r.check([match])
    _assert_match_first_item("MasterCard Number", res)
    assert "UNION NATIONAL BANK" in res[0]["Regex Pattern"]["Description"]


@pytest.mark.skip("Key:Value Pair is not ran by default because of low rarity.")
def test_username():
    res = r.check(["james:S3cr37_P@$$W0rd"])
    _assert_match_first_item("Key:Value Pair", res)


@pytest.mark.parametrize(
    "match,description",
    [
        ("+1-202-555-0156", "United States"),
        ("+662025550156", "Thailand"),
        ("+356 202 555 0156", "Malta"),
    ],
)
def test_phone_number2(match: str, description: str):
    res = r.check([match])
    _assert_match_first_item("Phone Number", res)
    assert description in res[0]["Regex Pattern"]["Description"]


@pytest.mark.parametrize(
    "match, exploit",
    [
        (
            "xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v",
            "https://slack.com/api/auth.test?token=xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v",
        ),
        (
            "xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ",
            "https://slack.com/api/auth.test?token=xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ",
        ),
    ],
)
def test_match_exploit_first_item(match: str, exploit: str):
    _assert_match_exploit_first_item(exploit, r.check([match]))
