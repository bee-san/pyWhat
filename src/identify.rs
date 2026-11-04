//! Identification of text: a port of `RegexIdentifier.iter_check()` and of the parts of
//! `Identifier` that work on text.

use crate::data::{regexes, ChildrenMethod, RegexEntry};
use crate::engine::{Compiled, EngineKind, MatchError, Whole};
use crate::filter::Filter;
use crate::processors::{default_processors, Processor};
use serde_json::Value;
use std::sync::{Arc, OnceLock};

/// Something that a regex found.
#[derive(Debug, Clone)]
pub struct Match {
    /// The matched text, without control characters.
    pub matched: String,
    /// The regex that found it.
    pub regex: &'static RegexEntry,
    /// The description: the regex's, or what `Children` or a processor made of it.
    pub description: Option<String>,
    /// The regex's exploit, with its `..._HERE` placeholders replaced by the match.
    pub exploit: Option<String>,
    /// The URL to analyse the match at (the match without spaces is appended to it).
    pub url: Option<String>,
    /// A link that a processor gave the match, used instead of `url` + match.
    pub link: Option<String>,
    /// The rarity (a processor may change it).
    pub rarity: f64,
    /// The tags (a processor may change them).
    pub tags: Vec<String>,
    /// Whether the match is part of a longer word or of a longer match.
    pub fragment: bool,
    /// The byte offsets of the match in the text it was found in.
    pub start: usize,
    pub end: usize,
}

impl Match {
    /// The link to analyse the match in the browser (`printer.get_link()`): the link of a
    /// processor, else the URL of the regex followed by the match without spaces.
    pub fn link(&self) -> Option<String> {
        if let Some(link) = self.link.as_deref().filter(|link| !link.is_empty()) {
            return Some(link.to_string());
        }
        self.url
            .as_deref()
            .filter(|url| !url.is_empty())
            .map(|url| format!("{url}{}", self.matched.replace(' ', "")))
    }

    /// The match as the Python package returns it: `{"Matched": ..., "Regex Pattern": {...},
    /// "Fragment": ...}`. Without `fragment`, there's no "Fragment" key (`--stream`).
    pub fn to_json_value(&self, fragment: bool) -> Value {
        let mut text = String::new();
        self.write_json(&mut text, fragment);
        serde_json::from_str(&text).expect("valid JSON")
    }

    /// Writes the match as `json.dumps()` writes it in Python, see [`Match::to_json_value`].
    pub fn write_json(&self, out: &mut String, fragment: bool) {
        use crate::json::{write_str, write_value};
        let write_text = |out: &mut String, value: &Option<String>| match value {
            Some(text) => write_str(out, text),
            None => out.push_str("null"),
        };
        out.push_str("{\"Matched\": ");
        write_str(out, &self.matched);
        out.push_str(", \"Regex Pattern\": {");
        let pattern = &self.regex.json;
        for (i, (key, value)) in pattern.iter().enumerate() {
            if i > 0 {
                out.push_str(", ");
            }
            write_str(out, key);
            out.push_str(": ");
            match key.as_str() {
                "Description" => write_text(out, &self.description),
                "Exploit" => write_text(out, &self.exploit),
                "URL" => write_text(out, &self.url),
                "Rarity" if self.rarity != self.regex.rarity => {
                    write_value(out, &number(self.rarity))
                }
                "Tags" if self.tags != self.regex.tags => {
                    out.push('[');
                    for (j, tag) in self.tags.iter().enumerate() {
                        if j > 0 {
                            out.push_str(", ");
                        }
                        write_str(out, tag);
                    }
                    out.push(']');
                }
                _ => write_value(out, value),
            }
        }
        // Keys that the regex doesn't have, which children or processors added
        let added = |out: &mut String, key: &str, value: &Option<String>| {
            if !pattern.contains_key(key) && value.is_some() {
                out.push_str(", ");
                write_str(out, key);
                out.push_str(": ");
                write_text(out, value);
            }
        };
        added(out, "Description", &self.description);
        added(out, "URL", &self.url);
        added(out, "Link", &self.link);
        out.push('}');
        if fragment {
            out.push_str(if self.fragment {
                ", \"Fragment\": true"
            } else {
                ", \"Fragment\": false"
            });
        }
        out.push('}');
    }
}

