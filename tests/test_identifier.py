import re

from pywhat import identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import Keys

r = identifier.Identifier()


def test_identifier_works():
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert (
        "Dogecoin (DOGE) Wallet Address"
        in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]
    )


def test_identifier_works2():
    out = r.identify("fixtures/file", only_text=False)
    assert "Ethereum (ETH) Wallet Address" in str(out)


def test_identifier_works3():
    out = r.identify("fixtures/file", only_text=False)
    assert "Dogecoin (DOGE) Wallet Address" in str(out)


def test_identifier_filtration():
    filter = {"Tags": ["Credentials"]}
    r = identifier.Identifier(dist=Distribution(filter))
    regexes = r.identify("fixtures/file", only_text=False)["Regexes"]["file"]
    for regex in regexes:
        assert "Credentials" in regex["Regex Pattern"]["Tags"]


def test_identifier_filtration2():
    filter1 = {"ExcludeTags": ["Identifiers"]}
    filter2 = {"Tags": ["Identifiers"], "MinRarity": 0.6}
    r = identifier.Identifier(dist=Distribution(filter1))
    regexes = r.identify("fixtures/file", only_text=False, dist=Distribution(filter2))[
        "Regexes"
    ]["file"]
    for regex in regexes:
        assert "Identifiers" in regex["Regex Pattern"]["Tags"]
        assert regex["Regex Pattern"]["Rarity"] >= 0.6


def test_identifier_sorting():
    r = identifier.Identifier(key=Keys.NAME, reverse=True)
    out = r.identify("fixtures/file", only_text=False)
    assert out["Regexes"]["file"]


def test_identifier_sorting2():
    out = r.identify("fixtures/file", only_text=False, key=Keys.RARITY, reverse=True)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Rarity"]
        prev = match["Regex Pattern"]["Rarity"]


def test_identifier_sorting3():
    out = r.identify("fixtures/file", only_text=False, key=Keys.NAME)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev <= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting4():
    r = identifier.Identifier(key=Keys.NAME, reverse=True)
    out = r.identify("fixtures/file", only_text=False)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting5():
    out = r.identify("fixtures/file", only_text=False, key=Keys.MATCHED)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev <= match["Matched"]
        prev = match["Matched"]


def test_identifier_sorting6():
    out = r.identify("fixtures/file", only_text=False, key=Keys.MATCHED, reverse=True)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Matched"]
        prev = match["Matched"]


def test_only_text():
    out = r.identify("fixtures/file")
    assert out["Regexes"] is None

    out = r.identify("THM{7281j}}", only_text=True)
    assert "TryHackMe Flag Format" in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]


def test_recursion():
    out = r.identify("fixtures", only_text=False)

    assert re.findall(r"\'(?:\/|\\\\)file\'", str(list(out["Regexes"].keys())))
    assert re.findall(
        r"\'(?:\/|\\\\)test(?:\/|\\\\)file\'", str(list(out["Regexes"].keys()))
    )


def test_boundaryless():
    r = identifier.Identifier(boundaryless=Filter())
    out = r.identify("127.0.0.1abrakadabra")
    assert (
        "Internet Protocol (IP) Address Version 4"
        in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]
    )
    out = r.identify("127.0.0.1abrakadabra", boundaryless=Filter({"Tags": ["Media"]}))
    assert out["Regexes"] is None


def test_finditer():
    r = identifier.Identifier(boundaryless=Filter())
    out = r.identify("anon@random.org dad@gmail.com")
    assert "anon@random.org" in out["Regexes"]["text"][2]["Matched"]
    assert "dad@gmail.com" in out["Regexes"]["text"][3]["Matched"]
