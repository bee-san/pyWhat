//! `Identifier::identify_whole` finds exactly the regexes whose `^(...)$` matches the whole
//! text: compared with a plain reference that runs every regex on fancy-regex, without the
//! engine's guards and cheap checks.

use pywhat::{regexes, Filter, Identifier};

/// Every regex of the database, compiled for the whole text on fancy-regex.
fn reference_regexes() -> Vec<(&'static pywhat::RegexEntry, fancy_regex::Regex)> {
    regexes()
        .iter()
        .map(|entry| {
            let regex = fancy_regex::RegexBuilder::new(&entry.regex)
                .backtrack_limit(100_000_000)
                .build()
                .expect("compiles");
            (entry, regex)
        })
        .collect()
}

fn reference(
    compiled: &[(&'static pywhat::RegexEntry, fancy_regex::Regex)],
    text: &str,
) -> Vec<String> {
    compiled
        .iter()
        .filter(|(entry, regex)| {
            regex.is_match(text).expect("no backtracking error")
                && (entry.name != "Bitcoin (\u{20bf}) Wallet Address"
                    || pywhat::is_bitcoin_address(text))
                && entry
                    .validator
                    .as_deref()
                    .is_none_or(|name| pywhat::validators::validator(name).expect("exists")(text))
        })
        .map(|(entry, _)| entry.name.clone())
        .collect()
}

fn texts() -> Vec<String> {
    let affixes = ["", "a", "0", " ", "\n", "é", "{", "x y", "\t"];
    let mut texts = Vec::new();
    for entry in regexes() {
        for example in entry.valid_examples.iter().chain(&entry.invalid_examples) {
            for affix in affixes {
                texts.push(format!("{affix}{example}"));
                texts.push(format!("{example}{affix}"));
            }
        }
    }
    texts.extend(
        [
            "",
            "a",
            "\n",
            "https://example.com",
            "https://example.com\n",
            "hello world",
            "5baa61e4c9b93f3f0682250b6cf8331b7ee68fd8",
            "+1 (555) 123-4567",
            "1 01 1990",
            "01/01/1990\nmore",
        ]
        .map(String::from),
    );
    texts
}

#[test]
fn identify_whole_equals_the_reference() {
    let identifier = Identifier::default().with_filter(Filter::default().with_min_rarity(0.0));
    let texts = texts();
    let compiled = reference_regexes();
    let mut differences = Vec::new();
    for text in &texts {
        let found: Vec<String> = identifier
            .identify_whole(text)
            .into_iter()
            .map(|m| m.regex.name.clone())
            .collect();
        let expected = reference(&compiled, text);
        if found != expected {
            differences.push(format!("{text:?}: {found:?} != {expected:?}"));
        }
    }
    assert!(
        differences.is_empty(),
        "{} of {} texts differ:\n{}",
        differences.len(),
        texts.len(),
        differences[..differences.len().min(20)].join("\n")
    );
}

#[test]
fn first_whole_is_the_first_of_identify_whole() {
    let identifier = Identifier::default();
    for text in texts() {
        assert_eq!(
            identifier.first_whole(&text).map(|m| m.regex.name.clone()),
            identifier
                .identify_whole(&text)
                .first()
                .map(|m| m.regex.name.clone()),
            "{text:?}"
        );
    }
}