/// What `Identifier.identify()` returns in Python, as JSON: `{"File Signatures": ...,
/// "Regexes": {location: [match, ...]}}`, with `null` for none. `regexes` are the matches of
/// each location, in the order of their first match; `signatures` the file signatures of
/// the files that have one.
pub fn to_identify_json(
    regexes: &[(String, Vec<Match>)],
    signatures: Option<&[(String, Value)]>,
) -> Value {
    let mut text = String::new();
    write_identify_json(&mut text, regexes, signatures);
    serde_json::from_str(&text).expect("valid JSON")
}

/// Writes what [`to_identify_json`] returns, as `json.dumps()` writes it.
pub fn write_identify_json(
    out: &mut String,
    regexes: &[(String, Vec<Match>)],
    signatures: Option<&[(String, Value)]>,
) {
    use crate::json::{write_str, write_value};
    out.push_str("{\"File Signatures\": ");
    match signatures.filter(|signatures| !signatures.is_empty()) {
        Some(signatures) => {
            out.push('{');
            // A location given twice keeps its first place and its last signature
            let mut seen: Vec<&str> = Vec::new();
            for (location, _) in signatures {
                if seen.contains(&location.as_str()) {
                    continue;
                }
                seen.push(location);
                let last = signatures
                    .iter()
                    .rev()
                    .find(|(l, _)| l == location)
                    .map(|(_, s)| s);
                if seen.len() > 1 {
                    out.push_str(", ");
                }
                write_str(out, location);
                out.push_str(": ");
                write_value(out, last.expect("present"));
            }
            out.push('}');
        }
        None => out.push_str("null"),
    }
    out.push_str(", \"Regexes\": ");
    let locations: Vec<&str> = {
        let mut locations: Vec<&str> = Vec::new();
        for (location, matches) in regexes {
            if !matches.is_empty() && !locations.contains(&location.as_str()) {
                locations.push(location);
            }
        }
        locations
    };
    if locations.is_empty() {
        out.push_str("null}");
        return;
    }
    out.push('{');
    for (i, location) in locations.iter().enumerate() {
        if i > 0 {
            out.push_str(", ");
        }
        write_str(out, location);
        out.push_str(": [");
        let mut first = true;
        for (_, matches) in regexes.iter().filter(|(l, _)| l == location) {
            for m in matches {
                if !first {
                    out.push_str(", ");
                }
                first = false;
                m.write_json(out, true);
            }
        }
        out.push(']');
    }
    out.push_str("}}");
}

fn number(value: f64) -> Value {
    if value.fract() == 0.0 && value.abs() < 1e15 {
        Value::from(value as i64)
    } else {
        serde_json::Number::from_f64(value).map_or(Value::Null, Value::Number)
    }
}

/// The compiled forms of a regex, compiled when they are first used.
struct Forms {
    anchored: OnceLock<Result<Compiled, String>>,
    boundaryless: OnceLock<Result<Compiled, String>>,
    whole: OnceLock<Whole>,
    children: OnceLock<Vec<Option<Compiled>>>,
    deletion: OnceLock<Option<regex::Regex>>,
}

fn forms() -> &'static [Forms] {
    static FORMS: OnceLock<Vec<Forms>> = OnceLock::new();
    FORMS.get_or_init(|| {
        regexes()
            .iter()
            .map(|_| Forms {
                anchored: OnceLock::new(),
                boundaryless: OnceLock::new(),
                whole: OnceLock::new(),
                children: OnceLock::new(),
                deletion: OnceLock::new(),
            })
            .collect()
    })
}

/// Which form of a regex to search with.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Form {
    /// `^(...)$` with `^` and `$` at line boundaries, like `re.MULTILINE`.
    Anchored,
    /// Without `^` and `$`.
    Boundaryless,
}

fn compiled(entry: &RegexEntry, form: Form) -> Result<&'static Compiled, String> {
    let forms = &forms()[entry.index];
    let (cell, pattern) = match form {
        Form::Anchored => (&forms.anchored, &entry.regex),
        Form::Boundaryless => (&forms.boundaryless, &entry.boundaryless_regex),
    };
    cell.get_or_init(|| Compiled::new(pattern, true))
        .as_ref()
        .map_err(|error| format!("{}: {error}", entry.name))
}

