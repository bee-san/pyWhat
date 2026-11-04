//! Character classes for the checks that the engine does around matches, such as the
//! guards of look-arounds and whether a character is part of a word.

use regex_syntax::hir::{Class, HirKind};

/// A set of characters, from a regex character class such as `[A-Z0-9]`.
#[derive(Debug, Clone)]
pub(crate) struct CharClass {
    /// Sorted, non-overlapping ranges.
    ranges: Vec<(char, char)>,
}

impl CharClass {
    /// The class of a regex that matches one character: a class such as `[A-Z0-9]` or
    /// `\d`, or a literal character. `case_insensitive` folds its case like `(?i)`.
    pub(crate) fn parse(pattern: &str, case_insensitive: bool) -> Option<CharClass> {
        let hir = regex_syntax::ParserBuilder::new()
            .case_insensitive(case_insensitive)
            .build()
            .parse(pattern)
            .ok()?;
        match hir.kind() {
            HirKind::Class(Class::Unicode(class)) => Some(CharClass {
                ranges: class
                    .ranges()
                    .iter()
                    .map(|r| (r.start(), r.end()))
                    .collect(),
            }),
            HirKind::Literal(literal) => {
                let text = std::str::from_utf8(&literal.0).ok()?;
                let mut chars = text.chars();
                let c = chars.next()?;
                chars.next().is_none().then(|| CharClass {
                    ranges: vec![(c, c)],
                })
            }
            _ => None,
        }
    }

    pub(crate) fn contains(&self, c: char) -> bool {
        self.ranges
            .binary_search_by(|&(start, end)| {
                if end < c {
                    std::cmp::Ordering::Less
                } else if start > c {
                    std::cmp::Ordering::Greater
                } else {
                    std::cmp::Ordering::Equal
                }
            })
            .is_ok()
    }
}

/// Whether `c` is a word character as `pywhat.ranking` sees it: `str.isalnum()` or `_`.
/// `[\p{L}\p{N}_]` equals Python's `isalnum()` for every character of Unicode 15.0, while
/// `char::is_alphanumeric` would also take combining marks and other code points.
pub(crate) fn is_word_character(c: char) -> bool {
    use std::sync::OnceLock;
    static WORD: OnceLock<CharClass> = OnceLock::new();
    if c.is_ascii() {
        return c.is_ascii_alphanumeric() || c == '_';
    }
    WORD.get_or_init(|| CharClass::parse(r"[\p{L}\p{N}_]", false).expect("valid class"))
        .contains(c)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn classes() {
        let class = CharClass::parse("[A-Z0-9]", false).unwrap();
        assert!(class.contains('A') && class.contains('7') && !class.contains('a'));
        let folded = CharClass::parse("[0-9a-z]", true).unwrap();
        assert!(folded.contains('Q') && folded.contains('q'));
        let literal = CharClass::parse(r"\.", false).unwrap();
        assert!(literal.contains('.') && !literal.contains('a'));
        assert!(CharClass::parse("ab", false).is_none());
    }

    #[test]
    fn word_characters() {
        for c in ['a', 'Z', '0', '_', 'é', '٣', '½', '²'] {
            assert!(is_word_character(c), "{c}");
        }
        for c in [' ', '-', '.', '\u{301}', '\n'] {
            assert!(!is_word_character(c), "{c:?}");
        }
    }
}
