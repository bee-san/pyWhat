import re

import pytest

from pywhat import regex_identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes

database = load_regexes()
r = regex_identifier.RegexIdentifier()


def _assert_match_first_item(name, res):
    assert name in res[0]["Regex Pattern"]["Name"]


def _assert_match_exploit_first_item(search, res):
    assert search in res[0]["Regex Pattern"]["Exploit"]


def test_regex_successfully_parses():
    assert "Name" in r.distribution.get_regexes()[0]


def _assert_match_in_items(name, res):
    for i in res:
        assert i["Regex Pattern"]["Name"] == name


@pytest.mark.skip(reason="Not all regex have tests now, check https://github.com/bee-san/pyWhat/pull/146#issuecomment-927087231 for info.")
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


def test_dogecoin():
    res = r.check(["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    _assert_match_first_item("Dogecoin (DOGE) Wallet Address", res)


def test_url():
    res = r.check(["tryhackme.com"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_url_2():
    res = r.check(["http://username:password@example.com/"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_invalid_tld():
    res = r.check(["tryhackme.comm"])
    assert "Uniform Resource Locator (URL)" not in res


def test_https():
    res = r.check(["hTTPs://tryhackme.com"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_lat_long():
    res = r.check(["52.6169586, -1.9779857"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long2():
    res = r.check(["53.76297,-1.9388732"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long3():
    res = r.check(["77\u00B0 30' 29.9988\" N"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long4():
    # degree symbol has to be a unicode character, otherwise Windows will not understand it
    res = r.check(["N 32\u00B0 53.733 W 096\u00B0 48.358"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long5():
    res = r.check(["41\u00B024'12.2\" N 2\u00B010'26.5\" E"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_lat_long6():
    res = r.check(["40.741895,-73.989308"])
    _assert_match_first_item("Latitude & Longitude Coordinates", res)


def test_ip():
    res = r.check(
        ["http://10.1.1.1/just/a/test"], boundaryless=Filter({"Tags": ["Identifiers"]})
    )
    _assert_match_first_item("Uniform Resource Locator (URL)", res)
    assert "Internet Protocol (IP) Address Version 4" in res[1]["Regex Pattern"]["Name"]


def test_ip_not_url():
    res = r.check(["http://10.1.1.1"])
    assert "Uniform Resource Locator (URL)" not in res[0]


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


def test_same_international_url_in_punycode():
    res = r.check(["https://xn--80aaxitdbjk.xn--p1ai/"])
    _assert_match_first_item("Uniform Resource Locator (URL)", res)


def test_ctf_flag():
    res = r.check(["thm{hello}"])
    _assert_match_first_item("TryHackMe Flag Format", res)


def test_ctf_flag_uppercase():
    res = r.check(["FLAG{hello}"])
    _assert_match_first_item("Capture The Flag (CTF) Flag", res)


def test_htb_flag():
    res = r.check(["htb{just_a_test}"])
    _assert_match_first_item("HackTheBox Flag Format", res)


def test_ethereum():
    res = r.check(["0x52908400098527886E0F7030069857D2E4169EE7"])
    _assert_match_first_item("Ethereum (ETH) Wallet Address", res)


def test_bitcoin_p2pkh():
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    _assert_match_first_item("Bitcoin (₿) Wallet Address", res)


def test_bitcoin_p2sh():
    res = r.check(["3EmUH8Uh9EXE7axgyAeBsCc2vdUdKkDqWK"])
    _assert_match_first_item("Bitcoin (₿) Wallet Address", res)


def test_bitcoin_bech32():
    res = r.check(["bc1qj89046x7zv6pm4n00qgqp505nvljnfp6xfznyw"])
    _assert_match_first_item("Bitcoin (₿) Wallet Address", res)


def test_monero():
    res = r.check(
        [
            "47DF8D9NwtmefhFUghynYRMqrexiZTsm48T1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFfdaqAT3jnBEwoMwCx6BYDJ1W3ub"
        ]
    )
    _assert_match_first_item("Monero (XMR) Wallet Address", res)


def test_litecoin():
    res = r.check(["LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m"])
    _assert_match_first_item("Litecoin (LTC) Wallet Address", res)


def test_bitcoincash():
    res = r.check(["bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"])
    _assert_match_first_item("Bitcoin Cash (BCH) Wallet Address", res)


def test_ripple():
    res = r.check(["rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"])
    _assert_match_first_item("Ripple (XRP) Wallet Address", res)


def test_visa():
    res = r.check(["4111111111111111"])
    _assert_match_first_item("Visa Card Number", res)


def test_visa_spaces():
    res = r.check(["4607 0000 0000 0009"])
    _assert_match_first_item("Visa Card Number", res)


def test_master_Card():
    res = r.check(["5409010000000004"])
    _assert_match_first_item("MasterCard Number", res)
    assert "UNION NATIONAL BANK" in res[0]["Regex Pattern"]["Description"]


def test_master_card_spaces():
    res = r.check(["5409 0100 0000 0004"])
    _assert_match_first_item("MasterCard Number", res)
    assert "UNION NATIONAL BANK" in res[0]["Regex Pattern"]["Description"]


def test_american_express():
    res = r.check(["340000000000009"])
    _assert_match_first_item("American Express Card Number", res)


def test_american_express_spaces():
    res = r.check(["3714 4963 5398 431"])
    _assert_match_first_item("American Express Card Number", res)


def test_american_diners_club():
    res = r.check(["30000000000004"])
    assert "Diners Club Card Number" in res[1]["Regex Pattern"]["Name"]


def test_american_diners_club_spaces():
    res = r.check(["3056 9309 0259 04"])
    _assert_match_first_item("Diners Club Card Number", res)


def test_discover_card():
    res = r.check(["6011000000000004"])
    _assert_match_first_item("Discover Card Number", res)


def test_discover_card_spaces():
    res = r.check(["6011 1111 1111 1117"])
    _assert_match_first_item("Discover Card Number", res)


def test_maestro_card():
    res = r.check(["5038146401278870"])
    _assert_match_first_item("Maestro Card Number", res)


def test_maestro_card_spaces():
    res = r.check(["6759 6498 2643 8453"])
    _assert_match_first_item("Maestro Card Number", res)


@pytest.mark.skip("Key:Value Pair is not ran by default because of low rarity.")
def test_username():
    res = r.check(["james:S3cr37_P@$$W0rd"])
    _assert_match_first_item("Key:Value Pair", res)


def test_email():
    res = r.check(["github@skerritt.blog"])
    _assert_match_first_item("Email Address", res)


def test_email2():
    res = r.check(["firstname+lastname@example.com"])
    _assert_match_first_item("Email Address", res)


def test_email3():
    res = r.check(
        ["john.smith@[123.123.123.123]"], boundaryless=Filter({"Tags": ["Identifiers"]})
    )
    assert "Email Address" in res[2]["Regex Pattern"]["Name"]


def test_email4():
    res = r.check(["email@example@example.com"])
    assert "Email Address" not in res


def test_phone_number():
    res = r.check(["202-555-0178"])
    _assert_match_first_item("Phone Number", res)


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


def test_youtube():
    res = r.check(["https://www.youtube.com/watch?v=ScOAntcCa78"])
    _assert_match_first_item("YouTube Video", res)


def test_youtube2():
    res = r.check(["http://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube Video", res)


def test_youtube_id():
    res = r.check(["dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube Video ID", res)


def test_youtube_id2():
    res = r.check(["078-05-1120"])
    assert "YouTube Video ID" not in res


def test_youtube_channel_id():
    res = r.check(["UCjXfkj5iapKHJrhYfAF9ZGg"])
    _assert_match_first_item("YouTube Channel ID", res)


def test_ssn():
    res = r.check(["001-01-0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn2():
    res = r.check(["001:01:0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn3():
    res = r.check(["001.01.0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn4():
    res = r.check(["001 01 0001"])
    _assert_match_first_item("American Social Security Number", res)


def test_ssn5():
    res = r.check(["900-01-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn6():
    res = r.check(["999-21-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn7():
    res = r.check(["666-21-2222"])
    assert "American Social Security Number" not in str(res)


def test_ssn8():
    res = r.check(["000-21-5544"])
    assert "American Social Security Number" not in str(res)


def test_ssn9():
    res = r.check(["122-00-5544"])
    assert "American Social Security Number" not in str(res)


def test_ssn10():
    res = r.check(["122-32-0000"])
    assert "American Social Security Number" not in str(res)


def test_cors():
    res = r.check(["Access-Control-Allow: *"])
    _assert_match_first_item("Access-Control-Allow-Header", res)


def test_jwt():
    res = r.check(
        [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        ]
    )
    _assert_match_first_item("JSON Web Token (JWT)", res)


def test_s3():
    res = r.check(["http://s3.amazonaws.com/bucket/"])
    _assert_match_first_item("Amazon Web Services Simple Storage (AWS S3) URL", res)


def test_s3_internal():
    res = r.check(["s3://bucket/path/key"])
    _assert_match_first_item(
        "Amazon Web Services Simple Storage (AWS S3) Internal URL", res
    )


def test_s3_internal2():
    res = r.check(["s3://bucket/path/directory/"])
    _assert_match_first_item(
        "Amazon Web Services Simple Storage (AWS S3) Internal URL", res
    )


def test_arn():
    res = r.check(["arn:partition:service:region:account-id:resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn2():
    res = r.check(["arn:partition:service:region:account-id:resourcetype/resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn3():
    res = r.check(["arn:partition:service:region:account-id:resourcetype:resource"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_arn4():
    res = r.check(["arn:aws:s3:::my_corporate_bucket/Development/*"])
    _assert_match_first_item("Amazon Resource Name (ARN)", res)


def test_unix_timestamp():
    res = r.check(["1577836800"])  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" in keys


def test_unix_timestamp2():
    res = r.check(["94694400"])  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp3():
    res = r.check(["1234567"])  # 7 numbers
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Timestamp" not in keys
    assert "Recent Unix Timestamp" not in keys


def test_unix_timestamp4():
    res = r.check(["1577836800000"])  # 2020-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" in keys


def test_unix_timestamp5():
    res = r.check(["94694400000"])  # 1973-01-01
    keys = [m["Regex Pattern"]["Name"] for m in res]
    assert "Unix Millisecond Timestamp" in keys
    assert "Recent Unix Millisecond Timestamp" not in keys


def test_ssh_rsa_key():
    res = r.check(
        [
            "ssh-rsa AAAAB3NzaC1tc2EAAAADAQABAAACAQDrnjkGtf3iA46rtwsvRiscvMTCw30l5Mmln/sf8Wohg4RPc7nuIx3/fB86K9jzBNoQk6Fb00p2cSW0dX6c3OTL5R5Q0rBjOFy6GV07MkS7rXa7WYh4ObxBh+M+LEzxVIw29anzQFZkR0TAf6x2rBoErK7JYU4fyqFBDFupTt3coQDPEEmVwtLLUCEnJrurbbnJKcWJ+/FbItLxYyMLPl8TwEn0iqiJ97onCU2DuBtiYv3hp1WoEH08b5WDF0F04zEPRdJT+WisxlEFRgaj51o2BtjOC+D2qZQDb4LHaAfJ0WcO4nu7YocdlcLp2JPfXKKgu9P5J8UDsmXbR3KCJ1oddFa2R6TbHc6d2hKyG4amBzMX5ltxXu7D6FLPZlFqua8YooY7A2zwIVirOUH/cfx+5O9o0CtspkNmj/iYzN0FPaOpELncWsuauy9hrGql/1cF4SUr20zHFoBoDQUtmvmBnWnKoGfpWXzuda449FVtmcrEjvBzCvCb3RStu0BbyOOybJagbKif3MkcYVO10pRbTveIUwgCD6F3ypD11XztoPNsgScmjme0sj/KWWNLyQkLWtpJEQ4k46745NAC5g+nP28TR2JM8doeqsxA8JovQkLWwDcR+WYZu2z/I8dfhOmalnoMRTJ2NzWDc0OSkKGYWjexR4fN6lAKCUOUptl9Nw== r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH RSA Public Key", res)


def test_ssh_ecdsa_key():
    res = r.check(
        [
            "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBCE9Uli8bGnD4hOWdeo5KKQJ/P/vOazI4MgqJK54w37emP2JwOAOdMmXuwpxbKng3KZz27mz+nKWIlXJ3rzSGMo= r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH ECDSA Public Key", res)


def test_ssh_ed25519_key():
    res = r.check(
        [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK0wmN/Cr3JXqmLW7u+g9pTh+wyqDHpSQEIQczXkVx9q r00t@my-random_host"
        ]
    )
    _assert_match_first_item("SSH ED25519 Public Key", res)


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


def test_asin():
    res = r.check(["B07ND5BB8V"])
    _assert_match_first_item("Amazon Standard Identification Number (ASIN)", res)


def test_google_api_key():
    res = r.check(["AIzaSyD7CQl6fRhagGok6CzFGOOPne2X1u1spoA"])
    _assert_match_first_item("Google API Key", res)


def test_google_recaptcha_api_key():
    res = r.check(["6Le3W6QUAAAANNT8X_9JwlNnK4kZGLaYTB3KqFLM"])
    _assert_match_first_item("Google ReCaptcha API Key", res)


def test_google_oauth_token():
    res = r.check(["ya29.AHES6ZRnn6CfjjaK6GCQ84vikePv_hk4NUAJwzaAXamCL0s"])
    _assert_match_first_item("Google OAuth Token", res)


def test_aws_access_key_id():
    res = r.check(["AKIA31OMZKYAARWZ3ERH"])
    _assert_match_first_item("Amazon Web Services Access Key", res)


def test_mailgun_api_key():
    res = r.check(["key-1e1631a9414aff7c262721e7b6ff6e43"])
    _assert_match_first_item("Mailgun API Key", res)


def test_twilio_api_key():
    res = r.check(["SK012dab2d3f4dab1c2f33dffafdf23142"])
    _assert_match_first_item("Twilio API Key", res)


def test_twilio_account_sid():
    res = r.check(["AC10a133ffdfb112abb2d3f42d1d2d3b14"])
    _assert_match_first_item("Twilio Account SID", res)


def test_twilio_application_sid():
    res = r.check(["APfff01abd2b134a2aff3adc243ab211ab"])
    _assert_match_first_item("Twilio Application SID", res)


def test_square_application_secret():
    res = r.check(["sq0csp-LBptIQ85io8CvbjVDvmzD1drQbOERgjlhnNrMgscFGk"])
    _assert_match_first_item("Square Application Secret", res)


def test_square_access_token():
    res = r.check(["EAAAEBQZoq15Ub0PBBr_kw0zK-uIHcBPBZcfjPFT05ODfjng9GqFK9Dbgtj1ILcU"])
    _assert_match_first_item("Square Access Token", res)


def test_stripe_api_key():
    res = r.check(["sk_live_vHDDrL02ioRF5vYtyqiYBKma"])
    _assert_match_first_item("Stripe API Key", res)


def test_github_access_token():
    res = r.check(["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:test@github.com"])
    _assert_match_first_item("GitHub Access Token", res)


def test_slack_api_key():
    res = r.check(["xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v"])
    _assert_match_first_item("Slack API Key", res)
    _assert_match_exploit_first_item("https://slack.com/api/auth.test?token=xoxp-514654431830-843187921057-792480346180-d44d2r9b71f954o8z2k5llt41ovpip6v", res)


def test_slack_token():
    res = r.check(["xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ"])
    _assert_match_first_item("Slack Token", res)
    _assert_match_exploit_first_item("https://slack.com/api/auth.test?token=xoxb-51465443183-hgvhXVd2ISC2x7gaoRWBOUdQ", res)


def test_pgp_public_key():
    res = r.check(
        [
            "-----BEGIN PGP PUBLIC KEY BLOCK-----Comment: Alice's OpenPGP certificateComment: https://www.ietf.org/id/draft-bre-openpgp-samples-01.htmlmDMEXEcE6RYJKwYBBAHaRw8BAQdArjWwk3FAqyiFbFBKT4TzXcVBqPTB3gmzlC/Ub7O1u120JkFsaWNlIExvdmVsYWNlIDxhbGljZUBvcGVucGdwLmV4YW1wbGU+iJAEExYIADgCGwMFCwkIBwIGFQoJCAsCBBYCAwECHgECF4AWIQTrhbtfozp14V6UTmPyMVUMT0fjjgUCXaWfOgAKCRDyMVUMT0fjjukrAPoDnHBSogOmsHOsd9qGsiZpgRnOdypvbm+QtXZqth9rvwD9HcDC0tC+PHAsO7OTh1S1TC9RiJsvawAfCPaQZoed8gK4OARcRwTpEgorBgEEAZdVAQUBAQdAQv8GIa2rSTzgqbXCpDDYMiKRVitCsy203x3sE9+eviIDAQgHiHgEGBYIACAWIQTrhbtfozp14V6UTmPyMVUMT0fjjgUCXEcE6QIbDAAKCRDyMVUMT0fjjlnQAQDFHUs6TIcxrNTtEZFjUFm1M0PJ1Dng/cDW4xN80fsn0QEA22Kr7VkCjeAEC08VSTeV+QFsmz55/lntWkwYWhmvOgE==iIGO-----END PGP PUBLIC KEY BLOCK-----"
        ]
    )
    _assert_match_first_item("PGP Public Key", res)


def test_pgp_private_key():
    res = r.check(
        [
            "-----BEGIN PGP PRIVATE KEY BLOCK-----Comment: Alice's OpenPGP Transferable Secret KeyComment: https://www.ietf.org/id/draft-bre-openpgp-samples-01.htmllFgEXEcE6RYJKwYBBAHaRw8BAQdArjWwk3FAqyiFbFBKT4TzXcVBqPTB3gmzlC/Ub7O1u10AAP9XBeW6lzGOLx7zHH9AsUDUTb2pggYGMzd0P3ulJ2AfvQ4RtCZBbGljZSBMb3ZlbGFjZSA8YWxpY2VAb3BlbnBncC5leGFtcGxlPoiQBBMWCAA4AhsDBQsJCAcCBhUKCQgLAgQWAgMBAh4BAheAFiEE64W7X6M6deFelE5j8jFVDE9H444FAl2lnzoACgkQ8jFVDE9H447pKwD6A5xwUqIDprBzrHfahrImaYEZzncqb25vkLV2arYfa78A/R3AwtLQvjxwLDuzk4dUtUwvUYibL2sAHwj2kGaHnfICnF0EXEcE6RIKKwYBBAGXVQEFAQEHQEL/BiGtq0k84Km1wqQw2DIikVYrQrMttN8d7BPfnr4iAwEIBwAA/3/xFPG6U17rhTuq+07gmEvaFYKfxRB6sgAYiW6TMTpQEK6IeAQYFggAIBYhBOuFu1+jOnXhXpROY/IxVQxPR+OOBQJcRwTpAhsMAAoJEPIxVQxPR+OOWdABAMUdSzpMhzGs1O0RkWNQWbUzQ8nUOeD9wNbjE3zR+yfRAQDbYqvtWQKN4AQLTxVJN5X5AWybPnn+We1aTBhaGa86AQ===n8OM-----END PGP PRIVATE KEY BLOCK-----"
        ]
    )
    _assert_match_first_item("PGP Private Key", res)


def test_discord_token():
    res = r.check(["NzQ4MDk3ODM3OTgzODU4NzIz.X0YeZw.UlcjuCywUAWvPH9s-3cXNBaq3M4"])
    _assert_match_first_item("Discord Bot Token", res)


def test_discord_token_2():
    res = r.check(["MTE4NDQyNjQ0NTAxMjk5MjAz.DPM2DQ.vLNMR02Qxb9DJFucGZK1UtTs__s"])
    _assert_match_first_item("Discord Bot Token", res)


def test_discord_token_3():
    res = r.check(["ODYyOTUyOTE3NTg4NjM5NzY1.YOf1iA.7lARgFXmodxpgmPvOXapaKUga6M"])
    _assert_match_first_item("Discord Bot Token", res)


def test_bcglobal():
    res = r.check(["6556123456789012"])
    _assert_match_first_item("BCGlobal Card Number", res)


def test_carte_blanche():
    res = r.check(["30137891521480"])
    _assert_match_first_item("Carte Blanche Card Number", res)


def test_instapayment():
    res = r.check(["6387849878080951"])
    _assert_match_first_item("Insta Payment Card Number", res)


def test_jcb_card():
    res = r.check(["3537124887293334"])
    _assert_match_first_item("JCB Card Number", res)

    res = r.check(["3543824683332150682"])
    _assert_match_first_item("JCB Card Number", res)


def test_switch_card():
    res = r.check(["633341812811453789"])
    _assert_match_first_item("Switch Card Number", res)


def test_korean_card():
    res = r.check(["9837282929900015"])
    _assert_match_first_item("Korean Local Card Number", res)


def test_laser_card():
    res = r.check(["630495060000000000"])
    _assert_match_first_item("Laser Card Number", res)


def test_solo_card():
    res = r.check(["6334498823141663"])
    _assert_match_first_item("Solo Card Number", res)


def test_github_personal_access_token():
    res = r.check(["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"])
    _assert_match_first_item("GitHub Personal Access Token", res)


def test_github_oauth_token():
    res = r.check(["gho_16C7e42F292c6912E7710c838347Ae178B4a"])
    _assert_match_first_item("GitHub OAuth Access Token", res)


def test_github_refresh_token():
    res = r.check(
        [
            "ghr_1B4a2e77838347a7E420ce178F2E7c6912E169246c34E1ccbF66C46812d16D5B1A9Dc86A1498"
        ]
    )
    _assert_match_first_item("GitHub Refresh Token", res)


def test_stripe_api_key():
    res = r.check(["sk_live_26PHem9AhJZvU623DfE1x4sd"])
    _assert_match_first_item("Stripe API Key", res)


def test_zapier_webhook():
    res = r.check(["https://hooks.zapier.com/hooks/catch/1234567/f8f22dgg/"])
    _assert_match_first_item("Zapier Webhook Token", res)


def test_new_relic_rest_api_key():
    res = r.check(["NRRA-2a2d50d7d9449f3bb7ef65ac1184c488bd4fe7a8bd"])
    _assert_match_first_item("New Relic REST API Key", res)


def test_new_relic_synthetics_api_key():
    res = r.check(["NRSP-us010E1E3D1716F721FF39F726B3E4CBCB7"])
    _assert_match_first_item("New Relic Synthetics Location Key", res)


def test_new_relic_user_api_key():
    res = r.check(["NRAK-WI4JTVS049IF5A3FGS5N51XS3Y5"])
    _assert_match_first_item("New Relic User API Key", res)

def test_windows_file_name():
    res = r.check(["cmd.exe"])
    _assert_match_first_item("Windows File Name", res)

