import re

import pytest

from pywhat import regex_identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes


def test_if_all_tests_exist():
    database = load_regexes()

    with open("tests/test_regex_identifier.py", "r", encoding="utf-8") as file:
        tests = file.read()

    for regex in database:
        assert (
            regex["Name"] in tests
        ), "No test for this regex found in 'test_regex_identifier.py'. Note that a test needs to assert the whole name."


def test_regex_format():
    database = load_regexes()

    for regex in database:
        assert re.findall(
            r"^(?:\(\?i\))?\^\(.*\)\$$", regex["Regex"]
        ), r"Please use ^(regex)$ regex format. If there is '\n' character, you have to escape it. If there is '(?i)', it is allowed and should be before the '^'."

        assert (
            re.findall(r"\^\||\|\^|\$\|\^|\$\||\|\$", regex["Regex"]) == []
        ), "Remove in-between boundaries. For example, '^|$' should only be '|'."


def test_sorted_by_rarity():
    database = load_regexes()
    rarity_num = [regex["Rarity"] for regex in database]

    assert rarity_num == sorted(
        rarity_num, reverse=True
    ), "Regexes should be sorted by rarity in 'regex.json'. Regexes with rarity '1' are at the top of the file and '0' is at the bottom."


def _assert_match_first_item(name, res):
    assert name in res[0]["Regex Pattern"]["Name"]


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    assert "Name" in r.distribution.get_regexes()[0]


def test_dogecoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    _assert_match_first_item("Dogecoin (DOGE) Wallet Address", res)


def test_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["tryhackme.com"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_url_2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://username:password@example.com/"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_invalid_tld():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["tryhackme.comm"])
    assert "Uniform Resource Locator (URL)" not in res


def test_https():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["hTTPs://tryhackme.com"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_lat_long():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["52.6169586, -1.9779857"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["53.76297,-1.9388732"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["77\u00B0 30' 29.9988\" N"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long4():
    r = regex_identifier.RegexIdentifier()
    # degree symbol has to be a unicode character, otherwise Windows will not understand it
    res = r.check(["N 32\u00B0 53.733 W 096\u00B0 48.358"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["41\u00B024'12.2\" N 2\u00B010'26.5\" E"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long6():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["40.741895,-73.989308"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        ["http://10.1.1.1/just/a/test"], boundaryless=Filter({"Tags": ["Identifiers"]})
    )
    _assert_match_first_item("Uniform Resource Locator (URL)", res)
    assert "Internet Protocol (IP) Address Version 4" in res[1]["Regex Pattern"]["Name"]


def test_ip_not_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://10.1.1.1"])
    assert "Uniform Resource Locator (URL)" not in res[0]


def test_ip2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["192.0.2.235:80"])
    assert "192.0.2.235:80" in res[0]["Matched"]


def test_ip3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["2001:0db8:85a3:0000:0000:8a2e:0370:7334"])
    _assert_match_first_item("Internet Protocol (IP) Address Version 6", res)


def test_ip4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["[2001:db8::1]:8080"])
    assert "[2001:db8::1]:8080" in res[0]["Matched"]


def test_mac():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["00:00:00:00:00:00"])
    assert (
        res
        and "00:00:00:00:00:00" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["00-00-00-00-00-00"])
    assert (
        res
        and "00-00-00-00-00-00" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["0000.0000.0000"])
    assert (
        res
        and "0000.0000.0000" in res[0]["Matched"]
        and res[0]["Regex Pattern"]["Name"]
        == "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["00-00-00-00.00-00"])
    assert (
        not res
        or res[0]["Regex Pattern"]["Name"]
        != "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["00:00-00-00-00-00"])
    assert (
        not res
        or res[0]["Regex Pattern"]["Name"]
        != "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
    )


def test_mac6():
    r = regex_identifier.RegexIdentifier()
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
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://папироска.рф"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_same_international_url_in_punycode():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://xn--80aaxitdbjk.xn--p1ai/"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["thm{hello}"])
    _assert_match_first_item("TryHackMe Flag Format", res)


def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["FLAG{hello}"])
    _assert_match_first_item("Capture The Flag (CTF) Flag", res)


def test_htb_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["htb{just_a_test}"])
    _assert_match_first_item("HackTheBox Flag Format", res)


def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["0x52908400098527886E0F7030069857D2E4169EE7"])
    _assert_match_first_item("Ethereum (ETH) Wallet Address", res)


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    _assert_match_first_item("Bitcoin (₿) Wallet Address", res)


def test_monero():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "47DF8D9NwtmefhFUghynYRMqrexiZTsm48T1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFfdaqAT3jnBEwoMwCx6BYDJ1W3ub"
        ]
    )
    _assert_match_first_item("Monero (XMR) Wallet Address", res)


def test_litecoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m"])
    _assert_match_first_item("Litecoin (LTC) Wallet Address", res)


def test_bitcoincash():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"])
    _assert_match_first_item("Bitcoin Cash (BCH) Wallet Address", res)


def test_ripple():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"])
    _assert_match_first_item("Ripple (XRP) Wallet Address", res)


def test_visa():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4111111111111111"])
    _assert_match_first_item("Visa Card Number", res)


def test_visa_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4607 0000 0000 0009"])
    _assert_match_first_item("Visa Card Number", res)


def test_master_Card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5500000000000004"])
    _assert_match_first_item("MasterCard Number", res)


def test_master_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5555 5555 5555 4444"])
    _assert_match_first_item("MasterCard Number", res)


def test_american_express():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["340000000000009"])
    _assert_match_first_item("American Express Card Number", res)


