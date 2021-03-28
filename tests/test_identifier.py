from What import identifier


def test_identifier_works():
    r = identifier.Identifier()
    out = r.identify("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o")
    assert "Dogecoin" in out["Regexes"][0]["Name"]


def test_identifier_spanish():
    r = identifier.Identifier()
    out = r.identify("Me gustan los bombos y la musica ")
    assert "es" in out["Language"]
