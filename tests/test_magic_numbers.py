import json

import pytest
from click.testing import CliRunner

from pywhat.identifier import Identifier
from pywhat.magic_numbers import get_magic_nums
from pywhat.what import main

LONG_HEADERS = [
    (b"SIMPLE  =                    T", "fits"),
    (b"<<< Oracle VM VirtualBox Disk Image >>>", "vdi"),
]


@pytest.mark.parametrize("header,extension", LONG_HEADERS)
def test_file_signatures_longer_than_24_bytes(tmp_path, header, extension):
    file = tmp_path / "sample"
    file.write_bytes(header + b"\n")
    assert get_magic_nums(str(file))["Filename Extension"] == extension


@pytest.mark.parametrize("header,extension", LONG_HEADERS)
def test_identify_long_file_signature(tmp_path, header, extension):
    file = tmp_path / "sample"
    file.write_bytes(header + b"\n")
    identified = Identifier().identify(str(file), only_text=False)
    assert identified["File Signatures"]["sample"]["Filename Extension"] == extension


@pytest.mark.parametrize("header,extension", LONG_HEADERS)
def test_json_long_file_signature(tmp_path, header, extension):
    file = tmp_path / "sample"
    file.write_bytes(header + b"\n")
    result = CliRunner().invoke(main, ["-db", "--json", str(file)])
    assert result.exit_code == 0
    identified = json.loads(result.output)
    assert identified["File Signatures"]["sample"]["Filename Extension"] == extension


@pytest.mark.parametrize("header,extension", LONG_HEADERS)
def test_incomplete_long_header_is_not_identified(tmp_path, header, extension):
    file = tmp_path / "sample"
    file.write_bytes(header[:24])
    assert get_magic_nums(str(file)) is None
    file.write_bytes(header[:-1] + b"X")
    assert get_magic_nums(str(file)) is None


@pytest.mark.parametrize(
    "header,extension", [(b"\x89PNG\r\n\x1a\n", "png"), (b"", None)]
)
def test_short_file_signature_still_works(tmp_path, header, extension):
    file = tmp_path / "sample"
    file.write_bytes(header)
    signature = get_magic_nums(str(file))
    if extension is None:
        assert signature is None
    else:
        assert signature["Filename Extension"] == extension
