# pyWhat in Rust: the `pywhat` crate

The crate at the root of this repository is pyWhat's identification in Rust: the same regexes,
filters, processors and output as the Python package. It reads the data files of the Python
package, `pywhat/Data/*.json` and `pywhat/Data/regexes/*.json`, at compile time (`include_str!`),
so both always use the same regexes. Adding a regex is still a change to the data only
([adding-regexes.md](adding-regexes.md)). Issue #291 is the plan.

```toml
[dependencies]
pywhat = "6"
```

```rust
use pywhat::{Filter, Identifier};

// Like `Identifier()` in Python: rarity 0.1 to 1, regexes with their boundaries (`^...$`
// match whole lines), the default processors (Unix timestamp dates, Bitcoin checksums, and the
// other checksums: card numbers, wallets, Turkish IDs)
let identifier = Identifier::default();
for found in identifier.identify("bee@skerritt.blog\nthm{a_flag}") {
    println!("{} is a {}", found.matched, found.regex.name);
}

// What the whole text is, not what it contains
let found = identifier.identify_whole("192.168.0.1");
assert_eq!(found[0].regex.name, "Internet Protocol (IP) Address Version 4");
assert!(identifier.identify_whole("IP: 192.168.0.1").is_empty());

// The CLI's defaults: also find matches inside longer text (boundaryless mode). The matches
// are in the order of the database: the URL skerritt.blog, then the email address
let cli = Identifier::default().with_boundaryless_filter(Filter::default());
let found = cli.identify("Mail me at bee@skerritt.blog");
assert!(found.iter().any(|m| m.matched == "bee@skerritt.blog" && m.regex.name == "Email Address"));
```

## API

| Rust | Python |
|---|---|
| `Identifier::default()` | `Identifier()` |
| `Identifier::new(dist, boundaryless, processors)` | `Identifier(dist=..., boundaryless=..., processors=...)` |
| `identifier.identify(text)` | `identify(text)["Regexes"]["text"]` |
| `identifier.identify_inputs(&inputs, options, key, reverse)` (feature `files`) | `identify_inputs(inputs, only_text=..., include_filenames=..., key=..., reverse=...)` |
| `identifier.iter_identify(&inputs, options, found, error)` (feature `files`) | `iter_identify(...)` |
| `identifier.iter_identify_with_progress(&inputs, options, found, error, progress)` and `Progress` (feature `files`) | `iter_identify(..., progress=...)` and `Progress`: `progress` gets the file, how many of the files and of the file's regex searches are done, and a regex that is searched for. For texts over 4 KB the regexes are searched for in parallel, so it is called from rayon's threads, one call at a time |
| `Identified::to_json()` | `json.dumps(identify(...))`, byte for byte |
| `Filter::new(tags, exclude_tags, min_rarity, max_rarity)`, `Filter::default()`, `Filter::none()`, `.and()`, `.or()` | `Filter({...})`, `&`, `\|` |
| `Processor` (trait), `default_processors()`, `processors::OpenStreetMap`, `processors::Validator` | `Processor`, `default_processors()`, `OpenStreetMapProcessor`, `ValidatorProcessor` |
| `validators::validator(name)`, `validators::luhn`, ... | `pywhat.validators.VALIDATORS`, `luhn`, ... |
| `ranking::sort_matches`, `Key`, `Top::parse`, `ranking::top_matches`, `Identified::top` | `Keys`, `parse_top`, `top_matches` |
| `Match` (`matched`, `regex`, `description`, `exploit`, `link()`, `rarity`, `tags`, `fragment`, `start`, `end`) | a match dict |
| `regexes()`, `tags()`, `RegexEntry` (with `validator` and `charset_only()`), `CHARSET_ONLY` | `load_regexes()`, `AvailableTags()`, the tag `"Charset Only"` |

Rust only:

- `identifier.identify_whole(text)` and `first_whole(text)`: the regexes whose `^(...)$` matches
  the whole text, where `^` and `$` only match at its start and end. This is what lemmeknow's
  `identify` did, and what a checker that asks "is this text a known format?" needs.
- lemmeknow's builder names: `min_rarity`, `max_rarity`, `include_tags`, `exclude_tags`,
  `boundaryless`. `include_tags` takes tags or names, case-insensitively, and a regex needs
  one of them (lemmeknow needed all of them).
- `identifier.warm_up()` compiles the regexes that the identifier uses, on rayon's thread
  pool. Otherwise each regex is compiled when it is first needed.

### Features

