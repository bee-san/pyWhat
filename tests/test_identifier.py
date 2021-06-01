from pywhat import identifier


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"]["None"][0]["Regex Pattern"]["Name"]

def test_identifier_works2():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert "Ethereum (ETH) Wallet Address" in out["Regexes"]["file"][0]["Regex Pattern"]["Name"]

def test_identifier_works3():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"]["file"][1]["Regex Pattern"]["Name"]