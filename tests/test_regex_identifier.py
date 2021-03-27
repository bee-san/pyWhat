from What import regex_identifier

def test_regex_successfully_parses():
    r = regex_identifier.RegexIdentifier()
    assert "Name" in r.regexes[0]

def test_regex_runs():
    r = regex_identifier.RegexIdentifier()
    res = r.check("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin" in res[0]["Name"]