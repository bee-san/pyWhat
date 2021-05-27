from pywhat import identifier


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"][0]["Regex Pattern"]["Name"]