/// `^(...)$` against the whole text.
fn whole(entry: &RegexEntry) -> &'static Whole {
    forms()[entry.index]
        .whole
        .get_or_init(|| Whole::new(&entry.regex))
}

/// Whether the whole of `text` matches `entry`'s regex.
fn whole_match(entry: &RegexEntry, text: &str) -> bool {
    whole(entry).is_match(text).unwrap_or(false)
}

/// Which engine runs the whole-text form of a regex (for tests and benchmarks).
pub fn whole_engine_of(entry: &RegexEntry) -> Result<EngineKind, String> {
    whole(entry).engine()
}

/// Which engine runs a form of a regex (for tests and benchmarks).
pub fn engine_of(entry: &RegexEntry, boundaryless: bool) -> Result<EngineKind, String> {
    let form = if boundaryless {
        Form::Boundaryless
    } else {
        Form::Anchored
    };
    compiled(entry, form).map(Compiled::engine)
}

/// Compiles the forms of every regex now instead of when they are first used, so that
/// the first identification is as fast as the others. With the `parallel` feature, the
/// regexes are compiled on rayon's thread pool.
pub fn compile_all() {
    let work = |entry: &'static RegexEntry| {
        for form in [Form::Anchored, Form::Boundaryless] {
            let _ = compiled(entry, form);
        }
        let _ = whole(entry).compile();
    };
    #[cfg(feature = "parallel")]
    {
        use rayon::prelude::*;
        regexes().par_iter().for_each(work);
    }
    #[cfg(not(feature = "parallel"))]
    regexes().iter().for_each(work);
}

/// `RegexIdentifier.clean_text()`: the text without control characters (U+0000 to U+001F
/// and U+007F to U+009F).
pub(crate) fn clean_text(text: &str) -> String {
    text.chars()
        .filter(|&c| !matches!(c, '\u{0}'..='\u{1f}' | '\u{7f}'..='\u{9f}'))
        .collect()
}

/// `re.sub(r"[A-Z_]+_HERE", lambda _: matched, exploit)`.
fn fill_exploit(exploit: &str, matched: &str) -> String {
    static PLACEHOLDER: OnceLock<regex::Regex> = OnceLock::new();
    PLACEHOLDER
        .get_or_init(|| regex::Regex::new("[A-Z_]+_HERE").expect("valid regex"))
        .replace_all(exploit, regex::NoExpand(matched))
        .into_owned()
}

/// The description that `Children` give a match, if any of them matches.
fn children_description(entry: &RegexEntry, matched: &str) -> Option<String> {
    let children = entry.children.as_ref()?;
    let items = children.items();
    let deletion = forms()[entry.index].deletion.get_or_init(|| {
        children
            .deletion_pattern
            .as_deref()
            .filter(|pattern| !pattern.is_empty())
            .and_then(|pattern| regex::Regex::new(pattern).ok())
    });
    let processed = match deletion {
        Some(regex) => regex.replace_all(matched, "").into_owned(),
        None => matched.to_string(),
    };
    let mut found: Vec<&str> = Vec::new();
    match children.method {
        ChildrenMethod::Hashmap => {
            for &length in &items.lengths {
                let end = processed
                    .char_indices()
                    .nth(length)
                    .map_or(processed.len(), |(i, _)| i);
                if let Some(&index) = items.by_key.get(&processed[..end]) {
                    found.push(&items.entries[index].1);
                }
            }
        }
        ChildrenMethod::Regex => {
            let compiled = forms()[entry.index].children.get_or_init(|| {
                items
                    .entries
                    .iter()
                    .map(|(pattern, _)| Compiled::new(pattern, true).ok())
                    .collect()
            });
            for ((_, description), regex) in items.entries.iter().zip(compiled) {
                if regex
                    .as_ref()
                    .is_some_and(|regex| regex.is_match(&processed).unwrap_or(false))
                {
                    found.push(description);
                }
            }
        }
        ChildrenMethod::StartsWith => {
            for (prefix, description) in &items.entries {
                if processed.starts_with(prefix.as_str()) {
                    found.push(description);
                }
            }
        }
    }
    (!found.is_empty()).then(|| format!("{}{}", children.entry, found.join(", ")))
}

