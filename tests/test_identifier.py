import os
import re

import pytest

from pywhat import identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import Keys
from pywhat.processors import Processor

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


@pytest.mark.parametrize(
    "text, name, matched",
    [
        (
            'GET /?q=${jndi:ldap://example.com/a} HTTP/1.1" 200',
            "Log4Shell (Log4j JNDI Lookup) Payload",
            "${jndi:ldap://example.com/a}",
        ),
        (
            "databaseURL: 'https://pywhat-test.firebaseio.com',",
            "Firebase Realtime Database URL",
            "https://pywhat-test.firebaseio.com",
        ),
        (
            "Cookie: session=rO0ABXQABWhlbGxv; path=/",
            "Base64 Encoded Java Serialized Object",
            "rO0ABXQABWhlbGxv",
        ),
        (
            "aws_access_key_id = AKIAIOSFODNN7EXAMPLE\n",
            "Amazon Web Services Access Key",
            "AKIAIOSFODNN7EXAMPLE",
        ),
        (
            "ingress allowed from 10.0.0.0/8 only",
            "Internet Protocol (IP) Address Version 4 CIDR Block",
            "10.0.0.0/8",
        ),
        (
            'Cookie: data=a:1:{s:4:"user";O:8:"stdClass":1:{s:2:"id";i:42;}}; path=/',
            "PHP Serialized Object",
            'a:1:{s:4:"user";O:8:"stdClass":1:{s:2:"id";i:42;}}',
        ),
    ],
)
def test_boundaryless_gf_regexes(text, name, matched):
    r = identifier.Identifier(boundaryless=Filter())
    out = r.identify(text)
    assert any(
        match["Regex Pattern"]["Name"] == name and match["Matched"] == matched
        for match in out["Regexes"]["text"]
    )


def test_identifier_sorting_directory(tmp_path):
    # The matches of every file of a directory are sorted, not only the
    # matches of the last file (whichever file the file system lists last)
    with open("fixtures/file", "rb") as file:
        contents = file.read()
    for name in ("a", "b"):
        (tmp_path / name).write_bytes(contents)
    out = r.identify(str(tmp_path), only_text=False, key=Keys.NAME)
    assert len(out["Regexes"]) == 2
    for matches in out["Regexes"].values():
        names = [match["Regex Pattern"]["Name"] for match in matches]
        assert names == sorted(names)


def test_identifier_sorting_without_matches():
    # Used to raise TypeError: 'NoneType' object is not subscriptable
    out = r.identify("nothing", key=Keys.NAME)
    assert out == {"File Signatures": None, "Regexes": None}


# Multiple inputs (issue #171)


def test_identify_inputs_single_input():
    # A single input is identified like with identify()
    for text in ["fixtures", "fixtures/file", "THM{hello}", "nothing"]:
        assert r.identify_inputs([text], only_text=False) == r.identify(
            text, only_text=False
        )


def test_identify_inputs_files():
    out = r.identify_inputs(["fixtures/file", "fixtures/test/file"], only_text=False)
    # Under their paths, as both files are called "file"
    assert list(out["Regexes"]) == ["fixtures/file", "fixtures/test/file"]
    assert (
        out["Regexes"]["fixtures/file"]
        == r.identify("fixtures/file", only_text=False)["Regexes"]["file"]
    )
    assert [match["Matched"] for match in out["Regexes"]["fixtures/test/file"]] == [
        "https://google.com"
    ]
    assert out["File Signatures"] is None


def test_identify_inputs_directory_and_text():
    out = r.identify_inputs(["fixtures", "THM{hello}"], only_text=False)
    assert set(out["Regexes"]) == {
        os.path.join("fixtures", "file"),
        os.path.join("fixtures", "test", "file"),
        "text",
    }
    assert out["Regexes"]["text"][0]["Matched"] == "THM{hello}"


def test_identify_inputs_texts():
    out = r.identify_inputs(["THM{hello}", "DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"])
    # The matches in every text are under "text", like in a single text
    assert list(out["Regexes"]) == ["text"]
    names = [match["Regex Pattern"]["Name"] for match in out["Regexes"]["text"]]
    assert "TryHackMe Flag Format" in names
    assert "Dogecoin (DOGE) Wallet Address" in names


def test_identify_inputs_only_text():
    # By default, like identify(), the inputs are text and not paths
    out = r.identify_inputs(["fixtures/file", "THM{hello}"])
    assert list(out["Regexes"]) == ["text"]
    assert [match["Matched"] for match in out["Regexes"]["text"]] == ["THM{hello}"]


def test_identify_inputs_nothing_found():
    assert r.identify_inputs(["nothing", ""], only_text=False) == {
        "File Signatures": None,
        "Regexes": None,
    }
    assert r.identify_inputs([]) == {"File Signatures": None, "Regexes": None}


def test_identify_inputs_file_signatures(tmp_path):
    image = str(tmp_path / "image.png")
    with open(image, "wb") as file:
        file.write(b"\x89PNG\r\n\x1a\nTHM{hello}\n")
    out = r.identify_inputs([image, "fixtures/test/file"], only_text=False)
    assert list(out["File Signatures"]) == [image]
    assert out["File Signatures"][image]["Filename Extension"] == "png"
    assert [match["Matched"] for match in out["Regexes"][image]] == ["THM{hello}"]


def test_identify_inputs_sorting():
    out = r.identify_inputs(
        ["fixtures/file", "THM{hello}", "fixtures"],
        only_text=False,
        key=Keys.NAME,
        reverse=True,
    )
    for matches in out["Regexes"].values():
        names = [match["Regex Pattern"]["Name"] for match in matches]
        assert names == sorted(names, reverse=True)

    # The key of the identifier is the default
    r_sorted = identifier.Identifier(key=Keys.MATCHED)
    out = r_sorted.identify_inputs(["THM{b}", "THM{a}"])
    assert [match["Matched"] for match in out["Regexes"]["text"]] == [
        "THM{a}",
        "THM{b}",
    ]


def test_identify_inputs_processors():
    class FlagCounter(Processor):
        names = ["TryHackMe Flag Format"]

        def __init__(self):
            self.count = 0

        def process(self, match):
            self.count += 1
            return match

    counter = FlagCounter()
    # A generator of processors is used for every input
    out = r.identify_inputs(["THM{a}", "THM{b}"], processors=(p for p in [counter]))
    assert counter.count == 2
    assert len(out["Regexes"]["text"]) == 2
