# Changelog

## 6.0.0 (unreleased)

pyWhat 6 adds a Rust crate, `pywhat`, that finds exactly what the Python package finds, from the
same data. The Python API doesn't change. The crate is published first, as `6.0.0-alpha.1`; the
Rust CLI and the Python wheel built on it follow before 6.0.0.

### Removed

- **Issuer bank names removed: licence.** MasterCard Number matches no longer name the issuing
  bank ("Issuer(s): …" in their description), and `pywhat/Data/mastercard_companies.json` is
  gone. Its source, Mastercard's Simplified BIN Account Range Table, has terms that forbid
  publishing, distributing, copying and derivative works
  ([#302](https://github.com/bee-san/pyWhat/issues/302)). The MasterCard Number regex and the
  rest of its output don't change.

### The Rust crate (#291, #299)

- The crate `pywhat` (`Identifier`, `Filter`, processors, `identify_inputs`, JSON output equal
  to `pywhat --json`) reads `pywhat/Data` at compile time. A golden test compares it with the
  Python package on every pull request: 43,332 texts and 142,376 comparisons, 0 differences.
- For Ciphey, which moves from lemmeknow to this crate: `Identifier::identify_whole` (is the whole
  text a known format), lemmeknow's builder names (`min_rarity`, `max_rarity`, `include_tags`,
  `exclude_tags`, `boundaryless`), and `warm_up`. docs/rust.md has the migration.
- A WebAssembly build (feature `wasm`) and a web page on it (`web/`).
- Where the crate differs from Python (docs/rust.md, "Differences from Python"): the Unicode
  classes of `\s`, `\w`, `\b`, `(?i)` and `\d`, and combining marks next to a match;
  directories are read in name order instead of the file system's; unreadable files are
  skipped instead of raising an error.

### Changed

- **Checksums** (#300, bee-san/Ciphey#1031): card numbers must pass the Luhn check; Dogecoin,
  Litecoin and XRP addresses their Base58Check; Bitcoin Cash addresses their CashAddr checksum;
  Turkish Identification Numbers their check digits. Bitcoin addresses already had to (#285).
  A regex names its check in a new `"Validator"` key, which the JSON output's `"Regex Pattern"`
  includes.
- **Tighter regexes** (#300): Facebook access tokens must have a lowercase letter, an uppercase
  letter and a digit after `EA` (bee-san/Ciphey#1104); Google reCAPTCHA keys start with `6L`;
  EC2 instance IDs are lowercase; an ARN's partition and service start with a lowercase letter.
- **The `Charset Only` tag** (#300) marks the 29 regexes that only check which characters a text
  has and how long it is. `--exclude "Charset Only"` leaves them out.
- **New regexes go into area files** (#300), `pywhat/Data/regexes/<area>.json`, following
  docs/adding-regexes.md.
- Rust-compatible forms of 6 regexes, with the same matches (#292).
- `Children` prefixes are matched longest first, instead of in set order: the vendors of 3,697
  MAC prefixes, and the locations of some +1 and +7 phone numbers, are listed in the other order
  (#292).
- Matches are substituted literally into `Exploit` texts and `--format`, so a backslash in a
  match no longer raises `re.error`; piped output is no longer wrapped at 80 columns (#292).
- Phone numbers need a `+`, parentheses or separators: plain runs of digits aren't phone numbers
  (#289).

### Added (since 5.1.0)

- Several files, directories and texts as input (#278); Unicode files, stdin and output:
  UTF-16 and UTF-32 with a byte order mark, and the UTF-16 strings of binary files (#275).
- Interactive mode, `--interactive` (#272).
- Progress bars, and `--stream` to print matches as they are found (#287).
- The most likely matches first, and `--top N` or `--top N%` (#286).
- Processors that process matches further, like the date of a Unix timestamp (#274);
  OpenStreetMap links with `--map osm` (#288); verifying Google API keys with `--verify`
  (#281).
- Alternative names for regexes, usable like tags, and `--names` (#279).
- `scripts/rarity_score.py`, which estimates the rarity of a regex (#280).
- Regexes based on gf's patterns (#273) and on the regex101 library (#276), What3Words
  addresses (#265), YouTube links in all common formats (#282), the Italian Fiscal Code (#243),
  and lists of regexes in regex.json (#244).
- `NOTICE`, with the source and licence of the data pyWhat ships (#303).

### Fixed (since 5.1.0)

- File signatures are identified from the contents rather than the file name (#294), and read
  completely (#296).
- Recursive results keep their nested paths (#295), and directory names are literal paths, not
  glob patterns (#297).
- URLs are matched fully, and only the URL itself (#277, #290).
- IPv6: hexadecimal characters (#266), and no false positives in boundaryless mode (#271).
- `--json` output is valid JSON on one line, without progress bars in it (#284).
- API key regexes caught by new tests (#283); Google Client ID (#246); Bitcoin addresses with a
  wrong checksum are filtered out (#285).

### Data and licences

- `pywhat/Data/file_signatures.json` is derived from Wikipedia and is under CC BY-SA 4.0, not
  MIT; the crate's licence is `MIT AND CC-BY-SA-4.0`. NOTICE and docs/data-sources.md give the
  source and licence of every data file (#302, #303).