/// A match as the regex found it, before processing.
fn new_match(entry: &'static RegexEntry, text: &str, start: usize, end: usize) -> Match {
    let matched = clean_text(&text[start..end]);
    let exploit = match entry.exploit.as_deref() {
        Some(exploit) if exploit.contains("curl") => Some(fill_exploit(exploit, &matched)),
        other => other.map(str::to_string),
    };
    let description = children_description(entry, &matched).or_else(|| entry.description.clone());
    Match {
        regex: entry,
        description,
        exploit,
        url: entry.url.clone(),
        link: None,
        rarity: entry.rarity,
        tags: entry.tags.clone(),
        fragment: false,
        start,
        end,
        matched,
    }
}

/// The processors of each regex, in their order (`processors_by_name()`).
pub(crate) fn processors_of<'a>(
    processors: &'a [Arc<dyn Processor>],
    name: &str,
) -> Vec<&'a dyn Processor> {
    processors
        .iter()
        .filter(|processor| processor.names().contains(&name))
        .map(|processor| processor.as_ref())
        .collect()
}

/// `run_processors()`: the processors in order, each on what the one before returned. A
/// match that a processor filtered out, or that is no longer in `dist`, is dropped.
fn run_processors(found: Match, processors: &[&dyn Processor], dist: &Filter) -> Option<Match> {
    let mut found = found;
    for processor in processors {
        found = processor.process(found)?;
    }
    dist.contains_with(found.regex, found.rarity, &found.tags)
        .then_some(found)
}

/// What to search for, and how: the settings of an identification.
pub(crate) struct Search<'a> {
    pub(crate) regexes: &'a [&'static RegexEntry],
    /// For each of `regexes`, whether to search with its boundaryless form.
    pub(crate) boundaryless: &'a [bool],
    pub(crate) processors: &'a [Arc<dyn Processor>],
    pub(crate) dist: &'a Filter,
}

/// The matches of every regex of `search` in `text`, in database order and then in the
/// order of the text, with their fragments marked (`iter_check()` for one string).
pub(crate) fn check(text: &str, search: &Search<'_>) -> Result<Vec<Match>, MatchError> {
    let spans = find_spans(text, search)?;
    let mut found = Vec::new();
    for (entry, entry_spans) in search.regexes.iter().zip(spans) {
        if entry_spans.is_empty() {
            continue;
        }
        let processors = processors_of(search.processors, &entry.name);
        for (start, end) in entry_spans {
            let new = new_match(entry, text, start, end);
            let processed = if processors.is_empty() {
                Some(new)
            } else {
                run_processors(new, &processors, search.dist)
            };
            found.extend(processed);
        }
    }
    mark_fragments(text, &mut found);
    Ok(found)
}

/// The spans of the matches of each regex of `search` in `text`.
fn find_spans(text: &str, search: &Search<'_>) -> Result<Vec<Vec<(usize, usize)>>, MatchError> {
    let spans_of = |(entry, &boundaryless): (&&'static RegexEntry, &bool)| {
        let form = if boundaryless {
            Form::Boundaryless
        } else {
            Form::Anchored
        };
        let compiled = compiled(entry, form).map_err(MatchError)?;
        let mut spans = Vec::new();
        compiled.find_iter(text, &mut |start, end| spans.push((start, end)))?;
        Ok(spans)
    };
    #[cfg(feature = "parallel")]
    if text.len() > 4096 {
        use rayon::prelude::*;
        return search
            .regexes
            .par_iter()
            .zip(search.boundaryless.par_iter())
            .map(spans_of)
            .collect();
    }
    search
        .regexes
        .iter()
        .zip(search.boundaryless.iter())
        .map(spans_of)
        .collect()
}