| Feature | Default | What it adds |
|---|---|---|
| `parallel` | yes | rayon: the regexes of a text over 4 KB are searched in parallel, and `warm_up` compiles in parallel |
| `files` | yes | `identify_inputs`, `iter_identify`: files, directories (recursive) and file signatures (`file_signatures.json`, under CC BY-SA 4.0) |
| `children` | yes | the tables that `Children` read from data files: the locations of phone numbers (`phone_codes.json`) in their descriptions |
| `mac-vendors` | yes | `children`, and the vendors of MAC address prefixes (1.6 MB) in the descriptions of EUI-48 matches |
| `wasm` | no | the WebAssembly API in `src/wasm.rs` (`identify(text, options_json)`, `tags()`, `version()`) |

For wasm32, use `default-features = false` (no threads, no file system), and `features = ["wasm"]`
for the JavaScript API. Without `files`, a build contains none of the CC BY-SA data; without
`children`, Phone Number and EUI-48 matches have the regex's own description.

The data files and what is known about their sources are listed in
[data-sources.md](data-sources.md).

## How the regexes run

Python's `re` and Rust's `regex` crate agree on what nearly every pyWhat regex matches. The
golden test (below) checks that they find the same matches. 137 of the 154 regexes run on the
`regex` crate. The other 17 need look-arounds or a back-reference, which the `regex` crate
doesn't support:

- **Guarded (8):** look-arounds that only check the character before or after the match (or that
  the rest of the line contains a character) are removed, the `regex` crate runs the rest, and each
  match is checked. A match whose check fails is searched again from the next character, which is
  what a backtracking engine does. This is exact when the checks are at the start of the match, or
  at the end of a match that always has the same length, which the engine verifies before choosing
  this. The AWS keys, Tox ID, Picatic, Java and PHP serialized objects and the YouTube video ID run
  this way.
- **fancy-regex with a line prefilter (7):** the regex without its look-arounds (which matches
  everywhere the regex does) finds the candidate lines, and fancy-regex only searches those, with
  the whole text visible to its look-arounds. This needs a regex that can't match a line break.
- **fancy-regex (2):** URL (an 18 KB regex, where the prefilter costs more than it saves) and Date
  of Birth (a back-reference).

fancy-regex runs with a backtracking limit of 100,000,000 (its default of 1,000,000 lost Phone
Number matches on large texts). `Identifier::try_identify` returns the error of a regex that hits
the limit; `identify` skips that regex. `tests/examples.rs` lists the 17 regexes, so a regex that
needs fancy-regex has to be added to the list on purpose.

`identify_whole` first rules out texts that are too short or too long for a regex, or that start
with a byte it can't start with. For the fancy-regex regexes it then runs the `regex`-crate
superset, and compiles a regex only when a text gets past these checks, so a call only compiles
the regexes that the text could match.

### Differences from Python

- **Unicode classes.** `\s` doesn't match U+001C to U+001F in Rust; `\w` and `\b` use Unicode's
  word characters (Rust takes combining marks, Python takes `²` and `½`), so a match next to a
  combining mark such as U+0301 can differ; `(?i)` doesn't match `İ` (U+0130) and `ı` (U+0131)
  with `i`; Rust's `\d` knows the digits added after Unicode 15.0. None of these occurred in the
  corpus of #291. `scripts/golden.py` has texts with them, and reports their differences without
  failing (a UK postcode and a browser user agent next to U+0301 differ today).
- Directories are searched in the order of their names, not in the order of the file system.
- A file that can't be read is skipped (Python raises an error).

## The golden test

```sh
python scripts/golden.py    # writes target/golden.jsonl and target/golden-files.jsonl
PYWHAT_GOLDEN=target/golden.jsonl PYWHAT_GOLDEN_FILES=target/golden-files.jsonl \
    cargo test --release --test golden -- --nocapture
```

