//! The module `pywhat._pywhat` of the Python package: the pywhat crate's regex engine.
//!
//! `pywhat.regex_identifier` searches with `finditer(pattern, text)` instead of
//! `re.finditer(pattern, text, re.MULTILINE)`, so the Python API finds what the crate's
//! `Identifier` finds, with the same engines (see `pywhat::engine`).

use pyo3::create_exception;
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyString;
use pywhat::engine::Pattern;
use std::collections::HashMap;
use std::sync::{Arc, LazyLock, Mutex, PoisonError};

create_exception!(
    pywhat._pywhat,
    MatchError,
    PyRuntimeError,
    "fancy-regex gave up on a search: it backtracked more than 100,000,000 times."
);

/// A compiled pattern, or why it can't be compiled.
type Compiled = Result<Arc<Pattern>, String>;

/// The patterns compiled so far, by pattern.
static PATTERNS: LazyLock<Mutex<HashMap<String, Compiled>>> = LazyLock::new(Mutex::default);

/// The most patterns kept compiled. regex.json has about 150 regexes, in two forms each;
/// like Python's `re`, the cache starts over when it is full.
const MAX_PATTERNS: usize = 1024;

fn compile(pattern: &str) -> Compiled {
    let lock = || PATTERNS.lock().unwrap_or_else(PoisonError::into_inner);
    if let Some(compiled) = lock().get(pattern) {
        return compiled.clone();
    }
    // Compiled without the lock: compiling a large pattern takes milliseconds
    let compiled = Pattern::new(pattern).map(Arc::new).map_err(|error| error.0);
    let mut patterns = lock();
    if patterns.len() >= MAX_PATTERNS {
        patterns.clear();
    }
    patterns.insert(pattern.to_owned(), compiled.clone());
    compiled
}

/// Turns byte offsets in `text` into character offsets, which is what Python's `str`
/// indexes by. The spans of a search come in the order of the text, so one pass suffices.
fn to_char_offsets(text: &str, spans: &mut [(usize, usize)]) {
    let (mut byte, mut chars) = (0, 0);
    for (start, end) in spans.iter_mut() {
        for offset in [start, end] {
            if *offset < byte {
                (byte, chars) = (0, 0);
            }
            chars += text[byte..*offset].chars().count();
            byte = *offset;
            *offset = chars;
        }
    }
}

/// A text encoded in UTF-8 for the engine.
struct Utf8 {
    text: Box<str>,
    /// Whether every character is one byte: the offsets of bytes are those of characters.
    ascii: bool,
}

impl Utf8 {
    /// Raises UnicodeEncodeError for lone surrogates, which UTF-8 can't encode.
    fn new(text: &Bound<'_, PyString>) -> PyResult<Utf8> {
        let utf8 = text.to_cow()?;
        Ok(Utf8 {
            ascii: utf8.len() == text.len()?,
            text: utf8.into(),
        })
    }
}

/// A text, encoded once for finditer(): the searches of a text for many patterns don't
/// encode it every time. Raises UnicodeEncodeError if text isn't valid Unicode (lone
/// surrogates).
#[pyclass(frozen, module = "pywhat._pywhat")]
struct Text(Utf8);

#[pymethods]
impl Text {
    #[new]
    fn new(text: &Bound<'_, PyString>) -> PyResult<Text> {
        Utf8::new(text).map(Text)
    }
}

enum Error {
    Pattern(String),
    Match(String),
}

fn search(py: Python<'_>, pattern: &str, text: &Utf8) -> PyResult<Vec<(usize, usize)>> {
    py.detach(|| {
        let compiled = compile(pattern).map_err(Error::Pattern)?;
        let mut spans = Vec::new();
        compiled
            .find_iter(&text.text, |start, end| spans.push((start, end)))
            .map_err(|error| Error::Match(error.0))?;
        if !text.ascii {
            to_char_offsets(&text.text, &mut spans);
        }
        Ok(spans)
    })
    .map_err(|error| match error {
        Error::Pattern(message) => PyValueError::new_err(message),
        Error::Match(message) => MatchError::new_err(message),
    })
}

/// The (start, end) character offsets of every match of pattern in text (a str, or a
/// Text), in order: the spans of re.finditer(pattern, text, re.MULTILINE), found by the
/// pywhat crate's engine.
///
/// Raises ValueError if the engine can't compile pattern, MatchError if it gives up on the
/// search, and UnicodeEncodeError if text isn't valid Unicode (lone surrogates).
#[pyfunction]
fn finditer(
    py: Python<'_>,
    pattern: &Bound<'_, PyString>,
    text: &Bound<'_, PyAny>,
) -> PyResult<Vec<(usize, usize)>> {
    let pattern = pattern.to_cow()?;
    match text.cast::<Text>() {
        Ok(prepared) => search(py, &pattern, &prepared.get().0),
        Err(_) => search(py, &pattern, &Utf8::new(text.cast::<PyString>()?)?),
    }
}

#[pymodule]
fn _pywhat(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(finditer, module)?)?;
    module.add_class::<Text>()?;
    module.add("MatchError", module.py().get_type::<MatchError>())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::to_char_offsets;

    #[test]
    fn char_offsets() {
        let text = "é a€b 😀c";
        let span = |part: &str| {
            let start = text.find(part).unwrap();
            (start, start + part.len())
        };
        let chars = |(start, end): (usize, usize)| {
            (text[..start].chars().count(), text[..end].chars().count())
        };
        // In the order of the text, as a search finds them, and out of it
        for parts in [vec!["é", "a€b", "c"], vec!["c", "é", "a€b"], vec![]] {
            let mut spans: Vec<(usize, usize)> = parts.iter().map(|part| span(part)).collect();
            let expected: Vec<(usize, usize)> = spans.iter().map(|&s| chars(s)).collect();
            to_char_offsets(text, &mut spans);
            assert_eq!(spans, expected, "{parts:?}");
        }
    }
}
