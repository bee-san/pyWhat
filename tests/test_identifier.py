from pywhat import identifier


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin (DOGE) Wallet Address" in out["Regexes"][0]["Regex Pattern"]["Name"]

"""
def test_rarity_filtration():
    r = identifier.Identifier()
    out = r.identify("someguy@gmail.com", min_rarity=0.6)
    assert len(out["Regexes"]) == 0


def test_rarity_filtration2():
    r = identifier.Identifier()
    out = r.identify("ScOAntcCa78", max_rarity=0.1)
    assert len(out["Regexes"]) == 0


def test_tag_filtration():
    r = identifier.Identifier()
    out = r.identify("fixtures/file", included_tags=["Cyber Security"])
    for regex in out["Regexes"]:
        assert "Cyber Security" in regex["Regex Pattern"]["Tags"]


def test_tag_filtration2():
    r = identifier.Identifier()
    out = r.identify("+91 (385) 985 2821", excluded_tags=["Identifiers", "Credentials"])
    assert len(out["Regexes"]) == 0
"""