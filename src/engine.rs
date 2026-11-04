//! The matching engine: Python `re.finditer(regex, text, re.MULTILINE)` semantics on Rust
//! regex engines.
//!
//! Every pattern is compiled with the `regex` crate if it can be. The patterns it can't
//! compile use look-arounds or back-references, and are compiled in one of two ways:
//!
//! * **Guarded**: look-arounds that only check one character next to the match, or whether
//!   the rest of the line contains some character, are removed. The `regex` crate runs the
//!   rest, and every match is checked against the look-arounds. A match whose check fails is
//!   searched again from the next character, which is what a backtracking engine does when
//!   a match fails at a position. This is exact when the look-arounds are at the start of the
//!   match, or when they are at the end and every match has the same length in characters.
//! * **Fancy**: everything else runs on `fancy-regex`. If the pattern can't match a line break,
//!   a *line prefilter* finds the lines where the pattern without its look-arounds matches (a
//!   superset of where the pattern matches), and fancy-regex only searches those lines.
//!   Look-arounds still see the whole text, so the matches are the same.

use crate::charclass::CharClass;
use fancy_regex::{Assertion, Expr, LookAround};
use std::sync::OnceLock;

/// fancy-regex's default of 1,000,000 lost Phone Number matches on large texts.
const BACKTRACK_LIMIT: usize = 100_000_000;

/// The longest pattern that gets a line prefilter. Running the superset of a very large
/// pattern costs about as much as fancy-regex's own search for its candidates: on a 4.2 MB
/// text, the 18 KB URL regex took 1.6 s on fancy-regex alone and 2.15 s with the prefilter,
/// while the prefilter made the other eight 5 to 200 times faster (the largest of them,
/// Cron Schedule, is 1.3 KB).
const MAX_PREFILTERED_LEN: usize = 4096;

/// An error from matching: fancy-regex gave up (it backtracked more than its limit).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct MatchError(pub String);

impl std::fmt::Display for MatchError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for MatchError {}

/// Which engine a pattern runs on.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum EngineKind {
    /// The `regex` crate.
    Regex,
    /// The `regex` crate, with the look-arounds checked around every match.
    Guarded,
    /// `fancy-regex`.
    Fancy,
    /// `fancy-regex`, on the lines that a `regex` superset of the pattern matches.
    FancyPrefiltered,
}

/// A look-around checked at the start of a match.
#[derive(Debug, Clone)]
enum LeadingGuard {
    /// `(?<![...])` / `(?<=[...])`: the character before the match is (not) in the class.
    Before { class: CharClass, negated: bool },
    /// `(?=.*[...])` / `(?!.*[...])`: the rest of the line has (no) character of the class.
    LineRest { class: CharClass, negated: bool },
    /// `(?=[...])` / `(?![...])`: the first character of the match is (not) in the class.
    First { class: CharClass, negated: bool },
}

/// A look-around checked at the end of a match: `(?![...])` / `(?=[...])`.
#[derive(Debug, Clone)]
struct TrailingGuard {
    class: CharClass,
    negated: bool,
}

#[derive(Debug)]
enum Kind {
    Plain(regex::Regex),
    Guarded {
        regex: regex::Regex,
        leading: Vec<LeadingGuard>,
        trailing: Vec<TrailingGuard>,
    },
    Fancy {
        regex: Box<fancy_regex::Regex>,
        prefilter: Option<regex::Regex>,
    },
}

/// A compiled pattern.
#[derive(Debug)]
pub(crate) struct Compiled {
    kind: Kind,
}

/// A pattern that must match the whole text (`^(...)$` without multi-line mode), for
/// [`crate::Identifier::identify_whole`]. Creating it only parses the pattern, which gives
/// cheap checks that rule out most texts (their length and first byte). The pattern is
/// compiled when a text passes them, so that a check doesn't compile the many patterns
/// that can't match it: compiling all of them takes about 100 ms.
#[derive(Debug)]
pub(crate) struct Whole {
    pattern: String,
    check: Option<WholeCheck>,
    /// The pattern without its look-arounds, for patterns that run on fancy-regex: it
    /// matches every text that the pattern matches, and is much faster.
    superset: Option<String>,
    compiled_superset: OnceLock<Option<regex::Regex>>,
    compiled: OnceLock<Result<Compiled, String>>,
}

