//! The regex database, embedded at compile time from `pywhat/Data/*.json`, the files that
//! the Python package ships too. It is loaded the way `pywhat.helper.load_regexes()` loads
//! it: list-valued regexes are joined, example parts are joined, the boundaryless form of
//! every regex is derived, and the items of `Children` are read from their files.

use serde_json::{Map, Value};
use std::collections::HashMap;
use std::sync::OnceLock;

pub(crate) const REGEX_JSON: &str = include_str!("../pywhat/Data/regex.json");
pub(crate) const FILE_SIGNATURES_JSON: &str = include_str!("../pywhat/Data/file_signatures.json");

/// The vendors of MAC address prefixes (1.6 MB), for the descriptions of EUI-48 matches.
/// Without the `mac-vendors` feature, these matches have the regex's own description.
#[cfg(feature = "mac-vendors")]
const MAC_VENDORS_JSON: &str = include_str!("../pywhat/Data/mac_vendors.json");
#[cfg(not(feature = "mac-vendors"))]
const MAC_VENDORS_JSON: &str = "{}";

/// The data files that a `Children` entry can name in its `"path"`.
fn data_file(path: &str) -> Option<&'static str> {
    Some(match path {
        "mac_vendors.json" => MAC_VENDORS_JSON,
        "phone_codes.json" => include_str!("../pywhat/Data/phone_codes.json"),
        "mastercard_companies.json" => include_str!("../pywhat/Data/mastercard_companies.json"),
        "regex.json" => REGEX_JSON,
        "file_signatures.json" => FILE_SIGNATURES_JSON,
        _ => return None,
    })
}

/// How the `Children` of a regex identify what a match is in more detail.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum ChildrenMethod {
    /// The items are a map from prefixes of the match to descriptions.
    Hashmap,
    /// The items are a map from regexes, searched for in the match, to descriptions.
    Regex,
    /// The items are a map from prefixes, which the match starts with, to descriptions.
    StartsWith,
}

/// The `Children` of a regex: sub-identification of its matches.
#[derive(Debug)]
pub(crate) struct Children {
    pub(crate) method: ChildrenMethod,
    /// Put before the descriptions of the children that match, e.g. "Vendor(s): ".
    pub(crate) entry: String,
    /// Deleted from the match before the children are looked up, e.g. `[:.-]`.
    pub(crate) deletion_pattern: Option<String>,
    /// Where the items are: inline in regex.json, or in a data file.
    items: ItemsSource,
    loaded: OnceLock<Items>,
}

