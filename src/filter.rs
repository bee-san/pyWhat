//! Which regexes to search for: a port of `pywhat/filter.py`.

use crate::data::{regexes, RegexEntry};
use std::collections::BTreeSet;

/// A filter or a name in it isn't a tag or a name of a regex (`InvalidTag` in Python).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct InvalidTag(pub String);

impl std::fmt::Display for InvalidTag {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(
            f,
            "Passed filter contains tags or names that are not used by 'what': {}",
            self.0
        )
    }
}

impl std::error::Error for InvalidTag {}

/// A set of tags and names that compares case-insensitively (`CaseInsensitiveSet`).
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub(crate) struct Labels(BTreeSet<String>);

impl Labels {
    pub(crate) fn new<I: IntoIterator<Item = S>, S: AsRef<str>>(values: I) -> Labels {
        Labels(
            values
                .into_iter()
                .map(|v| v.as_ref().to_lowercase())
                .collect(),
        )
    }

    pub(crate) fn contains(&self, value: &str) -> bool {
        self.0.contains(&value.to_lowercase())
    }

    fn is_disjoint<'a>(&self, values: impl IntoIterator<Item = &'a str>) -> bool {
        !values.into_iter().any(|value| self.contains(value))
    }

    fn union(&self, other: &Labels) -> Labels {
        Labels(self.0.union(&other.0).cloned().collect())
    }

    pub(crate) fn iter(&self) -> impl Iterator<Item = &str> {
        self.0.iter().map(String::as_str)
    }

    pub(crate) fn is_empty(&self) -> bool {
        self.0.is_empty()
    }
}

/// What selects regexes: tags or names to include and to exclude, and a rarity range.
///
/// Like `pywhat.Filter`: `Filter::default()` has every tag, no excluded tags and rarities
/// 0.1 to 1. Tags and names compare case-insensitively.
#[derive(Debug, Clone, PartialEq)]
pub struct Filter {
    /// The tags and names to include; `None` for every tag (the default).
    pub(crate) tags: Option<Labels>,
    pub(crate) exclude_tags: Labels,
    pub(crate) min_rarity: f64,
    pub(crate) max_rarity: f64,
}

impl Default for Filter {
    fn default() -> Self {
        Filter {
            tags: None,
            exclude_tags: Labels::default(),
            min_rarity: 0.1,
            max_rarity: 1.0,
        }
    }
}

/// The tags and names of a regex: what selects it in a filter.
fn labels(entry: &RegexEntry) -> impl Iterator<Item = &str> {
    entry.tags.iter().map(String::as_str).chain(entry.names())
}

/// Whether `value` is a tag or a name of a regex, whatever its case.
fn known(value: &str) -> bool {
    let value = value.to_lowercase();
    regexes()
        .iter()
        .any(|entry| labels(entry).any(|label| label.to_lowercase() == value))
}

impl Filter {
    /// A filter, checking that its tags and names exist (`Filter(filters_dict)`).
    /// `tags: None` means every tag.
    pub fn new<S: AsRef<str>>(
        tags: Option<&[S]>,
        exclude_tags: &[S],
        min_rarity: f64,
        max_rarity: f64,
    ) -> Result<Filter, InvalidTag> {
        let tags = tags.map(|tags| Labels::new(tags.iter().map(AsRef::as_ref)));
        let exclude_tags = Labels::new(exclude_tags.iter().map(AsRef::as_ref));
        for value in tags
            .iter()
            .flat_map(Labels::iter)
            .chain(exclude_tags.iter())
        {
            if !known(value) {
                return Err(InvalidTag(value.to_string()));
            }
        }
        Ok(Filter {
            tags,
            exclude_tags,
            min_rarity,
            max_rarity,
        })
    }

    /// A filter that no regex is in, `Filter({"Tags": []})`: the default for boundaryless
    /// mode, which turns it off.
    pub fn none() -> Filter {
        Filter {
            tags: Some(Labels::default()),
            ..Filter::default()
        }
    }

    pub fn min_rarity(&self) -> f64 {
        self.min_rarity
    }

    pub fn max_rarity(&self) -> f64 {
        self.max_rarity
    }

    /// Sets the minimum rarity.
    pub fn with_min_rarity(mut self, rarity: f64) -> Filter {
        self.min_rarity = rarity;
        self
    }

    /// Sets the maximum rarity.
    pub fn with_max_rarity(mut self, rarity: f64) -> Filter {
        self.max_rarity = rarity;
        self
    }

    /// Whether a regex is in the filter (`regex in filter`).
    pub fn contains(&self, entry: &RegexEntry) -> bool {
        self.contains_with(entry, entry.rarity, &entry.tags)
    }

