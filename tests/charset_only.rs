//! The "Charset Only" tag: the regexes that only check which characters a text has and how
//! long it is. Matches of them say little: decoder output and random strings match them.
//!
//! A regex is "Charset Only" when random strings over one of nine common alphabets (digits,
//! hex, HEX, lower, upper, alphanumeric, Base64, Base64url, Base58), of the right length, match
//! the whole of it more than 1 time in 1,000 (THRESHOLD), counting its checksum: a Luhn check
//! passes 1 in 10 random numbers, Base58Check 1 in 2^32. The chance is computed exactly, from
//! the regex's DFA: for every length up to 200 (or 50 past the regex's shortest match), the
//! share of the strings of that length that end in a match state. Regexes the DFA can't be built for are in `BY_HAND`, with a reason.
//!
//! When this test fails for a new or changed regex, add or remove the tag in regex.json, as the
//! message says. See docs/adding-regexes.md.

use regex_automata::dfa::{dense, Automaton, StartKind};
use regex_automata::util::primitives::StateID;
use regex_automata::{Anchored, Input};
use std::collections::HashMap;

const TAG: &str = "Charset Only";
const THRESHOLD: f64 = 1e-3;
const MAX_LENGTH: usize = 200;

const ALPHABETS: [(&str, &str); 9] = [
    ("digits", "0123456789"),
    ("hex", "0123456789abcdef"),
    ("HEX", "0123456789ABCDEF"),
    ("lower", "abcdefghijklmnopqrstuvwxyz"),
    ("upper", "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    (
        "alphanumeric",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
    ),
    (
        "Base64",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",
    ),
    (
        "Base64url",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_",
    ),
    (
        "Base58",
        "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz",
    ),
];

/// Regexes whose DFA can't be built here, decided by hand.
const BY_HAND: &[(&str, bool, &str)] = &[
    (
        "Uniform Resource Locator (URL)",
        false,
        "its DFA is too large; a URL needs a scheme, or a dot and a known TLD",
    ),
    (
        "Date of Birth",
        true,
        "a back-reference; 11,781 of the 10,000,000 seven-digit numbers are dates (1.18 in \
         1,000): 9 in 10 first digits, 11 in 100 months (it leaves out October) and 119 in \
         10,000 years",
    ),
    (
        "Phone Number",
        false,
        "its look-aheads require 9 to 14 digits after a + or between separators, which random \
         strings of these alphabets don't have",
    ),
];

/// The chance that random strings over `alphabet` of each length up to `max_length` match
/// all of the DFA.
fn chances(dfa: &dense::DFA<Vec<u32>>, alphabet: &[u8], max_length: usize) -> Vec<f64> {
    let start = dfa
        .start_state_forward(&Input::new("").anchored(Anchored::Yes))
        .expect("anchored start state");
    let mut states: HashMap<StateID, f64> = HashMap::from([(start, 1.0)]);
    let weight = 1.0 / alphabet.len() as f64;
    let mut out = Vec::with_capacity(max_length + 1);
    for _ in 0..=max_length {
        out.push(
            states
                .iter()
                .filter(|(state, _)| dfa.is_match_state(dfa.next_eoi_state(**state)))
                .map(|(_, chance)| chance)
                .sum(),
        );
        let mut next: HashMap<StateID, f64> = HashMap::new();
        for (&state, &chance) in &states {
            for &byte in alphabet {
                let to = dfa.next_state(state, byte);
                if !dfa.is_dead_state(to) {
                    *next.entry(to).or_insert(0.0) += chance * weight;
                }
            }
        }
        states = next;
        if states.is_empty() {
            out.resize(max_length + 1, 0.0);
            break;
        }
    }
    out
}

/// The share of the regex's random matches over `alphabet` that pass its validator: how
/// much the validator lowers the chance that a random string matches.
fn validator_factor(validator: Option<&str>, alphabet: &str) -> f64 {
    let has = |f: fn(&u8) -> bool| alphabet.as_bytes().iter().any(f);
    match validator {
        None => 1.0,
        Some("luhn") => 0.1,
        // The regex already takes only even last digits, the only ones a valid number has:
        // 1 in 50 of its matches pass (1 in 100 of all 11-digit numbers do)
        Some("tc-kimlik") => 0.02,
        Some("base58check" | "ripple-base58check") => 2f64.powi(-32),
        Some("cashaddr") => 2f64.powi(-40),
        Some("facebook-access-token") => {
            if has(u8::is_ascii_lowercase) && has(u8::is_ascii_uppercase) && has(u8::is_ascii_digit)
            {
                1.0
            } else {
                0.0
            }
        }
        Some(other) => area_validator_factor(other, alphabet)
            .unwrap_or_else(|| panic!("unknown validator {other}: add its factor here")),
    }
}

