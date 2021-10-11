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


def _assert_match_exploit_first_item(search, res):
    assert search in res[0]["Regex Pattern"]["Exploit"]


def test_regex_successfully_parses():
    assert "Name" in r.distribution.get_regexes()[0]


def _assert_match_in_items(name, res):
    assert any(name in i["Regex Pattern"]["Name"] for i in res)


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


def test_regex_format():
    for regex in database:
        assert re.findall(
            r"^(?:\(\?i\))?\^\(.*\)\$$", regex["Regex"]
        ), r"Please use ^(regex)$ regex format. If there is '\n' character, you have to escape it. If there is '(?i)', it is allowed and should be before the '^'."

        assert (
            re.findall(r"\^\||\|\^|\$\|\^|\$\||\|\$", regex["Regex"]) == []
        ), "Remove in-between boundaries. For example, '^|$' should only be '|'."


def test_sorted_by_rarity():
    rarity_num = [regex["Rarity"] for regex in database]

    assert rarity_num == sorted(
        rarity_num, reverse=True
    ), "Regexes should be sorted by rarity in 'regex.json'. Regexes with rarity '1' are at the top of the file and '0' is at the bottom."


@pytest.mark.parametrize(
    "name,match",
    [
        (regex["Name"], match)
        for regex in database
        for match in regex.get("Examples", {}).get("Valid", [])  # not in all entries
    ],
)
def test_regex_valid_match(name: str, match: str):
    res = r.check([match])
    _assert_match_first_item(name, res)


@pytest.mark.parametrize(
    "name,match",
    [
        (regex["Name"], match)
        for regex in database
        for match in regex.get("Examples", {}).get("Invalid", [])  # not in all entries
    ],
)
def test_regex_invalid_match(name: str, match: str):
    res = r.check([match])
    assert name not in str(res)


def test_ip():
    res = r.check(
        ["http://10.1.1.1/just/a/test"],
        boundaryless=Filter({"Tags": ["Identifiers"]}),
    )
    _assert_match_first_item("Uniform Resource Locator (URL)", res)
    assert "Internet Protocol (IP) Address Version 4" in res[1]["Regex Pattern"]["Name"]


def test_ip2():
    res = r.check(["192.0.2.235:80"])
    assert "192.0.2.235:80" in res[0]["Matched"]


def test_ip3():
    res = r.check(["2001:0db8:85a3:0000:0000:8a2e:0370:7334"])
    _assert_match_first_item("Internet Protocol (IP) Address Version 6", res)


def test_ip4():
    res = r.check(["[2001:db8::1]:8080"])
    assert "[2001:db8::1]:8080" in res[0]["Matched"]


def test_mac():
    res = r.check(["00:00:00:00:00:00"])
    assert (
        res
        and "00:00:00:00:00:00" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
        and "Xerox Corp" in res[0]["Regex Pattern"]["Description"]
    )


def test_mac2():
    res = r.check(["00-00-00-00-00-00"])
    assert (
        res
        and "00-00-00-00-00-00" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
        and "Xerox Corp" in res[0]["Regex Pattern"]["Description"]
    )


def test_mac3():
    res = r.check(["0000.0000.0000"])
    assert (
        res
        and "0000.0000.0000" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
        and "Xerox Corp" in res[0]["Regex Pattern"]["Description"]
    )


