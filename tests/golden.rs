//! The golden parity test: what the Rust crate finds must be what the Python package finds.
//!
//!     python scripts/golden.py    # writes target/golden.jsonl and target/golden-files.jsonl
//!     PYWHAT_GOLDEN=target/golden.jsonl PYWHAT_GOLDEN_FILES=target/golden-files.jsonl \
//!         cargo test --release --test golden -- --nocapture
//!
//! Without PYWHAT_GOLDEN (PYWHAT_GOLDEN_FILES) the test (the file test) does nothing. See scripts/golden.py for the texts and the
//! option sets.

use pywhat::processors::OpenStreetMap;
use pywhat::{default_processors, Filter, Identifier, Key, Match, Processor, Top};
use serde_json::Value;
use std::collections::BTreeMap;
use std::io::BufRead;

fn identifiers() -> BTreeMap<&'static str, Identifier> {
    let cli = Filter::default();
    let with = |tags: Option<&[&str]>, exclude: &[&str], min: f64| {
        Filter::new(tags, exclude, min, 1.0).expect("valid filter")
    };
    let mut osm: Vec<Box<dyn Processor>> = default_processors();
    osm.push(Box::new(OpenStreetMap));
    BTreeMap::from([
        ("api", Identifier::default()),
        (
            "cli",
            Identifier::default().with_boundaryless_filter(cli.clone()),
        ),
        (
            "all",
            Identifier::default()
                .with_filter(Filter::default().with_min_rarity(0.0))
                .with_boundaryless_filter(Filter::default().with_min_rarity(0.0)),
        ),
        (
            "bug_bounty",
            Identifier::default()
                .with_filter(with(Some(&["Bug Bounty"]), &[], 0.1))
                .with_boundaryless_filter(cli.clone()),
        ),
        (
            "identifiers_media",
            Identifier::default()
                .with_filter(with(Some(&["Identifiers", "Media"]), &[], 0.5))
                .with_boundaryless_filter(cli.clone()),
        ),
        (
            "exclude_aws",
            Identifier::default()
                .with_filter(with(None, &["AWS"], 0.1))
                .with_boundaryless_filter(cli.clone()),
        ),
        (
            "no_processing",
            Identifier::default()
                .with_boundaryless_filter(cli.clone())
                .with_processors(vec![]),
        ),
        (
            "osm",
            Identifier::default()
                .with_boundaryless_filter(cli.clone())
                .with_processors(osm),
        ),
        (
            "and",
            Identifier::default()
                .with_filter(finance().and(&btc()))
                .with_boundaryless_filter(with(Some(&["Bitcoin"]), &["Credit Card"], 0.1)),
        ),
        (
            "or",
            Identifier::default()
                .with_filter(finance().or(&btc()))
                .with_boundaryless_filter(with(Some(&["Identifiers"]), &[], 0.2)),
        ),
        (
            "and_exclude",
            Identifier::default()
                .with_filter(with(Some(&["AWS"]), &["Credentials"], 0.1).and(&with(
                    Some(&["AWS"]),
                    &[],
                    0.1,
                )))
                .with_boundaryless_filter(cli.clone()),
        ),
    ])
}

fn finance() -> Filter {
    Filter::new(Some(&["Finance"]), &["Credit Card"], 0.1, 1.0).expect("valid filter")
}

fn btc() -> Filter {
    Filter::new(
        Some(&["BTC Wallet", "Credentials"]),
        &["Credit Card", "AWS"],
        0.3,
        1.0,
    )
    .expect("valid filter")
}

/// The option sets that every record of a kind must have.
fn expected_sets(kind: &str) -> Vec<&'static str> {
    if kind == "affixed" {
        return vec!["api", "cli", "all"];
    }
    let mut sets: Vec<&str> = identifiers().into_keys().collect();
    sets.extend([
        "key_name",
        "key_name_reverse",
        "key_rarity",
        "key_rarity_reverse",
        "key_matched",
        "key_likely",
        "key_likely_reverse",
        "top_10",
        "top_5_percent",
    ]);
    sets
}

fn compact(found: &Match) -> Value {
    let text = |value: &Option<String>| value.clone().map_or(Value::Null, Value::String);
    Value::Array(vec![
        Value::String(found.regex.name.clone()),
        Value::String(found.matched.clone()),
        Value::Bool(found.fragment),
        text(&found.description),
        text(&found.exploit),
        text(&found.link()),
    ])
}

fn sorted(found: &[Match], key: Key, reverse: bool) -> Vec<Match> {
    let mut found = found.to_vec();
    pywhat::ranking::sort_matches(&mut found, key, reverse);
    found
}

