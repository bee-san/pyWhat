import re
from typing import List, Tuple

import pytest

from pywhat import regex_identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import load_regexes

database = load_regexes()
r = regex_identifier.RegexIdentifier()
filter1 = Filter({"MinRarity": 0.0})
d = Distribution(filter1)
r_rarity_0 = regex_identifier.RegexIdentifier()


def _assert_match_first_item(name, res):
    assert name in res[0]["Regex Pattern"]["Name"]
    # TODO:
    # - http://10.1.1.1 == ip


def _assert_match_exploit_first_item(search, res):
    assert search in res[0]["Regex Pattern"]["Exploit"]


def test_regex_successfully_parses():
    assert "Name" in r.distribution.get_regexes()[0]


def _assert_match_in_items(name, res):
    assert any(name in i["Regex Pattern"]["Name"] for i in res)


def regex_valid_match(name: str, match: str) -> bool:
    return any(name in matched["Regex Pattern"]["Name"] for matched in r.check([match]))


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


def test_visual_studio_token():
    res = r.check(["4435bc4358816be97a3f014499116c83ab224fb2"])
    _assert_match_in_items("Visual Studio App Center API Token", res)


def test_master_Card():
    res = r.check(["5409010000000004"])
    _assert_match_first_item("MasterCard Number", res)
    assert "UNION NATIONAL BANK" in res[0]["Regex Pattern"]["Description"]


def test_master_card_spaces():
    res = r.check(["5409 0100 0000 0004"])
    _assert_match_first_item("MasterCard Number", res)
    assert "UNION NATIONAL BANK" in res[0]["Regex Pattern"]["Description"]


def test_american_diners_club():
    res = r.check(["30000000000004"])
    assert "Diners Club Card Number" in res[1]["Regex Pattern"]["Name"]


@pytest.mark.skip("Key:Value Pair is not ran by default because of low rarity.")
def test_username():
    res = r.check(["james:S3cr37_P@$$W0rd"])
    _assert_match_first_item("Key:Value Pair", res)


def test_email3():
    res = r.check(
        ["john.smith@[123.123.123.123]"],
        boundaryless=Filter({"Tags": ["Identifiers"]}),
    )
    assert "Email Address" in res[2]["Regex Pattern"]["Name"]


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


def test_youtube_id():
    res = r.check(["dQw4w9WgXcQ"], dist=d)
    _assert_match_first_item("YouTube Video ID", res)


@pytest.mark.parametrize(
    "match, valid, valid_recent",
    [
        ("1577836800", True, True),  # 2020-01-01
        ("94694400", True, False),  # 1973-01-01
        ("1234567", False, False),  # 7 numbers
    ],
)
def test_unix_timestamp(match: str, valid: bool, valid_recent: bool):
    res = r.check([match], dist=d)
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert ("Unix Timestamp" in keys) == valid
    assert ("Recent Unix Timestamp" in keys) == valid_recent


@pytest.mark.parametrize(
    "match, valid, valid_recent",
    [
        ("1577836800000", True, True),  # 2020-01-01
        ("94694400000", True, False),  # 1973-01-01
    ],
)
def test_unix_millisecond_timestamp(match: str, valid: bool, valid_recent: bool):
    res = r.check([match], dist=d)
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert ("Unix Millisecond Timestamp" in keys) == valid
    assert ("Recent Unix Millisecond Timestamp" in keys) == valid_recent


def test_slack_api_key():
    res = r.check(
        ["xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v"]
    )
    _assert_match_first_item("Slack API Key", res)
    _assert_match_exploit_first_item(
        "https://slack.com/api/auth.test?token=xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v",
        res,
    )


def test_slack_token():
    res = r.check(["xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ"])
    _assert_match_first_item("Slack Token", res)
    _assert_match_exploit_first_item(
        "https://slack.com/api/auth.test?token=xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ",
        res,
    )
