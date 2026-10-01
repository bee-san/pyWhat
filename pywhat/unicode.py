"""
Unicode support (issue #34): the text that pyWhat searches in the bytes of a
file or of stdin.

* A byte order mark (BOM) gives the encoding: UTF-8, or UTF-16 or UTF-32 in
  little- or big-endian byte order. Windows programs such as Notepad,
  PowerShell and regedit save "Unicode" text like this.
* Without a BOM, the text is UTF-8 (which includes ASCII). Bytes that are not
  UTF-8 are skipped, so that the text in binary files can be searched too.
* Windows programs store most of their strings in UTF-16LE, these are the
  "Unicode" strings of the strings tool (strings -el). The UTF-16LE strings
  in binary data are searched as well.

Line breaks become "\\n", like when Python reads a text file.
"""
import codecs
import io
import re
from typing import Any, List, Optional

# UTF-32 first, because the UTF-32LE BOM starts with the UTF-16LE BOM
_BOMS = [
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
]

# The minimum length of a UTF-16LE string, the default of strings
MIN_STRING_LENGTH = 4
# Printable ASCII characters and tabs in UTF-16LE, every character is followed
# by a zero byte
_UTF16LE_STRING = re.compile(rb"(?:[\t\x20-\x7e]\x00){%d,}" % MIN_STRING_LENGTH)


def _universal_newlines(text: str) -> str:
    # Like the universal newlines mode that open() reads text files with
    if "\r" in text:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text


def _decode_bom(data: bytes) -> Optional[str]:
    """
    Decode data that starts with a UTF-16 or UTF-32 BOM. Returns None if it does
    not, or if the rest of data is not valid in the encoding of the BOM. Then
    data is binary data that happens to start like a BOM.
    """
    for bom, encoding in _BOMS:
        if data.startswith(bom):
            try:
                return data[len(bom) :].decode(encoding)
            except UnicodeDecodeError:
                continue  # FF FE 00 00 can be UTF-16LE text, too
    return None


def _decode_text(data: bytes, encoding: Optional[str]) -> str:
    for name in ("utf-8-sig", encoding):
        if name is not None:
            try:
                return data.decode(name)
            except (UnicodeDecodeError, LookupError):
                pass
    return data.decode("utf-8-sig", errors="ignore")


def decode(data: bytes, encoding: Optional[str] = None) -> str:
    """
    Decode data, the bytes of a file or of stdin, to text.

    A UTF-16 or UTF-32 byte order mark (BOM) gives the encoding. Otherwise data
    is UTF-8, with or without a BOM. If data is not valid UTF-8 but is valid in
    encoding (pyWhat uses the encoding of stdin for stdin), it is decoded with
    encoding. Else the bytes that are not UTF-8 are skipped.
    """
    text = _decode_bom(data)
    if text is None:
        text = _decode_text(data, encoding)
    return _universal_newlines(text)


def utf16_strings(data: bytes) -> List[str]:
    """
    The UTF-16LE strings in data, which are at least MIN_STRING_LENGTH printable
    ASCII characters long, like the ones that strings -el finds.
    """
    return [
        match.group().decode("utf-16-le") for match in _UTF16LE_STRING.finditer(data)
    ]


def texts(data: bytes, encoding: Optional[str] = None) -> List[str]:
    """
    The texts that pyWhat searches in data, the bytes of a file or of stdin:
    data decoded with decode() and, unless data is UTF-16 or UTF-32 text with
    a BOM, the UTF-16LE strings in data, one per line, if there are any.
    """
    text = _decode_bom(data)
    if text is not None:
        return [_universal_newlines(text)]
    found = [_universal_newlines(_decode_text(data, encoding))]
    strings = utf16_strings(data)
    if strings:
        found.append("\n".join(strings))
    return found


def read_file(path: str) -> List[str]:
    """The texts that pyWhat searches in a file, see texts()."""
    with open(path, "rb") as file:
        return texts(file.read())


def escape_unencodable(stream: Any) -> None:
    """
    Make stream (sys.stdout) write the characters that its encoding cannot
    encode as escape sequences such as \\u20bf, instead of raising
    UnicodeEncodeError. For example, Python on Windows writes in a legacy
    encoding such as cp1252 when the output is redirected to a file.
    """
    if isinstance(stream, io.TextIOWrapper) and stream.errors == "strict":
        stream.reconfigure(errors="backslashreplace")
