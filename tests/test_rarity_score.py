"""
Tests for scripts/rarity_score.py, which estimates the rarity of a regex from
the regex itself (issue #238).
"""
import importlib.util
import json
import math
import re
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

# scripts/ is not a package, so load the script from its file
SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "rarity_score.py"
_spec = importlib.util.spec_from_file_location("rarity_score", SCRIPT)
assert _spec is not None and _spec.loader is not None
rarity_score = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rarity_score)

LETTER = math.log2(26)
DIGIT = math.log2(10)
SEPARATOR = math.log2(59 / 4)
SYMBOL = math.log2(59)


@pytest.mark.parametrize(
    "regex, bits",
    [
        # Fixed characters
        ("^(a)$", LETTER),
        ("^(Z)$", LETTER),
        ("(?i)^(a)$", LETTER),
        ("^(7)$", DIGIT),
        ("^(-)$", SEPARATOR),
        ("^( )$", SEPARATOR),
        ("^(@)$", SYMBOL),
        ("^(\\{)$", SYMBOL),
        ("^(\u00b0)$", SYMBOL),
        ("^(ghp_)$", 3 * LETTER + SEPARATOR),
        # Character classes: the largest share of a kind of characters
        ("^([13])$", math.log2(10 / 2)),
        ("^([a-f])$", math.log2(26 / 6)),
        ("(?i)^([A-F])$", math.log2(26 / 6)),
        ("^([aB])$", LETTER),
        ("(?i)^([aB])$", math.log2(26 / 2)),
        ("^((?i:[aB]))$", math.log2(26 / 2)),
        ("(?i)^((?-i:[aB]))$", LETTER),
        ("^([@#])$", math.log2(59 / 2)),
        ("^([-.])$", math.log2(59 / 8)),
        ("^([0-9a-f])$", 0),
        ("^([0-9a-fA-F])$", 0),
        ("^([A-Za-z0-9+/=])$", 0),
        ("^([a-z])$", 0),
        ("^(\\d)$", 0),
        ("^(\\w)$", 0),
        ("^(\\D)$", 0),
        ("^(\\S)$", 0),
        ("^(.)$", 0),
        ("^([^a])$", 0),
        ("^([^\\n])$", 0),
        ("^([^\\d])$", 0),
        ("^([^\\x00-\\x7f])$", 0),
        ("^([\u0400-\u04ff])$", 0),
        # Repeats count their minimum
        ("^(a{3})$", 3 * LETTER),
        ("^(a{2,5})$", 2 * LETTER),
        ("^(a+)$", LETTER),
        ("^(a+?)$", LETTER),
        ("^(a?)$", 0),
        ("^(a*)$", 0),
        ("^(a{0,30})$", 0),
        ("^((?:ab){2})$", 4 * LETTER),
        ("^([0-9a-f]{40})$", 0),
        # The chances of alternatives add up
        ("^(abc|xyz)$", 3 * LETTER - 1),
        ("^(abc|xy)$", -math.log2(26**-3 + 26**-2)),
        ("^(abc|[0-9]+)$", 0),
        ("^(a|)$", 0),
        ("^((a)?(?(2)b|c))$", LETTER - 1),
        ("^((a)?(?(2)b))$", 0),
        # Only the rarer of a lookahead and what follows it counts
        ("^((?=abc)[a-z]+)$", 3 * LETTER),
        ("^((?=a)abc)$", 3 * LETTER),
        ("^((?=[a-z])abc)$", 3 * LETTER),
        ("^(x(?=abc)[a-z]+)$", 4 * LETTER),
        # Lookbehinds, negative lookarounds, anchors and backreferences
        ("^((?<=x)abc)$", 3 * LETTER),
        ("^((?<![a-z])abc(?![a-z]))$", 3 * LETTER),
        ("^(\\babc\\b)$", 3 * LETTER),
        ("^((a)\\2)$", LETTER),
        ("abc", 3 * LETTER),
    ],
)
def test_specificity(regex, bits):
    assert rarity_score.specificity(regex) == pytest.approx(bits)


def test_specificity_of_a_list_of_regexes_is_any_of_them():
    assert rarity_score.specificity(["^(abc)$", "^(xyz)$"]) == pytest.approx(
        rarity_score.specificity("^(abc|xyz)$")
    )
    assert rarity_score.specificity(["^(abc)$"]) == pytest.approx(3 * LETTER)
    assert rarity_score.specificity([]) == 0


@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="Atomic groups and possessive repeats are new in Python 3.11",
)
@pytest.mark.parametrize(
    "regex, bits",
    [("^((?>abc))$", 3 * LETTER), ("^(a++)$", LETTER), ("^(a{2}+)$", 2 * LETTER)],
)
def test_specificity_of_atomic_groups_and_possessive_repeats(regex, bits):
    assert rarity_score.specificity(regex) == pytest.approx(bits)


