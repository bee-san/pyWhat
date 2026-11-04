"""
Record what the Python package finds, for tests/golden.rs to compare with the Rust crate.

    python scripts/golden.py
    PYWHAT_GOLDEN=target/golden.jsonl PYWHAT_GOLDEN_FILES=target/golden-files.jsonl \
        cargo test --release --test golden

Every line of the output is one text with what Python's Identifier finds in it with
several sets of options. A match is recorded as [name, matched, fragment, description,
exploit, link]. For the "full" texts, the exact json.dumps() of identify() is recorded too,
to compare the JSON byte for byte.

The texts are generated: every example of regex.json alone and with each of 20 strings
before it, after it and on both sides, the repository's text files, and texts with the
Unicode characters that Python's re and Rust's regex crate treat differently (those are
compared, but their differences are documented, not failures).
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pywhat import Identifier, regex_identifier  # noqa: E402
from pywhat.filter import Distribution, Filter  # noqa: E402
from pywhat.helper import Keys, load_regexes  # noqa: E402
from pywhat.printer import get_link  # noqa: E402
from pywhat.processors import OpenStreetMapProcessor, default_processors  # noqa: E402
from pywhat.ranking import located_matches, top_matches  # noqa: E402

# What Python's re finds, which the Rust crate is compared with: not the Rust engine,
# which the package searches with once its extension is built (pip install -e .)
regex_identifier._pywhat = None  # type: ignore[assignment]

AFFIXES = [
    "a",
    "Z",
    "0",
    "5",
    "_",
    "-",
    ".",
    "/",
    "+",
    "=",
    ":",
    " ",
    "\n",
    "é",
    "٣",
    "x ",
    " x",
    "{",
    "}",
    "'",
]

# Characters that Python's re and Rust's regex crate classify differently (issue #291):
# \s (U+001C-U+001F), \w (superscripts, fractions, combining marks), (?i) with the dotted
# and dotless i, and digits newer than Unicode 15.0
UNICODE_TEXTS = [
    "a\x1cb thm{x}\x1d",
    "\x1e192.168.0.1\x1f",
    "user\x1c@example.com",
    "x² thm{a²} ½@example.com",
    "e\u0301xample@example.com",
    "THM{x}\u0301",
    "\u0130@example.com THM{\u0131}",
    "https://\u0131.example.com",
    "\U0001fbf1\U0001fbf2 1637093119",
    "\u0131bc@example.com",
    # Combining marks next to a match: \b and \w (Rust counts U+0301 as a word character)
    "SW1A 1AA\u0301",
    "e\u0301 SW1A 1AA x",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/119.0\u0301",
]

# Fake keys are written in parts, so that secret scanners don't take them for keys
TWITTER_SECRET = "L8qq9PZyRg6ieKGEKhZolGC0vJWLw8iEJ88" + "DRdyOg"

# Texts that the examples don't cover: many candidate lines for the line prefilter (over
# 64, then fancy-regex searches the rest itself), C1 control characters inside matches,
# and $ and \ inside matches whose exploit gets the match substituted
EXTRA_TEXTS = [
    "\n".join(
        f"x 10.0.{i}.0/{i % 33} y 192.168.{i}.1 +1 (555) 123-{i:04d} 2021-11-16T20:05:{i % 60:02d}Z"
        for i in range(200)
    ),
    "thm{a\x85b} bee\x9b@skerritt.blog THM{x\x80y}",
    f'twitter$_api_secret = "{TWITTER_SECRET}"',
    f'twitter\\q_api_secret = "{TWITTER_SECRET}"',
]


FINANCE = Filter({"Tags": ["Finance"], "ExcludeTags": ["Credit Card"]})
BTC = Filter(
    {
        "Tags": ["BTC Wallet", "Credentials"],
        "ExcludeTags": ["Credit Card", "AWS"],
        "MinRarity": 0.3,
    }
)


def options():
    """The option sets: (name, Identifier keyword arguments), see tests/golden.rs."""
    cli_boundaryless = Filter({"MinRarity": 0.1, "MaxRarity": 1})
    return {
        # Identifier(): rarity 0.1:1, no boundaryless mode, default processors
        "api": {},
        # The CLI's defaults: --rarity 0.1:1, --boundaryless-rarity 0.1:1
        "cli": {"boundaryless": cli_boundaryless},
        # --rarity 0: -br 0:
        "all": {
            "dist": Distribution(Filter({"MinRarity": 0})),
            "boundaryless": Filter({"MinRarity": 0}),
        },
        # --include "Bug Bounty"
        "bug_bounty": {
            "dist": Distribution(Filter({"Tags": ["Bug Bounty"]})),
            "boundaryless": cli_boundaryless,
        },
        # --include Identifiers,Media --rarity 0.5:
        "identifiers_media": {
            "dist": Distribution(
                Filter({"Tags": ["Identifiers", "Media"], "MinRarity": 0.5})
            ),
            "boundaryless": cli_boundaryless,
        },
        # --exclude AWS
        "exclude_aws": {
            "dist": Distribution(Filter({"ExcludeTags": ["AWS"]})),
            "boundaryless": cli_boundaryless,
        },
        # -dp
        "no_processing": {"boundaryless": cli_boundaryless, "processors": []},
        # --map osm
        "osm": {
            "boundaryless": cli_boundaryless,
            "processors": [*default_processors(), OpenStreetMapProcessor()],
        },
        # Filter & and |, with names and excluded tags, and -bi/-be-like boundaryless filters
        "and": {
            "dist": Distribution(FINANCE & BTC),
            "boundaryless": Filter(
                {"Tags": ["Bitcoin"], "ExcludeTags": ["Credit Card"]}
            ),
        },
        "or": {
            "dist": Distribution(FINANCE | BTC),
            "boundaryless": Filter({"Tags": ["Identifiers"], "MinRarity": 0.2}),
        },
    }


# Sorting and --top, applied to the "cli" results
SORTS = [
    ("key_name", Keys.NAME, False),
    ("key_name_reverse", Keys.NAME, True),
    ("key_rarity", Keys.RARITY, False),
    ("key_rarity_reverse", Keys.RARITY, True),
    ("key_matched", Keys.MATCHED, False),
    ("key_likely", Keys.LIKELY, False),
    ("key_likely_reverse", Keys.LIKELY, True),
]
TOPS = [("top_10", 10), ("top_5_percent", "5%")]


def compact(match):
    return [
        match["Regex Pattern"]["Name"],
        match["Matched"],
        match.get("Fragment"),
        match["Regex Pattern"].get("Description"),
        match["Regex Pattern"].get("Exploit"),
        get_link(match),
    ]


def matches_of(identified):
    return [compact(match) for _, match in located_matches(identified)]


def texts():
    """(text, kind): kind "base" gets every option set, "affixed" only api, cli and all."""
    examples = []
    for regex in load_regexes():
        for kind in ("Valid", "Invalid"):
            examples += regex.get("Examples", {}).get(kind, [])
    examples = list(dict.fromkeys(examples))
    for example in examples:
        yield example, "base"
    for text in UNICODE_TEXTS:
        yield text, "unicode"
    for text in EXTRA_TEXTS:
        yield text, "base"
    files = [
        ROOT / "README.md",
        ROOT / "fixtures" / "file",
        ROOT / "pywhat/Data/regex.json",
    ]
    files += sorted((ROOT / "tests").glob("*.py"))
    for path in files:
        yield path.read_text(encoding="utf-8").replace("\r\n", "\n"), "base"
    for example in examples:
        for affix in AFFIXES:
            yield affix + example, "affixed"
            yield example + affix, "affixed"
            yield affix + example + affix, "affixed"


def write_files(directory: Path) -> None:
    """Generated files for the file stage: encodings, binary data, hidden files."""
    directory.mkdir(parents=True, exist_ok=True)
    text = (
        "Email: bee@skerritt.blog\r\nTHM{unicode_files}\r\nhttps://github.com/bee-san\n"
    )
    (directory / "utf8.txt").write_bytes(text.encode("utf-8"))
    (directory / "utf8-bom.txt").write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    (directory / "utf16le-bom.txt").write_bytes(b"\xff\xfe" + text.encode("utf-16-le"))
    (directory / "utf16be-bom.txt").write_bytes(b"\xfe\xff" + text.encode("utf-16-be"))
    (directory / "utf32le-bom.txt").write_bytes(
        b"\xff\xfe\x00\x00" + text.encode("utf-32-le")
    )
    (directory / "utf32be-bom.txt").write_bytes(
        b"\x00\x00\xfe\xff" + text.encode("utf-32-be")
    )
    (directory / "invalid-utf8.txt").write_bytes(
        b"a\xffb THM{in\xe2\x82valid} \xc3\xa9 192.168.0.1"
    )
    binary = bytearray(b"\x89PNG\r\n\x1a\n\x00\x01\x02")
    binary += "THM{utf16_strings}".encode("utf-16-le") + b"\x00\x00\xff"
    binary += "https://example.com/path".encode("utf-16-le") + b"\x00\x00ab\x00"
    binary += bytes(range(256))
    (directory / "binary.png").write_bytes(bytes(binary))
    (directory / "89504E470D0A1A0A").write_text("THM{hex_named_file}")
    (directory / "fits").write_bytes(b"SIMPLE  =                    T\n")
    sub = directory / "sub dir"
    sub.mkdir(exist_ok=True)
    (sub / "nested.txt").write_text("flag{nested} 1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY")
    (sub / ".hidden").write_text("THM{hidden_file_is_skipped}")
    hidden = directory / ".hidden_dir"
    hidden.mkdir(exist_ok=True)
    (hidden / "file").write_text("THM{hidden_dir_is_skipped}")


def copy_repo(directory: Path) -> None:
    """The files that git tracks, a copy of the repository without build output."""
    import shutil
    import subprocess

    files = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    if directory.exists():
        shutil.rmtree(directory)
    for name in files:
        source = ROOT / name
        if source.is_file():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def file_stage(out, files_dir: str, repo_dir: str):
    """Records what identify_inputs() finds in files and directories."""
    identifiers = {
        "api": Identifier(),
        "cli": Identifier(boundaryless=Filter({"MinRarity": 0.1, "MaxRarity": 1})),
    }
    cases = [
        (["fixtures"], False),
        (["fixtures"], True),
        (["fixtures/file"], False),
        (["fixtures/file", "fixtures", "THM{x}"], False),
        ([files_dir], False),
        ([files_dir], True),
        ([f"{files_dir}/binary.png", f"{files_dir}/utf16le-bom.txt"], False),
        ([repo_dir], False),
    ]
    for inputs, include_filenames in cases:
        for name, identifier in identifiers.items():
            identified = identifier.identify_inputs(
                inputs, only_text=False, include_filenames=include_filenames
            )
            record = {
                "inputs": inputs,
                "include_filenames": include_filenames,
                "options": name,
                "signatures": {
                    location: signature["Hexadecimal File Signature"]
                    for location, signature in (
                        identified["File Signatures"] or {}
                    ).items()
                },
                "regexes": {
                    location: [compact(match) for match in matches]
                    for location, matches in (identified["Regexes"] or {}).items()
                },
            }
            # Byte for byte, where the order of the files is not the file system's
            if not any(os.path.isdir(i) for i in inputs):
                record["json"] = json.dumps(identified)
            out.write(json.dumps(record) + "\n")


# Where the recordings go: target/, which cargo and git ignore
TARGET = ROOT / "target"
OUT = TARGET / "golden.jsonl"
FILES_OUT = TARGET / "golden-files.jsonl"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--full",
        type=int,
        default=300,
        help="record the json.dumps() of the first N base texts",
    )
    args = parser.parse_args()
    files_dir = TARGET / "golden-files"
    repo_dir = TARGET / "golden-repo"
    write_files(files_dir)
    copy_repo(repo_dir)
    with open(FILES_OUT, "w", encoding="utf-8") as out:
        file_stage(
            out, os.path.relpath(files_dir, ROOT), os.path.relpath(repo_dir, ROOT)
        )
    print(f"golden: file inputs in {FILES_OUT}")
    sets = options()
    identifiers = {name: Identifier(**kwargs) for name, kwargs in sets.items()}
    count = 0
    full = 0
    with open(OUT, "w", encoding="utf-8") as out:
        seen = set()
        for text, kind in texts():
            if text in seen:
                continue
            seen.add(text)
            names = list(sets) if kind != "affixed" else ["api", "cli", "all"]
            results = {}
            cli = None
            for name in names:
                identified = identifiers[name].identify(text)
                results[name] = matches_of(identified)
                if name == "cli":
                    cli = identified
            record = {"text": text, "kind": kind, "results": results}
            if kind != "affixed":
                for name, key, reverse in SORTS:
                    regexes = cli["Regexes"] or {}
                    for matches in regexes.values():
                        matches.sort(key=key, reverse=reverse)
                    results[name] = matches_of(cli)
                    # Back to the order they were found in, for the next sort
                    cli = identifiers["cli"].identify(text)
                for name, top in TOPS:
                    results[name] = matches_of(top_matches(cli, top))
                if kind == "base" and full < args.full:
                    record["json"] = json.dumps(cli)
                    full += 1
            out.write(json.dumps(record) + "\n")
            count += 1
    print(f"golden: {count} texts in {OUT} ({os.path.getsize(OUT)} bytes)")


if __name__ == "__main__":
    main()
