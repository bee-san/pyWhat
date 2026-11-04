Please read our wiki here:
https://github.com/bee-san/pyWhat/wiki/Adding-your-own-Regex

New regexes go into the file of their area in `pywhat/Data/regexes/`, and must work the same in
Python and in Rust: [docs/adding-regexes.md](docs/adding-regexes.md) is the checklist (test the
regex in regex101's Rust flavour, examples, checksums, rarity, the `Charset Only` tag, false
positives), and its tests run in CI.

To pick the rarity of a new regex, `python scripts/rarity_score.py 'REGEX'` estimates it from the regex.

Every regex needs at least one valid example in its `"Examples"`, as the examples are run as tests. Please add invalid examples too, like values that look similar but must not match.

Secret scanners take fake API keys, like a Stripe or Shopify key, for leaked secrets: GitHub may block the push, and SonarCloud fails the pull request. To avoid that, write such an example as a list of parts, which pyWhat joins when it loads the regexes:

```json
"Valid": [
   [
      "sk_live_",
      "tkOg6ekCDvaFSDfSfyQqMfA0"
   ]
]
```

## Running the tests

The Python package searches with the regex engine of the Rust crate at the root of the repository, through its extension module `pywhat._pywhat` (`py/`). Building it needs [Rust](https://rustup.rs):

```console
$ pip install -r requirements.txt
$ pip install -e .     # builds the extension into pywhat/; run it again after changing Rust code
$ pytest
```

`nox` runs the tests the way CI does. The Rust crate has tests of its own (`cargo test`), see [docs/rust.md](docs/rust.md).