/// Whether the span of `text` is inside a longer word (`inside_word()`): it starts with a
/// word character right after another one, or ends with one right before another one.
fn inside_word(text: &str, start: usize, end: usize) -> bool {
    use crate::charclass::is_word_character as word;
    if start >= end {
        return false;
    }
    let before = text[..start].chars().next_back();
    let first = text[start..].chars().next();
    let last = text[..end].chars().next_back();
    let after = text[end..].chars().next();
    (before.is_some_and(word) && first.is_some_and(word))
        || (after.is_some_and(word) && last.is_some_and(word))
}

/// Sets `fragment` on the matches found in `text` (`mark_fragments()`): whether a match is
/// inside a longer word or inside a longer match with a rarity above 0.
pub(crate) fn mark_fragments(text: &str, found: &mut [Match]) {
    let mut containers: Vec<(usize, usize)> = found
        .iter()
        .filter(|m| m.rarity > 0.0)
        .map(|m| (m.start, m.end))
        .collect();
    containers.sort_unstable();
    let starts: Vec<usize> = containers.iter().map(|&(start, _)| start).collect();
    // furthest[i] is the furthest end of containers[..=i]
    let mut furthest: Vec<usize> = Vec::with_capacity(containers.len());
    for &(_, end) in &containers {
        let next = furthest.last().map_or(end, |&last: &usize| last.max(end));
        furthest.push(next);
    }
    for m in found.iter_mut() {
        let (start, end) = (m.start, m.end);
        let before = starts.partition_point(|&s| s < start);
        let same_start = starts.partition_point(|&s| s <= start);
        m.fragment = (before > 0 && furthest[before - 1] >= end)
            || (same_start > before && containers[same_start - 1].1 > end)
            || inside_word(text, start, end);
    }
}

/// Identifies text with the regex database, like `pywhat.Identifier`.
///
/// ```
/// let identifier = pywhat::Identifier::default();
/// let found = identifier.identify("https://github.com/bee-san/pyWhat");
/// assert_eq!(found[0].regex.name, "Uniform Resource Locator (URL)");
/// ```
///
/// The builder methods have the names of lemmeknow's, so code that used lemmeknow changes
/// little: `Identifier::default().min_rarity(0.1)`.
#[derive(Clone)]
pub struct Identifier {
    dist: Filter,
    boundaryless: Filter,
    processors: Vec<Arc<dyn Processor>>,
    /// The tags and names given to [`Identifier::include_tags`], if it was called.
    included: Option<crate::filter::Labels>,
    /// The regexes of `dist`, and which of them are searched for in boundaryless mode.
    selected: OnceLock<(Vec<&'static RegexEntry>, Vec<bool>)>,
}

impl Default for Identifier {
    /// Like `Identifier()` in Python: every tag, rarity 0.1 to 1, no boundaryless mode and
    /// the default processors.
    fn default() -> Self {
        Identifier::new(Filter::default(), Filter::none(), default_processors())
    }
}

impl std::fmt::Debug for Identifier {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("Identifier")
            .field("dist", &self.dist)
            .field("boundaryless", &self.boundaryless)
            .field("processors", &self.processors.len())
            .finish()
    }
}

impl Identifier {
    /// An identifier for the regexes of `dist`, searched for in boundaryless mode if they are
    /// in `boundaryless` too, with `processors` (`Identifier(dist=..., boundaryless=...,
    /// processors=...)`).
    pub fn new(dist: Filter, boundaryless: Filter, processors: Vec<Box<dyn Processor>>) -> Self {
        Identifier {
            dist,
            boundaryless,
            processors: processors.into_iter().map(Arc::from).collect(),
            included: None,
            selected: OnceLock::new(),
        }
    }

    fn changed(mut self, change: impl FnOnce(&mut Self)) -> Self {
        change(&mut self);
        self.selected = OnceLock::new();
        self
    }

    /// Only regexes with at least this rarity (lemmeknow's `min_rarity`).
    pub fn min_rarity(self, rarity: f64) -> Self {
        self.changed(|id| id.dist.min_rarity = rarity)
    }

    /// Only regexes with at most this rarity (lemmeknow's `max_rarity`).
    pub fn max_rarity(self, rarity: f64) -> Self {
        self.changed(|id| id.dist.max_rarity = rarity)
    }