    /// Whether a regex with the given (possibly processed) rarity and tags is in the filter.
    pub(crate) fn contains_with(&self, entry: &RegexEntry, rarity: f64, tags: &[String]) -> bool {
        if !(self.min_rarity <= rarity && rarity <= self.max_rarity) {
            return false;
        }
        let labels = || tags.iter().map(String::as_str).chain(entry.names());
        let included = match &self.tags {
            // Every tag: every regex that has a tag
            None => !tags.is_empty(),
            Some(included) => !included.is_disjoint(labels()),
        };
        included && (self.exclude_tags.is_empty() || self.exclude_tags.is_disjoint(labels()))
    }

    /// The included tags and names, every tag if the filter has none of its own.
    fn included(&self) -> Labels {
        match &self.tags {
            Some(tags) => tags.clone(),
            None => Labels::new(crate::data::tags()),
        }
    }

    /// The regexes in the filter, in database order (`Distribution(filter).get_regexes()`).
    pub fn regexes(&self) -> Vec<&'static RegexEntry> {
        regexes()
            .iter()
            .filter(|entry| self.contains(entry))
            .collect()
    }

    /// `self & other`: the regexes in both filters.
    pub fn and(&self, other: &Filter) -> Filter {
        Filter {
            tags: Some(intersection(&self.included(), &other.included())),
            exclude_tags: intersection(&self.exclude_tags, &other.exclude_tags),
            min_rarity: self.min_rarity.max(other.min_rarity),
            max_rarity: self.max_rarity.min(other.max_rarity),
        }
    }

    /// `self | other`: the regexes in either filter.
    pub fn or(&self, other: &Filter) -> Filter {
        Filter {
            tags: Some(self.included().union(&other.included())),
            exclude_tags: self.exclude_tags.union(&other.exclude_tags),
            min_rarity: self.min_rarity.min(other.min_rarity),
            max_rarity: self.max_rarity.max(other.max_rarity),
        }
    }
}

/// `_intersection()`: the tags and names in both. A name that isn't a tag is in both if the
/// other one has a tag or name of its regex too.
fn intersection(first: &Labels, second: &Labels) -> Labels {
    let tags = Labels::new(crate::data::tags());
    let mut shared: Vec<String> = first
        .iter()
        .filter(|value| second.contains(value))
        .map(str::to_string)
        .collect();
    for entry in regexes() {
        for name in entry.names() {
            if !tags.contains(name)
                && ((first.contains(name) && !second.is_disjoint(labels(entry)))
                    || (second.contains(name) && !first.is_disjoint(labels(entry))))
            {
                shared.push(name.to_string());
            }
        }
    }
    Labels::new(shared)
}

/// Splits a comma separated list of tags and names, except at commas in parentheses
/// (`split_tags()`), so that names like "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)"
/// can be in the list.
pub fn split_tags(text: &str) -> Vec<String> {
    let mut parts = Vec::new();
    let mut depth = 0usize;
    let mut start = 0;
    for (index, c) in text.char_indices() {
        match c {
            '(' => depth += 1,
            ')' if depth > 0 => depth -= 1,
            ',' if depth == 0 => {
                parts.push(text[start..index].to_string());
                start = index + 1;
            }
            _ => {}
        }
    }
    parts.push(text[start..].to_string());
    parts
}

#[cfg(test)]
mod tests {
    use super::*;

    fn names(filter: &Filter) -> Vec<&'static str> {
        filter
            .regexes()
            .iter()
            .map(|entry| entry.name.as_str())
            .collect()
    }

    #[test]
    fn default_filter() {
        let all = names(&Filter::default());
        assert!(all.contains(&"Uniform Resource Locator (URL)"));
        assert!(!all.contains(&"YouTube Video ID"), "rarity 0");
        assert!(names(&Filter::none()).is_empty());
    }

    #[test]
    fn tags_and_names_are_case_insensitive() {
        let filter = Filter::new(Some(&["btc wallet", "ETH WALLET"]), &[], 0.0, 1.0).unwrap();
        assert_eq!(
            names(&filter),
            vec![
                "Bitcoin (₿) Wallet Address",
                "Ethereum (ETH) Wallet Address"
            ]
        );
        assert!(Filter::new(Some(&["no such tag"]), &[], 0.0, 1.0).is_err());
    }

    #[test]
    fn intersection_keeps_names_in_tags() {
        let finance = Filter::new(Some(&["Finance"]), &[], 0.0, 1.0).unwrap();
        let btc = Filter::new(Some(&["BTC Wallet"]), &[], 0.0, 1.0).unwrap();
        assert_eq!(
            names(&finance.and(&btc)),
            vec!["Bitcoin (₿) Wallet Address"]
        );
    }

    #[test]
    fn split_tags_keeps_parentheses() {
        assert_eq!(
            split_tags("a,EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc),b"),
            vec![
                "a",
                "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)",
                "b"
            ]
        );
        assert_eq!(split_tags(""), vec![""]);
    }
}
