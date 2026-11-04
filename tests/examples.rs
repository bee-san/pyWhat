//! Every example in regex.json, like tests/test_regex_identifier.py: a valid example must be
//! found by a regex whose name contains the example's regex's name (anchored, rarity 0 to
//! 1, default processors), and an invalid one must not.

use pywhat::{regexes, EngineKind, Filter, Identifier};

fn identifier() -> Identifier {
    Identifier::default().with_filter(Filter::default().with_min_rarity(0.0))
}

fn found_by(identifier: &Identifier, name: &str, example: &str) -> bool {
    identifier
        .identify(example)
        .iter()
        .any(|found| found.regex.name.contains(name))
}

#[test]
fn valid_examples_match() {
    let identifier = identifier();
    let mut failures = Vec::new();
    let mut checked = 0;
    for entry in regexes() {
        assert!(
            !entry.valid_examples.is_empty(),
            "{} has no valid examples",
            entry.name
        );
        for example in &entry.valid_examples {
            checked += 1;
            if !found_by(&identifier, &entry.name, example) {
                failures.push(format!("{}: {example:?}", entry.name));
            }
        }
    }
    assert!(
        failures.is_empty(),
        "valid examples not found:\n{}",
        failures.join("\n")
    );
    assert!(checked > 400, "{checked}");
}

#[test]
fn invalid_examples_do_not_match() {
    let identifier = identifier();
    let mut failures = Vec::new();
    for entry in regexes() {
        for example in &entry.invalid_examples {
            if found_by(&identifier, &entry.name, example) {
                failures.push(format!("{}: {example:?}", entry.name));
            }
        }
    }
    assert!(
        failures.is_empty(),
        "invalid examples found:\n{}",
        failures.join("\n")
    );
}

/// The regexes that the `regex` crate can't run, and how they run instead. A new regex that
/// needs look-arounds or back-references has to be added here on purpose: fancy-regex is a
/// backtracking engine, slower and with a backtracking limit.
const NOT_ON_THE_REGEX_CRATE: &[(&str, EngineKind, EngineKind)] = &[
    // (name, anchored form, boundaryless form)
    (
        "YouTube Video",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    ("Picatic API Key", EngineKind::Guarded, EngineKind::Guarded),
    (
        "Regex101 Permalink",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    (
        "Amazon Web Services Access Key",
        EngineKind::Guarded,
        EngineKind::Guarded,
    ),
    (
        "Amazon Web Services IAM Unique Identifier",
        EngineKind::Guarded,
        EngineKind::Guarded,
    ),
    (
        "Base64 Encoded Java Serialized Object",
        EngineKind::Guarded,
        EngineKind::Guarded,
    ),
    (
        "PHP Serialized Object",
        EngineKind::Guarded,
        EngineKind::Guarded,
    ),
    (
        "Internet Protocol (IP) Address Version 6",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    (
        "Uniform Resource Locator (URL)",
        EngineKind::Fancy,
        EngineKind::Fancy,
    ),
    (
        "ISO 8601 Timestamp",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    (
        "Internet Protocol (IP) Address Version 4 CIDR Block",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    (
        "Phone Number",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    (
        "Cron Schedule",
        EngineKind::FancyPrefiltered,
        EngineKind::FancyPrefiltered,
    ),
    ("Tox ID", EngineKind::Guarded, EngineKind::Guarded),
    ("Date of Birth", EngineKind::Fancy, EngineKind::Fancy),
    (
        "Amazon Web Services Secret Access Key",
        EngineKind::Guarded,
        EngineKind::Guarded,
    ),
    ("YouTube Video ID", EngineKind::Guarded, EngineKind::Guarded),
];

#[test]
fn only_the_allowlisted_regexes_need_more_than_the_regex_crate() {
    let mut actual = Vec::new();
    for entry in regexes() {
        let anchored = pywhat::engine_of(entry, false).unwrap();
        let boundaryless = pywhat::engine_of(entry, true).unwrap();
        if anchored != EngineKind::Regex || boundaryless != EngineKind::Regex {
            actual.push((entry.name.as_str(), anchored, boundaryless));
        }
    }
    let expected: Vec<(&str, EngineKind, EngineKind)> = NOT_ON_THE_REGEX_CRATE.to_vec();
    assert_eq!(
        actual, expected,
        "regexes that don't run on the regex crate (update NOT_ON_THE_REGEX_CRATE on purpose)"
    );
}