/// The factors of the validators of the area files, each area in its own block, so that
/// pull requests for different areas don't change the same lines.
#[allow(clippy::match_single_binding)]
fn area_validator_factor(validator: &str, alphabet: &str) -> Option<f64> {
    let _ = alphabet;
    match validator {
        // --- crypto ---
        // --- end crypto ---
        // --- cloud ---
        // --- end cloud ---
        // --- ctf ---
        // --- end ctf ---
        // --- network ---
        // --- end network ---
        // --- ids ---
        // --- end ids ---
        // --- files ---
        // --- end files ---
        // --- social ---
        // --- end social ---
        _ => None,
    }
}

/// The pattern to build the DFA of: the regex, or for regexes that need fancy-regex, the
/// regex without its look-arounds (which matches every text that the regex matches).
fn pattern(entry: &pywhat::RegexEntry) -> Option<String> {
    if regex_syntax::Parser::new().parse(&entry.regex).is_ok() {
        return Some(entry.regex.clone());
    }
    let tree = fancy_regex::Expr::parse_tree(&entry.regex).ok()?;
    fn relax(expr: &mut fancy_regex::Expr) {
        match expr {
            fancy_regex::Expr::LookAround(..) => *expr = fancy_regex::Expr::Empty,
            _ => {
                for child in expr.children_iter_mut() {
                    relax(child);
                }
            }
        }
    }
    let mut expr = tree.expr.clone();
    relax(&mut expr);
    std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
        let mut out = String::new();
        expr.to_str(&mut out, 0);
        out
    }))
    .ok()
}

/// The largest chance that a random string matches `entry`, with the alphabet and length.
fn weakness(entry: &pywhat::RegexEntry) -> Result<(f64, String), String> {
    let pattern = pattern(entry).ok_or("can't be written for the regex crate")?;
    let dfa = dense::Builder::new()
        .configure(
            dense::Config::new()
                .start_kind(StartKind::Anchored)
                .unicode_word_boundary(true)
                .dfa_size_limit(Some(64 << 20))
                .determinize_size_limit(Some(64 << 20)),
        )
        .build(&pattern)
        .map_err(|error| error.to_string())?;
    // At least MAX_LENGTH, and past the shortest match of a long regex (Facebook access
    // tokens are 192 characters or more)
    let shortest = regex_syntax::Parser::new()
        .parse(&pattern)
        .ok()
        .and_then(|hir| hir.properties().minimum_len())
        .unwrap_or(0);
    let max_length = MAX_LENGTH.max(shortest + 50);
    let validator = entry.validator.as_deref().or(
        // The Bitcoin regex is checked by its own processor (Base58Check or Bech32)
        (entry.name == "Bitcoin (\u{20bf}) Wallet Address").then_some("base58check"),
    );
    let mut best = (0.0, String::from("nothing matches"));
    for (name, alphabet) in ALPHABETS {
        let factor = validator_factor(validator, alphabet);
        for (length, chance) in chances(&dfa, alphabet.as_bytes(), max_length)
            .iter()
            .enumerate()
        {
            if chance * factor > best.0 {
                best = (chance * factor, format!("{name}, length {length}"));
            }
        }
    }
    Ok(best)
}

#[test]
fn charset_only_tags_are_the_regexes_random_strings_match() {
    let mut wrong = Vec::new();
    let mut tagged = 0;
    for entry in pywhat::regexes() {
        let has_tag = entry.tags.iter().any(|tag| tag == TAG);
        tagged += usize::from(has_tag);
        let (charset_only, why) = match BY_HAND.iter().find(|(name, _, _)| *name == entry.name) {
            Some((_, charset_only, reason)) => {
                (*charset_only, format!("decided by hand: {reason}"))
            }
            None => match weakness(entry) {
                Ok((chance, at)) => (
                    chance >= THRESHOLD,
                    format!("{:.3e} of random strings match ({at})", chance),
                ),
                Err(error) => {
                    wrong.push(format!(
                        "{}: no DFA ({error}); decide by hand in BY_HAND",
                        entry.name
                    ));
                    continue;
                }
            },
        };
        if charset_only != has_tag {
            let fix = if charset_only {
                format!("add the tag \"{TAG}\"")
            } else {
                format!("remove the tag \"{TAG}\"")
            };
            wrong.push(format!("{}: {why}: {fix}", entry.name));
        }
    }
    assert!(
        wrong.is_empty(),
        "\"{TAG}\" marks the regexes that more than 1 in {} random strings match \
         (tests/charset_only.rs):\n{}",
        (1.0 / THRESHOLD) as u32,
        wrong.join("\n")
    );
    assert!(tagged > 10, "{tagged}");
}

#[test]
fn every_by_hand_decision_is_for_a_regex_that_exists() {
    for (name, _, _) in BY_HAND {
        assert!(
            pywhat::regexes().iter().any(|entry| entry.name == *name),
            "{name} is not in regex.json"
        );
    }
}