#[derive(Debug)]
struct WholeCheck {
    /// The length in bytes of the texts that can match.
    min_len: usize,
    max_len: Option<usize>,
    /// The bytes that a match can start with.
    first: Box<[bool; 256]>,
}

impl Whole {
    pub(crate) fn new(pattern: &str) -> Whole {
        let parse = |pattern: &str| {
            regex_syntax::ParserBuilder::new()
                .build()
                .parse(pattern)
                .ok()
        };
        let (hir, superset) = match parse(pattern) {
            Some(hir) => (Some(hir), None),
            None => {
                let superset = Expr::parse_tree(pattern)
                    .ok()
                    .filter(|tree| tree.backrefs.is_empty())
                    .and_then(|tree| superset(&tree.expr));
                (superset.as_deref().and_then(parse), superset)
            }
        };
        let check = hir.and_then(|hir| {
            let mut first = Box::new([false; 256]);
            let (nullable, _) = first_bytes(&hir, &mut first);
            let properties = hir.properties();
            (!nullable).then_some(())?;
            Some(WholeCheck {
                min_len: properties.minimum_len()?,
                max_len: properties.maximum_len(),
                first,
            })
        });
        Whole {
            pattern: pattern.to_string(),
            check,
            superset,
            compiled_superset: OnceLock::new(),
            compiled: OnceLock::new(),
        }
    }

    /// Compiles the pattern now, if it hasn't been.
    pub(crate) fn compile(&self) -> Result<&Compiled, String> {
        self.compiled
            .get_or_init(|| Compiled::new(&self.pattern, false))
            .as_ref()
            .map_err(Clone::clone)
    }

    pub(crate) fn engine(&self) -> Result<EngineKind, String> {
        self.compile().map(Compiled::engine)
    }

    /// Whether the pattern matches the whole of `text`.
    pub(crate) fn is_match(&self, text: &str) -> Result<bool, MatchError> {
        if let Some(check) = &self.check {
            if text.len() < check.min_len
                || check.max_len.is_some_and(|max| text.len() > max)
                || text
                    .as_bytes()
                    .first()
                    .is_none_or(|&b| !check.first[usize::from(b)])
            {
                return Ok(false);
            }
        }
        if let Some(superset) = &self.superset {
            let compiled = self
                .compiled_superset
                .get_or_init(|| regex::Regex::new(superset).ok());
            if compiled
                .as_ref()
                .is_some_and(|superset| !superset.is_match(text))
            {
                return Ok(false);
            }
        }
        self.compile().map_err(MatchError)?.is_match(text)
    }
}

/// Adds the first bytes of the matches of `hir` to `first`. Returns whether `hir` can match
/// the empty string (then what follows it can start a match too), and whether it consumed
/// nothing for sure (only assertions).
fn first_bytes(hir: &regex_syntax::hir::Hir, first: &mut [bool; 256]) -> (bool, bool) {
    use regex_syntax::hir::{Class, HirKind};
    match hir.kind() {
        HirKind::Empty | HirKind::Look(_) => (true, true),
        HirKind::Literal(literal) => {
            if let Some(&b) = literal.0.first() {
                first[usize::from(b)] = true;
                (false, false)
            } else {
                (true, true)
            }
        }
        HirKind::Class(Class::Unicode(class)) => {
            for range in class.ranges() {
                let (start, end) = (u32::from(range.start()), u32::from(range.end()));
                // The first bytes of the UTF-8 encodings of start..=end
                for (lo, hi, lead) in [
                    (0x0, 0x7F, None),
                    (0x80, 0x7FF, Some((0xC0u32, 6))),
                    (0x800, 0xFFFF, Some((0xE0, 12))),
                    (0x10000, 0x10FFFF, Some((0xF0, 18))),
                ] {
                    let (a, b) = (start.max(lo), end.min(hi));
                    if a > b {
                        continue;
                    }
                    match lead {
                        None => {
                            for byte in a..=b {
                                first[byte as usize] = true;
                            }
                        }
                        Some((prefix, shift)) => {
                            for byte in (prefix | (a >> shift))..=(prefix | (b >> shift)) {
                                first[byte as usize] = true;
                            }
                        }
                    }
                }
            }
            (class.ranges().is_empty(), false)
        }
        HirKind::Class(Class::Bytes(class)) => {
            for range in class.ranges() {
                for byte in range.start()..=range.end() {
                    first[usize::from(byte)] = true;
                }
            }
            (class.ranges().is_empty(), false)
        }
        HirKind::Repetition(repetition) => {
            let (nullable, _) = first_bytes(&repetition.sub, first);
            (nullable || repetition.min == 0, false)
        }
        HirKind::Capture(capture) => first_bytes(&capture.sub, first),
        HirKind::Concat(parts) => {
            for part in parts {
                let (nullable, _) = first_bytes(part, first);
                if !nullable {
                    return (false, false);
                }
            }
            (true, false)
        }
        HirKind::Alternation(alternatives) => {
            let mut nullable = false;
            for alternative in alternatives {
                nullable |= first_bytes(alternative, first).0;
            }
            (nullable, false)
        }
    }
}

