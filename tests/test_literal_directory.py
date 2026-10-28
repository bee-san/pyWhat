import os

import pytest

from pywhat.identifier import Identifier


@pytest.mark.parametrize("name", ["scan[2026]", "scan?2026", "scan*2026"])
def test_directory_names_are_literal_paths(tmp_path, name):
    # Brackets are legal on Windows too; ? and * are only legal on Unix.
    if os.name == "nt" and any(char in name for char in "?*"):
        pytest.skip("Windows does not allow this character in a directory name")
    directory = tmp_path / name
    directory.mkdir()
    (directory / "data.txt").write_text("THM{literal_directory}", encoding="utf-8")
    # A sibling that matches the unescaped glob must not be scanned instead.
    sibling = tmp_path / "scanX2026"
    sibling.mkdir()
    (sibling / "other.txt").write_text("THM{wrong_directory}", encoding="utf-8")

    result = Identifier().identify(str(directory), only_text=False)
    found = [
        match["Matched"]
        for matches in (result["Regexes"] or {}).values()
        for match in matches
    ]
    assert "THM{literal_directory}" in found
    assert "THM{wrong_directory}" not in found
