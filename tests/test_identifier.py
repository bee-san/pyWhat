from pywhat.distribution import Distribution
from pywhat import identifier


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]


def test_identifier_works2():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert "Ethereum (ETH) Wallet Address" in out["Regexes"]["file"][0]["Regex Pattern"]["Name"]


def test_identifier_works3():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"]["file"][1]["Regex Pattern"]["Name"]


def test_identifier_filtration():
    filter = {"Tags": ["Password"]}
    r = identifier.Identifier(Distribution(filter))
    regexes = r.identify('fixtures/file')["Regexes"]["file"]
    for regex in regexes:
        assert "Password" in regex["Regex Pattern"]["Tags"]


def test_identifier_filtration2():
    filter1 = {"ExcludeTags": ["Identifiers"]}
    filter2 = {"Tags": ["Identifiers"], "MinRarity": 0.6}
    r = identifier.Identifier(Distribution(filter1))
    regexes = r.identify('fixtures/file', dist=Distribution(filter2))["Regexes"]["file"]
    for regex in regexes:
        assert "Identifiers" in regex["Regex Pattern"]["Tags"]
        assert regex["Regex Pattern"]["Rarity"] >= 0.6