impl Compiled {
    /// Compiles `pattern`. With `multi_line`, `^` and `$` match at line boundaries, as with
    /// `re.MULTILINE`; without, only at the start and end of the text.
    pub(crate) fn new(pattern: &str, multi_line: bool) -> Result<Compiled, String> {
        if let Ok(regex) = regex::RegexBuilder::new(pattern)
            .multi_line(multi_line)
            .build()
        {
            return Ok(Compiled {
                kind: Kind::Plain(regex),
            });
        }
        let flagged = if multi_line {
            format!("(?m){pattern}")
        } else {
            pattern.to_string()
        };
        let tree = Expr::parse_tree(&flagged).map_err(|error| error.to_string())?;
        if let Some(kind) = guarded(&tree.expr) {
            return Ok(Compiled { kind });
        }
        let regex = fancy_regex::RegexBuilder::new(pattern)
            .multi_line(multi_line)
            .backtrack_limit(BACKTRACK_LIMIT)
            .build()
            .map_err(|error| error.to_string())?;
        let prefilter = if tree.backrefs.is_empty()
            && pattern.len() <= MAX_PREFILTERED_LEN
            && !can_match_newline(&tree.expr)
        {
            superset(&tree.expr).and_then(|superset| regex::Regex::new(&superset).ok())
        } else {
            None
        };
        Ok(Compiled {
            kind: Kind::Fancy {
                regex: Box::new(regex),
                prefilter,
            },
        })
    }

    pub(crate) fn engine(&self) -> EngineKind {
        match &self.kind {
            Kind::Plain(_) => EngineKind::Regex,
            Kind::Guarded { .. } => EngineKind::Guarded,
            Kind::Fancy {
                prefilter: None, ..
            } => EngineKind::Fancy,
            Kind::Fancy {
                prefilter: Some(_), ..
            } => EngineKind::FancyPrefiltered,
        }
    }

    /// Calls `found(start, end)` with the byte span of every match, like `re.finditer`.
    pub(crate) fn find_iter(
        &self,
        text: &str,
        found: &mut dyn FnMut(usize, usize),
    ) -> Result<(), MatchError> {
        match &self.kind {
            Kind::Plain(regex) => {
                for m in regex.find_iter(text) {
                    found(m.start(), m.end());
                }
                Ok(())
            }
            Kind::Guarded {
                regex,
                leading,
                trailing,
            } => {
                let mut position = 0;
                while position <= text.len() {
                    let Some(m) = regex.find_at(text, position) else {
                        break;
                    };
                    if passes(text, m.start(), m.end(), leading, trailing) {
                        found(m.start(), m.end());
                        position = if m.end() > m.start() {
                            m.end()
                        } else {
                            next_char(text, m.end())
                        };
                    } else {
                        position = next_char(text, m.start());
                    }
                }
                Ok(())
            }
            Kind::Fancy {
                regex,
                prefilter: None,
            } => {
                for m in regex.find_iter(text) {
                    let m = m.map_err(|error| MatchError(error.to_string()))?;
                    found(m.start(), m.end());
                }
                Ok(())
            }
            Kind::Fancy {
                regex,
                prefilter: Some(prefilter),
            } => {
                let mut position = 0;
                // Lines searched, and lines skipped, so far. When a large share of the lines
                // are candidates, the prefilter only costs time, and fancy-regex searches the
                // rest of the text itself (a match can't contain a line break, so starting at
                // a line gives the same matches).
                let (mut candidates, mut skipped) = (0usize, 0usize);
                while let Some(candidate) = prefilter.find_at(text, position) {
                    let line_start = text[..candidate.start()].rfind('\n').map_or(0, |i| i + 1);
                    if candidates >= 64 && candidates * 4 > skipped {
                        let input =
                            fancy_regex::RegexInput::new(text).range(line_start..text.len());
                        for m in regex.find_iter_input(input) {
                            let m = m.map_err(|error| MatchError(error.to_string()))?;
                            found(m.start(), m.end());
                        }
                        return Ok(());
                    }
                    skipped += text.as_bytes()[position..line_start]
                        .iter()
                        .filter(|&&b| b == b'\n')
                        .count();
                    candidates += 1;
                    let line_end = text[candidate.start()..]
                        .find('\n')
                        .map_or(text.len(), |i| candidate.start() + i);
                    let input = fancy_regex::RegexInput::new(text).range(line_start..line_end);
                    for m in regex.find_iter_input(input) {
                        let m = m.map_err(|error| MatchError(error.to_string()))?;
                        found(m.start(), m.end());
                    }
                    if line_end >= text.len() {
                        break;
                    }
                    position = line_end + 1;
                }
                Ok(())
            }
        }
    }

