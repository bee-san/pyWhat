import pytest

from pywhat import regex_identifier


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    assert "Name" in r.distribution.get_regexes()[0]


def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    assert "Dogecoin (DOGE) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["tryhackme.com"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_url_2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://username:password@example.com/"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_invalid_tld():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["tryhackme.comm"])
    assert "Uniform Resource Locator (URL)" not in res


def test_https():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["hTTPs://tryhackme.com"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_lat_long():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["52.6169586, -1.9779857"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["53.76297,-1.9388732"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["77\u00B0 30' 29.9988\" N"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long4():
    r = regex_identifier.RegexIdentifier()
    # degree symbol has to be a unicode character, otherwise Windows will not understand it
    res = r.check(["N 32\u00B0 53.733 W 096\u00B0 48.358"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["41\u00B024'12.2\" N 2\u00B010'26.5\" E"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long6():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["40.741895,-73.989308"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://10.1.1.1/just/a/test"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]
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
    assert "Internet Protocol (IP) Address Version 6" in res[0]["Regex Pattern"]["Name"]


def test_ip4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["[2001:db8::1]:8080"])
    assert "[2001:db8::1]:8080" in res[0]["Matched"]


@pytest.mark.skip(
    reason="Fails because not a valid TLD. If presented in punycode, it works."
)
def test_international_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://папироска.рф"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_same_international_url_in_punycode():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://xn--80aaxitdbjk.xn--p1ai/"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["thm{hello}"])
    assert "TryHackMe Flag Format" in res[0]["Regex Pattern"]["Name"]


def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["FLAG{hello}"])
    assert "Capture The Flag (CTF) Flag" in res[0]["Regex Pattern"]["Name"]


def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["0x52908400098527886E0F7030069857D2E4169EE7"])
    assert "Ethereum (ETH) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    assert "Bitcoin" in res[0]["Regex Pattern"]["Name"]


def test_monero():
    r = regex_identifier.RegexIdentifier()
    res = r.check(
        [
            "47DF8D9NwtmefhFUghynYRMqrexiZTsm48T1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFfdaqAT3jnBEwoMwCx6BYDJ1W3ub"
        ]
    )
    assert "Monero (XMR) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_litecoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m"])
    assert "Litecoin (LTC) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_bitcoincash():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"])
    assert "Bitcoin Cash (BCH) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_ripple():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"])
    assert "Ripple (XRP) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_visa():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4111111111111111"])
    assert "Visa" in res[0]["Regex Pattern"]["Name"]


def test_visa_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4607 0000 0000 0009"])
    assert "Visa" in res[0]["Regex Pattern"]["Name"]


def test_master_Card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5500000000000004"])
    assert "MasterCard" in res[0]["Regex Pattern"]["Name"]


def test_master_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5555 5555 5555 4444"])
    assert "MasterCard" in res[0]["Regex Pattern"]["Name"]


def test_american_express():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["340000000000009"])
    assert "American Express" in res[0]["Regex Pattern"]["Name"]


def test_american_express_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3714 4963 5398 431"])
    assert "American Express" in res[0]["Regex Pattern"]["Name"]


def test_american_diners_club():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["30000000000004"])
    assert "Diners Club Card" in res[0]["Regex Pattern"]["Name"]


def test_american_diners_club_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["3056 9309 0259 04"])
    assert "Diners Club Card" in res[0]["Regex Pattern"]["Name"]


def test_discover_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011000000000004"])
    assert "Discover" in res[0]["Regex Pattern"]["Name"]


def test_discover_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011 1111 1111 1117"])
    assert "Discover" in res[0]["Regex Pattern"]["Name"]


def test_maestro_card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5038146401278870"])
    assert "Maestro" in res[0]["Regex Pattern"]["Name"]


def test_maestro_card_spaces():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6759 6498 2643 8453"])
    assert "Maestro" in res[0]["Regex Pattern"]["Name"]


@pytest.mark.skip("Key:value is turned off")
def test_username():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["james:S3cr37_P@$$W0rd"])
    assert "Key:Value" in res[0]["Regex Pattern"]["Name"]


def test_email():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["github@skerritt.blog"])
    assert "Email" in res[0]["Regex Pattern"]["Name"]


def test_email2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["firstname+lastname@example.com"])
    assert "Email" in res[0]["Regex Pattern"]["Name"]


def test_email3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["john.smith@[123.123.123.123]"])
    assert "Email" in res[1]["Regex Pattern"]["Name"]


def test_email4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["email@example@example.com"])
    assert "Email" not in res


def test_phone_number():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["202-555-0178"])
    assert "Phone Number" in res[0]["Regex Pattern"]["Name"]


def test_phone_number2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+1-202-555-0156"])
    assert "Phone Number" in res[0]["Regex Pattern"]["Name"]
    assert "United States" in res[0]["Regex Pattern"]["Description"]


def test_phone_number3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+662025550156"])
    assert "Phone Number" in res[0]["Regex Pattern"]["Name"]
    assert "Thailand" in res[0]["Regex Pattern"]["Description"]


def test_phone_number4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["+356 202 555 0156"])
    assert "Phone Number" in res[0]["Regex Pattern"]["Name"]
    assert "Malta" in res[0]["Regex Pattern"]["Description"]


def test_youtube():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://www.youtube.com/watch?v=ScOAntcCa78"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_youtube2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://www.youtube.com/watch?v=dQw4w9WgXcQ"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_youtube_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["dQw4w9WgXcQ"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_youtube_id2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["078-05-1120"])
    assert "YouTube" not in res[0]


def test_ssn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001-01-0001"])
    assert "Social" in str(res)


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

def test_aws_access_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["AKIAIOSFODNN7EXAMPLE"])
    assert "Amazon Web Services Access Key" in str(res)

def test_aws_secret_access_key():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["Nw0XP0t2OdyUkaIk3B8TaAa2gEXAMPLEMvD2tW+g"])
    assert "Amazon Web Services Secret Access Key" in str(res)