//! What Python's built-ins do with strings, where the CLI has to do the same: `str.strip()`,
//! `float()`, `int()`, `repr()` and `str.casefold()`.

use std::fmt::Write;
use std::sync::OnceLock;

/// `str.isspace()` of one character: Rust's `char::is_whitespace` and U+001C to U+001F,
/// which Python counts as whitespace too.
pub(crate) fn is_space(c: char) -> bool {
    c.is_whitespace() || ('\u{1c}'..='\u{1f}').contains(&c)
}

/// `str.strip()`.
pub(crate) fn strip(text: &str) -> &str {
    text.trim_matches(is_space)
}

/// `str.rstrip()`.
pub(crate) fn rstrip(text: &str) -> &str {
    text.trim_end_matches(is_space)
}

/// `str.lstrip()`.
pub(crate) fn lstrip(text: &str) -> &str {
    text.trim_start_matches(is_space)
}

/// `str.isspace()`: not empty, and only whitespace.
pub(crate) fn is_all_space(text: &str) -> bool {
    !text.is_empty() && text.chars().all(is_space)
}

fn unicode_class(
    pattern: &'static str,
    cell: &'static OnceLock<regex::Regex>,
) -> &'static regex::Regex {
    cell.get_or_init(|| regex::Regex::new(pattern).expect("valid class"))
}

/// The value of a decimal digit (Unicode category Nd), like `unicodedata.decimal()`.
/// Decimal digits are encoded in runs of ten, 0 to 9, so the value is the position in
/// the run.
pub(crate) fn decimal_value(c: char) -> Option<u32> {
    if c.is_ascii_digit() {
        return c.to_digit(10);
    }
    static DIGIT: OnceLock<regex::Regex> = OnceLock::new();
    let digit = unicode_class(r"^\p{Nd}$", &DIGIT);
    let is_digit = |c: char| digit.is_match(c.encode_utf8(&mut [0; 4]));
    if !is_digit(c) {
        return None;
    }
    let mut before = 0;
    let mut code = c as u32;
    while let Some(previous) = code.checked_sub(1).and_then(char::from_u32) {
        if !is_digit(previous) {
            break;
        }
        before += 1;
        code -= 1;
    }
    Some(before % 10)
}

/// `_PyUnicode_TransformDecimalAndSpaceToASCII()`, which `float()` and `int()` start
/// with: non-ASCII whitespace becomes a space and non-ASCII decimal digits ASCII digits.
/// `None` if there is any other non-ASCII character, which makes the number invalid.
fn transform_decimal_and_space(text: &str) -> Option<String> {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        if (c as u32) < 127 {
            out.push(c);
        } else if is_space(c) {
            out.push(' ');
        } else {
            out.push(char::from_digit(decimal_value(c)?, 10)?);
        }
    }
    Some(out)
}

/// `_Py_string_to_number_with_underscores()`: the text without underscores, which are
/// only allowed between two digits.
fn remove_underscores(text: &str) -> Option<String> {
    if !text.contains('_') {
        return Some(text.to_string());
    }
    let mut out = String::with_capacity(text.len());
    let mut previous = '\0';
    for c in text.chars() {
        if c == '_' {
            if !previous.is_ascii_digit() {
                return None;
            }
        } else {
            if previous == '_' && !c.is_ascii_digit() {
                return None;
            }
            out.push(c);
        }
        previous = c;
    }
    (previous != '_').then_some(out)
}

/// The whitespace that `float()` and `int()` strip (`Py_ISSPACE`), after the transform.
fn is_ascii_space(c: char) -> bool {
    matches!(c, ' ' | '\t' | '\n' | '\x0b' | '\x0c' | '\r')
}

/// `float(text)`, or `None` where Python raises `ValueError`.
pub(crate) fn float(text: &str) -> Option<f64> {
    let ascii = transform_decimal_and_space(text)?;
    let without_underscores = remove_underscores(&ascii)?;
    let number = without_underscores.trim_matches(is_ascii_space);
    // Python and Rust read the same decimal numbers, infinities and NaNs (in any case),
    // both correctly rounded; Rust doesn't take a NUL or anything after the number either
    number.parse::<f64>().ok()
}

/// `int(text)`, or `None` where Python raises `ValueError`. Saturates at the limits of
/// `i128`, which is enough for comparisons.
pub(crate) fn int(text: &str) -> Option<i128> {
    let ascii = transform_decimal_and_space(text)?;
    let number = ascii.trim_matches(is_ascii_space);
    let (negative, digits) = match number.as_bytes().first()? {
        b'-' => (true, &number[1..]),
        b'+' => (false, &number[1..]),
        _ => (false, number),
    };
    if digits.is_empty() || digits.starts_with('_') {
        return None;
    }
    let digits = remove_underscores(digits)?;
    if digits.is_empty() || !digits.bytes().all(|b| b.is_ascii_digit()) {
        return None;
    }
    let mut value: i128 = 0;
    for b in digits.bytes() {
        value = value
            .saturating_mul(10)
            .saturating_add(i128::from(b - b'0'));
    }
    Some(if negative { -value } else { value })
}

