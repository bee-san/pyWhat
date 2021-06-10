from pywhat import identifier
from pywhat.distribution import Distribution
from pywhat.helper import Keys


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert (
        "Dogecoin (DOGE) Wallet Address" in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]
    )


def test_identifier_works2():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert (
        "Ethereum (ETH) Wallet Address"
        in out["Regexes"]["file"][0]["Regex Pattern"]["Name"]
    )


def test_identifier_works3():
    r = identifier.Identifier()
    out = r.identify("fixtures/file")
    assert (
        "Dogecoin (DOGE) Wallet Address"
        in out["Regexes"]["file"][1]["Regex Pattern"]["Name"]
    )


def test_identifier_filtration():
    filter = {"Tags": ["Password"]}
    r = identifier.Identifier(dist=Distribution(filter))
    regexes = r.identify("fixtures/file")["Regexes"]["file"]
    for regex in regexes:
        assert "Password" in regex["Regex Pattern"]["Tags"]


def test_identifier_filtration2():
    filter1 = {"ExcludeTags": ["Identifiers"]}
    filter2 = {"Tags": ["Identifiers"], "MinRarity": 0.6}
    r = identifier.Identifier(dist=Distribution(filter1))
    regexes = r.identify("fixtures/file", dist=Distribution(filter2))["Regexes"]["file"]
    for regex in regexes:
        assert "Identifiers" in regex["Regex Pattern"]["Tags"]
        assert regex["Regex Pattern"]["Rarity"] >= 0.6


def test_identifier_sorting():
    r = identifier.Identifier(key=Keys.NAME, reverse=True)
    out = r.identify("fixtures/file")
    assert out["Regexes"]["file"]


def test_identifier_sorting2():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=Keys.RARITY, reverse=True)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Rarity"]
        prev = match["Regex Pattern"]["Rarity"]


def test_identifier_sorting3():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=Keys.NAME)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev <= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting4():
    r = identifier.Identifier(key=Keys.NAME, reverse=True)
    out = r.identify("fixtures/file")
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Regex Pattern"]["Name"]
        prev = match["Regex Pattern"]["Name"]


def test_identifier_sorting5():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=Keys.MATCHED)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev <= match["Matched"]
        prev = match["Matched"]


def test_identifier_sorting6():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", key=Keys.MATCHED, reverse=True)
    prev = None
    for match in out["Regexes"]["file"]:
        if prev is not None:
            assert prev >= match["Matched"]
        prev = match["Matched"]


def test_only_text():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", only_text=True)
    assert None == out["Regexes"]

    out = r.identify("THM{7281j}}", only_text=True)
    assert "TryHackMe Flag Format" in out["Regexes"]["text"][0]["Regex Pattern"]["Name"]