    /// The span of the first match, if any.
    pub(crate) fn find(&self, text: &str) -> Result<Option<(usize, usize)>, MatchError> {
        match &self.kind {
            Kind::Plain(regex) => Ok(regex.find(text).map(|m| (m.start(), m.end()))),
            Kind::Fancy { regex, .. } => regex
                .find(text)
                .map(|m| m.map(|m| (m.start(), m.end())))
                .map_err(|error| MatchError(error.to_string())),
            Kind::Guarded { .. } => {
                let mut first = None;
                self.find_iter(text, &mut |start, end| {
                    if first.is_none() {
                        first = Some((start, end));
                    }
                })?;
                Ok(first)
            }
        }
    }

    /// Whether the pattern matches anywhere in `text`.
    pub(crate) fn is_match(&self, text: &str) -> Result<bool, MatchError> {
        match &self.kind {
            Kind::Plain(regex) => Ok(regex.is_match(text)),
            Kind::Fancy { regex, .. } => regex
                .is_match(text)
                .map_err(|error| MatchError(error.to_string())),
            Kind::Guarded { .. } => Ok(self.find(text)?.is_some()),
        }
    }
}

fn next_char(text: &str, position: usize) -> usize {
    position + text[position..].chars().next().map_or(1, char::len_utf8)
}

fn passes(
    text: &str,
    start: usize,
    end: usize,
    leading: &[LeadingGuard],
    trailing: &[TrailingGuard],
) -> bool {
    let before = text[..start].chars().next_back();
    let after = text[end..].chars().next();
    leading.iter().all(|guard| match guard {
        LeadingGuard::Before { class, negated } => {
            before.is_some_and(|c| class.contains(c)) != *negated
        }
        LeadingGuard::First { class, negated } => {
            text[start..]
                .chars()
                .next()
                .is_some_and(|c| class.contains(c))
                != *negated
        }
        LeadingGuard::LineRest { class, negated } => {
            // `.*` stops before the line break, but the class after it can match the break
            let rest = &text[start..];
            let line = &rest[..rest.find('\n').map_or(rest.len(), |i| i + 1)];
            line.chars().any(|c| class.contains(c)) != *negated
        }
    }) && trailing
        .iter()
        .all(|guard| after.is_some_and(|c| guard.class.contains(c)) != guard.negated)
}

/// The class of a look-around body that matches one character, e.g. `[A-Z0-9]`.
fn single_char_class(expr: &Expr) -> Option<CharClass> {
    match expr {
        Expr::Delegate { inner, casei } => CharClass::parse(inner, *casei),
        Expr::Literal { val, casei } if val.chars().count() == 1 => {
            CharClass::parse(&regex_syntax::escape(val), *casei)
        }
        Expr::Group(inner) => single_char_class(inner),
        _ => None,
    }
}

/// The class `X` of a look-ahead body `.*X` (any characters but line breaks, then `X`).
fn line_rest_class(expr: &Expr) -> Option<CharClass> {
    let Expr::Concat(parts) = expr else {
        return None;
    };
    match parts.as_slice() {
        [Expr::Repeat {
            child,
            lo: 0,
            hi: usize::MAX,
            greedy: true,
        }, class]
            if matches!(**child, Expr::Any { newline: false, .. }) =>
        {
            single_char_class(class)
        }
        _ => None,
    }
}