def test_mac4():
    res = r.check(["00-00-00-00.00-00"])
    assert (
        not res
        or res[0]["Regex Pattern"]["Name"]
        != "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac5():
    res = r.check(["00:00-00-00-00-00"])
    assert (
        not res
        or res[0]["Regex Pattern"]["Name"]
        != "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac6():
    res = r.check(["00:00:0G:00:00:00"])
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


def test_phone_number2():
    res = r.check(["+1-202-555-0156"])
    _assert_match_first_item("Phone Number", res)
    assert "United States" in res[0]["Regex Pattern"]["Description"]


def test_phone_number3():
    res = r.check(["+662025550156"])
    _assert_match_first_item("Phone Number", res)
    assert "Thailand" in res[0]["Regex Pattern"]["Description"]


def test_phone_number4():
    res = r.check(["+356 202 555 0156"])
    _assert_match_first_item("Phone Number", res)
    assert "Malta" in res[0]["Regex Pattern"]["Description"]


def test_youtube_id():
    res = r.check(["dQw4w9WgXcQ"], dist=d)
    _assert_match_first_item("YouTube Video ID", res)


def test_unix_timestamp():
    res = r.check(["1577836800"], dist=d)  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" in keys


def test_unix_timestamp2():
    res = r.check(["94694400"], dist=d)  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp3():
    res = r.check(["1234567"], dist=d)  # 7 numbers
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" not in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp4():
    res = r.check(["1577836800000"], dist=d)  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" in keys


def test_unix_timestamp5():
    res = r.check(["94694400000"], dist=d)  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" not in keys


def test_aws_access_key():
    res = r.check(["AKIAIOSFODNN7EXAMPLE"])
    assert "Amazon Web Services Access Key" in str(res)


def test_aws_secret_access_key():
    res = r.check(["Nw0XP0t2OdyUkaIk3B8TaAa2gEXAMPLEMvD2tW+g"])
    assert "Amazon Web Services Secret Access Key" in str(res)


def test_aws_ec2_id():
    res = r.check(["i-1234567890abcdef0"])
    assert "Amazon Web Services EC2 Instance identifier" in str(res)


def test_aws_org_id():
    res = r.check(["o-aa111bb222"])
    assert "Amazon Web Services Organization identifier" in str(res)


def test_aws_sns():
    res = r.check(["arn:aws:sns:us-east-2:123456789012:MyTopic"])
    assert "Amazon SNS Topic" in str(res)


def test_google_cal():
    res = r.check(
        [
            "https://calendar.google.com/calendar/embed?src=ht3jlfaac5lfd6263ulfh4tql8%40group.calendar.google.com&ctz=Europe%2FLondon"
        ]
    )
    assert "Google Calendar URI" in str(res)


def test_notion_note():
    res = r.check(
        ["https://www.notion.so/test-user/My-Note-fa45346d9dd4421abc6857ce2e7fb0db"]
    )
    assert "Notion Note URI" in str(res)


def test_notion_team_note():
    res = r.check(
        ["https://testorg.notion.site/My-Note-9f8863871e024ea6acc64d6564004a22"]
    )
    assert "Notion Team Note URI" in str(res)


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


def test_jcb_card():
    res = r.check(["3537124887293334"])
    _assert_match_first_item("JCB Card Number", res)

    res = r.check(["3543824683332150682"])
    _assert_match_first_item("JCB Card Number", res)


def test_zapier_webhook():
    res = r.check(["https://hooks.zapier.com/hooks/catch/1234567/f8f22dgg/"])
    _assert_match_first_item("Zapier Webhook Token", res)


def test_turkish_id_number():
    res = r.check(["12345678902"])
    assert "Turkish Identification Number" in str(res)


def test_turkish_id_number2():
    res = r.check(["12345678900"])
    assert "Turkish Identification Number" in str(res)


def test_turkish_tax_number():
    res = r.check(["1234567890"], dist=d)
    assert "Turkish Tax Number" in str(res)


def test_uuid():
    res = r.check(["b2ced6f5-2542-4f7d-b131-e3ada95d8b75"])
    assert "UUID" in str(res)


def test_objectid():
    res = r_rarity_0.check(["5fc7c33a7ef88b139122a38a"], dist=d)
    assert "ObjectID" in str(res)


def test_ulid():
    res = r_rarity_0.check(["01ERJ58HMWDN3VTRRHZQV2T5R5"], dist=d)
    assert "ULID" in str(res)
