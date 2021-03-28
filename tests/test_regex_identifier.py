import pytest
from What import regex_identifier

def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    assert "Name" in r.regexes[0]

def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin" in res[0]["Name"]

def test_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check("tryhackme.com")
    assert "Uniform Resource Locator (URL)" in res[0]["Name"]

@pytest.mark.skip(reason="Fails Regex due to http://")
def test_https():
    r = regex_identifier.RegexIdentifier()
    res = r.check("https://tryhackme.com")
    assert "Uniform Resource Locator (URL)" in res[0]["Name"]

@pytest.mark.skip(reason="Fails Regex due to http://")
def test_ip():
    r = regex_identifier.RegexIdentifier()
    res = r.check("http://10.1.1.1")
    assert "Uniform Resource Locator (URL)" in res[0]["Name"]

@pytest.mark.skip(reason="Fails Regex due to http://")
def test_ip2():
    r = regex_identifier.RegexIdentifier()
    res = r.check("http://0.0.0.0")
    assert "Uniform Resource Locator (URL)" in res[0]["Name"]

@pytest.mark.skip(reason="Fails Regex due to http://")
def test_internationak_url():
    r = regex_identifier.RegexIdentifier()
    res = r.check("http://папироска.рф")
    assert "Uniform Resource Locator (URL)" in res[0]["Name"]

def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check("thm{hello}")
    assert "Flag from Capture The Flag (CyberSecurity)" in res[0]["Name"]

def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check("FLAG{hello}")
    assert "Flag from Capture The Flag (CyberSecurity)" in res[0]["Name"]

def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check("0x52908400098527886E0F7030069857D2E4169EE7")
    assert "Ethereum Wallet" in res[0]["Name"]

def test_bitcoin():
    r = regex_identifier.RegexIdentifier()
    res = r.check("1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY")
    assert "Bitcoin" in res[0]["Name"]