/// `str.isprintable()` of a non-ASCII character: not in the categories Cc, Cf, Cs, Co,
/// Cn, Zl, Zp and Zs.
fn is_printable(c: char) -> bool {
    static UNPRINTABLE: OnceLock<regex::Regex> = OnceLock::new();
    !unicode_class(
        r"^[\p{Cc}\p{Cf}\p{Co}\p{Cn}\p{Zl}\p{Zp}\p{Zs}]$",
        &UNPRINTABLE,
    )
    .is_match(c.encode_utf8(&mut [0; 4]))
}

/// `repr(text)`: the string in quotes, with escapes for what isn't printable.
pub(crate) fn repr(text: &str) -> String {
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(text.len() + 2);
    out.push(quote);
    for c in text.chars() {
        let code = c as u32;
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            _ if c == quote => {
                out.push('\\');
                out.push(c);
            }
            _ if code < 0x20 || code == 0x7f => {
                let _ = write!(out, "\\x{code:02x}");
            }
            _ if c.is_ascii() || is_printable(c) => out.push(c),
            _ if code < 0x100 => {
                let _ = write!(out, "\\x{code:02x}");
            }
            _ if code < 0x10000 => {
                let _ = write!(out, "\\u{code:04x}");
            }
            _ => {
                let _ = write!(out, "\\U{code:08x}");
            }
        }
    }
    out.push(quote);
    out
}

/// `text.casefold()` if it is ASCII, which is all that a comparison with an ASCII string
/// needs: `None` if the case folded text isn't ASCII.
pub(crate) fn casefold_ascii(text: &str) -> Option<String> {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        let folded = match c {
            _ if c.is_ascii() => {
                out.push(c.to_ascii_lowercase());
                continue;
            }
            'ß' | 'ẞ' => "ss",
            'ſ' => "s",
            'K' => "k",
            'ﬀ' => "ff",
            'ﬁ' => "fi",
            'ﬂ' => "fl",
            'ﬃ' => "ffi",
            'ﬄ' => "ffl",
            'ﬅ' | 'ﬆ' => "st",
            _ => return None,
        };
        out.push_str(folded);
    }
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn whitespace() {
        assert_eq!(strip("\u{1c} a \u{3000}"), "a");
        assert!(is_all_space(" \u{1f}"));
        assert!(!is_all_space(""));
        assert_eq!(rstrip("a\n\n"), "a");
        assert_eq!(lstrip("\t a"), "a");
    }

    #[test]
    fn floats_like_python() {
        // Checked with Python 3.10
        for (text, expected) in [
            ("0.5", Some(0.5)),
            (" 1 ", Some(1.0)),
            ("\u{2000}1", Some(1.0)),
            ("١.٥", Some(1.5)),
            ("1_0", Some(10.0)),
            ("١_٠", Some(10.0)),
            ("1e5", Some(1e5)),
            (".5", Some(0.5)),
            ("5.", Some(5.0)),
            ("-Infinity", Some(f64::NEG_INFINITY)),
            ("1e400", Some(f64::INFINITY)),
            ("\u{1c}1.5\u{1f}", None),
            ("١٫٥", None),
            ("1__0", None),
            ("_1", None),
            ("1_", None),
            ("1_.5", None),
            ("1._5", None),
            (" 1e_5", None),
            ("", None),
            (" ", None),
            ("0x10", None),
            ("1,5", None),
            ("nan_", None),
            ("1\u{0}", None),
        ] {
            assert_eq!(float(text), expected, "{text:?}");
        }
        assert!(float("nAn").unwrap().is_nan());
        assert!(float("+nan").unwrap().is_nan());
    }

    #[test]
    fn ints_like_python() {
        for (text, expected) in [
            ("٨٠", Some(80)),
            (" 80 ", Some(80)),
            ("+80", Some(80)),
            ("8_0", Some(80)),
            ("-5", Some(-5)),
            ("080", Some(80)),
            ("80.0", None),
            ("", None),
            ("-", None),
            ("_8", None),
            ("8_", None),
            ("-_8", None),
        ] {
            assert_eq!(int(text), expected, "{text:?}");
        }
        assert_eq!(int(&"9".repeat(60)), Some(i128::MAX));
    }

    #[test]
    fn repr_like_python() {
        assert_eq!(repr("x"), "'x'");
        assert_eq!(repr("it's"), "\"it's\"");
        assert_eq!(repr("'\""), "'\\'\"'");
        assert_eq!(repr("a\\b\n\t\r\x01\x7f"), "'a\\\\b\\n\\t\\r\\x01\\x7f'");
        assert_eq!(
            repr("é₿\u{a0}\u{200b}\u{2028}😂"),
            "'é₿\\xa0\\u200b\\u2028😂'"
        );
        assert_eq!(repr("\u{e000}\u{10ffff}"), "'\\ue000\\U0010ffff'");
    }

    #[test]
    fn casefold() {
        assert_eq!(casefold_ascii("OſM").as_deref(), Some("osm"));
        assert_eq!(casefold_ascii("Google").as_deref(), Some("google"));
        assert_eq!(casefold_ascii("goögle"), None);
    }

    #[test]
    fn decimal_digits() {
        assert_eq!(decimal_value('٣'), Some(3));
        assert_eq!(decimal_value('𝟗'), Some(9)); // U+1D7D7, in a run of five runs of ten
        assert_eq!(decimal_value('²'), None);
        assert_eq!(decimal_value('a'), None);
    }
}
