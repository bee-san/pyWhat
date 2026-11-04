import json
import os

import pytest
from click.testing import CliRunner

from pywhat.identifier import Identifier
from pywhat.what import main

r = Identifier()


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX absolute paths can repeat in children"
)
@pytest.mark.parametrize("absolute", [False, True])
@pytest.mark.parametrize("several", [False, True])
def test_directory_locations_preserve_repeated_root(
    tmp_path, monkeypatch, absolute, several
):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "scan"
    ordinary = root / "backup" / "item"
    nested = root / "backup" / str(root).lstrip(os.sep) / "item"
    ordinary.parent.mkdir(parents=True)
    nested.parent.mkdir(parents=True)
    ordinary.write_bytes(b"%PDF-1.7\nTHM{ordinary}")
    nested.write_bytes(b"\x89PNG\r\n\x1a\nTHM{nested}")
    source = str(root) if absolute else "scan"
    inputs = [source, "THM{extra}"] if several else [source]
    out = r.identify_inputs(inputs, only_text=False)
    ordinary_location = os.sep + str(ordinary.relative_to(root))
    nested_location = os.sep + str(nested.relative_to(root))
    if several:
        ordinary_location = os.path.join(source, ordinary_location.lstrip(os.sep))
        nested_location = os.path.join(source, nested_location.lstrip(os.sep))
    assert set(out["File Signatures"]) == {ordinary_location, nested_location}
    assert out["File Signatures"][ordinary_location]["Filename Extension"] == "pdf"
    assert out["File Signatures"][nested_location]["Filename Extension"] == "png"
    assert [match["Matched"] for match in out["Regexes"][ordinary_location]] == [
        "THM{ordinary}"
    ]
    assert [match["Matched"] for match in out["Regexes"][nested_location]] == [
        "THM{nested}"
    ]
    if several:
        assert out["Regexes"]["text"][0]["Matched"] == "THM{extra}"


@pytest.mark.parametrize("absolute", [False, True])
def test_ordinary_directory_location_format(tmp_path, monkeypatch, absolute):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "scan"
    root.mkdir()
    (root / "item").write_text("THM{ordinary}")
    source = str(root) if absolute else "scan"
    out = r.identify(source, only_text=False)
    assert list(out["Regexes"]) == [os.sep + "item"]
    out = r.identify_inputs([source, "THM{extra}"], only_text=False)
    assert set(out["Regexes"]) == {os.path.join(source, "item"), "text"}


@pytest.mark.skipif(
    os.name == "nt", reason="POSIX absolute paths can repeat in children"
)
def test_json_directory_preserves_colliding_path_components(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "scan"
    ordinary = root / "backup" / "item"
    nested = root / "backup" / str(root).lstrip(os.sep) / "item"
    ordinary.parent.mkdir(parents=True)
    nested.parent.mkdir(parents=True)
    ordinary.write_bytes(b"%PDF-1.7\nTHM{ordinary}")
    nested.write_bytes(b"\x89PNG\r\n\x1a\nTHM{nested}")
    result = CliRunner().invoke(main, ["-db", "--json", "scan"])
    assert result.exit_code == 0
    out = json.loads(result.output)
    expected = {
        os.sep + str(ordinary.relative_to(root)),
        os.sep + str(nested.relative_to(root)),
    }
    assert set(out["File Signatures"]) == expected
    assert set(out["Regexes"]) == expected
