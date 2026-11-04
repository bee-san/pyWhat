//! Tests of the `what` command: its argument parser and its output formats. They run the
//! binary that cargo built, without a terminal, so there are no colours and no progress
//! bars. `scripts/parity_cli.py` compares the output with the Python CLI's.

use std::io::Write;
use std::path::Path;
use std::process::{Command, Stdio};

/// The exit code, stdout and stderr of `what args` with `stdin`.
fn what_with(args: &[&str], stdin: &[u8], env: &[(&str, &str)]) -> (i32, String, String) {
    let mut command = Command::new(env!("CARGO_BIN_EXE_what"));
    command
        .args(args)
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .env_remove("NO_COLOR")
        .env_remove("COLUMNS")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    for (name, value) in env {
        command.env(name, value);
    }
    let mut child = command.spawn().expect("what runs");
    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(stdin)
        .expect("stdin is written");
    let output = child.wait_with_output().expect("what finishes");
    (
        output.status.code().expect("an exit code"),
        String::from_utf8(output.stdout).expect("UTF-8 stdout"),
        String::from_utf8(output.stderr).expect("UTF-8 stderr"),
    )
}

fn what(args: &[&str]) -> (i32, String, String) {
    what_with(args, b"", &[])
}

/// The names of the matches in raw output.
fn names(output: &str) -> Vec<&str> {
    output
        .lines()
        .filter_map(|line| line.strip_prefix("Name: "))
        .collect()
}

// The argument parser

#[test]
fn unknown_options_are_inputs() {
    // click's ignore_unknown_options: -1606586780 is the text to search, as after --
    let (code, stdout, _) = what(&["--rarity", "0:", "--format", "%m|%n", "-1606586780"]);
    assert_eq!(code, 0);
    assert_eq!(stdout, "160658678|American Social Security Number\n");
    let (_, after_dashes, _) = what(&["--rarity", "0:", "--format", "%m|%n", "--", "-1606586780"]);
    assert_eq!(stdout, after_dashes);
    let (code, stdout, _) = what(&["-db", "--nope", "THM{x}"]);
    assert_eq!(code, 0);
    assert_eq!(names(&stdout), ["TryHackMe Flag Format"]);
}

#[test]
fn multi_letter_short_options() {
    let (_, with, _) = what(&["abc118.103.238.230abc"]);
    let (_, without, _) = what(&["-db", "abc118.103.238.230abc"]);
    assert!(names(&with).contains(&"Internet Protocol (IP) Address Version 4"));
    assert_eq!(without, "Nothing found!\n");
    // -bi takes a value, -pt is a flag
    let (_, stdout, _) = what(&["-bi", "IPv4 Address", "-pt", "abc118.103.238.230abc"]);
    assert!(
        stdout.starts_with("Matched on: 118.103.238.230\n"),
        "{stdout}"
    );
    assert!(stdout.contains("\nTags: "), "{stdout}");
    // The email address has a rarity below 0.6, so -br 0.6: searches it with boundaries
    let (_, stdout, _) = what(&["-br", "0.6:", "-be", "URL", "123myEmail@host.org456"]);
    assert_eq!(stdout, "Nothing found!\n");
}