#[derive(Debug)]
enum ItemsSource {
    Inline(Map<String, Value>),
    File(&'static str),
}

/// The items of `Children`, in the order of their file.
#[derive(Debug)]
pub(crate) struct Items {
    /// (key, description), in file order.
    pub(crate) entries: Vec<(String, String)>,
    /// The descriptions by key, for the hashmap method.
    pub(crate) by_key: HashMap<String, usize>,
    /// The lengths (in characters) of the keys, longest first, as `load_regexes()` sorts them.
    pub(crate) lengths: Vec<usize>,
}

impl Children {
    pub(crate) fn items(&self) -> &Items {
        self.loaded.get_or_init(|| {
            let map = match &self.items {
                ItemsSource::Inline(map) => map.clone(),
                ItemsSource::File(text) => serde_json::from_str::<Map<String, Value>>(text)
                    .expect("the Children data file is a JSON object"),
            };
            let entries: Vec<(String, String)> = map
                .into_iter()
                .map(|(key, value)| (key, value_to_string(&value)))
                .collect();
            let by_key = entries
                .iter()
                .enumerate()
                .map(|(index, (key, _))| (key.clone(), index))
                .collect();
            let mut lengths: Vec<usize> =
                entries.iter().map(|(key, _)| key.chars().count()).collect();
            lengths.sort_unstable_by(|a, b| b.cmp(a));
            lengths.dedup();
            Items {
                entries,
                by_key,
                lengths,
            }
        })
    }
}

fn value_to_string(value: &Value) -> String {
    match value {
        Value::String(s) => s.clone(),
        other => other.to_string(),
    }
}

/// A regex of the database, an entry of `pywhat/Data/regex.json`.
#[derive(Debug)]
pub struct RegexEntry {
    /// Its position in the database (the order in which regexes are searched for).
    pub index: usize,
    /// Its name, e.g. "Uniform Resource Locator (URL)".
    pub name: String,
    /// Other names it is known by, e.g. "ETH Wallet" (may be empty).
    pub alternative_names: Vec<String>,
    /// The regex, in the `^(regex)$` format (list-valued regexes joined).
    pub regex: String,
    /// The regex without its `^` and `$` boundaries, for boundaryless mode.
    pub boundaryless_regex: String,
    pub plural_name: bool,
    pub description: Option<String>,
    /// How unlikely a match is to be a false positive, from 0 to 1.
    pub rarity: f64,
    pub url: Option<String>,
    pub tags: Vec<String>,
    /// How to use what was found, with `..._HERE` placeholders for the match.
    pub exploit: Option<String>,
    /// The valid examples (parts joined).
    pub valid_examples: Vec<String>,
    /// The invalid examples (parts joined).
    pub invalid_examples: Vec<String>,
    pub(crate) children: Option<Children>,
    /// The entry as the Python package prints it in a match's "Regex Pattern": the keys
    /// of regex.json in order, without "Children", with "Boundaryless Regex" at the end.
    pub(crate) json: Map<String, Value>,
}

impl RegexEntry {
    /// The names of the regex: its name, then its alternative names (`get_names()`).
    pub fn names(&self) -> impl Iterator<Item = &str> {
        std::iter::once(self.name.as_str()).chain(self.alternative_names.iter().map(String::as_str))
    }

    /// The entry as a JSON object, like the "Regex Pattern" of a match in `--json` output.
    pub fn to_json_value(&self) -> &Map<String, Value> {
        &self.json
    }
}

/// The regexes of the database, in its order.
pub fn regexes() -> &'static [RegexEntry] {
    static DATABASE: OnceLock<Vec<RegexEntry>> = OnceLock::new();
    DATABASE.get_or_init(|| load(REGEX_JSON).expect("pywhat/Data/regex.json is valid"))
}

/// The tags of the regexes (`AvailableTags().get_tags()`), sorted.
pub fn tags() -> Vec<&'static str> {
    let mut tags: Vec<&str> = regexes()
        .iter()
        .flat_map(|entry| entry.tags.iter().map(String::as_str))
        .collect();
    tags.sort_unstable();
    tags.dedup();
    tags
}

pub(crate) fn load(text: &str) -> Result<Vec<RegexEntry>, String> {
    let raw: Vec<Map<String, Value>> =
        serde_json::from_str(text).map_err(|error| format!("regex.json: {error}"))?;
    raw.into_iter()
        .enumerate()
        .map(|(index, entry)| load_entry(index, entry))
        .collect()
}