    /// Only regexes with at least one of these tags or names, case-insensitively, like
    /// `--include`. Unlike lemmeknow, a regex needs one of the tags, not all of them. Calling
    /// it again adds to the tags. A tag that no regex has selects nothing, like lemmeknow's
    /// (`Filter::new` checks them, like the CLI).
    pub fn include_tags<S: AsRef<str>>(self, tags: &[S]) -> Self {
        let tags = crate::filter::Labels::new(tags.iter().map(AsRef::as_ref));
        self.changed(|id| {
            let included = match id.included.take() {
                Some(included) => included.union_with(&tags),
                None => tags,
            };
            id.dist.tags = Some(included.clone());
            id.included = Some(included);
        })
    }

    /// No regexes with any of these tags or names, case-insensitively, like `--exclude`.
    /// Calling it again adds to the tags.
    pub fn exclude_tags<S: AsRef<str>>(self, tags: &[S]) -> Self {
        let tags = crate::filter::Labels::new(tags.iter().map(AsRef::as_ref));
        self.changed(|id| id.dist.exclude_tags = id.dist.exclude_tags.union_with(&tags))
    }

    /// Search for every regex without its boundaries (`true`), so that matches inside
    /// longer text are found too, or with them (`false`, the default), like lemmeknow's
    /// `boundaryless`. [`Identifier::with_boundaryless_filter`] chooses per regex.
    pub fn boundaryless(self, boundaryless: bool) -> Self {
        let filter = if boundaryless {
            Filter::default().with_min_rarity(0.0)
        } else {
            Filter::none()
        };
        self.changed(|id| id.boundaryless = filter)
    }

    /// The regexes that are searched for without boundaries: those in `filter` (the
    /// CLI uses `--boundaryless-rarity 0.1:1` by default).
    pub fn with_boundaryless_filter(self, filter: Filter) -> Self {
        self.changed(|id| id.boundaryless = filter)
    }

    /// The regexes to search for.
    pub fn with_filter(self, dist: Filter) -> Self {
        self.changed(|id| id.dist = dist)
    }

    /// The processors to run on the matches. `vec![]` turns processing off.
    pub fn with_processors(mut self, processors: Vec<Box<dyn Processor>>) -> Self {
        self.processors = processors.into_iter().map(Arc::from).collect();
        self
    }

    pub fn filter(&self) -> &Filter {
        &self.dist
    }

    pub fn boundaryless_filter(&self) -> &Filter {
        &self.boundaryless
    }

    pub fn processors(&self) -> &[Arc<dyn Processor>] {
        &self.processors
    }

    fn selected(&self) -> &(Vec<&'static RegexEntry>, Vec<bool>) {
        self.selected.get_or_init(|| {
            let regexes = self.dist.regexes();
            let boundaryless = regexes
                .iter()
                .map(|entry| self.boundaryless.contains(entry))
                .collect();
            (regexes, boundaryless)
        })
    }