def test_american_express_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3714 4963 5398 431"])
    _assert_match_first_item("American Express Card Number", res)


def test_american_diners_club():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["30000000000004"])
    assert "Diners Club Card Number" in res[1]["Regex Pattern"]["Name"]


def test_american_diners_club_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3056 9309 0259 04"])
    _assert_match_first_item("Diners Club Card Number", res)


def test_discover_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011000000000004"])
    _assert_match_first_item("Discover Card Number", res)


def test_discover_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011 1111 1111 1117"])
    _assert_match_first_item("Discover Card Number", res)


def test_maestro_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5038146401278870"])
    _assert_match_first_item("Maestro Card Number", res)


def test_maestro_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6759 6498 2643 8453"])
    _assert_match_first_item("Maestro Card Number", res)


@pytest.mark.skip("Key:Value Pair is not ran by default because of low rarity.")
def test_username():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["james:S3cr37_P@$$W0rd"])
    _assert_match_first_item("Key:Value Pair", res)


def test_email():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["github@skerritt.blog"])
    _assert_match_first_item("Email Address", res)


def test_email2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["firstname+lastname@example.com"])
    _assert_match_first_item("Email Address", res)


def test_email3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        ["john.smith@[123.123.123.123]"], boundaryless=Filter({"Tags": ["Identifiers"]})
    )
    assert "Email Address" in res[2]["Regex Pattern"]["Name"]


def test_email4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["email@example@example.com"])
    assert "Email Address" not in res


def test_phone_number():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["202-555-0178"])
    _assert_match_first_item("Phone Number", res)


def test_phone_number2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+1-202-555-0156"])
    _assert_match_first_item("Phone Number", res)
    assert "United States" in res[0]["Regex Pattern"]["Description"]


def test_phone_number3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+662025550156"])
    _assert_match_first_item("Phone Number", res)
    assert "Thailand" in res[0]["Regex Pattern"]["Description"]


def test_phone_number4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+356 202 555 0156"])
    _assert_match_first_item("Phone Number", res)
    assert "Malta" in res[0]["Regex Pattern"]["Description"]


def test_youtube():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://www.youtube.com/watch?v=ScOAntcCa78"])
    _assert_match_first_item("YouTube Video", res)


def test_youtube2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube Video", res)


def test_youtube_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube Video ID", res)


def test_youtube_id2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["078-05-1120"])
    assert "YouTube Video ID" not in res