fn load_entry(index: usize, mut json: Map<String, Value>) -> Result<RegexEntry, String> {
    let name = json
        .get("Name")
        .and_then(Value::as_str)
        .ok_or_else(|| format!("entry {index} has no Name"))?
        .to_string();
    let regex = match json.get("Regex") {
        Some(Value::String(regex)) => regex.clone(),
        Some(Value::Array(patterns)) => {
            let patterns: Vec<&str> = patterns
                .iter()
                .map(|pattern| {
                    pattern
                        .as_str()
                        .ok_or_else(|| format!("{name}: a Regex is not a string"))
                })
                .collect::<Result<_, _>>()?;
            join_regexes(&patterns).map_err(|error| format!("{name}: {error}"))?
        }
        _ => return Err(format!("{name}: no Regex")),
    };
    json.insert("Regex".to_string(), Value::String(regex.clone()));
    if let Some(Value::Object(examples)) = json.get_mut("Examples") {
        for values in examples.values_mut() {
            if let Value::Array(values) = values {
                for value in values.iter_mut() {
                    if let Value::Array(parts) = value {
                        let joined: String = parts.iter().filter_map(Value::as_str).collect();
                        *value = Value::String(joined);
                    }
                }
            }
        }
    }
    let boundaryless_regex = boundaryless(&regex);
    // shift_remove keeps the order of the other keys, like Python's dict.pop()
    let children = match json.shift_remove("Children") {
        Some(Value::Object(children)) => Some(load_children(&name, children)?),
        Some(_) => return Err(format!("{name}: Children is not an object")),
        None => None,
    };
    json.insert(
        "Boundaryless Regex".to_string(),
        Value::String(boundaryless_regex.clone()),
    );
    let strings = |key: &str| -> Vec<String> {
        match json.get(key) {
            Some(Value::Array(values)) => values
                .iter()
                .filter_map(|value| value.as_str().map(str::to_string))
                .collect(),
            _ => Vec::new(),
        }
    };
    let optional = |key: &str| json.get(key).and_then(Value::as_str).map(str::to_string);
    let examples = |kind: &str| -> Vec<String> {
        json.get("Examples")
            .and_then(|examples| examples.get(kind))
            .and_then(Value::as_array)
            .map(|values| {
                values
                    .iter()
                    .filter_map(|v| v.as_str().map(str::to_string))
                    .collect()
            })
            .unwrap_or_default()
    };
    Ok(RegexEntry {
        index,
        alternative_names: strings("Alternative Names"),
        plural_name: json
            .get("plural_name")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        description: optional("Description"),
        rarity: json
            .get("Rarity")
            .and_then(Value::as_f64)
            .ok_or_else(|| format!("{name}: no Rarity"))?,
        url: optional("URL"),
        tags: strings("Tags"),
        exploit: optional("Exploit"),
        valid_examples: examples("Valid"),
        invalid_examples: examples("Invalid"),
        name,
        regex,
        boundaryless_regex,
        children,
        json,
    })
}

fn load_children(name: &str, children: Map<String, Value>) -> Result<Children, String> {
    let method = match children.get("method").and_then(Value::as_str) {
        Some("hashmap") => ChildrenMethod::Hashmap,
        Some("regex") => ChildrenMethod::Regex,
        Some("startswith") => ChildrenMethod::StartsWith,
        other => return Err(format!("{name}: unknown Children method {other:?}")),
    };
    let items = match children.get("path").and_then(Value::as_str) {
        Some(path) => ItemsSource::File(
            data_file(path).ok_or_else(|| format!("{name}: {path} is not embedded"))?,
        ),
        None => match children.get("Items") {
            Some(Value::Object(items)) => ItemsSource::Inline(items.clone()),
            _ => return Err(format!("{name}: Children without Items or path")),
        },
    };
    Ok(Children {
        method,
        entry: children
            .get("entry")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_string(),
        deletion_pattern: children
            .get("deletion_pattern")
            .and_then(Value::as_str)
            .map(str::to_string),
        items,
        loaded: OnceLock::new(),
    })
}

/// Joins a list of regexes in the `^(regex)$` format into one, like
/// `pywhat.helper.join_regexes()`: `["^(a)$", "^(b)$"]` becomes `^(?:(a)|(b))$`.
pub(crate) fn join_regexes(patterns: &[&str]) -> Result<String, String> {
    let case_insensitive: Vec<bool> = patterns.iter().map(|p| p.starts_with("(?i)")).collect();
    let all_insensitive = case_insensitive.iter().all(|&yes| yes);
    let mut bodies = Vec::new();
    for (pattern, &ignore_case) in patterns.iter().zip(&case_insensitive) {
        let body = if ignore_case { &pattern[4..] } else { pattern };
        if !(body.starts_with('^') && body.ends_with('$')) || body.len() < 2 {
            return Err(format!("Regex {pattern:?} is not in the ^(regex)$ format"));
        }
        let body = &body[1..body.len() - 1];
        bodies.push(if ignore_case && !all_insensitive {
            format!("(?i:{body})")
        } else {
            body.to_string()
        });
    }
    let prefix = if all_insensitive { "(?i)" } else { "" };
    Ok(format!("{prefix}^(?:{})$", bodies.join("|")))
}