#[test]
fn rust_finds_what_python_finds() {
    let Ok(path) = std::env::var("PYWHAT_GOLDEN") else {
        eprintln!("PYWHAT_GOLDEN is not set: skipping the golden test");
        return;
    };
    let file = std::fs::File::open(&path).expect("PYWHAT_GOLDEN file");
    let identifiers = identifiers();
    let mut texts = 0;
    let mut compared = 0;
    let mut differences: BTreeMap<String, usize> = BTreeMap::new();
    let mut unicode_differences = 0;
    let mut shown = 0;
    let mut jsons = 0;
    let mut trailer = None;
    for line in std::io::BufReader::new(file).lines() {
        let record: Value = serde_json::from_str(&line.expect("line")).expect("JSON line");
        if let Some(counts) = record.get("trailer") {
            trailer = Some(counts.clone());
            continue;
        }
        assert!(trailer.is_none(), "records after the trailer in {path}");
        let text = record["text"].as_str().expect("text");
        let kind = record["kind"].as_str().expect("kind");
        texts += 1;
        let results = record["results"].as_object().expect("results");
        for set in expected_sets(kind) {
            assert!(
                results.contains_key(set),
                "the recording has no {set:?} results for {text:?}: regenerate it with scripts/golden.py"
            );
        }
        let cli = identifiers["cli"].identify(text);
        let mut ours: BTreeMap<String, Vec<Match>> = BTreeMap::new();
        for (name, expected) in results {
            let found = match name.as_str() {
                "key_name" => sorted(&cli, Key::Name, false),
                "key_name_reverse" => sorted(&cli, Key::Name, true),
                "key_rarity" => sorted(&cli, Key::Rarity, false),
                "key_rarity_reverse" => sorted(&cli, Key::Rarity, true),
                "key_matched" => sorted(&cli, Key::Matched, false),
                "key_likely" => sorted(&cli, Key::Likely, false),
                "key_likely_reverse" => sorted(&cli, Key::Likely, true),
                "top_10" => pywhat::ranking::top_matches(&cli, &Top::Number(10)),
                "top_5_percent" => pywhat::ranking::top_matches(&cli, &Top::Percent("5".into())),
                other => identifiers[other].identify(text),
            };
            let actual = Value::Array(found.iter().map(compact).collect());
            compared += 1;
            if &actual != expected {
                if kind == "unicode" {
                    unicode_differences += 1;
                    eprintln!("documented Unicode difference ({name}) on {text:?}:\n  python: {expected}\n  rust:   {actual}");
                    continue;
                }
                *differences.entry(name.clone()).or_default() += 1;
                if shown < 20 {
                    shown += 1;
                    eprintln!("DIFFERENCE ({name}) on {:?}:", truncate(text));
                    report(expected, &actual);
                }
            }
            ours.insert(name.clone(), found);
        }
        if let Some(json) = record.get("json").and_then(Value::as_str) {
            compared += 1;
            jsons += 1;
            let mut actual = String::new();
            pywhat::identify::write_identify_json(
                &mut actual,
                &[("text".to_string(), ours.remove("cli").unwrap_or(cli))],
                None,
            );
            if actual != json {
                *differences.entry("json".into()).or_default() += 1;
                if shown < 20 {
                    shown += 1;
                    eprintln!(
                        "JSON DIFFERENCE on {:?}:\n  python: {}\n  rust:   {}",
                        truncate(text),
                        truncate(json),
                        truncate(&actual)
                    );
                    let at = actual
                        .bytes()
                        .zip(json.bytes())
                        .position(|(a, b)| a != b)
                        .unwrap_or(0);
                    eprintln!(
                        "  first difference at byte {at}: python {:?} rust {:?}",
                        &json[at.saturating_sub(40)..(at + 80).min(json.len())],
                        &actual[at.saturating_sub(40)..(at + 80).min(actual.len())]
                    );
                }
            }
        }
    }
    let total: usize = differences.values().sum();
    eprintln!(
        "golden: {texts} texts, {compared} comparisons, {total} differences {differences:?}, \
         {unicode_differences} documented Unicode differences"
    );
    assert!(texts > 0, "no texts in {path}");
    assert!(compared > texts, "{compared} comparisons for {texts} texts");
    // scripts/golden.py ends the recording with its counts: a cut recording, or one whose
    // JSON was left out, fails here
    let trailer = trailer.unwrap_or_else(|| panic!("{path} has no trailer: cut off?"));
    assert_eq!(trailer["texts"], texts, "texts recorded and read");
    assert_eq!(trailer["json"], jsons, "JSON records recorded and read");
    assert!(jsons > 0, "no JSON records in {path}");
    assert_eq!(total, 0, "Rust and Python differ: {differences:?}");
}

fn truncate(text: &str) -> String {
    if text.chars().count() > 300 {
        format!(
            "{}...<{} bytes>",
            text.chars().take(300).collect::<String>(),
            text.len()
        )
    } else {
        text.to_string()
    }
}

