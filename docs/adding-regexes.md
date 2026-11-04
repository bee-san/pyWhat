# Adding regexes

pyWhat's regexes are data: JSON files that the Python package and the Rust crate both read.
A new regex is a change to those files, plus its examples. This page is the checklist that
every new regex has to pass. The tests check most of it.

## Where it goes

- New regexes go into the file of their area in `pywhat/Data/regexes/`:

  | File | What |
  |---|---|
  | `crypto.json` | cryptocurrency addresses and keys |
  | `cloud.json` | cloud and SaaS API keys and tokens |
  | `ctf.json` | CTF flag formats |
  | `network.json` | protocols, URIs, IP/MAC addresses and ports |
  | `ids.json` | IDs and document numbers, especially those with a checksum (ISBN, ISSN, IBAN, VIN, ...) |
  | `files.json` | file and malware indicators (hashes in context, paths, registry keys, ...) |
  | `social.json` | handles and contact formats |

  `pywhat/Data/regex.json` holds the regexes from before these files existed. Fixes to them
  stay there.
- Both packages load `regex.json` and then the area files in this order (`REGEX_AREAS` in
  `pywhat/helper.py`, `REGEX_AREA_FILES` in `src/data.rs`), and sort all regexes by rarity,
  the highest first. Regexes with the same rarity keep the order of the files.
- Every file is sorted by rarity, the highest first (a test checks). Add a regex at the end of
  the regexes with its rarity, so that changes for different areas, and for different rarities,
  don't touch the same lines.

## What an entry has

```json
{
   "Name": "GitHub Personal Access Token",
   "Alternative Names": ["GitHub PAT"],
   "Regex": "^(ghp_[0-9a-zA-Z]{36})$",
   "plural_name": false,
   "Description": "...",
   "Rarity": 1,
   "URL": null,
   "Tags": ["Credentials", "GitHub", "Bug Bounty"],
   "Exploit": "Use the command below to verify that the token is valid:\n  $ curl ... TOKEN_HERE",
   "Examples": {
      "Valid": [["ghp_", "0123456789abcdefghijklmnopqrstuvwxyz"]],
      "Invalid": ["ghp_0123456789abcdefghijklmnopqrstuvwxy"]
   }
}
```