`scripts/golden.py` runs the Python package on 40,587 texts: every example in `regex.json`, alone
and with 20 different strings before it, after it and on both sides, the repository's text files,
the Unicode texts above, 200 lines that are all candidates of the line prefilter, C1 control
characters inside matches, and `$` and `\` inside matches that an exploit gets substituted into.
It uses 10 sets of options (the API's and the CLI's defaults, `--rarity 0:`, `--include`,
`--exclude`, `-dp`, `--map osm`, and filters combined with `&` and `|`), every sort key with and
without `--reverse`, and `--top`. It also runs `identify_inputs` on `fixtures/`, a copy of the repository and generated
files (UTF-8, UTF-16 and UTF-32 with byte order marks, invalid UTF-8, binary files with UTF-16LE
strings, hidden files). `tests/golden.rs` compares every match (name, matched text, fragment,
description, exploit and link, in order), and for 304 cases the `json.dumps()` output byte for
byte. The test fails if the recording lacks an option set or compares nothing. The Rust workflow
runs it on every pull request; it reports 0 differences.

## Measurements

Rust 1.99.1, Python 3.10.20, on a shared 64-core machine with a load average of 20 to 50 while
measuring, so absolute times can be twice as high as on an idle machine. The wall time on the big
file varies most: writing 297 MB of JSON took 2 to 6 s of system time on the loaded machine.

**A big file.** The repository's text files 10 times over (`python scripts/bench_corpus.py` writes
it to `target/bench.txt`: 4.2 MB, 115,270 lines), with the CLI's defaults:

| | Wall time | CPU time | JSON |
|---|---|---|---|
| `pywhat --json --no-progress target/bench.txt` (Python) | 25.0 s | 19.2 s user | 296,955,554 bytes |
| `cargo run --release --example bench_file -- target/bench.txt --json out.json` (Rust) | 4.8–8.5 s | 3.2–3.4 s user | the same bytes (`cmp`) |

`cargo run --release --example bench_file -- FILE` prints the time per regex. Most of the Rust
time is the URL regex (1.7 s) and Date of Birth (0.4 s), which run on fancy-regex.

**Short texts, for Ciphey.** `cargo bench --bench whole -- PLAINTEXT_DIR` times `identify_whole`
and lemmeknow 0.8.0's `identify` (both rarity 0.1 to 1) on the 7,371 texts of Ciphey's
plaintext-detection data (`benches/data/plaintext/{curated,gutenberg,captured}.tsv` of
bee-san/Ciphey), each text 20 times in a row, the two crates taking turns, median of 5 rounds:

| | p50 | p99 | mean |
|---|---|---|---|
| lemmeknow 0.8.0 `identify` | 2.14 µs | 6.76 µs | 2.26 µs |
| pywhat `identify_whole` | 1.09 µs | 4.74 µs | 1.47 µs |

The first call in a process compiles what it needs: 45–51 ms for lemmeknow and 45–53 ms for
pywhat (5 processes each). `Identifier::warm_up()` compiles all the regexes of the identifier in
65–105 ms on 4 threads.

**WebAssembly.** `cargo rustc --lib --release --target wasm32-unknown-unknown --no-default-features
--features wasm --crate-type cdylib`, then `wasm-bindgen --target web` and `wasm-opt -Oz` (binaryen
133):

| | `wasm-opt -Oz` | gzip -9 |
|---|---|---|
| `--features wasm` | 1,950,784 bytes | 671,147 bytes |
| `--features wasm,children` | 1,956,671 bytes | 673,318 bytes |
| `--features wasm,mac-vendors` | 3,579,077 bytes | 1,199,460 bytes |

The data is most of it: `regex.json` is 154 KB and `mac_vendors.json` 1.6 MB. Before `files` and
`children` also gated their data (and before the MasterCard bank names were removed),
`--features wasm` was 2,053,094 bytes (693,813 gzipped) with the file signatures, the phone codes
and the bank names in it, and `--features wasm,mac-vendors` 3,675,505 (1,220,038).
`scripts/wasm_smoke.js` checks the build under Node.js, and `scripts/web_selftest.sh` builds
`web/index.html`, a page that identifies text in the browser, and checks in headless Chrome that it
identifies the README's examples.

## Moving Ciphey from lemmeknow 0.8 to pywhat 6

Ciphey's LemmeKnow checker (`src/checkers/lemmeknow_checker.rs`) asks lemmeknow which formats a
whole text is, and filters the matches. With pywhat:

1. `Cargo.toml`: replace `lemmeknow = "0.8.0"` with `pywhat = { version = "6", default-features =
   false, features = ["parallel"] }` (no file support, so no file signatures, and no `children`
   tables: Ciphey checks text, and the locations of phone numbers or vendors of MAC addresses in
   descriptions don't matter for plaintext detection). Its web build adds `wasm` instead of
   `parallel`.
2. `use lemmeknow::{Data, Identifier}` becomes `use pywhat::{Identifier, RegexEntry}`, and
   `use lemmeknow::Identifier` becomes `use pywhat::Identifier`, in the 14 files that use it
   (`grep -rl 'lemmeknow::' src`): `checkers/lemmeknow_checker.rs`, `checkers/checker_type.rs`,
   `checkers/athena.rs`, `checkers/code_checker.rs`, `checkers/default_checker.rs`,
   `checkers/english.rs`, `checkers/json_checker.rs`, `checkers/password.rs`,
   `checkers/regex_checker.rs`, `checkers/wait_athena.rs`, `checkers/wordlist.rs`,
   `decoders/jwt_decoder.rs`, `config/mod.rs` and `api_library_input_struct.rs`. `detection.rs`
   has no `use lemmeknow` line; its change is step 6.
   `Checker::lemmeknow_config` keeps its name and holds a `pywhat::Identifier`, which is
   `Clone + Send + Sync`; the checkers that don't identify anything keep
   `lemmeknow_config: Identifier::default()`.
3. `MIN_RARITY` becomes an `f64`. The checker:

   ```rust
   lemmeknow_config: Identifier::default().min_rarity(MIN_RARITY),
   ```

   stays as it is, and `identify` calls `identify_whole`:

   ```rust
   identifier
       .identify_whole(text)
       .iter()
       .map(|found| found.regex)
       .find(|entry| is_trusted_match(entry, text))
       .map(|entry| entry.name.clone())
   ```

   `is_trusted_match(entry: &RegexEntry, text: &str)` reads `entry.name` (a `String`) and
   `entry.tags` (a `Vec<String>`): `EXCLUDED_NAMES.contains(&entry.name.as_str())`,
   `entry.tags.iter().any(|tag| EXCLUDED_TAGS.contains(&tag.as_str()))`,
   `entry.tags.iter().any(|tag| tag == "CTF Flag")`.
4. `warm_up()` becomes `rayon::spawn(|| LEMMEKNOW_CHECKER.lemmeknow_config.warm_up())`, and
   `warm_up_tasks` goes: pywhat compiles what a check needs on first use, so the tag bands aren't
   needed. On wasm32, rayon has no thread pool and `rayon::spawn`'s closure may never run, so the
   warm-up does nothing there (checks compile what they need, as without a warm-up); gate it
   with `#[cfg(not(target_arch = "wasm32"))]` to make that explicit.
