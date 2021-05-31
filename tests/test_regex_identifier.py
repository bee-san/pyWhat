import pytest
from pywhat import regex_identifier


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    print(r.regexes)
    assert "Name" in r.regexes[0]


def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"]})
    assert "Dogecoin (DOGE) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


@pytest.mark.skip(reason="Fails Regex due to http://")
def test_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["tryhackme.com"]})
    assert "Uniform Resource Locator (URL)" in res["test"][0]["Regex Pattern"]["Name"]


def test_https():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["hTTPs://tryhackme.com"]})
    assert "Uniform Resource Locator (URL)" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["52.6169586, -1.9779857"]})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["53.76297,-1.9388732"]})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ['77\u00B0 30\' 29.9988" N']})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long4():
    r = regex_identifier.RegexIdentifier()
    # degree symbol has to be a unicode character, otherwise Windows will not understand it
    res = r.check({"test": ["N 32\u00B0 53.733 W 096\u00B0 48.358"]})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long5():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["41\u00B024\'12.2\" N 2\u00B010\'26.5\" E"]})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_lat_long6():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["40.741895,-73.989308"]})
    assert "Latitude & Longitude Coordinates" in res["test"][0]["Regex Pattern"]["Name"]


def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["http://10.1.1.1"]})
    assert "Internet Protocol (IP) Address Version 4" in res["test"][0]["Regex Pattern"]["Name"]


def test_ip_not_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["http://10.1.1.1"]})
    assert "URL" not in res["test"][0]["Regex Pattern"]["Name"]


def test_ip2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["192.0.2.235:80"]})
    assert "192.0.2.235:80" in res["test"][0]["Matched"]


def test_ip3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["2001:0db8:85a3:0000:0000:8a2e:0370:7334"]})
    assert "Internet Protocol (IP) Address Version 6" in res["test"][0]["Regex Pattern"]["Name"]


def test_ip4():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["[2001:db8::1]:8080"]})
    assert "[2001:db8::1]:8080" in res["test"][0]["Matched"]


def test_internationak_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["http://папироска.рф"]})
    assert "Uniform Resource Locator (URL)" in res["test"][0]["Regex Pattern"]["Name"]


def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["thm{hello}"]})
    assert "TryHackMe Flag Format" in res["test"][0]["Regex Pattern"]["Name"]


def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["FLAG{hello}"]})
    assert "Capture The Flag (CTF) Flag" in res["test"][0]["Regex Pattern"]["Name"]


def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["0x52908400098527886E0F7030069857D2E4169EE7"]})
    assert "Ethereum (ETH) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"]})
    assert "Bitcoin" in res["test"][0]["Regex Pattern"]["Name"]


def test_monero():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["47DF8D9NwtmefhFUghynYRMqrexiZTsm48T1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFfdaqAT3jnBEwoMwCx6BYDJ1W3ub"]})
    assert "Monero (XMR) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


def test_litecoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m"]})
    assert "Litecoin (LTC) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


def test_bitcoincash():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"]})
    assert "Bitcoin Cash (BCH) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


def test_ripple():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"]})
    assert "Ripple (XRP) Wallet Address" in res["test"][0]["Regex Pattern"]["Name"]


def test_visa():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["4111111111111111"]})
    assert "Visa" in res["test"][0]["Regex Pattern"]["Name"]


def test_master_Card():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["5500000000000004"]})
    assert "MasterCard" in res["test"][0]["Regex Pattern"]["Name"]


def test_american_express():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["340000000000009"]})
    assert "American Express" in res["test"][0]["Regex Pattern"]["Name"]


def test_american_diners_club():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["30000000000004"]})
    assert "Diners Club Card" in res["test"][0]["Regex Pattern"]["Name"]


def test_american_diners_discover():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["6011000000000004"]})
    assert "Discover" in res["test"][0]["Regex Pattern"]["Name"]


@pytest.mark.skip("Key:value is turned off")
def test_username():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["james:S3cr37_P@$$W0rd"]})
    assert "Key:Value" in res["test"][0]["Regex Pattern"]["Name"]


def test_email():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["github@skerritt.blog"]})
    assert "Email" in res["test"][0]["Regex Pattern"]["Name"]


def test_email2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["firstname+lastname@example.com"]})
    assert "Email" in res["test"][0]["Regex Pattern"]["Name"]


def test_email3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["john.smith@[123.123.123.123]"]})
    assert "Email" in res["test"][1]["Regex Pattern"]["Name"]


def test_email4():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["email@example@example.com"]})
    assert "Email" not in res


def test_phone_number():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["202-555-0178"]})
    assert "Phone Number" in res["test"][0]["Regex Pattern"]["Name"]


def test_phone_number2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["+1-202-555-0156"]})
    assert "Phone Number" in res["test"][0]["Regex Pattern"]["Name"]
    assert "United States" in res["test"][0]["Regex Pattern"]["Description"]


def test_phone_number3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["+662025550156"]})
    assert "Phone Number" in res["test"][0]["Regex Pattern"]["Name"]
    assert "Thailand" in res["test"][0]["Regex Pattern"]["Description"]


def test_phone_number4():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["+356 202 555 0156"]})
    assert "Phone Number" in res["test"][0]["Regex Pattern"]["Name"]
    assert "Malta" in res["test"][0]["Regex Pattern"]["Description"]


def test_youtube():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["https://www.youtube.com/watch?v=ScOAntcCa78"]})
    assert "YouTube" in res["test"][0]["Regex Pattern"]["Name"]


def test_youtube2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["http://www.youtube.com/watch?v=dQw4w9WgXcQ"]})
    assert "YouTube" in res["test"][0]["Regex Pattern"]["Name"]


def test_youtube_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["dQw4w9WgXcQ"]})
    assert "YouTube" in res["test"][0]["Regex Pattern"]["Name"]


def test_youtube_id2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["078-05-1120"]})
    assert "YouTube" not in res["test"][0]["Regex Pattern"]["Name"]


def test_ssn():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["001-01-0001"]})
    assert "Social" in str(res)


def test_cors():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["Access-Control-Allow: *"]})
    assert "Access" in str(res)

def test_jwt():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"]})
    assert "JWT" in str(res)

def test_s3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["http://s3.amazonaws.com/bucket/"]})
    assert "S3" in str(res)

def test_s3_internal():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["s3://bucket/path/key"]})
    assert "S3" in str(res)

def test_s3_internal2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["s3://bucket/path/directory/"]})
    assert "S3" in str(res)

def test_arn():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["arn:partition:service:region:account-id:resource"]})
    assert "ARN" in str(res)

def test_arn2():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["arn:partition:service:region:account-id:resourcetype/resource"]})
    assert "ARN" in str(res)

def test_arn3():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["arn:partition:service:region:account-id:resourcetype:resource"]})
    assert "ARN" in str(res)

def test_arn4():
    r = regex_identifier.RegexIdentifier()
    res = r.check({"test": ["arn:aws:s3:::my_corporate_bucket/Development/*"]})
    assert "ARN" in str(res)