/// The boundaryless form of a regex, like `load_regexes()` derives it with
/// `re.sub(r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])", "", regex)` and the same for `$`: every `^`
/// (then every `$`) that is not preceded by a backslash and is not followed by an
/// unescaped `]` before any other bracket, i.e. that isn't inside a character class.
pub(crate) fn boundaryless(regex: &str) -> String {
    remove_boundary(&remove_boundary(regex, '^'), '$')
}

fn remove_boundary(text: &str, anchor: char) -> String {
    let chars: Vec<char> = text.chars().collect();
    let mut out = String::with_capacity(text.len());
    for (i, &c) in chars.iter().enumerate() {
        if c == anchor && !(i > 0 && chars[i - 1] == '\\') && !closes_class(&chars, i + 1) {
            continue;
        }
        out.push(c);
    }
    out
}

/// Whether `(?![^\[\]]*(?<!\\)\])` fails at `start`: the first bracket from there is a `]`
/// that isn't preceded by a backslash.
fn closes_class(chars: &[char], start: usize) -> bool {
    match chars[start..].iter().position(|&c| c == '[' || c == ']') {
        Some(offset) => {
            let at = start + offset;
            chars[at] == ']' && !(at > 0 && chars[at - 1] == '\\')
        }
        None => false,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn join_regexes_like_python() {
        // tests/test_regex_database.py::test_join_regexes
        assert_eq!(join_regexes(&["^(a)$"]).unwrap(), "^(?:(a))$");
        assert_eq!(
            join_regexes(&["^(a)$", "^(b|c)$"]).unwrap(),
            "^(?:(a)|(b|c))$"
        );
        assert_eq!(
            join_regexes(&["(?i)^(a)$", "(?i)^(b)$"]).unwrap(),
            "(?i)^(?:(a)|(b))$"
        );
        assert_eq!(
            join_regexes(&["(?i)^(a)$", "^(B)$"]).unwrap(),
            "^(?:(?i:(a))|(B))$"
        );
        assert!(join_regexes(&["^(a)$", "(b)"]).is_err());
    }

    #[test]
    fn boundaryless_equals_the_python_substitution() {
        // The two substitutions of load_regexes(), run with fancy-regex
        let caret = fancy_regex::Regex::new(r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])").unwrap();
        let dollar = fancy_regex::Regex::new(r"(?<!\\)\$(?![^\[\]]*(?<!\\)\])").unwrap();
        let python = |regex: &str| {
            let without_carets = caret.replace_all(regex, "").to_string();
            dollar.replace_all(&without_carets, "").to_string()
        };
        let mut checked = 0;
        for entry in regexes() {
            assert_eq!(
                entry.boundaryless_regex,
                python(&entry.regex),
                "{}",
                entry.name
            );
            checked += 1;
        }
        for regex in [
            r"^(a[^b]c)$",
            r"^([\^$]\$)$",
            r"^(a\]^)$",
            r"x[a\]^]",
            "^$",
            r"\\^",
        ] {
            assert_eq!(boundaryless(regex), python(regex), "{regex}");
        }
        assert!(checked > 100);
    }

    #[test]
    fn every_children_path_is_embedded() {
        for entry in regexes() {
            if let Some(children) = &entry.children {
                if !cfg!(feature = "mac-vendors") && entry.name.starts_with("EUI-48") {
                    continue;
                }
                assert!(!children.items().entries.is_empty(), "{}", entry.name);
            }
        }
    }

    #[test]
    fn regex_pattern_keys_are_in_python_order() {
        let entry = regexes()
            .iter()
            .find(|entry| entry.name == "Phone Number")
            .unwrap();
        let keys: Vec<&str> = entry.json.keys().map(String::as_str).collect();
        assert_eq!(keys.last(), Some(&"Boundaryless Regex"));
        assert!(!keys.contains(&"Children"));
    }
}