/// The length in characters of every match of `expr`, if they all have the same length.
/// Look-arounds and assertions are zero-width.
fn fixed_length(expr: &Expr) -> Option<usize> {
    match expr {
        Expr::Empty | Expr::Assertion(_) | Expr::LookAround(..) => Some(0),
        Expr::Any { .. } | Expr::Delegate { .. } => Some(1),
        Expr::Literal { val, casei } => {
            // Case folding can map a character to one of another length in UTF-8, but the
            // length in characters stays the same.
            let _ = casei;
            Some(val.chars().count())
        }
        Expr::Concat(parts) => parts.iter().map(fixed_length).sum(),
        Expr::Alt(alternatives) => {
            let mut lengths = alternatives.iter().map(fixed_length);
            let first = lengths.next()??;
            lengths.all(|length| length == Some(first)).then_some(first)
        }
        Expr::Group(inner) => fixed_length(inner),
        Expr::Repeat { child, lo, hi, .. } if lo == hi => fixed_length(child).map(|n| n * lo),
        _ => None,
    }
}

/// The guarded form of a pattern, if its look-arounds can be checked around the matches of
/// the rest of it (see the module docs).
fn guarded(expr: &Expr) -> Option<Kind> {
    // The match is the outermost concatenation (inside groups), with optional ^ and $
    let mut leading = Vec::new();
    let mut trailing = Vec::new();
    let body = match_body(expr)?;
    let parts: &[Expr] = match body {
        Expr::Concat(parts) => parts,
        other => std::slice::from_ref(other),
    };
    let mut first = 0;
    while first < parts.len() {
        let guard = match &parts[first] {
            Expr::LookAround(inner, LookAround::LookBehind | LookAround::LookBehindNeg) => {
                let negated = matches!(
                    &parts[first],
                    Expr::LookAround(_, LookAround::LookBehindNeg)
                );
                LeadingGuard::Before {
                    class: single_char_class(inner)?,
                    negated,
                }
            }
            Expr::LookAround(inner, kind @ (LookAround::LookAhead | LookAround::LookAheadNeg)) => {
                let negated = *kind == LookAround::LookAheadNeg;
                if let Some(class) = line_rest_class(inner) {
                    LeadingGuard::LineRest { class, negated }
                } else {
                    LeadingGuard::First {
                        class: single_char_class(inner)?,
                        negated,
                    }
                }
            }
            _ => break,
        };
        leading.push(guard);
        first += 1;
    }
    let mut last = parts.len();
    while last > first {
        match &parts[last - 1] {
            Expr::LookAround(inner, kind @ (LookAround::LookAhead | LookAround::LookAheadNeg)) => {
                trailing.push(TrailingGuard {
                    class: single_char_class(inner)?,
                    negated: *kind == LookAround::LookAheadNeg,
                });
                last -= 1;
            }
            _ => break,
        }
    }
    if leading.is_empty() && trailing.is_empty() {
        return None;
    }
    let middle = Expr::Concat(parts[first..last].to_vec());
    if !is_easy(&middle) {
        return None;
    }
    // A check at the end only decides about a match if no other match at the same start
    // could end elsewhere
    if !trailing.is_empty() && fixed_length(&middle).is_none() {
        return None;
    }
    let stripped = replace_match_body(expr, middle)?;
    let mut pattern = String::new();
    stripped.to_str(&mut pattern, 0);
    let regex = regex::Regex::new(&pattern).ok()?;
    Some(Kind::Guarded {
        regex,
        leading,
        trailing,
    })
}

/// The part of a pattern that is the match: inside `^(...)$`, `(...)` or `^(?:(...))$`.
fn match_body(expr: &Expr) -> Option<&Expr> {
    match expr {
        Expr::Concat(parts) => {
            let inner: Vec<&Expr> = parts
                .iter()
                .filter(|part| !is_line_or_text_anchor(part))
                .collect();
            match inner.as_slice() {
                [only] if parts.len() > 1 => match_body(only),
                _ => Some(expr),
            }
        }
        Expr::Group(inner) => match_body(inner),
        _ => Some(expr),
    }
}

