import pytest
from pywhat import regex_identifier


def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    print(r.regexes)
    assert "Name" in r.regexes[0]


def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    assert "Dogecoin (DOGE) Wallet Address" in res[0]["Regex Pattern"]["Name"]


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


def test_lat_long3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(['77° 30\' 29.9988" N'])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["N 32° 53.733 W 096° 48.358"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long5():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["41°24\'12.2\" N 2°10\'26.5\" E"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_lat_long6():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["40.741895,-73.989308"])
    assert "Latitude & Longitude Coordinates" in res[0]["Regex Pattern"]["Name"]


def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["10.1.1.1"])
    assert "Internet Protocol (IP) Address version 4" in res[0]["Regex Pattern"]["Name"]


def test_ip2():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["192.0.2.235:80"])
    assert "192.0.2.235:80" in res[0]["Matched"]


def test_ip3():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["2001:0db8:85a3:0000:0000:8a2e:0370:7334"])
    assert "Internet Protocol (IP) Address version 6" in res[0]["Regex Pattern"]["Name"]


def test_ip4():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["[2001:db8::1]:8080"])
    assert "[2001:db8::1]:8080" in res[0]["Matched"]


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
    assert "Ethereum (ETH) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    assert "Bitcoin (BTC) Wallet Address" in res[0]["Regex Pattern"]["Name"]


def test_monero():
    r = regex_identifier.RegexIdentifier()
    res = r.check(["47DF8D9NwtmefhFUghynYRMqrexiZTsm48T1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFfdaqAT3jnBEwoMwCx6BYDJ1W3ub"])
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
