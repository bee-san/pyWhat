"""
Unicode support (issue #34): UTF-8, UTF-16 and UTF-32 files and stdin, the
UTF-16LE strings in binary data, and output that the terminal cannot encode.
"""
import codecs
import io
import json
import sys

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Filter
from pywhat.magic_numbers import check_magic_nums
from pywhat.unicode import decode, escape_unencodable, read_file, texts, utf16_strings
from pywhat.what import main, read_stdin

r = identifier.Identifier()

FLAG = "THM{ünïcödé}"
EMAIL = "github@skerritt.blog"
URL = "https://tryhackme.com/room/unicode"
# Windows line breaks, they become "\n"
TEXT = f"{FLAG}\r\n{EMAIL}\r\n{URL}\r\n"
LINES = f"{FLAG}\n{EMAIL}\n{URL}\n"

BOMS = [
    ("utf-8", codecs.BOM_UTF8, "UTF-8"),
    ("utf-16-le", codecs.BOM_UTF16_LE, "little-endian UTF-16"),
    ("utf-16-be", codecs.BOM_UTF16_BE, "big-endian UTF-16"),
    ("utf-32-le", codecs.BOM_UTF32_LE, "little-endian UTF-32"),
    ("utf-32-be", codecs.BOM_UTF32_BE, "big-endian UTF-32"),
]

# A Windows program with its strings in UTF-16LE
PROGRAM = (
    b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    + URL.encode("utf-16-le")
    + b"\x00\x00\x13\x37"
    + "abc".encode("utf-16-le")  # too short to be a string
    + b"\x00\x00"
    + EMAIL.encode("utf-16-le")
    + b"\x00\x00"
)


def matched(out: dict, location: str) -> list:
    return [match["Matched"] for match in (out["Regexes"] or {}).get(location, [])]


@pytest.mark.parametrize(
    "encoding, bom", [("utf-8", b"")] + [(encoding, bom) for encoding, bom, _ in BOMS]
)
def test_decode(encoding, bom):
    assert decode(bom + TEXT.encode(encoding)) == LINES


def test_decode_line_breaks():
    assert decode(b"a\r\nb\rc\nd\r") == "a\nb\nc\nd\n"


def test_decode_skips_bytes_that_are_not_utf8():
    # As before, so that the text in binary files can be searched
    data = b"\xff\x00thm{abc}\x80\xc3"
    assert decode(data) == data.decode("utf-8", errors="ignore") == "\x00thm{abc}"


def test_decode_binary_data_that_starts_like_a_bom():
    # A high surrogate (D800) without a low one is not UTF-16
    assert decode(codecs.BOM_UTF16_LE + b"\x00\xd8thm{abc}") == "\x00thm{abc}"


def test_decode_utf16_text_that_starts_like_utf32():
    # FF FE 00 00 also starts UTF-16LE text that starts with U+0000
    data = codecs.BOM_UTF16_LE + "\x00thm{abc}".encode("utf-16-le")
    assert data.startswith(codecs.BOM_UTF32_LE)
    assert decode(data) == "\x00thm{abc}"


def test_decode_with_encoding():
    assert decode("THM{café}".encode("cp1252"), "cp1252") == "THM{café}"
    # Valid UTF-8 is UTF-8
    assert decode("THM{café}".encode("utf-8"), "cp1252") == "THM{café}"
    # Neither UTF-8 nor cp1252 (which has no 0x81)
    assert decode(b"THM{caf\xe9\x81}", "cp1252") == "THM{caf}"
    assert decode(b"THM{caf\xe9}", "no such encoding") == "THM{caf}"


def test_utf16_strings():
    tabbed = "\tTHM{wide strings}"
    data = PROGRAM + tabbed.encode("utf-16-le")
    assert utf16_strings(data) == [URL, EMAIL, tabbed]
    # Strings are found in any byte position
    assert utf16_strings(b"\x01" + data) == [URL, EMAIL, tabbed]


@pytest.mark.parametrize(
    "data",
    [
        b"",
        EMAIL.encode(),
        LINES.encode("utf-8"),
        "abc".encode("utf-16-le"),
        b"a\x00b\x00c\x00\xffd\x00e\x00f\x00",
    ],
)
def test_no_utf16_strings(data):
    assert utf16_strings(data) == []


def test_texts_of_binary_data():
    data = b"\x7fELF\x02\x01" + FLAG.encode() + b"\x00" + PROGRAM
    assert texts(data) == [data.decode("utf-8", errors="ignore"), f"{URL}\n{EMAIL}"]


def test_texts_of_utf16_text():
    # The decoded text is not searched for UTF-16LE strings again
    assert texts(codecs.BOM_UTF16_LE + TEXT.encode("utf-16-le")) == [LINES]