5. `config/mod.rs` builds the identifier from its fields with the builders instead of a struct
   literal: `Identifier::default().min_rarity(min.into()).max_rarity(max.into())
   .include_tags(&tags).exclude_tags(&exclude).boundaryless(boundaryless)`, skipping
   `include_tags` when the list is empty (an empty list includes nothing). The `const
   LEMMEKNOW_DEFAULT_CONFIG` becomes a function or a `LazyLock`.
6. `detection.rs`'s `lemmeknow_rarity` reads `found.regex.rarity` (an `f64`).
7. The crate's licence is `MIT AND CC-BY-SA-4.0`: its file signatures are derived from Wikipedia
   and are under CC BY-SA 4.0, and [NOTICE](../NOTICE) lists the sources of all its data. With
   the features of step 1, Ciphey's builds contain no file signatures and no `children` tables,
   only the regexes (MIT, with the credits in NOTICE). Link or copy pyWhat's NOTICE in Ciphey's
   own NOTICE for those credits.

What changes for Ciphey's results:

- pywhat has today's 154 regexes. lemmeknow 0.8.0 had an older copy, without the 8 that the `regex`
  crate can't compile (IPv6, Bitcoin, SSN, Date of Birth, JWT, both AWS keys, YouTube video ID), so
  these formats are found now, and some names are different. On the 7,371 texts above, both find a
  format in 207, only pywhat in 85, and only lemmeknow in 13.
- Bitcoin addresses must have a valid checksum (the default processors), so the Bitcoin regex no
  longer takes random Base58.
- The CTF flag regexes now escape `{`, as Python's do, and match the same texts as before.
- Card numbers, Dogecoin, Litecoin, XRP and Bitcoin Cash addresses and Turkish IDs must pass
  their checksums, and Facebook access tokens must mix cases and digits (#1104).
- **The `EXCLUDED_NAMES` and `EXCLUDED_TAGS` lists can go:** the regexes that only check which
  characters a text has and how long it is have the tag `Charset Only` (29 of them, computed by
  `tests/charset_only.rs`). Ciphey's checker leaves them out with
  `Identifier::default().min_rarity(MIN_RARITY).exclude_tags(&[pywhat::CHARSET_ONLY])`, or keeps
  the identifier and skips `found.regex.charset_only()` in `is_trusted_match`. On Ciphey's
  plaintext data this leaves 1 false positive in 5,726 search candidates and none in 40,000
  random strings of each of nine alphabets, while 136 of Ciphey's 146 samples of formats are
  still found (the 10 others are SSNs, dates of birth and a Monero address, which are tagged).
  Phone Number isn't tagged, because pyWhat's regex needs a `+`, parentheses or separators,
  where lemmeknow's took any 10 to 13 digits: `18005551234` is no longer a phone number, which
  changes Ciphey's `is_phone_number` (DTMF) and its test `phone_numbers_are_recognised_but_not_identified`.
