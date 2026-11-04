//! JSON exactly as Python's `json.dumps()` writes it with its default options: `", "` and
//! `": "` separators, and every character outside printable ASCII escaped (`\n`, `\uXXXX`,
//! surrogate pairs for characters outside the BMP).

use serde_json::Value;
use std::fmt::Write;

/// `json.dumps(value)`.
pub fn dumps(value: &Value) -> String {
    let mut out = String::new();
    write_value(&mut out, value);
    out
}

pub(crate) fn write_value(out: &mut String, value: &Value) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(true) => out.push_str("true"),
        Value::Bool(false) => out.push_str("false"),
        Value::Number(number) => write_number(out, number),
        Value::String(text) => write_str(out, text),
        Value::Array(values) => {
            out.push('[');
            for (i, value) in values.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_value(out, value);
            }
            out.push(']');
        }
        Value::Object(map) => {
            out.push('{');
            for (i, (key, value)) in map.iter().enumerate() {
                if i > 0 {
                    out.push_str(", ");
                }
                write_str(out, key);
                out.push_str(": ");
                write_value(out, value);
            }
            out.push('}');
        }
    }
}

/// A number like Python's `repr()`: integers as they are, floats in their shortest form
/// with at least one decimal (`1.0`), and exponents like `1e-05` and `1e+16`.
fn write_number(out: &mut String, number: &serde_json::Number) {
    if number.is_f64() {
        let float = number.as_f64().unwrap_or(0.0);
        write_float(out, float);
    } else {
        let _ = write!(out, "{number}");
    }
}

pub(crate) fn write_float(out: &mut String, float: f64) {
    if float.is_nan() {
        out.push_str("NaN");
        return;
    }
    if float.is_infinite() {
        out.push_str(if float > 0.0 { "Infinity" } else { "-Infinity" });
        return;
    }
    // Rust's `{:?}` is the shortest round-trip representation, as `repr()` is, but it
    // writes exponents differently: Python uses scientific notation from 1e16 and below
    // 1e-4, with a sign and at least two exponent digits.
    let abs = float.abs();
    if abs != 0.0 && !(1e-4..1e16).contains(&abs) {
        let formatted = format!("{float:e}");
        let (mantissa, exponent) = formatted.split_once('e').unwrap_or((&formatted, "0"));
        let exponent: i32 = exponent.parse().unwrap_or(0);
        let sign = if exponent < 0 { '-' } else { '+' };
        let _ = write!(out, "{mantissa}e{sign}{:02}", exponent.abs());
    } else {
        let formatted = format!("{float:?}");
        out.push_str(&formatted);
    }
}

/// A string as `json.dumps()` (with `ensure_ascii=True`) writes it.
pub(crate) fn write_str(out: &mut String, text: &str) {
    out.push('"');
    for c in text.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            ' '..='~' => out.push(c),
            _ => {
                let mut units = [0u16; 2];
                for unit in c.encode_utf16(&mut units) {
                    let _ = write!(out, "\\u{unit:04x}");
                }
            }
        }
    }
    out.push('"');
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn like_json_dumps() {
        assert_eq!(
            dumps(&json!({"a": [1, 0.5, null, true], "b": "x"})),
            r#"{"a": [1, 0.5, null, true], "b": "x"}"#
        );
        assert_eq!(
            dumps(&json!("é\u{20bf}😂\n\u{7f}\u{1}\"\\/")),
            r#""\u00e9\u20bf\ud83d\ude02\n\u007f\u0001\"\\/""#
        );
        assert_eq!(dumps(&json!([])), "[]");
        assert_eq!(dumps(&json!({})), "{}");
    }

    #[test]
    fn floats_like_repr() {
        for (float, python) in [
            (0.1, "0.1"),
            (1.0, "1.0"),
            (0.7, "0.7"),
            (1e-5, "1e-05"),
            (1e16, "1e+16"),
            (1.5e16, "1.5e+16"),
            (123456789012345.6, "123456789012345.6"),
            (0.0001, "0.0001"),
            (-2.5e-7, "-2.5e-07"),
        ] {
            let mut out = String::new();
            write_float(&mut out, float);
            assert_eq!(out, python, "{float}");
        }
    }
}
