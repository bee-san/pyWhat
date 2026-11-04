//! The text that pyWhat searches in the bytes of a file or of stdin, a port of
//! `pywhat/unicode.py`:
//!
//! * A byte order mark gives the encoding: UTF-8, or UTF-16 or UTF-32 in little- or
//!   big-endian byte order.
//! * Without one, the text is UTF-8, and bytes that aren't UTF-8 are skipped.
//! * The UTF-16LE strings in the bytes (what `strings -el` finds) are searched too.
//!
//! Line breaks become `\n`.

/// The minimum length of a UTF-16LE string, the default of `strings`.
pub const MIN_STRING_LENGTH: usize = 4;

/// `_universal_newlines()`: `\r\n` and `\r` become `\n`.
pub(crate) fn universal_newlines(text: String) -> String {
    if text.contains('\r') {
        text.replace("\r\n", "\n").replace('\r', "\n")
    } else {
        text
    }
}

/// `_decode_bom()`: the text of bytes that start with a UTF-16 or UTF-32 BOM, or `None` if
/// they don't or the rest isn't valid in the BOM's encoding.
fn decode_bom(data: &[u8]) -> Option<String> {
    // UTF-32 first, because the UTF-32LE BOM starts with the UTF-16LE BOM
    const BOMS: [(&[u8], Encoding); 4] = [
        (&[0xFF, 0xFE, 0x00, 0x00], Encoding::Utf32Le),
        (&[0x00, 0x00, 0xFE, 0xFF], Encoding::Utf32Be),
        (&[0xFF, 0xFE], Encoding::Utf16Le),
        (&[0xFE, 0xFF], Encoding::Utf16Be),
    ];
    for (bom, encoding) in BOMS {
        if let Some(rest) = data.strip_prefix(bom) {
            if let Some(text) = encoding.decode(rest) {
                return Some(text);
            }
            // FF FE 00 00 can be UTF-16LE text, too
        }
    }
    None
}

#[derive(Clone, Copy)]
enum Encoding {
    Utf32Le,
    Utf32Be,
    Utf16Le,
    Utf16Be,
}

impl Encoding {
    /// Strict decoding, like Python's codecs (lone surrogates and odd lengths are errors).
    fn decode(self, data: &[u8]) -> Option<String> {
        match self {
            Encoding::Utf32Le | Encoding::Utf32Be => {
                if !data.len().is_multiple_of(4) {
                    return None;
                }
                data.as_chunks::<4>()
                    .0
                    .iter()
                    .map(|&bytes| {
                        let value = match self {
                            Encoding::Utf32Le => u32::from_le_bytes(bytes),
                            _ => u32::from_be_bytes(bytes),
                        };
                        char::from_u32(value)
                    })
                    .collect()
            }
            Encoding::Utf16Le | Encoding::Utf16Be => {
                if !data.len().is_multiple_of(2) {
                    return None;
                }
                let units = data.as_chunks::<2>().0.iter().map(|&bytes| match self {
                    Encoding::Utf16Le => u16::from_le_bytes(bytes),
                    _ => u16::from_be_bytes(bytes),
                });
                char::decode_utf16(units)
                    .collect::<Result<String, _>>()
                    .ok()
            }
        }
    }
}

/// `data.decode("utf-8-sig", errors="ignore")`: UTF-8 without a leading BOM, skipping the
/// bytes that aren't UTF-8 the way Python's decoder does.
pub(crate) fn decode_utf8_lossy_skipping(data: &[u8]) -> String {
    let data = data.strip_prefix(b"\xEF\xBB\xBF").unwrap_or(data);
    let mut out = String::with_capacity(data.len());
    for chunk in data.utf8_chunks() {
        out.push_str(chunk.valid());
        // Python's "ignore" drops the invalid bytes; utf8_chunks splits them where
        // Python's decoder does (at the maximal invalid prefix), and dropping them all is the
        // same whatever the split.
    }
    out
}

/// `_decode_text()`: UTF-8 (with or without a BOM), else bytes that aren't UTF-8 skipped.
/// (Python also tries the encoding of stdin for stdin; on systems where that is UTF-8
/// this is the same.)
fn decode_text(data: &[u8]) -> String {
    let without_bom = data.strip_prefix(b"\xEF\xBB\xBF").unwrap_or(data);
    match std::str::from_utf8(without_bom) {
        Ok(text) => text.to_string(),
        Err(_) => decode_utf8_lossy_skipping(data),
    }
}

/// `decode()`: the text of the bytes of a file or of stdin.
pub fn decode(data: &[u8]) -> String {
    universal_newlines(decode_bom(data).unwrap_or_else(|| decode_text(data)))
}

/// `utf16_strings()`: the UTF-16LE strings in `data` of at least [`MIN_STRING_LENGTH`]
/// printable ASCII characters or tabs, like the ones `strings -el` finds.
pub fn utf16_strings(data: &[u8]) -> Vec<String> {
    // (?:[\t\x20-\x7e]\x00){4,}, leftmost-first like re.finditer
    let mut strings = Vec::new();
    let mut i = 0;
    while i + 1 < data.len() {
        let mut j = i;
        let mut text = String::new();
        while j + 1 < data.len() && is_printable(data[j]) && data[j + 1] == 0 {
            text.push(data[j] as char);
            j += 2;
        }
        if text.len() >= MIN_STRING_LENGTH {
            strings.push(text);
            i = j;
        } else {
            i += 1;
        }
    }
    strings
}

fn is_printable(byte: u8) -> bool {
    byte == b'\t' || (0x20..=0x7E).contains(&byte)
}

/// `texts()`: the texts that pyWhat searches in the bytes of a file or of stdin: the
/// decoded text and, unless the bytes are UTF-16 or UTF-32 with a BOM, the UTF-16LE strings
/// in them, one per line, if there are any.
pub fn texts(data: &[u8]) -> Vec<String> {
    if let Some(text) = decode_bom(data) {
        return vec![universal_newlines(text)];
    }
    let mut found = vec![universal_newlines(decode_text(data))];
    let strings = utf16_strings(data);
    if !strings.is_empty() {
        found.push(strings.join("\n"));
    }
    found
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn boms() {
        let utf16le: Vec<u8> = [0xFF, 0xFE]
            .into_iter()
            .chain("thm{x}\r\n".encode_utf16().flat_map(u16::to_le_bytes))
            .collect();
        assert_eq!(texts(&utf16le), vec!["thm{x}\n"]);
        let utf32be: Vec<u8> = [0, 0, 0xFE, 0xFF]
            .into_iter()
            .chain("é".chars().flat_map(|c| (c as u32).to_be_bytes()))
            .collect();
        assert_eq!(decode(&utf32be), "é");
        // An odd length after a UTF-16 BOM isn't UTF-16
        assert_eq!(decode(&[0xFF, 0xFE, b'a']), "a");
    }

    #[test]
    fn utf8_with_invalid_bytes() {
        assert_eq!(decode(b"\xEF\xBB\xBFab\xFFc\r"), "abc\n");
        assert_eq!(decode(b"a\xE2\x82b"), "ab");
    }

    #[test]
    fn utf16_strings_in_binary() {
        let mut data = b"\x00\x01".to_vec();
        data.extend("THM{abc}".encode_utf16().flat_map(u16::to_le_bytes));
        data.extend(b"\x00\x00ab\x00");
        data.extend("ab".encode_utf16().flat_map(u16::to_le_bytes));
        assert_eq!(utf16_strings(&data), vec!["THM{abc}"]);
        assert_eq!(texts(&data).len(), 2);
    }
}