/// `expr` with its match body (see [`match_body`]) replaced by `body`.
fn replace_match_body(expr: &Expr, body: Expr) -> Option<Expr> {
    match expr {
        Expr::Concat(parts) => {
            let inner: Vec<usize> = (0..parts.len())
                .filter(|&i| !is_line_or_text_anchor(&parts[i]))
                .collect();
            match inner.as_slice() {
                [only] if parts.len() > 1 => {
                    let mut parts = parts.clone();
                    parts[*only] = replace_match_body(&parts[*only], body)?;
                    Some(Expr::Concat(parts))
                }
                _ => Some(body),
            }
        }
        Expr::Group(inner) => Some(Expr::Group(std::sync::Arc::new(replace_match_body(
            inner, body,
        )?))),
        _ => Some(body),
    }
}

fn is_line_or_text_anchor(expr: &Expr) -> bool {
    matches!(
        expr,
        Expr::Assertion(
            Assertion::StartText
                | Assertion::EndText
                | Assertion::StartLine { .. }
                | Assertion::EndLine { .. }
        )
    )
}

/// Whether the `regex` crate can run `expr` (as `Expr::to_str` writes it).
fn is_easy(expr: &Expr) -> bool {
    let leaf_ok = |e: &Expr| match e {
        Expr::Empty | Expr::Any { .. } | Expr::Literal { .. } | Expr::Delegate { .. } => true,
        Expr::Assertion(assertion) => !matches!(
            assertion,
            Assertion::EndTextIgnoreTrailingNewlines { .. }
                | Assertion::LeftWordHalfBoundary
                | Assertion::RightWordHalfBoundary
        ),
        Expr::Concat(_) | Expr::Alt(_) | Expr::Group(_) | Expr::Repeat { .. } => true,
        _ => false,
    };
    leaf_ok(expr) && !expr.has_descendant(|e| !leaf_ok(e))
}

/// Whether a match of `expr` can contain a line break. Look-arounds don't count: they don't
/// consume, and with a [`fancy_regex::RegexInput`] range they still see the whole text.
fn can_match_newline(expr: &Expr) -> bool {
    match expr {
        Expr::LookAround(..) => false,
        Expr::Any { newline, .. } => *newline,
        Expr::GeneralNewline { .. } => true,
        Expr::Literal { val, .. } => val.contains('\n'),
        Expr::LiteralBytes { bytes } => bytes.contains(&b'\n'),
        Expr::Delegate { inner, casei } => {
            CharClass::parse(inner, *casei).is_none_or(|class| class.contains('\n'))
        }
        Expr::Backref { .. } | Expr::BackrefWithRelativeRecursionLevel { .. } => true,
        _ => expr.children_iter().any(can_match_newline),
    }
}

/// A pattern for the `regex` crate that matches wherever `expr` does: `expr` without its
/// look-arounds and `\Z`.
fn superset(expr: &Expr) -> Option<String> {
    let mut relaxed = expr.clone();
    relax(&mut relaxed);
    if !is_easy(&relaxed) {
        return None;
    }
    let mut pattern = String::new();
    relaxed.to_str(&mut pattern, 0);
    Some(pattern)
}