    pub(crate) fn search(&self) -> Search<'_> {
        let (regexes, boundaryless) = self.selected();
        Search {
            regexes,
            boundaryless,
            processors: &self.processors,
            dist: &self.dist,
        }
    }

    /// Everything found in `text`, like `Identifier().identify(text)["Regexes"]["text"]`:
    /// the matches of each regex in database order, and of a regex in the order of the
    /// text. A regex with boundaries matches whole lines of the text.
    ///
    /// A regex that fancy-regex gives up on (it backtracked more than 100,000,000 times) is
    /// skipped; [`Identifier::try_identify`] returns the error instead.
    pub fn identify(&self, text: &str) -> Vec<Match> {
        let search = self.search();
        match check(text, &search) {
            Ok(found) => found,
            Err(_) => {
                // Skip the regexes that fail, keep the others
                let mut found = Vec::new();
                for (i, entry) in search.regexes.iter().enumerate() {
                    let one = Search {
                        regexes: std::slice::from_ref(entry),
                        boundaryless: &search.boundaryless[i..=i],
                        processors: search.processors,
                        dist: search.dist,
                    };
                    if let Ok(matches) = check(text, &one) {
                        found.extend(matches);
                    }
                }
                mark_fragments(text, &mut found);
                found
            }
        }
    }

    /// Like [`Identifier::identify`], but returns the error of a regex that fancy-regex
    /// gave up on.
    pub fn try_identify(&self, text: &str) -> Result<Vec<Match>, MatchError> {
        check(text, &self.search())
    }

    /// The regexes whose match is the whole of `text`, in database order, after
    /// processing: what `text` *is*, rather than what it contains. `^` and `$` only match at
    /// the start and the end of `text` (lemmeknow's `identify`), and the boundaryless filter
    /// isn't used.
    ///
    /// ```
    /// let identifier = pywhat::Identifier::default();
    /// assert_eq!(identifier.identify_whole("192.168.0.1")[0].regex.name, "Internet Protocol (IP) Address Version 4");
    /// assert!(identifier.identify_whole("IP: 192.168.0.1").is_empty());
    /// assert!(identifier.identify_whole("192.168.0.1\nsomething else").is_empty());
    /// ```
    pub fn identify_whole(&self, text: &str) -> Vec<Match> {
        let (regexes, _) = self.selected();
        let mut found = Vec::new();
        for entry in regexes {
            if !whole_match(entry, text) {
                continue;
            }
            let new = new_match(entry, text, 0, text.len());
            let processors = processors_of(&self.processors, &entry.name);
            let processed = if processors.is_empty() {
                Some(new)
            } else {
                run_processors(new, &processors, &self.dist)
            };
            found.extend(processed);
        }
        found
    }

    /// The first of [`Identifier::identify_whole`], without trying the others.
    pub fn first_whole(&self, text: &str) -> Option<Match> {
        let (regexes, _) = self.selected();
        for entry in regexes {
            if !whole_match(entry, text) {
                continue;
            }
            let new = new_match(entry, text, 0, text.len());
            let processors = processors_of(&self.processors, &entry.name);
            let processed = if processors.is_empty() {
                Some(new)
            } else {
                run_processors(new, &processors, &self.dist)
            };
            if processed.is_some() {
                return processed;
            }
        }
        None
    }

    /// Compiles the regexes that this identifier searches with, so that the first
    /// identification is as fast as the others: with the `parallel` feature, on rayon's
    /// thread pool, which can be done in the background (`rayon::spawn(move ||
    /// identifier.warm_up())`). Without it, regexes are compiled when they are first needed.
    pub fn warm_up(&self) {
        let (regexes, boundaryless) = self.selected();
        let work = |(entry, &boundaryless): (&&'static RegexEntry, &bool)| {
            let _ = compiled(
                entry,
                if boundaryless {
                    Form::Boundaryless
                } else {
                    Form::Anchored
                },
            );
            let _ = whole(entry).compile();
        };
        #[cfg(feature = "parallel")]
        {
            use rayon::prelude::*;
            regexes
                .par_iter()
                .zip(boundaryless.par_iter())
                .for_each(work);
        }
        #[cfg(not(feature = "parallel"))]
        regexes.iter().zip(boundaryless.iter()).for_each(work);
    }
}

impl crate::filter::Labels {
    fn union_with(&self, other: &crate::filter::Labels) -> crate::filter::Labels {
        crate::filter::Labels::new(self.iter().chain(other.iter()))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn identifiers_can_be_shared_between_threads() {
        fn shared<T: Send + Sync + Clone>() {}
        shared::<Identifier>();
    }

    /// A fake GitHub token, in parts so that secret scanners don't take it for one.
    fn github_token() -> String {
        format!("ghp_{}", "0123456789abcdefghijklmnopqrstuvwxyz")
    }

    #[test]
    fn lemmeknow_style_builders() {
        let identifier = Identifier::default()
            .min_rarity(0.0)
            .include_tags(&["Credentials"])
            .exclude_tags(&["AWS"]);
        let names: Vec<String> = identifier
            .identify_whole(&github_token())
            .into_iter()
            .map(|m| m.regex.name.clone())
            .collect();
        assert_eq!(names, ["GitHub Personal Access Token"]);
        let clone = identifier.clone();
        assert_eq!(clone.identify_whole(&github_token()).len(), 1);
        assert!(Identifier::default()
            .include_tags(&["no such tag"])
            .identify_whole(&github_token())
            .is_empty());
    }
}