def test_youtube_channel_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["UCjXfkj5iapKHJrhYfAF9ZGg"])
    _assert_match_first_item("YouTube Channel ID", res)


def test_ssn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001-01-0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001:01:0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001.01.0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001 01 0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["900-01-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn6():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["999-21-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn7():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["666-21-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn8():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["000-21-5544"])
    assert "American Social Security Number" not in str(res)


def test_ssn9():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["122-00-5544"])
    assert "American Social Security Number" not in str(res)


def test_ssn10():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["122-32-0000"])
    assert "American Social Security Number" not in str(res)


def test_cors():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["Access-Control-Allow: *"])
    _assert_match_first_item("Access-Control-Allow-Header", res)


def test_jwt():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        ]
    )
    _assert_match_first_item("JSON Web Token (JWT)", res)


def test_s3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://s3.amazonaws.com/bucket/"])
    _assert_match_first_item("Amazon Web Services Simple Storage (AWS S3) URL", res)


def test_s3_internal():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["s3://bucket/path/key"])
    _assert_match_first_item(
        "Amazon Web Services Simple Storage (AWS S3) Internal URL", res
    )


def test_s3_internal2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["s3://bucket/path/directory/"])
    _assert_match_first_item(
        "Amazon Web Services Simple Storage (AWS S3) Internal URL", res
    )


