import pytest
from pywhat import regex_identifier


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    print(r.regexes)
    assert "Name" in r.regexes[0]


def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    assert "Dogecoin Wallet Address" in res[0]["Regex Pattern"]["Name"]


@pytest.mark.skip(reason="Fails Regex due to http://")
def test_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["tryhackme.com"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_https():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://tryhackme.com"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_lat_long():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["52.6169586, -1.9779857"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["53.76297,-1.9388732"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://10.1.1.1"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_ip2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://0.0.0.0"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


@pytest.mark.skip(reason="Fails Regex due to http://")
def test_internationak_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["http://папироска.рф"])
    assert "Uniform Resource Locator (URL)" in res[0]["Regex Pattern"]["Name"]


def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["thm{hello}"])
    assert "TryHackMe Flag Format" in res[0]["Regex Pattern"]["Name"]


def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["FLAG{hello}"])
    assert "CTF Flag" in res[0]["Regex Pattern"]["Name"]


def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["0x52908400098527886E0F7030069857D2E4169EE7"])
    assert "Ethereum Wallet" in res[0]["Regex Pattern"]["Name"]


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    assert "Bitcoin" in res[0]["Regex Pattern"]["Name"]


def test_visa():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["4111111111111111"])
    assert "Visa" in res[0]["Regex Pattern"]["Name"]


def test_master_Card():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["5500000000000004"])
    assert "MasterCard" in res[0]["Regex Pattern"]["Name"]


def test_american_express():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["340000000000009"])
    assert "American Express" in res[0]["Regex Pattern"]["Name"]


def test_american_diners_club():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["30000000000004"])
    assert "Diners Club Card" in res[0]["Regex Pattern"]["Name"]


def test_american_diners_discover():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["6011000000000004"])
    assert "Discover" in res[0]["Regex Pattern"]["Name"]


@pytest.mark.skip("Key:value is turned off")
def test_username():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["james:S3cr37_P@$$W0rd"])
    assert "Key:Value" in res[0]["Regex Pattern"]["Name"]


def test_email():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["github@skerritt.blog"])
    assert "Email" in res[0]["Regex Pattern"]["Name"]


def test_youtube():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://www.youtube.com/watch?v=ScOAntcCa78"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_youtube2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["https://www.youtube.com/watch?v=ScOAntcCa78"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_youtube_id():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["ScOAntcCa78"])
    assert "YouTube" in res[0]["Regex Pattern"]["Name"]


def test_ssn():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["001-01-0001"])
    assert "Social" in str(res)

def test_cors():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["Access-Control-Allow: *"])
    assert "Access" in str(res)