fn relax(expr: &mut Expr) {
    match expr {
        Expr::LookAround(..) | Expr::Assertion(Assertion::EndTextIgnoreTrailingNewlines { .. }) => {
            *expr = Expr::Empty;
        }
        _ => {
            for child in expr.children_iter_mut() {
                relax(child);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn spans(compiled: &Compiled, text: &str) -> Vec<(usize, usize)> {
        let mut out = Vec::new();
        compiled
            .find_iter(text, &mut |start, end| out.push((start, end)))
            .unwrap();
        out
    }

    fn fancy_spans(pattern: &str, text: &str) -> Vec<(usize, usize)> {
        let regex = fancy_regex::RegexBuilder::new(pattern)
            .multi_line(true)
            .backtrack_limit(BACKTRACK_LIMIT)
            .build()
            .unwrap();
        regex
            .find_iter(text)
            .map(|m| {
                let m = m.unwrap();
                (m.start(), m.end())
            })
            .collect()
    }

    #[test]
    fn guards_equal_fancy_regex() {
        let cases = [
            // The class of a rest-of-line look-ahead can match the line break itself
            (r"((?=.*\s)[a-z]{3})", "abc\nxyz w"),
            (r"((?!.*\s)[a-z]{3})", "abc\nxyz"),
            (r"((?=.*[^a])[a-z]{3})", "aaa\nbbb"),
            (r"((?=.*\W)[a-z]{3})", "abc\n"),
            (r"((?<![A-Z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9]))", "xAKIAABCDEFGHIJKLMNOP AKIAABCDEFGHIJKLMNOP AKIAABCDEFGHIJKLMNOPQ AKIAABCDEFGHIJKLMNOP"),
            (r"((?<![A-Za-z0-9+\/])rO0AB[A-Za-z0-9+\/]{10,}={0,2})", "a rO0ABAAAAAAAAAAAA= xrO0ABAAAAAAAAAAAA=\nrO0ABBBBBBBBBBBBB"),
            (r"((?=.*[A-Z])(?=.*[a-z])[0-9A-Za-z_-]{10}[048AEIMQUYcgkosw]{1})", "dQw4w9WgXcQ 0123456789A abcdefghijk\nABCDEFGHIJ4 xABCDEFGHIJ4"),
        ];
        // Fake keys are written in parts, so that secret scanners don't take them for keys
        let picatic = format!("sk_{}_{}", "live", "0123456789abcdef0123456789abcdef");
        let picatic_text = format!("{picatic}\n{picatic}g");
        let cases = cases.iter().copied().chain([(
            r"(?i)^(sk_(?:live|test)_[0-9a-z]{32}(?![0-9a-z]))$",
            picatic_text.as_str(),
        )]);
        for (pattern, text) in cases {
            let compiled = Compiled::new(pattern, true).unwrap();
            assert_eq!(compiled.engine(), EngineKind::Guarded, "{pattern}");
            assert_eq!(
                spans(&compiled, text),
                fancy_spans(pattern, text),
                "{pattern}"
            );
        }
    }

    #[test]
    fn variable_length_with_trailing_lookahead_is_not_guarded() {
        // (?![0-9]) after a variable-length body: a shorter match could pass the check
        let compiled = Compiled::new(r"((?<![0-9])[0-9]{2,4}(?![0-9]))", true).unwrap();
        assert_ne!(compiled.engine(), EngineKind::Guarded);
    }

    #[test]
    fn prefilter_equals_fancy_regex() {
        let pattern = r"((?<![0-9.])(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\/(?:3[0-2]|[12][0-9]|[0-9])(?![0-9]))";
        let compiled = Compiled::new(pattern, true).unwrap();
        assert_eq!(compiled.engine(), EngineKind::FancyPrefiltered);
        let text = "10.0.0.0/8 x\n1.10.0.0.0/8\nnothing here\n192.168.1.0/24 and 192.168.1.0/245\n0.0.0.0/0";
        assert_eq!(spans(&compiled, text), fancy_spans(pattern, text));
    }

    #[test]
    fn lookarounds_see_across_lines_with_the_prefilter() {
        // The look-arounds at the edges of a candidate line see the text around the line
        for pattern in [
            r"((?<!\n)[0-9]{2,4}(?![0-9]))",
            r"((?<![0-9])[0-9]{2,4}(?!\n))",
        ] {
            let compiled = Compiled::new(pattern, true).unwrap();
            assert_eq!(compiled.engine(), EngineKind::FancyPrefiltered, "{pattern}");
            for text in ["12\n34", "x12\n34x", "1234\n\n56", "12 34\n"] {
                assert_eq!(
                    spans(&compiled, text),
                    fancy_spans(pattern, text),
                    "{pattern} {text:?}"
                );
            }
        }
    }

    #[test]
    fn the_prefilter_hands_dense_text_to_fancy_regex() {
        // Over 64 candidate lines, and most lines candidates: fancy-regex searches the rest
        // from the start of the next candidate line
        let pattern = r"((?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}\/[0-9]{1,2}(?![0-9]))";
        let compiled = Compiled::new(pattern, true).unwrap();
        assert_eq!(compiled.engine(), EngineKind::FancyPrefiltered);
        let mut text = String::new();
        for i in 0..200 {
            text.push_str(&format!("x 10.0.{}.0/{} y 1.2.3.4/56\n", i % 256, i % 33));
            if i % 7 == 0 {
                text.push_str("no address here\n");
            }
        }
        assert_eq!(spans(&compiled, &text), fancy_spans(pattern, &text));
    }

    #[test]
    fn back_references_run_on_fancy_regex() {
        let compiled = Compiled::new(r"^([0-9])(-)?[0-9]\2$", true).unwrap();
        assert_eq!(compiled.engine(), EngineKind::Fancy);
        // Like Python, a back-reference to a group that did not take part fails
        assert_eq!(spans(&compiled, "1-2-\n12\n1-2"), vec![(0, 4)]);
    }
}