def test_arn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resourcetype/resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resourcetype:resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:aws:s3:::my_corporate_bucket/Development/*"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_unix_timestamp():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1577836800"])  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" in keys


def test_unix_timestamp2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["94694400"])  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1234567"])  # 7 numbers
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" not in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1577836800000"])  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" in keys


def test_unix_timestamp5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["94694400000"])  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" not in keys


def test_ssh_rsa_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ssh-rsa AAAAB3NzaC1tc2EAAAADAQABAAACAQDrnjkGtf3iA46rtwsvRiscvMTCw30l5Mmln/sf8Wohg4RPc7nuIx3/fB86K9jzBNoQk6Fb00p2cSW0dX6c3OTL5R5Q0rBjOFy6GV07MkS7rXa7WYh4ObxBh+M+LEzxVIw29anzQFZkR0TAf6x2rBoErK7JYU4fyqFBDFupTt3coQDPEEmVwtLLUCEnJrurbbnJKcWJ+/FbItLxYyMLPl8TwEn0iqiJ97onCU2DuBtiYv3hp1WoEH08b5WDF0F04zEPRdJT+WisxlEFRgaj51o2BtjOC+D2qZQDb4LHaAfJ0WcO4nu7YocdlcLp2JPfXKKgu9P5J8UDsmXbR3KCJ1oddFa2R6TbHc6d2hKyG4amBzMX5ltxXu7D6FLPZlFqua8YooY7A2zwIVirOUH/cfx+5O9o0CtspkNmj/iYzN0FPaOpELncWsuauy9hrGql/1cF4SUr20zHFoBoDQUtmvmBnWnKoGfpWXzuda449FVtmcrEjvBzCvCb3RStu0BbyOOybJagbKif3MkcYVO10pRbTveIUwgCD6F3ypD11XztoPNsgScmjme0sj/KWWNLyQkLWtpJEQ4k46745NAC5g+nP28TR2JM8doeqsxA8JovQkLWwDcR+WYZu2z/I8dfhOmalnoMRTJ2NzWDc0OSkKGYWjexR4fN6lAKCUOUptl9Nw== r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH RSA Public Key", res)


def test_ssh_ecdsa_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBCE9Uli8bGnD4hOWdeo5KKQJ/P/vOazI4MgqJK54w37emP2JwOAOdMmXuwpxbKng3KZz27mz+nKWIlXJ3rzSGMo= r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH ECDSA Public Key", res)


def test_ssh_ed25519_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK0wmN/Cr3JXqmLW7u+g9pTh+wyqDHpSQEIQczXkVx9q r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH ED25519 Public Key", res)


def test_aws_access_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["AKIAIOSFODNN7EXAMPLE"])
    assert "Amazon Web Services Access Key" in str(res)


def test_aws_secret_access_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["Nw0XP0t2OdyUkaIk3B8TaAa2gEXAMPLEMvD2tW+g"])
    assert "Amazon Web Services Secret Access Key" in str(res)


def test_aws_ec2_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["i-1234567890abcdef0"])
    assert "Amazon Web Services EC2 Instance identifier" in str(res)


def test_aws_sg_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["sg-6e616f6d69"])
    assert "Amazon Web Services EC2 Security Group identifier" in str(res)


def test_aws_org_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["o-aa111bb222"])
    assert "Amazon Web Services Organization identifier" in str(res)


def test_asin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["B07ND5BB8V"])
    _assert_match_first_item("Amazon Standard Identification Number (ASIN)", res)


def test_google_api_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["AIzaSyD7CQl6fRhagGok6CzFGOOPne2X1u1spoA"])
    _assert_match_first_item("Google API Key", res)


def test_google_recaptcha_api_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6Le3W6QUAAAANNT8X_9JwlNnK4kZGLaYTB3KqFLM"])
    _assert_match_first_item("Google ReCaptcha API Key", res)


def test_google_oauth_token():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["ya29.AHES6ZRnn6CfjjaK6GCQ84vikePv_hk4NUAJwzaAXamCL0s"])
    _assert_match_first_item("Google OAuth Token", res)


def test_aws_access_key_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["AKIA31OMZKYAARWZ3ERH"])
    _assert_match_first_item("Amazon Web Services Access Key", res)


def test_mailgun_api_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["key-1e1631a9414aff7c262721e7b6ff6e43"])
    _assert_match_first_item("Mailgun API Key", res)


def test_twilio_api_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["SK012dab2d3f4dab1c2f33dffafdf23142"])
    _assert_match_first_item("Twilio API Key", res)


def test_twilio_account_sid():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["AC10a133ffdfb112abb2d3f42d1d2d3b14"])
    _assert_match_first_item("Twilio Account SID", res)


def test_twilio_application_sid():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["APfff01abd2b134a2aff3adc243ab211ab"])
    _assert_match_first_item("Twilio Application SID", res)


def test_square_application_secret():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["sq0csp-LBptIQ85io8CvbjVDvmzD1drQbOERgjlhnNrMgscFGk"])
    _assert_match_first_item("Square Application Secret", res)


def test_square_access_token():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["EAAAEBQZoq15Ub0PBBr_kw0zK-uIHcBPBZcfjPFT05ODfjng9GqFK9Dbgtj1ILcU"])
    _assert_match_first_item("Square Access Token", res)


def test_stripe_api_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["sk_live_vHDDrL02ioRF5vYtyqiYBKma"])
    _assert_match_first_item("Stripe API Key", res)


def test_github_access_token():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["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:test@github.com"])
    _assert_match_first_item("GitHub Access Token", res)


def test_slack_token():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ"])
    _assert_match_first_item("Slack Token", res)


def test_pgp_public_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "-----BEGIN PGP PUBLIC KEY BLOCK-----Comment: Alice's OpenPGP certificateComment: https://www.ietf.org/id/draft-bre-openpgp-samples-01.htmlmDMEXEcE6RYJKwYBBAHaRw8BAQdArjWwk3FAqyiFbFBKT4TzXcVBqPTB3gmzlC/Ub7O1u120JkFsaWNlIExvdmVsYWNlIDxhbGljZUBvcGVucGdwLmV4YW1wbGU+iJAEExYIADgCGwMFCwkIBwIGFQoJCAsCBBYCAwECHgECF4AWIQTrhbtfozp14V6UTmPyMVUMT0fjjgUCXaWfOgAKCRDyMVUMT0fjjukrAPoDnHBSogOmsHOsd9qGsiZpgRnOdypvbm+QtXZqth9rvwD9HcDC0tC+PHAsO7OTh1S1TC9RiJsvawAfCPaQZoed8gK4OARcRwTpEgorBgEEAZdVAQUBAQdAQv8GIa2rSTzgqbXCpDDYMiKRVitCsy203x3sE9+eviIDAQgHiHgEGBYIACAWIQTrhbtfozp14V6UTmPyMVUMT0fjjgUCXEcE6QIbDAAKCRDyMVUMT0fjjlnQAQDFHUs6TIcxrNTtEZFjUFm1M0PJ1Dng/cDW4xN80fsn0QEA22Kr7VkCjeAEC08VSTeV+QFsmz55/lntWkwYWhmvOgE==iIGO-----END PGP PUBLIC KEY BLOCK-----"
        ]
    )
    _assert_match_first_item("PGP Public Key", res)


def test_pgp_private_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "-----BEGIN PGP PRIVATE KEY BLOCK-----Comment: Alice's OpenPGP Transferable Secret KeyComment: https://www.ietf.org/id/draft-bre-openpgp-samples-01.htmllFgEXEcE6RYJKwYBBAHaRw8BAQdArjWwk3FAqyiFbFBKT4TzXcVBqPTB3gmzlC/Ub7O1u10AAP9XBeW6lzGOLx7zHH9AsUDUTb2pggYGMzd0P3ulJ2AfvQ4RtCZBbGljZSBMb3ZlbGFjZSA8YWxpY2VAb3BlbnBncC5leGFtcGxlPoiQBBMWCAA4AhsDBQsJCAcCBhUKCQgLAgQWAgMBAh4BAheAFiEE64W7X6M6deFelE5j8jFVDE9H444FAl2lnzoACgkQ8jFVDE9H447pKwD6A5xwUqIDprBzrHfahrImaYEZzncqb25vkLV2arYfa78A/R3AwtLQvjxwLDuzk4dUtUwvUYibL2sAHwj2kGaHnfICnF0EXEcE6RIKKwYBBAGXVQEFAQEHQEL/BiGtq0k84Km1wqQw2DIikVYrQrMttN8d7BPfnr4iAwEIBwAA/3/xFPG6U17rhTuq+07gmEvaFYKfxRB6sgAYiW6TMTpQEK6IeAQYFggAIBYhBOuFu1+jOnXhXpROY/IxVQxPR+OOBQJcRwTpAhsMAAoJEPIxVQxPR+OOWdABAMUdSzpMhzGs1O0RkWNQWbUzQ8nUOeD9wNbjE3zR+yfRAQDbYqvtWQKN4AQLTxVJN5X5AWybPnn+We1aTBhaGa86AQ===n8OM-----END PGP PRIVATE KEY BLOCK-----"
        ]
    )
    _assert_match_first_item("PGP Private Key", res)


def test_placekey():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["zzw-223@63r-6cs-j5f"])
    _assert_match_first_item("Placekey Universal Identifier for Physical Place", res)

    r = regex_identifier.RegexIdentifier()
    res = r.check(["226-223@5py-nm7-fs5"])
    _assert_match_first_item("Placekey Universal Identifier for Physical Place", res)

    r = regex_identifier.RegexIdentifier()
    res = r.check(["22d@627-s8q-xkf"])
    _assert_match_first_item("Placekey Universal Identifier for Physical Place", res)


def test_bcglobal():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6556123456789012"])
    _assert_match_first_item("BCGlobal Card Number", res)


def test_carte_blanche():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["30137891521480"])
    _assert_match_first_item("Carte Blanche Card Number", res)


def test_instapayment():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6387849878080951"])
    _assert_match_first_item("Insta Payment Card Number", res)


def test_jcb_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3537124887293334"])
    _assert_match_first_item("JCB Card Number", res)

    r = regex_identifier.RegexIdentifier()
    res = r.check(["3543824683332150682"])
    _assert_match_first_item("JCB Card Number", res)


def test_switch_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["633341812811453789"])
    _assert_match_first_item("Switch Card Number", res)


def test_korean_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["9837282929900015"])
    _assert_match_first_item("Korean Local Card Number", res)


def test_laser_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["630495060000000000"])
    _assert_match_first_item("Laser Card Number", res)


def test_solo_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6334498823141663"])
    _assert_match_first_item("Solo Card Number", res)
