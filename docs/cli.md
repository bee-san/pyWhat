# The `what` command in Rust

`cargo install pywhat` installs `what` and `pywhat`: the command line of the Python package in
Rust, with the same options, defaults, help, error messages and exit codes (`what --help`), and the
same output. `pywhat::cli::main(std::env::args_os())` runs it and returns the exit code. Both
binaries do just that, and the Python package's commands can call it too. It is the crate's `cli`
feature, and `--verify` is its `verify` feature (both are default features, and add nothing on
wasm32).

- The arguments are parsed the way click parses them: `-br`, `-db` and the other options with
  several letters after one `-`, clusters such as `-ok name`, `--top=5`, `--` before inputs that
  start with `-`, and unknown options are inputs (`what -1606586780` searches `-1606586780`).
- Raw output, custom `--format` strings, `--json`, `--stream` (with `--json`: a JSON object per
  line, without `"Fragment"`) and `Nothing found!` are byte for byte what the Python CLI prints.
  `--format pretty` has the same cells, in a table that comfy-table draws.
- Colours (bold `#D7AFFF` labels) only on a terminal, without colours if `NO_COLOR` is set.
  Progress bars follow the Python CLI's rules: only on a terminal, after half a second, on stderr
  if stdout is a file, never into a pipe, and `--no-progress` turns them off.
- `--verify` sends each Google API key to Google once, like `GoogleAPIKeyVerifier`, with the same
  messages. The verifier is `pywhat::cli::verify::GoogleApiKeyVerifier`, a `Processor` whose
  `with_http` takes the HTTP call, so that tests don't send anything.
- `--interactive` is only in the Python package: `what --interactive` says so and exits with 2.

## Differences from the Python CLI

- The matched text and the file names are printed as they are. The Python CLI takes them for rich
  markup and emoji codes: `pywhat 'thm{[bold]x[/bold]}'` prints `thm{x}`, and `pywhat 'thm{[/x]}'`
  crashes with a `MarkupError` (#291, Python bug 4). The markup in the data files (some
  descriptions) and in `--format` strings is rendered as rich renders it; emoji codes in a
  `--format` string are not.
- `-v` prints the version of the crate.
- Directories are searched in the order of their names, where Python takes the order of the file
  system (#291, Python bug 5). A file that can't be read is skipped and reported on stderr, with
  exit code 1, where Python stops with a traceback.
- On Windows, output redirected to a file is UTF-8, where Python writes the ANSI code page with
  escapes such as `\u20bf` for what it can't encode. Arguments that aren't valid UTF-8 get U+FFFD
  for the invalid bytes.
- Without arguments, `what` reads stdin, as `pywhat` does; `python -m pywhat` shows the help.

## Parity tests

`scripts/parity_cli.py` runs 272 command lines with both CLIs and compares their stdout and exit
codes: every case of `tests/test_click.py` (read from it), every option on `fixtures/file`, the
examples of the README and of the help, and corner cases of the argument parser, of stdin and of
files. Python runs with glob listing directories in name order, so that the output of directories
can be compared byte for byte. `tests/conftest.py` runs `tests/test_click.py` against the binary
when `PYWHAT_CLI` is set:

```sh
cargo build --release
python scripts/parity_cli.py
PYWHAT_CLI=target/release/what pytest -o addopts="" tests/test_click.py
```

The Rust workflow runs both on every pull request.

## Measurements

`hyperfine -N` (hyperfine 2.0.0), with 5 runs for the big file and 10 for the others, on a shared
64-core machine with a load average of 61 to 83, JSON to `/dev/null`. `target/bench.txt` is the
4.2 MB text that `python scripts/bench_corpus.py` writes (see [rust.md](rust.md#measurements)):

| | `what` (Rust) | `pywhat` (Python 3.10) |
|---|---|---|
| `--json --no-progress target/bench.txt` | 3.05 s wall, 3.64 s user, 366 MiB | 22.87 s wall, 21.72 s user, 632 MiB |
| `--json --no-progress fixtures/file` | 0.14 s wall | 0.36 s wall |
| `--no-progress 'THM{a}'` | 0.12 s wall | 0.30 s wall |

Both print the same 296,955,554 bytes for `target/bench.txt` (`cmp`).