/// Prints the first matches that differ.
fn report(expected: &Value, actual: &Value) {
    let empty = Vec::new();
    let expected = expected.as_array().unwrap_or(&empty);
    let actual = actual.as_array().unwrap_or(&empty);
    eprintln!(
        "  python: {} matches, rust: {} matches",
        expected.len(),
        actual.len()
    );
    for i in 0..expected.len().max(actual.len()) {
        let (e, a) = (expected.get(i), actual.get(i));
        if e != a {
            eprintln!(
                "  #{i} python: {}",
                e.map_or("-".into(), |v| truncate(&v.to_string()))
            );
            eprintln!(
                "  #{i} rust:   {}",
                a.map_or("-".into(), |v| truncate(&v.to_string()))
            );
            break;
        }
    }
}

#[cfg(feature = "files")]
/// File and directory inputs, recorded by `scripts/golden.py` in target/golden-files.jsonl. Directory
/// locations are compared without regard to their order (Python's glob uses the order of
/// the file system, Rust sorts by name).
#[test]
fn rust_reads_files_like_python() {
    let Ok(path) = std::env::var("PYWHAT_GOLDEN_FILES") else {
        eprintln!("PYWHAT_GOLDEN_FILES is not set: skipping the file golden test");
        return;
    };
    let file = std::fs::File::open(&path).expect("PYWHAT_GOLDEN_FILES file");
    let identifiers = identifiers();
    let mut cases = 0;
    let mut jsons = 0;
    let mut trailer = None;
    let mut differences = Vec::new();
    for line in std::io::BufReader::new(file).lines() {
        let record: Value = serde_json::from_str(&line.expect("line")).expect("JSON line");
        if let Some(counts) = record.get("trailer") {
            trailer = Some(counts.clone());
            continue;
        }
        assert!(trailer.is_none(), "records after the trailer in {path}");
        let inputs: Vec<String> = record["inputs"]
            .as_array()
            .expect("inputs")
            .iter()
            .map(|i| i.as_str().expect("input").to_string())
            .collect();
        let options = pywhat::InputOptions {
            only_text: false,
            include_filenames: record["include_filenames"].as_bool().unwrap_or(false),
        };
        let name = record["options"].as_str().expect("options");
        let identified = identifiers[name].identify_inputs(&inputs, options, Key::None, false);
        cases += 1;
        let signatures: BTreeMap<String, Value> = identified
            .signatures
            .iter()
            .map(|(location, signature)| {
                (
                    location.clone(),
                    signature["Hexadecimal File Signature"].clone(),
                )
            })
            .collect();
        let expected_signatures: BTreeMap<String, Value> = record["signatures"]
            .as_object()
            .expect("signatures")
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        if signatures != expected_signatures {
            differences.push(format!(
                "{inputs:?} ({name}): signatures\n  python: {expected_signatures:?}\n  rust:   {signatures:?}"
            ));
        }
        let regexes: BTreeMap<String, Value> = identified
            .regexes
            .iter()
            .map(|(location, matches)| {
                (
                    location.clone(),
                    Value::Array(matches.iter().map(compact).collect()),
                )
            })
            .collect();
        let expected: BTreeMap<String, Value> = record["regexes"]
            .as_object()
            .expect("regexes")
            .iter()
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect();
        for location in expected.keys().chain(regexes.keys()) {
            if expected.get(location) != regexes.get(location) {
                let none = Value::Null;
                differences.push(format!(
                    "{inputs:?} ({name}) {location}:\n  python: {}\n  rust:   {}",
                    truncate(&expected.get(location).unwrap_or(&none).to_string()),
                    truncate(&regexes.get(location).unwrap_or(&none).to_string())
                ));
                break;
            }
        }
        if let Some(json) = record.get("json").and_then(Value::as_str) {
            jsons += 1;
            let actual = identified.to_json();
            if actual != json {
                let at = actual
                    .bytes()
                    .zip(json.bytes())
                    .position(|(a, b)| a != b)
                    .unwrap_or(0);
                differences.push(format!(
                    "{inputs:?} ({name}): JSON differs at byte {at}: python {:?} rust {:?}",
                    &json[at.saturating_sub(60)..(at + 60).min(json.len())],
                    &actual[at.saturating_sub(60)..(at + 60).min(actual.len())]
                ));
            }
        }
    }
    for difference in &differences {
        eprintln!("DIFFERENCE {difference}");
    }
    eprintln!(
        "golden files: {cases} cases, {} differences",
        differences.len()
    );
    assert!(cases > 0);
    let trailer = trailer.unwrap_or_else(|| panic!("{path} has no trailer: cut off?"));
    assert_eq!(trailer["cases"], cases, "cases recorded and read");
    assert_eq!(trailer["json"], jsons, "JSON records recorded and read");
    assert!(jsons > 0, "no JSON records in {path}");
    assert!(differences.is_empty(), "{} differences", differences.len());
}