#[test]
fn clusters_and_attached_values() {
    // -o and -k in one argument, -k with its value attached
    let (code, stdout, _) = what(&["-okname", "--json", "fixtures/file", "THM{x}"]);
    assert_eq!(code, 0);
    assert!(
        stdout
            .starts_with(r#"{"File Signatures": null, "Regexes": {"text": [{"Matched": "THM{x}""#),
        "{stdout}"
    );
    let (_, a, _) = what(&[
        "--top=1",
        "-db",
        "0x52908400098527886E0F7030069857D2E4169EE7",
    ]);
    let (_, b, _) = what(&[
        "--top",
        "1",
        "-db",
        "0x52908400098527886E0F7030069857D2E4169EE7",
    ]);
    assert_eq!(a, b);
}

#[test]
fn double_dash() {
    let (code, stdout, _) = what(&["--format", "%m", "--", "-db", "THM{x}"]);
    assert_eq!(code, 0);
    assert!(stdout.lines().any(|line| line == "THM{x}"), "{stdout}");
}

#[test]
fn usage_errors_exit_with_2() {
    let (code, stdout, stderr) = what(&["--rarity"]);
    assert_eq!((code, stdout.as_str()), (2, ""));
    assert_eq!(
        stderr,
        "Usage: what [OPTIONS] [TEXT_INPUT]...\nTry 'what --help' for help.\n\n\
         Error: Option '--rarity' requires an argument.\n"
    );
    let (code, _, stderr) = what(&["--json=1", "x"]);
    assert_eq!(code, 2);
    assert!(stderr.ends_with("Error: Option '--json' does not take a value.\n"));
    let (code, _, stderr) = what(&["--map", "bing", "x"]);
    assert_eq!(code, 2);
    assert!(stderr
        .ends_with("Error: Invalid value for '--map': 'bing' is not one of 'google', 'osm'.\n"));
}

#[test]
fn errors_exit_with_1() {
    for (args, message) in [
        (&["--rarity", "1", "x"][..], "Invalid rarity range format ('min:max' expected)\n"),
        (&["--rarity", "a:", "x"], "Invalid rarity argument (float expected)\n"),
        (&["--key", "nope", "x"], "Invalid key\n"),
        (
            &["--top", "0", "x"],
            "Invalid top '0', use a number of matches such as 10, a percentage of them such as 5% or all\n",
        ),
    ] {
        let (code, stdout, _) = what(args);
        assert_eq!((code, stdout.as_str()), (1, message), "{args:?}");
    }
    let (code, stdout, _) = what(&["--include", "ETH Walet", "x"]);
    assert_eq!(code, 1);
    assert!(stdout.contains("Passed tags are not valid"));
    assert!(stdout.contains("'pywhat --names'"));
    for (option, value, message) in [
        (
            "--key",
            "name",
            "--stream cannot sort the matches, so it cannot be used with --key\n",
        ),
        (
            "--top",
            "1",
            "--stream cannot pick the most likely matches, so it cannot be used with --top\n",
        ),
    ] {
        let (code, _, stderr) = what(&["--stream", option, value, "x"]);
        assert_eq!((code, stderr.as_str()), (1, message));
    }
}

#[test]
fn interactive_needs_python() {
    let (code, stdout, stderr) = what(&["--interactive", "x"]);
    assert_eq!((code, stdout.as_str()), (2, ""));
    assert_eq!(stderr.lines().count(), 1);
    assert!(stderr.contains("pip install pywhat"));
}

#[test]
fn eager_options() {
    let (code, stdout, _) = what(&["--tags", "x"]);
    assert_eq!(code, 0);
    assert!(stdout.lines().any(|line| line == "Bug Bounty"));
    let (_, stdout, _) = what(&["--names"]);
    assert!(stdout
        .lines()
        .any(|line| line == "Ethereum (ETH) Wallet Address: Ethereum Wallet, ETH Wallet"));
    let (_, stdout, _) = what(&["-v"]);
    assert_eq!(
        stdout,
        format!("PyWhat version {}\n", env!("CARGO_PKG_VERSION"))
    );
    // --help comes first, whatever the order
    let (code, stdout, _) = what(&["--map", "bing", "--help"]);
    assert_eq!(code, 0);
    assert!(stdout.starts_with("Usage: what [OPTIONS] [TEXT_INPUT]...\n\n  pyWhat - Identify"));
}

#[test]
fn help_wraps_at_the_width_of_click() {
    let (_, wide, _) = what_with(&["--help"], b"", &[("COLUMNS", "10000")]);
    assert!(wide.lines().all(|line| line.chars().count() <= 78));
    assert!(wide.contains("  -br, --boundaryless-rarity TEXT\n"));
    let (_, narrow, _) = what_with(&["--help"], b"", &[("COLUMNS", "30")]);
    assert!(
        narrow.lines().all(|line| line.chars().count() <= 50),
        "at least 50 columns"
    );
    assert!(narrow.lines().count() > wide.lines().count());
}

#[test]
fn stdin_without_inputs() {
    let (code, stdout, _) = what_with(&["-db"], b"THM{hello}\nfixtures/file\n", &[]);
    assert_eq!(code, 0);
    // One text, not a list of inputs
    assert_eq!(names(&stdout), ["TryHackMe Flag Format"]);
    assert!(!stdout.contains("File:"));
    let (_, stdout, _) = what_with(&["--json"], &utf16_with_bom("THM{wide}"), &[]);
    assert!(stdout.contains(r#""Matched": "THM{wide}""#), "{stdout}");
    let (code, stdout, _) = what_with(&[], b"", &[]);
    assert_eq!((code, stdout.as_str()), (0, "Nothing found!\n"));
}

fn utf16_with_bom(text: &str) -> Vec<u8> {
    let mut data = vec![0xFF, 0xFE];
    data.extend(text.encode_utf16().flat_map(u16::to_le_bytes));
    data
}

// The formats

#[test]
fn raw_output() {
    let (code, stdout, _) = what(&["-db", "THM{hello}", "github@skerritt.blog"]);
    assert_eq!(code, 0);
    assert_eq!(
        stdout,
        "Matched on: THM{hello}\nName: TryHackMe Flag Format\n\
         Description: Used for Capture The Flags at https://tryhackme.com\n\n\
         Matched on: github@skerritt.blog\nName: Email Address\n"
    );
    let (_, stdout, _) = what(&["-db", "-pt", "thm{2}"]);
    assert!(stdout.contains("Tags: CTF Flag"));
    let (_, stdout, _) = what(&["-db", "fixtures/test/file", "THM{hello}"]);
    assert!(stdout.contains("File: fixtures/test/file\nMatched on: https://google.com"));
    assert!(stdout.contains("File: text\nMatched on: THM{hello}"));
}

#[test]
fn matched_text_is_not_markup() {
    // The Python CLI prints "thm{x}" (#291, Python bug 4)
    let (_, stdout, _) = what(&["-db", "thm{[bold]x[/bold]}"]);
    assert!(
        stdout.starts_with("Matched on: thm{[bold]x[/bold]}\n"),
        "{stdout}"
    );
    // The markup of the data is rendered, like rich does
    let (_, stdout, _) = what(&["-db", "Access-Control-Allow: *"]);
    assert!(
        stdout.contains("Description: Used for Cross-Origin Resource Sharing (CORS)\n"),
        "{stdout}"
    );
}

#[test]
fn nothing_found() {
    assert_eq!(what(&["-db", ""]).1, "Nothing found!\n");
    assert_eq!(what(&["-db", "nothing", "here"]).1, "Nothing found!\n");
    assert_eq!(what(&["-db", "--format", "%m", "nothing"]).1, "");
    assert_eq!(
        what(&["-db", "--json", ""]).1,
        "{\"File Signatures\": null, \"Regexes\": null}\n"
    );
}

#[test]
fn custom_format() {
    let (_, stdout, _) = what(&[
        "-db",
        "--format",
        r"%m 2%n %d --- -%e%r %l %t \%d",
        "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk",
    ]);
    assert_eq!(
        stdout,
        "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk 2Ripple (XRP) Wallet Address  --- -0.3 \
         https://xrpscan.com/account/rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk Finance, \
         Cryptocurrency Wallet, Ripple Wallet, Ripple, XRP %d\n"
    );
    // \\ is a backslash, and a backslash in the match is not an escape (Python bug 2)
    let (code, stdout, _) = what(&["-db", "--format", r"\\%m - %n", r"thm{a\1}"]);
    assert_eq!(code, 0);
    assert_eq!(stdout, "\\thm{a\\1} - TryHackMe Flag Format\n");
    // An absent exploit is nothing
    assert_eq!(what(&["-db", "--format", "%e", "thm{2}"]).1, "");
}

#[test]
fn json_is_one_line_of_ascii() {
    let (code, stdout, _) = what(&[
        "--json",
        "fixtures/test",
        "fixtures/file",
        "THM{caf\u{e9} \u{20bf}}",
    ]);
    assert_eq!(code, 0);
    assert!(stdout.is_ascii());
    assert_eq!(stdout.matches('\n').count(), 1);
    assert!(stdout.contains(r#""Matched": "THM{caf\u00e9 \u20bf}""#));
    let json: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let locations: Vec<&String> = json["Regexes"].as_object().unwrap().keys().collect();
    let test_file = Path::new("fixtures/test").join("file");
    assert!(locations.contains(&&test_file.to_string_lossy().into_owned()));
    assert!(locations.contains(&&"text".to_string()));
    // --format json is --json
    assert_eq!(
        what(&["--format", " json ", "abc@example.com"]).1,
        what(&["--json", "abc@example.com"]).1
    );
}

#[test]
fn stream_json_lines_without_fragment() {
    let (code, stdout, _) = what(&["--stream", "--json", "fixtures/file"]);
    assert_eq!(code, 0);
    let (_, all, _) = what(&["--json", "fixtures/file"]);
    let all: serde_json::Value = serde_json::from_str(&all).unwrap();
    let mut expected = all["Regexes"]["file"].as_array().unwrap().clone();
    for found in &mut expected {
        found.as_object_mut().unwrap().remove("Fragment");
    }
    let mut streamed = Vec::new();
    for line in stdout.lines() {
        let found: serde_json::Value = serde_json::from_str(line).unwrap();
        assert!(found["File Signatures"].is_null());
        let matches = found["Regexes"]["file"].as_array().unwrap();
        assert_eq!(matches.len(), 1);
        assert!(matches[0].get("Fragment").is_none());
        streamed.push(matches[0].clone());
    }
    assert_eq!(streamed, expected);
    // Nothing found: no lines at all
    assert_eq!(what(&["--stream", "--json", "-db", ""]).1, "");
}

/// The output with every run of empty lines as one empty line (`squeeze()` of
/// tests/test_click.py).
fn squeeze(output: &str) -> String {
    let mut squeezed = output.to_string();
    while squeezed.contains("\n\n\n") {
        squeezed = squeezed.replace("\n\n\n", "\n\n");
    }
    squeezed
}

#[test]
fn stream_raw_is_the_complete_output() {
    for args in [
        &["-db", "fixtures/file"][..],
        &["fixtures/file", "fixtures/test/file", "THM{hello}"],
        &["--format", "%m - %n", "fixtures"],
        &["-db", ""],
    ] {
        let (_, complete, _) = what(args);
        let (code, streamed, _) = what(&[&["--stream"], args].concat());
        assert_eq!(code, 0);
        assert_eq!(squeeze(&streamed), squeeze(&complete), "{args:?}");
    }
}

#[test]
fn top_note_on_stderr() {
    let eth = "0x52908400098527886E0F7030069857D2E4169EE7";
    let (code, stdout, stderr) = what(&["--top", "1", "--json", eth]);
    assert_eq!(code, 0);
    let json: serde_json::Value = serde_json::from_str(&stdout).unwrap();
    let matches = json["Regexes"]["text"].as_array().unwrap();
    assert_eq!(matches.len(), 1);
    assert_eq!(
        matches[0]["Regex Pattern"]["Name"],
        "Ethereum (ETH) Wallet Address"
    );
    assert!(
        stderr.starts_with("\nShowing the 1 most likely of "),
        "{stderr}"
    );
    assert!(stderr.ends_with(
        " matches. Use --top to show more of them, or --interactive to search through all of them.\n"
    ));
    // No note when nothing is left out
    assert_eq!(what(&["--top", "all", eth]).2, "");
}

/// The cells of the tables in `output`, one row per line, with the lines of a cell
/// joined by spaces.
fn cells(output: &str) -> Vec<Vec<String>> {
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut row: Vec<Vec<String>> = Vec::new();
    for line in output.lines() {
        if line.starts_with(['┡', '├', '└']) {
            if let Some(first) = row.first() {
                let columns = first.len();
                rows.push(
                    (0..columns)
                        .map(|i| {
                            let parts: Vec<&str> = row
                                .iter()
                                .map(|parts| parts[i].as_str())
                                .filter(|part| !part.is_empty())
                                .collect();
                            parts.join(" ")
                        })
                        .collect(),
                );
            }
            row.clear();
        } else if line.starts_with(['┃', '│']) {
            // "┃ a ┃ b ┃" is "", " a ", " b ", ""
            let parts: Vec<&str> = line.split(['┃', '│']).collect();
            row.push(
                parts[1..parts.len() - 1]
                    .iter()
                    .map(|cell| cell.trim().to_string())
                    .collect(),
            );
        }
    }
    rows
}

#[test]
fn pretty_table() {
    let (code, stdout, _) = what_with(
        &[
            "-db",
            "--format",
            "pretty",
            "fixtures/test/file",
            "THM{hello}",
        ],
        b"",
        &[("COLUMNS", "200")],
    );
    assert_eq!(code, 0);
    assert!(stdout.starts_with("Possible Identification\n┏"), "{stdout}");
    assert_eq!(
        cells(&stdout),
        [
            ["Matched Text", "Identified as", "Description", "File"],
            [
                "https://google.com",
                "Uniform Resource Locator (URL)",
                "None",
                "fixtures/test/file"
            ],
            [
                "THM{hello}",
                "TryHackMe Flag Format",
                "Used for Capture The Flags at https://tryhackme.com",
                "text"
            ],
        ]
    );
    // An Exploit column when a regex has one, and the tags
    let heroku = "heroku00000000-0000-0000-0000-000000000000";
    let (_, stdout, _) = what_with(
        &[
            "-db",
            "--include",
            "Bug Bounty",
            "--format",
            "pretty",
            "-pt",
            heroku,
        ],
        b"",
        &[("COLUMNS", "1000")],
    );
    let rows = cells(&stdout);
    assert_eq!(
        rows[0],
        ["Matched Text", "Identified as", "Description", "Exploit"]
    );
    assert_eq!(
        rows[1][2],
        "Tags: Bug Bounty, API Keys, Credentials, Heroku"
    );
    assert!(rows[1][3].contains("curl -X POST https://api.heroku.com/apps"));
    // Nothing found
    assert_eq!(
        what(&["-db", "--format", "pretty", "nothing"]).1,
        "Nothing found!\n"
    );
}

#[test]
fn pretty_table_fits_narrow_terminals() {
    let (code, stdout, _) = what_with(
        &["-db", "--format", "pretty", "fixtures/file"],
        b"",
        &[("COLUMNS", "60")],
    );
    assert_eq!(code, 0);
    assert!(stdout.lines().all(|line| line.chars().count() <= 60));
}

#[test]
fn processing_and_maps() {
    let (_, stdout, _) = what(&[
        "--rarity",
        "0:",
        "--include",
        "UNIX Timestamp",
        "--format",
        "%d",
        "1637093119",
    ]);
    assert!(
        stdout.contains("Date: November 16, 2021 8:05:19 PM UTC"),
        "{stdout}"
    );
    // Bitcoin addresses with a wrong checksum are filtered out, unless -dp
    let wrong = "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F";
    assert!(!names(&what(&["-db", wrong]).1).contains(&"Bitcoin (₿) Wallet Address"));
    assert!(names(&what(&["-db", "-dp", wrong]).1).contains(&"Bitcoin (₿) Wallet Address"));
    let (_, stdout, _) = what(&["--map", "osm", "--format", "%l", "52.6169586, -1.9779857"]);
    assert!(stdout
        .lines()
        .any(|line| line == "https://www.openstreetmap.org/search?query=52.6169586,-1.9779857"));
}

#[test]
fn files_and_signatures() {
    let dir = std::env::temp_dir().join(format!("pywhat-cli-test-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let image = dir.join("image.png");
    std::fs::write(&image, b"\x89PNG\r\n\x1a\nTHM{hello}\n").unwrap();
    let image = image.to_string_lossy().into_owned();
    let (code, stdout, _) = what(&["-db", &image]);
    assert_eq!(code, 0);
    assert!(
        stdout.starts_with("\nFile Identified: image.png with Magic Numbers .PNG.....\n"),
        "{stdout}"
    );
    assert!(stdout.contains("Matched on: THM{hello}"));
    let (_, streamed, _) = what(&["-db", "--stream", &image]);
    assert_eq!(streamed, stdout);
    // -if searches the name of the file too
    let named = dir.join("THM{name}.txt");
    std::fs::write(&named, b"nothing").unwrap();
    let (_, stdout, _) = what(&["-if", "--format", "%m", &named.to_string_lossy()]);
    assert_eq!(stdout, "THM{name}\n");
    std::fs::remove_dir_all(&dir).unwrap();
}

#[test]
fn closed_output_ends_quietly() {
    // what ... | head: the rest of the output can't be written
    let mut child = Command::new(env!("CARGO_BIN_EXE_what"))
        .args(["--rarity", "0:", "fixtures/file"])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .unwrap();
    drop(child.stdout.take());
    let output = child.wait_with_output().unwrap();
    assert_eq!(output.status.code(), Some(1));
    assert!(
        output.stderr.is_empty(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}