- `Name`: unique (also against other regexes' alternative names), with every word capitalised.
  `Alternative Names` (optional): abbreviations and other names; they work like tags in filters.
- `Regex`: `^(...)$`, optionally with `(?i)` before the `^`, or a list of such regexes.
- `Validator` (optional): the checksum its matches must pass (see below).
- `Rarity`: 0 to 1 (see below).
- `URL`: a URL that the match (without spaces) is appended to, to look it up, or `null`.
- `Tags`: groups such as `Credentials`, `Bug Bounty`, `Cryptocurrency Wallet`. Use the
  existing ones (`pywhat --tags`) where they fit.
- `Exploit` (optional): how to use what was found. `..._HERE` placeholders are replaced by the
  match when the exploit contains `curl`.
- `Examples`: at least one valid example, and invalid ones (see below).

## The regex

- **It must mean the same in Python's `re` and in Rust's `regex` crate.** Test it on
  [regex101](https://regex101.com) in the Rust flavour as well as the Python one.
  - Escape literal braces: `flag\{.*\}`, not `flag{.*}` (Python reads `{` as a literal where
    Rust rejects it).
  - Prefer ASCII classes (`[0-9]`, `[A-Za-z0-9_]`) to `\d`, `\w` and `\s`, which match slightly
    different characters in the two engines (docs/rust.md, "Differences from Python").
  - **No look-arounds or back-references** unless there is no other way. The `regex` crate
    doesn't have them; such a regex runs on fancy-regex, a backtracking engine that is slower
    and has a backtracking limit. If one is needed, add the regex to `NOT_ON_THE_REGEX_CRATE`
    in `tests/examples.rs`, with the engine the test reports, and say why in the pull request.
  - No nested quantifiers that can backtrack a lot, such as `(a+)+`.
- **Make it specific.** A regex that only checks which characters a text has and how long it
  is (`[0-9a-f]{40}`) matches every SHA-1 hash, and Ciphey and other tools run pyWhat on
  decoder output. Anchor it on what the format really has: a literal prefix (`ghp_`, `xoxb-`),
  separators, a checksum.

## Where a regex comes from

Write a regex from the format's documentation. A regex adapted from another project must come
from one under MIT, BSD, Apache-2.0, CC0, CC BY or a public-domain dedication, not GPL, AGPL,
LGPL, MPL or CC BY-SA, and not from one without a licence. It gets a row in its area's section of
[regex-sources.md](regex-sources.md), with the project's version or commit, and unless the
project is public domain or CC0, an entry in [NOTICE](../NOTICE) with its copyright line and
licence. A new data file in `pywhat/Data/`, like the lists that `Children` look up, follows the
same rules, with a row in [data-sources.md](data-sources.md) that gives its URL, its version or
the date it was fetched, its sha256 and its licence. Examples are made up: never a real
key.

## Examples

- Valid examples are run as tests in both packages (`tests/test_regex_identifier.py`,
  `tests/examples.rs`): a valid example must be identified as this regex, an invalid one must
  not be.
- Add invalid examples that are near misses: one character too few or too many, a wrong
  prefix, a wrong checksum, the wrong case.
- Write fake API keys as a list of parts (`["sk_live_", "abc..."]`), which pyWhat joins when it
  loads them, so that secret scanners don't block the push (see CONTRIBUTING.md).

## Validators (checksums)

If the format has a checksum, the regex must name it in `Validator`, and its matches must pass
it (`ValidatorProcessor` in Python, `processors::Validator` in Rust, both default processors).
The validators in `pywhat/validators/__init__.py` and `src/validators/mod.rs`:

| Validator | For | Random strings that pass |
|---|---|---|
| `luhn` | payment card numbers | 1 in 10 |
| `base58check` | Base58Check addresses of a version byte and a 20 byte hash (Bitcoin-like) | 1 in 2^32 |
| `ripple-base58check` | the same in Ripple's alphabet (XRP) | 1 in 2^32 |
| `cashaddr` | Bitcoin Cash CashAddr | 1 in 2^40 |
| `tc-kimlik` | Turkish Identification Numbers | 1 in 100 |
| `facebook-access-token` | Facebook access tokens: the part after `EA` has a lowercase letter, an uppercase letter and a digit | all real ones, none of all-one-case decoder output |

A new checksum (ISBN, ISSN, IBAN mod-97, VIN, Bech32, ...) goes into the files of its area,
which no other area's pull request changes:

- `pywhat/validators/<area>.py`: the function and its name in that module's `VALIDATORS`;
- `src/validators/<area>.rs`: the same function in Rust, with the same results, in that
  module's table;
- `tests/test_validators_<area>.py` (a new file) and a `#[cfg(test)]` module in
  `src/validators/<area>.rs`: valid and invalid cases, the same in both;
- its factor in the `<area>` block of `area_validator_factor` in `tests/charset_only.rs`: the
  share of the regex's random matches that pass the validator (not of all random strings:
  if the regex already fixes part of the checksum, the share is higher).

Validators use the Python standard library and pure Rust only: the crate builds for wasm32 and
the wheel has no dependencies for them. (Keccak-256 for EIP-55 isn't in `hashlib`, whose
`sha3_256` is NIST SHA-3; write it out or leave the checksum out.) Add an invalid example
with a wrong checksum, and document the validator in its module's docstring rather than in the
table above.

## Rarity

Rarity is how unlikely a match is to be a false positive, from 0 to 1. The CLI and the API show
regexes with a rarity of 0.1 or more by default.

- `python scripts/rarity_score.py 'REGEX'` estimates it from the regex: the more specific
  characters a match has to have, the rarer it is. Start from its estimate
  (`--database` compares every regex file's rarities with their estimates).
- 1 is for formats that something unique marks (a literal prefix like `ghp_`, a URL host).
- Formats that random data matches often get less than 0.5, or 0 if they match almost
  anything (a YouTube video ID on its own).

## The "Charset Only" tag

`tests/charset_only.rs` computes, from each regex's DFA, the largest share of random strings of
nine alphabets (digits, hex, HEX, lower, upper, alphanumeric, Base64, Base64url, Base58) and of
every length up to 200 that match it, after its checksum. A regex that more than 1 in 1,000 of
them match has to have the tag `Charset Only`, and only those may have it. When the test fails,
it says which regex needs the tag added or removed. Ciphey ignores these regexes when it asks
whether a whole text is a known format, and `pywhat --exclude "Charset Only"` leaves them out.

## False positives

Measure your regexes on junk, before and after:

```sh
cargo bench --bench false_positives -- --exclude-charset-only [--show] \
    [--ciphey CIPHEY/benches/data/plaintext] [--gib GIBBERISH_OR_NOT/bench/corpus/v1]
```

It identifies (`identify_whole`, rarity 0.1 to 1) random strings of the nine alphabets and,
with the paths, Ciphey's search candidates (`captured.tsv`), English sentences and
gibberish-or-not's corpus of junk (wrong cipher keys, encodings, mojibake, random bytes), and
prints the false positives of every regex. A new regex without the `Charset Only` tag must have
none. Put the before and after numbers in the pull request.

## Checks before a pull request

- Python: `pytest` on Python 3.8 and 3.10, as CI runs it (`nox`).
- Rust: `cargo fmt --all -- --check`, `cargo clippy --all-targets -- -D warnings`, `cargo test`
  (the examples, the regex-crate allowlist and the `Charset Only` tags).
- The golden test, which checks that Rust finds exactly what Python finds:

  ```sh
  python scripts/golden.py    # writes target/golden.jsonl and target/golden-files.jsonl
  PYWHAT_GOLDEN=target/golden.jsonl PYWHAT_GOLDEN_FILES=target/golden-files.jsonl \
      cargo test --release --test golden -- --nocapture
  ```

  It must report 0 differences. CI runs all of these on every pull request.
