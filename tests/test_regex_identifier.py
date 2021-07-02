import pytest

from pywhat import regex_identifier
from pywhat.filter import Filter


def _assert_match_first_item(name, res):
    assert name in res[0]["Regex Pattern"]["Name"]


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    assert "Name" in r.distribution.get_regexes()[0]


def test_regex_runs():
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
    assert "URL" not in res[0]


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


def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["0x52908400098527886E0F7030069857D2E4169EE7"])
    _assert_match_first_item("Ethereum (ETH) Wallet Address", res)


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    _assert_match_first_item("Bitcoin", res)


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
    _assert_match_first_item("Visa", res)


def test_visa_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4607 0000 0000 0009"])
    _assert_match_first_item("Visa", res)


def test_master_Card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5500000000000004"])
    _assert_match_first_item("MasterCard", res)


def test_master_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5555 5555 5555 4444"])
    _assert_match_first_item("MasterCard", res)


def test_american_express():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["340000000000009"])
    _assert_match_first_item("American Express", res)


def test_american_express_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3714 4963 5398 431"])
    _assert_match_first_item("American Express", res)


def test_american_diners_club():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["30000000000004"])
    _assert_match_first_item("Diners Club Card", res)


def test_american_diners_club_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3056 9309 0259 04"])
    _assert_match_first_item("Diners Club Card", res)


def test_discover_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011000000000004"])
    _assert_match_first_item("Discover", res)


def test_discover_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011 1111 1111 1117"])
    _assert_match_first_item("Discover", res)


def test_maestro_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5038146401278870"])
    _assert_match_first_item("Maestro", res)


def test_maestro_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6759 6498 2643 8453"])
    _assert_match_first_item("Maestro", res)


@pytest.mark.skip("Key:value is turned off")
def test_username():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["james:S3cr37_P@$$W0rd"])
    _assert_match_first_item("Key:Value", res)


def test_email():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["github@skerritt.blog"])
    _assert_match_first_item("Email", res)


def test_email2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["firstname+lastname@example.com"])
    _assert_match_first_item("Email", res)


def test_email3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        ["john.smith@[123.123.123.123]"], boundaryless=Filter({"Tags": ["Identifiers"]})
    )
    assert "Email" in res[2]["Regex Pattern"]["Name"]


def test_email4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["email@example@example.com"])
    assert "Email" not in res


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
    _assert_match_first_item("YouTube", res)


def test_youtube2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube", res)


def test_youtube_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["dQw4w9WgXcQ"])
    _assert_match_first_item("YouTube", res)


def test_youtube_id2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["078-05-1120"])
    assert "YouTube" not in res[0]


def test_ssn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001-01-0001"])
    assert "Social" in str(res)


def test_ssn2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001:01:0001"])
    assert "Social" in str(res)


def test_ssn3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001.01.0001"])
    assert "Social" in str(res)


def test_ssn4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001 01 0001"])
    assert "Social" in str(res)


def test_ssn5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["900-01-2222"])
    assert "Social" not in str(res)


def test_ssn6():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["999-21-2222"])
    assert "Social" not in str(res)


def test_ssn7():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["666-21-2222"])
    assert "Social" not in str(res)


def test_ssn8():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["000-21-5544"])
    assert "Social" not in str(res)


def test_ssn9():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["122-00-5544"])
    assert "Social" not in str(res)


def test_ssn10():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["122-32-0000"])
    assert "Social" not in str(res)


def test_cors():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["Access-Control-Allow: *"])
    assert "Access" in str(res)


def test_jwt():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        ]
    )
    assert "JWT" in str(res)


def test_s3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://s3.amazonaws.com/bucket/"])
    assert "S3" in str(res)


def test_s3_internal():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["s3://bucket/path/key"])
    assert "S3" in str(res)


def test_s3_internal2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["s3://bucket/path/directory/"])
    assert "S3" in str(res)


def test_arn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resource"])
    assert "ARN" in str(res)


def test_arn2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resourcetype/resource"])
    assert "ARN" in str(res)


def test_arn3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:partition:service:region:account-id:resourcetype:resource"])
    assert "ARN" in str(res)


def test_arn4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["arn:aws:s3:::my_corporate_bucket/Development/*"])
    assert "ARN" in str(res)


def test_ssh_rsa_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ssh-rsa AAAAB3NzaC1tc2EAAAADAQABAAACAQDrnjkGtf3iA46rtwsvRiscvMTCw30l5Mmln/sf8Wohg4RPc7nuIx3/fB86K9jzBNoQk6Fb00p2cSW0dX6c3OTL5R5Q0rBjOFy6GV07MkS7rXa7WYh4ObxBh+M+LEzxVIw29anzQFZkR0TAf6x2rBoErK7JYU4fyqFBDFupTt3coQDPEEmVwtLLUCEnJrurbbnJKcWJ+/FbItLxYyMLPl8TwEn0iqiJ97onCU2DuBtiYv3hp1WoEH08b5WDF0F04zEPRdJT+WisxlEFRgaj51o2BtjOC+D2qZQDb4LHaAfJ0WcO4nu7YocdlcLp2JPfXKKgu9P5J8UDsmXbR3KCJ1oddFa2R6TbHc6d2hKyG4amBzMX5ltxXu7D6FLPZlFqua8YooY7A2zwIVirOUH/cfx+5O9o0CtspkNmj/iYzN0FPaOpELncWsuauy9hrGql/1cF4SUr20zHFoBoDQUtmvmBnWnKoGfpWXzuda449FVtmcrEjvBzCvCb3RStu0BbyOOybJagbKif3MkcYVO10pRbTveIUwgCD6F3ypD11XztoPNsgScmjme0sj/KWWNLyQkLWtpJEQ4k46745NAC5g+nP28TR2JM8doeqsxA8JovQkLWwDcR+WYZu2z/I8dfhOmalnoMRTJ2NzWDc0OSkKGYWjexR4fN6lAKCUOUptl9Nw== r00t@my-random_host"
        ]
    )
    assert "SSH RSA" in str(res)


def test_ssh_ecdsa_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBCE9Uli8bGnD4hOWdeo5KKQJ/P/vOazI4MgqJK54w37emP2JwOAOdMmXuwpxbKng3KZz27mz+nKWIlXJ3rzSGMo= r00t@my-random_host"
        ]
    )
    assert "SSH ECDSA" in str(res)


def test_ssh_ed25519_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIK0wmN/Cr3JXqmLW7u+g9pTh+wyqDHpSQEIQczXkVx9q r00t@my-random_host"
        ]
    )
    assert "SSH ED25519" in str(res)


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
    _assert_match_first_item("AWS Access Key ID", res)


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