def test_specificity_of_very_rare_alternatives():
    # The chances of 2 alternatives of 2000 bits are not rounded down to 0
    assert rarity_score.specificity("^(a{426}|b{426})$") == pytest.approx(
        426 * LETTER - 1
    )


def test_specificity_of_an_invalid_regex():
    with pytest.raises(re.error):
        rarity_score.specificity("^(abc$")


@pytest.mark.parametrize(
    "bits, rarity",
    [
        (0, 0),
        (0.99, 0),
        (1, 0.1),  # 0.05 is rounded up
        (6, 0.3),
        (9.9, 0.5),
        (10, 0.5),
        (14, 0.7),
        (18.99, 0.9),
        (19, 1),
        (20, 1),
        (315, 1),
    ],
)
def test_rarity(bits, rarity):
    assert rarity_score.rarity(bits) == rarity


@pytest.mark.parametrize(
    "regex, rarity",
    [
        # Contains a word that is unique to it
        (
            "^(-----BEGIN PGP PUBLIC KEY BLOCK-----[a-zA-Z0-9/+=\\n]+"
            "-----END PGP PUBLIC KEY BLOCK-----)$",
            1,
        ),
        ("(?i)^(xox[pboa]-[0-9]{12}-[0-9]{12}-[0-9]{12}-[a-z0-9]{32})$", 1),
        ("^(ghp_[0-9a-zA-Z]{36})$", 0.9),
        # A few specific characters
        ("^(SK[0-9a-fA-F]{32})$", 0.5),
        ("(?i)^(0x[a-f0-9]{40})$", 0.4),
        # Almost no specific characters
        ("^([0-9a-f]{40})$", 0),
        ("^([0-9]{10})$", 0),
        ("^(.*)$", 0),
    ],
)
def test_estimate_rarity(regex, rarity):
    assert rarity_score.estimate_rarity(regex) == rarity


def test_database_rows_are_the_regexes_of_regex_json():
    with open(rarity_score.REGEX_JSON, encoding="utf-8") as file:
        database = json.load(file)
    rows = rarity_score.database_rows()

    assert [row.name for row in rows] == [entry["Name"] for entry in database]
    assert [row.rarity for row in rows] == [entry["Rarity"] for entry in database]
    for row in rows:
        assert row.bits >= 0
        assert row.estimate == rarity_score.rarity(row.bits)


def test_database_rows_with_a_min_difference():
    rows = rarity_score.database_rows(min_difference=0.3)
    assert 0 < len(rows) < len(rarity_score.database_rows())
    for row in rows:
        assert round(abs(row.rarity - row.estimate), 6) >= 0.3


def test_estimates_agree_with_the_rarities_in_regex_json():
    """The estimates are close to the rarities that were picked by hand."""
    rows = rarity_score.database_rows()
    close = [row for row in rows if abs(row.rarity - row.estimate) <= 0.3 + 1e-9]
    assert len(close) >= len(rows) * 2 / 3

    rare = statistics.mean(row.estimate for row in rows if row.rarity == 1)
    common = statistics.mean(row.estimate for row in rows if row.rarity <= 0.2)
    assert rare - common >= 0.5


def test_main_with_regexes(capsys):
    assert rarity_score.main(["^(ghp_[0-9a-zA-Z]{36})$", "^([0-9]{10})$"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "Estimate  Bits  Regex",
        "     0.9  18.0  ^(ghp_[0-9a-zA-Z]{36})$",
        "       0   0.0  ^([0-9]{10})$",
    ]


def test_main_with_database(capsys):
    assert rarity_score.main(["--database"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["Rarity", "Estimate", "Bits", "Name"]
    assert len(lines) == len(rarity_score.database_rows()) + 1
    assert any(line.endswith("  PGP Public Key") for line in lines)


def test_main_with_database_and_min_difference(capsys):
    assert rarity_score.main(["--database", "--min-difference", "0.3"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == len(rarity_score.database_rows(0.3)) + 1


def test_main_with_regex_and_database(capsys):
    assert rarity_score.main(["^(abc)$", "--database"]) == 0
    tables = capsys.readouterr().out.split("\n\n")
    assert tables[0].splitlines()[0] == "Estimate  Bits  Regex"
    assert tables[1].splitlines()[0].startswith("Rarity  Estimate")


@pytest.mark.parametrize("argv", [[], ["^(abc$"]])
def test_main_errors(argv, capsys):
    with pytest.raises(SystemExit) as error:
        rarity_score.main(argv)
    assert error.value.code == 2
    assert capsys.readouterr().err


def test_script_runs_from_anywhere(tmp_path):
    # Like python scripts/rarity_score.py --database, from another directory,
    # including the names that the encoding of stdout may not have (₿)
    process = subprocess.run(
        [sys.executable, str(SCRIPT), "--database"],
        cwd=tmp_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.returncode == 0, process.stderr
    assert b"PGP Public Key" in process.stdout
    assert b"Bitcoin (" in process.stdout