@pytest.mark.parametrize("path", ["fixtures/file", "fixtures/test/file"])
def test_read_text_file_like_before(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        assert read_file(path) == [file.read()]


@pytest.mark.parametrize("encoding, bom, name", BOMS)
def test_identify_unicode_file(tmp_path, encoding, bom, name):
    (tmp_path / "unicode.txt").write_bytes(bom + TEXT.encode(encoding))
    out = r.identify(str(tmp_path / "unicode.txt"), only_text=False)
    # Without boundaryless mode, so the first line is found after the BOM too
    assert {FLAG, EMAIL, URL} <= set(matched(out, "unicode.txt"))
    assert name in out["File Signatures"]["unicode.txt"]["Description"]


def test_identify_utf16_strings_in_binary_file(tmp_path):
    (tmp_path / "program.exe").write_bytes(PROGRAM)
    out = r.identify(str(tmp_path / "program.exe"), only_text=False)
    assert "DOS MZ executable" in out["File Signatures"]["program.exe"]["Description"]
    assert {URL, EMAIL} <= set(matched(out, "program.exe"))


def test_identify_utf16_strings_once(tmp_path):
    (tmp_path / "program.exe").write_bytes(PROGRAM)
    out = identifier.Identifier(boundaryless=Filter()).identify(
        str(tmp_path / "program.exe"), only_text=False
    )
    found = matched(out, "program.exe")
    assert found.count(URL) == 1
    assert found.count(EMAIL) == 1
    # No string is found again from the wrong byte position
    assert EMAIL[1:] not in found
    assert URL[1:] not in found


@pytest.mark.parametrize("encoding, bom, name", BOMS)
def test_byte_order_mark_signature(encoding, bom, name):
    signature = check_magic_nums((bom + "thm".encode(encoding)).hex())
    assert name in signature["Description"]


def test_longest_signature_is_used():
    # 00 is a signature too, 0000FEFF is the more specific one
    assert "UTF-32" in check_magic_nums("0000feff00000074")["Description"]
    assert "UTF-16" in check_magic_nums("fffe7400")["Description"]
    assert check_magic_nums("74686d7b") is None


def test_stdin_utf16():
    result = CliRunner().invoke(
        main, ["-db"], input=codecs.BOM_UTF16_LE + TEXT.encode("utf-16-le")
    )
    assert result.exit_code == 0
    assert FLAG in result.output
    assert "TryHackMe Flag Format" in result.output
    assert "Email Address" in result.output


def test_stdin_that_is_not_utf8():
    # Used to raise UnicodeDecodeError
    result = CliRunner().invoke(main, ["-db"], input=b"THM{caf\xe9}")
    assert result.exit_code == 0
    assert "TryHackMe Flag Format" in result.output


def test_stdin_in_the_encoding_of_stdin():
    result = CliRunner(charset="cp1252").invoke(
        main, ["-db"], input="THM{café}".encode("cp1252")
    )
    assert result.exit_code == 0
    assert "THM{café}" in result.output


def test_stdin_utf16_strings():
    result = CliRunner().invoke(main, ["-db"], input=PROGRAM)
    assert result.exit_code == 0
    assert URL in result.output
    assert EMAIL in result.output


def test_stdin_without_binary_stream(monkeypatch):
    monkeypatch.setattr(sys, "stdin", io.StringIO(f" {FLAG}\n"))
    assert read_stdin() == FLAG


@pytest.mark.parametrize(
    "output_format, expected",
    [
        ([], "Name: Bitcoin (\\u20bf) Wallet Address"),
        (["--format", "pretty"], "Possible Identification"),
    ],
)
def test_output_that_the_terminal_cannot_encode(output_format, expected):
    # The Bitcoin regex is called "Bitcoin (\u20bf) Wallet Address", and cp1252
    # (e.g. Python on Windows, redirected to a file) has no U+20BF
    result = CliRunner(charset="cp1252").invoke(
        main, ["-db", *output_format, "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"]
    )
    assert result.exit_code == 0, result.output
    assert expected in result.output
    assert "\\u20bf" in result.output


def test_output_ascii_terminal():
    result = CliRunner(charset="ascii").invoke(main, ["-db", FLAG])
    assert result.exit_code == 0, result.output
    assert "THM{\\xfcn\\xefc\\xf6d\\xe9}" in result.output


def test_json_output_ascii_terminal():
    result = CliRunner(charset="ascii").invoke(main, ["-db", "--json", FLAG])
    assert result.exit_code == 0
    assert json.loads(result.output)["Regexes"]["text"][0]["Matched"] == FLAG


def test_escape_unencodable():
    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="cp1252")
    escape_unencodable(stream)
    stream.write("café \u20bf")
    stream.flush()
    assert buffer.getvalue() == b"caf\xe9 \\u20bf"


def test_escape_unencodable_keeps_other_error_handlers():
    stream = io.TextIOWrapper(io.BytesIO(), encoding="ascii", errors="replace")
    escape_unencodable(stream)
    assert stream.errors == "replace"
    escape_unencodable(io.StringIO())  # not a TextIOWrapper, nothing to do
