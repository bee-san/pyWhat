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

def test_ctf_flag():
    r = regex_identifier.RegexIdentifier()
    res = r.check("thm{hello}")
    assert "Capture The Flag Flags" in res[0]["Name"]

def test_ctf_flag_uppercase():
    r = regex_identifier.RegexIdentifier()
    res = r.check("FLAG{hello}")
    assert "Capture The Flag Flags" in res[0]["Name"]

def test_ethereum():
    r = regex_identifier.RegexIdentifier()
    res = r.check("0x52908400098527886E0F7030069857D2E4169EE7")
    assert "Ethereum Wallet" in res[0]["Name"]