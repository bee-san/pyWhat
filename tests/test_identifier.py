import re
from pywhat import identifier
from pywhat.distribution import Distribution
from pywhat.helper import keys


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert (
        "Dogecoin (DOGE) Wallet Address" in out["Regexes"][0]["Regex Pattern"]["Name"]
    )


def test_identifier_filtration():
    filter = {"Tags": ["Password"]}
    r = identifier.Identifier(dist=Distribution(filter))
    regexes = r.identify("fixtures/file")["Regexes"]
    for regex in regexes:
        assert "Password" in regex["Regex Pattern"]["Tags"]


def test_identifier_filtration2():
    filter1 = {"ExcludeTags": ["Identifiers"]}
    filter2 = {"Tags": ["Identifiers"], "MinRarity": 0.6}
    r = identifier.Identifier(dist=Distribution(filter1))
    regexes = r.identify("fixtures/file", dist=Distribution(filter2))["Regexes"]
    for regex in regexes:
        assert "Identifiers" in regex["Regex Pattern"]["Tags"]
        assert regex["Regex Pattern"]["Rarity"] >= 0.6


def test_identifier_sorting():
    r = identifier.Identifier(key=keys.name, reverse=True)
    out = r.identify("fixtures/file", key=keys.rarity, reverse=False)
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev <= match["Regex Pattern"]["Rarity"]
        prev = match["Regex Pattern"]["Rarity"]


def test_identifier_sorting2():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", reverse=True)
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Rarity"]
        prev = match["Regex Pattern"]["Rarity"]


def test_identifier_sorting3():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=keys.name)
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev <= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting4():
    r = identifier.Identifier(key=keys.name, reverse=True)
    out = r.identify("fixtures/file")
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting5():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=keys.matched)
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev <= match["Matched"]
        prev = match["Matched"]


def test_identifier_sorting6():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=keys.matched, reverse=True)
    prev = None
    for match in out["Regexes"]:
        if prev is not None:
            assert prev >= match["Matched"]
        prev = match["Matched"]