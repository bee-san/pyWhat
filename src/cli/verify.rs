//! `--verify`: asks Google whether the Google API keys found are valid, and adds the answer
//! to their description, like `GoogleAPIKeyVerifier` of `pywhat/processors.py`: "Verification:
//! invalid, Google rejected the key (API_KEY_INVALID)". Every key is sent once, however many
//! times it is found.

use crate::identify::Match;
use crate::processors::Processor;
use std::collections::HashMap;
use std::sync::Mutex;

/// What a GET request answered: the HTTP status and the body, or why there is no answer.
pub type Answer = Result<(u16, Vec<u8>), String>;

/// Sends a GET request (with the User-Agent `pywhat`) and returns the answer.
pub type HttpGet = dyn Fn(&str) -> Answer + Send + Sync;

/// Asks Google whether Google API keys are valid (`GoogleAPIKeyVerifier`).
pub struct GoogleApiKeyVerifier {
    get: Box<HttpGet>,
    /// The answer for each key, so that it is only sent once.
    results: Mutex<HashMap<String, String>>,
}

impl GoogleApiKeyVerifier {
    /// The request: an API that costs nothing (the languages of the YouTube Data API, one
    /// unit of quota), with the key.
    pub const URL: &str = "https://www.googleapis.com/youtube/v3/i18nLanguages?part=snippet&key=";

    /// The reasons of the `google.rpc.ErrorInfo` of the errors that Google answers when the
    /// key is valid but can't be used for the request.
    pub const VALID_KEY_REASONS: [&str; 9] = [
        "API_KEY_ANDROID_APP_BLOCKED",
        "API_KEY_HTTP_REFERRER_BLOCKED",
        "API_KEY_IOS_APP_BLOCKED",
        "API_KEY_IP_ADDRESS_BLOCKED",
        "API_KEY_SERVICE_BLOCKED",
        "BILLING_DISABLED",
        "RATE_LIMIT_EXCEEDED",
        "RESOURCE_QUOTA_EXCEEDED",
        "SERVICE_DISABLED",
    ];

    /// A verifier that asks Google over HTTPS, with the timeouts of Python's `urlopen(...,
    /// timeout=10)`: 10 s to connect and for every read and write.
    pub fn new() -> Self {
        Self::with_http(Box::new(get))
    }

    /// A verifier that sends its requests with `get`, e.g. a fake Google in tests.
    pub fn with_http(get: Box<HttpGet>) -> Self {
        GoogleApiKeyVerifier {
            get,
            results: Mutex::new(HashMap::new()),
        }
    }

    /// Asks Google whether `key` is valid, and returns the answer, e.g. "valid, Google
    /// accepted the key".
    pub fn verify(&self, key: &str) -> String {
        match (self.get)(&format!("{}{}", Self::URL, quote(key))) {
            Ok((status, _)) if (200..300).contains(&status) => {
                "valid, Google accepted the key".to_string()
            }
            Ok((status, body)) => Self::describe_error(status, &body),
            Err(error) => format!("unknown, could not ask Google ({error})"),
        }
    }

    /// The answer for a key that Google answered an error for.
    pub fn describe_error(status: u16, body: &[u8]) -> String {
        let reason = google_error_reason(body);
        match &reason {
            Some(PyValue::Str(reason)) if reason == "API_KEY_INVALID" => {
                format!("invalid, Google rejected the key ({reason})")
            }
            Some(PyValue::Str(reason)) if Self::VALID_KEY_REASONS.contains(&reason.as_str()) => {
                format!("valid, but Google refused the request ({reason})")
            }
            Some(reason) if reason.truthy() => {
                format!("unknown, Google answered HTTP {status} ({})", reason.str())
            }
            _ => format!("unknown, Google answered HTTP {status}"),
        }
    }
}

impl Default for GoogleApiKeyVerifier {
    fn default() -> Self {
        Self::new()
    }
}

impl Processor for GoogleApiKeyVerifier {
    fn names(&self) -> &[&str] {
        &["Google API Key"]
    }

    fn process(&self, mut found: Match) -> Option<Match> {
        let result = {
            let mut results = self
                .results
                .lock()
                .unwrap_or_else(std::sync::PoisonError::into_inner);
            results
                .entry(found.matched.clone())
                .or_insert_with(|| self.verify(&found.matched))
                .clone()
        };
        let result = format!("Verification: {result}");
        found.description = Some(match found.description.as_deref() {
            Some(description) if !description.is_empty() => format!("{description}. {result}"),
            _ => result,
        });
        Some(found)
    }
}

/// `google_error_reason()`: the reason of the `google.rpc.ErrorInfo` in the error that a
/// Google API answered, such as "API_KEY_INVALID", or `None`. Like Python, it gives up at
/// the first detail that isn't an object or whose `@type` isn't a string.
fn google_error_reason(body: &[u8]) -> Option<PyValue> {
    let PyValue::Dict(json) = pyjson::loads(body)? else {
        return None;
    };
    let PyValue::Dict(error) = pyjson::get(&json, "error")? else {
        return None;
    };
    let details = match pyjson::get(error, "details") {
        None => return None,
        Some(PyValue::List(details)) => details,
        Some(_) => return None,
    };
    for detail in details {
        let PyValue::Dict(detail) = detail else {
            return None;
        };
        let kind = match pyjson::get(detail, "@type") {
            None => "",
            Some(PyValue::Str(kind)) => kind,
            Some(_) => return None,
        };
        if kind.ends_with("google.rpc.ErrorInfo") {
            return pyjson::get(detail, "reason").cloned();
        }
    }
    None
}

/// A value as Python's `json.loads()` returns it.
#[derive(Debug, Clone, PartialEq)]
enum PyValue {
    None,
    Bool(bool),
    /// An integer, as its digits: Python's integers have no limit.
    Int(String),
    Float(f64),
    Str(String),
    List(Vec<PyValue>),
    /// The keys in the order of their first appearance, with their last values, as in a dict.
    Dict(Vec<(String, PyValue)>),
}

impl PyValue {
    /// Python's truth value.
    fn truthy(&self) -> bool {
        match self {
            PyValue::None => false,
            PyValue::Bool(value) => *value,
            PyValue::Int(digits) => digits.bytes().any(|b| b.is_ascii_digit() && b != b'0'),
            PyValue::Float(value) => *value != 0.0,
            PyValue::Str(text) => !text.is_empty(),
            PyValue::List(values) => !values.is_empty(),
            PyValue::Dict(items) => !items.is_empty(),
        }
    }

    /// `str()`.
    fn str(&self) -> String {
        match self {
            PyValue::Str(text) => text.clone(),
            other => other.repr(),
        }
    }

    /// `repr()`.
    fn repr(&self) -> String {
        match self {
            PyValue::None => "None".to_string(),
            PyValue::Bool(true) => "True".to_string(),
            PyValue::Bool(false) => "False".to_string(),
            PyValue::Int(digits) => digits.clone(),
            PyValue::Float(value) if value.is_nan() => "nan".to_string(),
            PyValue::Float(value) if value.is_infinite() => {
                if *value > 0.0 { "inf" } else { "-inf" }.to_string()
            }
            PyValue::Float(value) => {
                let mut out = String::new();
                crate::json::write_float(&mut out, *value);
                out
            }
            PyValue::Str(text) => super::python::repr(text),
            PyValue::List(values) => {
                let items: Vec<String> = values.iter().map(PyValue::repr).collect();
                format!("[{}]", items.join(", "))
            }
            PyValue::Dict(items) => {
                let items: Vec<String> = items
                    .iter()
                    .map(|(key, value)| format!("{}: {}", super::python::repr(key), value.repr()))
                    .collect();
                format!("{{{}}}", items.join(", "))
            }
        }
    }
}

/// Python's `json.loads()` of bytes: the encoding detected like `json.detect_encoding()`,
/// `NaN`, `Infinity` and `-Infinity`, integers of any size.
mod pyjson {
    use super::PyValue;

    /// The value of a key of a dict.
    pub(super) fn get<'a>(items: &'a [(String, PyValue)], key: &str) -> Option<&'a PyValue> {
        items.iter().find(|(k, _)| k == key).map(|(_, value)| value)
    }

    /// `json.detect_encoding()` and `bytes.decode(encoding, "surrogatepass")` (lone
    /// surrogates become U+FFFD).
    fn decode(data: &[u8]) -> Option<String> {
        let utf16 = |data: &[u8], little: bool| -> Option<String> {
            if !data.len().is_multiple_of(2) {
                return None;
            }
            let units = data.as_chunks::<2>().0.iter().map(|&pair| {
                if little {
                    u16::from_le_bytes(pair)
                } else {
                    u16::from_be_bytes(pair)
                }
            });
            Some(
                char::decode_utf16(units)
                    .map(|c| c.unwrap_or('\u{fffd}'))
                    .collect(),
            )
        };
        let utf32 = |data: &[u8], little: bool| -> Option<String> {
            if !data.len().is_multiple_of(4) {
                return None;
            }
            data.as_chunks::<4>()
                .0
                .iter()
                .map(|&quad| {
                    let value = if little {
                        u32::from_le_bytes(quad)
                    } else {
                        u32::from_be_bytes(quad)
                    };
                    match value {
                        0xD800..=0xDFFF => Some('\u{fffd}'),
                        _ => char::from_u32(value),
                    }
                })
                .collect()
        };
        if let Some(rest) = data.strip_prefix(&[0xFF, 0xFE, 0, 0]) {
            return utf32(rest, true);
        }
        if let Some(rest) = data.strip_prefix(&[0, 0, 0xFE, 0xFF]) {
            return utf32(rest, false);
        }
        if let Some(rest) = data.strip_prefix(&[0xFF, 0xFE]) {
            return utf16(rest, true);
        }
        if let Some(rest) = data.strip_prefix(&[0xFE, 0xFF]) {
            return utf16(rest, false);
        }
        if let Some(rest) = data.strip_prefix(b"\xEF\xBB\xBF") {
            return String::from_utf8(rest.to_vec()).ok();
        }
        if data.len() >= 4 {
            if data[0] == 0 {
                return if data[1] != 0 {
                    utf16(data, false)
                } else {
                    utf32(data, false)
                };
            }
            if data[1] == 0 {
                return if data[2] != 0 || data[3] != 0 {
                    utf16(data, true)
                } else {
                    utf32(data, true)
                };
            }
        } else if data.len() == 2 {
            if data[0] == 0 {
                return utf16(data, false);
            }
            if data[1] == 0 {
                return utf16(data, true);
            }
        }
        String::from_utf8(data.to_vec()).ok()
    }

    /// `json.loads(data)`, or `None` where Python raises an error.
    pub(super) fn loads(data: &[u8]) -> Option<PyValue> {
        let text = decode(data)?;
        let mut parser = Parser {
            text: text.as_bytes(),
            at: 0,
            depth: 0,
        };
        parser.whitespace();
        let value = parser.value()?;
        parser.whitespace();
        (parser.at == parser.text.len()).then_some(value)
    }

    struct Parser<'a> {
        text: &'a [u8],
        at: usize,
        depth: usize,
    }

    impl Parser<'_> {
        fn peek(&self) -> Option<u8> {
            self.text.get(self.at).copied()
        }

        fn eat(&mut self, literal: &str) -> bool {
            if self.text[self.at..].starts_with(literal.as_bytes()) {
                self.at += literal.len();
                true
            } else {
                false
            }
        }

        fn whitespace(&mut self) {
            while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
                self.at += 1;
            }
        }

        fn value(&mut self) -> Option<PyValue> {
            // Python stops at about 1,000 levels too
            if self.depth > 500 {
                return None;
            }
            match self.peek()? {
                b'{' => self.dict(),
                b'[' => self.list(),
                b'"' => self.string().map(PyValue::Str),
                b'n' if self.eat("null") => Some(PyValue::None),
                b't' if self.eat("true") => Some(PyValue::Bool(true)),
                b'f' if self.eat("false") => Some(PyValue::Bool(false)),
                b'N' if self.eat("NaN") => Some(PyValue::Float(f64::NAN)),
                b'I' if self.eat("Infinity") => Some(PyValue::Float(f64::INFINITY)),
                b'-' if self.eat("-Infinity") => Some(PyValue::Float(f64::NEG_INFINITY)),
                b'-' | b'0'..=b'9' => self.number(),
                _ => None,
            }
        }

        fn digits(&mut self) -> usize {
            let start = self.at;
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.at += 1;
            }
            self.at - start
        }

        /// `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?`: a float with a fraction or an
        /// exponent, else an integer.
        fn number(&mut self) -> Option<PyValue> {
            let start = self.at;
            let negative = self.eat("-");
            match self.peek() {
                Some(b'0') => self.at += 1,
                Some(b'1'..=b'9') => {
                    self.digits();
                }
                _ => return None,
            }
            let integer_end = self.at;
            let mut float = false;
            if self.peek() == Some(b'.') && matches!(self.text.get(self.at + 1), Some(b'0'..=b'9'))
            {
                self.at += 1;
                self.digits();
                float = true;
            }
            if matches!(self.peek(), Some(b'e' | b'E')) {
                let save = self.at;
                self.at += 1;
                if matches!(self.peek(), Some(b'+' | b'-')) {
                    self.at += 1;
                }
                if self.digits() == 0 {
                    self.at = save;
                } else {
                    float = true;
                }
            }
            let text = std::str::from_utf8(&self.text[start..self.at]).ok()?;
            if float {
                return text.parse().ok().map(PyValue::Float);
            }
            let digits =
                std::str::from_utf8(&self.text[start + negative as usize..integer_end]).ok()?;
            Some(PyValue::Int(if negative && digits != "0" {
                format!("-{digits}")
            } else {
                digits.to_string()
            }))
        }

        fn hex4(&mut self) -> Option<u32> {
            let hex = std::str::from_utf8(self.text.get(self.at..self.at + 4)?).ok()?;
            if !hex.bytes().all(|b| b.is_ascii_hexdigit()) {
                return None;
            }
            self.at += 4;
            u32::from_str_radix(hex, 16).ok()
        }

        fn string(&mut self) -> Option<String> {
            self.at += 1; // the opening quote
            let mut out = String::new();
            loop {
                let start = self.at;
                while let Some(b) = self.peek() {
                    if b == b'"' || b == b'\\' || b < 0x20 {
                        break;
                    }
                    self.at += 1;
                }
                out.push_str(std::str::from_utf8(&self.text[start..self.at]).ok()?);
                match self.peek()? {
                    b'"' => {
                        self.at += 1;
                        return Some(out);
                    }
                    b'\\' => {
                        self.at += 1;
                        let escape = self.peek()?;
                        self.at += 1;
                        match escape {
                            b'"' => out.push('"'),
                            b'\\' => out.push('\\'),
                            b'/' => out.push('/'),
                            b'b' => out.push('\u{8}'),
                            b'f' => out.push('\u{c}'),
                            b'n' => out.push('\n'),
                            b'r' => out.push('\r'),
                            b't' => out.push('\t'),
                            b'u' => {
                                let first = self.hex4()?;
                                let mut code = first;
                                if (0xD800..0xDC00).contains(&first) && self.eat("\\u") {
                                    let save = self.at;
                                    match self.hex4() {
                                        Some(second) if (0xDC00..0xE000).contains(&second) => {
                                            code = 0x10000
                                                + ((first - 0xD800) << 10)
                                                + (second - 0xDC00);
                                        }
                                        Some(_) => {
                                            // A lone surrogate, then another escape
                                            self.at = save - 2;
                                        }
                                        None => return None,
                                    }
                                }
                                out.push(char::from_u32(code).unwrap_or('\u{fffd}'));
                            }
                            _ => return None,
                        }
                    }
                    _ => return None, // a control character
                }
            }
        }

        fn list(&mut self) -> Option<PyValue> {
            self.at += 1;
            self.depth += 1;
            let mut values = Vec::new();
            self.whitespace();
            if self.eat("]") {
                self.depth -= 1;
                return Some(PyValue::List(values));
            }
            loop {
                self.whitespace();
                values.push(self.value()?);
                self.whitespace();
                if self.eat("]") {
                    self.depth -= 1;
                    return Some(PyValue::List(values));
                }
                if !self.eat(",") {
                    return None;
                }
            }
        }

        fn dict(&mut self) -> Option<PyValue> {
            self.at += 1;
            self.depth += 1;
            let mut items: Vec<(String, PyValue)> = Vec::new();
            self.whitespace();
            if self.eat("}") {
                self.depth -= 1;
                return Some(PyValue::Dict(items));
            }
            loop {
                self.whitespace();
                if self.peek()? != b'"' {
                    return None;
                }
                let key = self.string()?;
                self.whitespace();
                if !self.eat(":") {
                    return None;
                }
                self.whitespace();
                let value = self.value()?;
                match items.iter_mut().find(|(k, _)| *k == key) {
                    Some(item) => item.1 = value,
                    None => items.push((key, value)),
                }
                self.whitespace();
                if self.eat("}") {
                    self.depth -= 1;
                    return Some(PyValue::Dict(items));
                }
                if !self.eat(",") {
                    return None;
                }
            }
        }
    }
}

/// `urllib.parse.quote(text, safe="")`.
fn quote(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for &b in text.as_bytes() {
        if b.is_ascii_alphanumeric() || b"_.-~".contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// A GET request, like Python's `urlopen(Request(url, headers={"User-Agent": "pywhat"}),
/// timeout=10)`: 10 s to connect and for every read and write (not for the whole request),
/// redirects followed for 301, 302, 303 and 307 (up to 10), and errors described the way
/// `urllib` describes the common ones (`timed out`, `<urlopen error [Errno 111] Connection
/// refused>`).
#[cfg(feature = "verify")]
fn get(url: &str) -> Answer {
    use std::time::Duration;
    let ten = Some(Duration::from_secs(10));
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_connect(ten)
        .timeout_per_read(ten)
        .timeout_per_write(ten)
        .http_status_as_error(false)
        .max_redirects(0)
        .max_redirects_will_error(false)
        .user_agent("pywhat")
        .build()
        .into();
    let mut url = url.to_string();
    let mut redirects = 0;
    loop {
        let mut response = agent.get(&url).call().map_err(urllib_error)?;
        let status = response.status().as_u16();
        let location = response
            .headers()
            .get("location")
            .or_else(|| response.headers().get("uri"))
            .and_then(|value| value.to_str().ok())
            .map(str::to_string);
        let body = response.body_mut().read_to_vec().map_err(urllib_error)?;
        if let (true, Some(location)) = (matches!(status, 301 | 302 | 303 | 307), location) {
            let next = urljoin(&url, &location);
            let allowed = next.starts_with("http://") || next.starts_with("https://");
            if allowed && redirects < 10 {
                redirects += 1;
                url = next;
                continue;
            }
        }
        return Ok((status, body));
    }
}

/// `urllib.parse.urljoin(base, location)`, for the forms that a Location header has.
#[cfg(feature = "verify")]
fn urljoin(base: &str, location: &str) -> String {
    let (scheme, rest) = base.split_once("://").unwrap_or(("https", base));
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    if location.contains("://") {
        location.to_string()
    } else if let Some(path) = location.strip_prefix("//") {
        format!("{scheme}://{path}")
    } else if location.starts_with('/') {
        format!("{scheme}://{authority}{location}")
    } else {
        let path_end = rest.find(['?', '#']).unwrap_or(rest.len());
        let directory = rest[..path_end]
            .rfind('/')
            .map_or(rest.len().min(path_end), |i| i + 1);
        let directory = if directory <= authority.len() {
            format!("{authority}/")
        } else {
            rest[..directory].to_string()
        };
        format!("{scheme}://{directory}{location}")
    }
}

/// How Python's `urlopen()` describes an error, as far as it can be told from ureq's: the
/// errors of connecting are `<urlopen error ...>`, OS errors are `[Errno N] message`, and
/// timeouts `timed out`.
#[cfg(feature = "verify")]
fn urllib_error(error: ureq::Error) -> String {
    use ureq::Timeout;
    let os_error = |error: &std::io::Error| {
        let code = error.raw_os_error()?;
        let text = error.to_string();
        let message = text
            .strip_suffix(&format!(" (os error {code})"))
            .unwrap_or(&text)
            .to_string();
        Some(format!("[Errno {code}] {message}"))
    };
    match &error {
        ureq::Error::Timeout(Timeout::Resolve | Timeout::Connect | Timeout::SendRequest) => {
            "<urlopen error timed out>".to_string()
        }
        ureq::Error::Timeout(_) => "timed out".to_string(),
        ureq::Error::Io(io) => {
            use std::io::ErrorKind::*;
            let lookup = io.to_string();
            if let Some(detail) = lookup.strip_prefix("failed to lookup address information: ") {
                // getaddrinfo()'s errors, which Python shows with their EAI_ code
                let code = match detail {
                    "Name or service not known" => Some(-2),
                    "Temporary failure in name resolution" => Some(-3),
                    "No address associated with hostname" => Some(-5),
                    "nodename nor servname provided, or not known" => Some(8),
                    _ => None,
                };
                return match code {
                    Some(code) => format!("<urlopen error [Errno {code}] {detail}>"),
                    None => format!("<urlopen error {detail}>"),
                };
            }
            match (io.kind(), os_error(io)) {
                (
                    ConnectionRefused | AddrNotAvailable | NetworkUnreachable | HostUnreachable
                    | NetworkDown | PermissionDenied | TimedOut,
                    Some(message),
                ) => format!("<urlopen error {message}>"),
                (_, Some(message)) => message,
                (_, None) => error.to_string(),
            }
        }
        _ => error.to_string(),
    }
}

#[cfg(not(feature = "verify"))]
fn get(_url: &str) -> Answer {
    Err("this pywhat was built without the verify feature".to_string())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::Arc;

    fn google_error(reason: &str) -> Vec<u8> {
        serde_json::json!({
            "error": {
                "code": 400,
                "message": "API key not valid. Please pass a valid API key.",
                "details": [
                    {"@type": "type.googleapis.com/google.rpc.ErrorInfo", "reason": reason},
                    {"@type": "type.googleapis.com/google.rpc.LocalizedMessage"},
                ],
            }
        })
        .to_string()
        .into_bytes()
    }

    #[test]
    fn answers() {
        let invalid = GoogleApiKeyVerifier::with_http(Box::new(|_| {
            Ok((400, google_error("API_KEY_INVALID")))
        }));
        assert_eq!(
            invalid.verify("k"),
            "invalid, Google rejected the key (API_KEY_INVALID)"
        );
        let disabled = GoogleApiKeyVerifier::with_http(Box::new(|_| {
            Ok((403, google_error("SERVICE_DISABLED")))
        }));
        assert_eq!(
            disabled.verify("k"),
            "valid, but Google refused the request (SERVICE_DISABLED)"
        );
        let other = GoogleApiKeyVerifier::with_http(Box::new(|_| Ok((403, google_error("OTHER")))));
        assert_eq!(
            other.verify("k"),
            "unknown, Google answered HTTP 403 (OTHER)"
        );
        let html = GoogleApiKeyVerifier::with_http(Box::new(|_| Ok((502, b"<html>".to_vec()))));
        assert_eq!(html.verify("k"), "unknown, Google answered HTTP 502");
        let valid = GoogleApiKeyVerifier::with_http(Box::new(|_| Ok((200, b"{}".to_vec()))));
        assert_eq!(valid.verify("k"), "valid, Google accepted the key");
        let offline = GoogleApiKeyVerifier::with_http(Box::new(|_| Err("timed out".into())));
        assert_eq!(
            offline.verify("k"),
            "unknown, could not ask Google (timed out)"
        );
    }

    #[test]
    fn once_per_key_in_the_description() {
        let requests = Arc::new(AtomicUsize::new(0));
        let urls = Arc::new(Mutex::new(Vec::new()));
        let (counter, seen) = (requests.clone(), urls.clone());
        let verifier = GoogleApiKeyVerifier::with_http(Box::new(move |url| {
            counter.fetch_add(1, Ordering::SeqCst);
            seen.lock().unwrap().push(url.to_string());
            Ok((400, google_error("API_KEY_INVALID")))
        }));
        let key = format!("AIza{}", "SyA00000000000000000000000000000000");
        let identifier = crate::Identifier::default()
            .with_processors(vec![Box::new(verifier)])
            .include_tags(&["Google API Key"]);
        let text = format!("{key}\n{key}\n{key}");
        let found = identifier.identify(&text);
        assert_eq!(found.len(), 3);
        for m in &found {
            assert!(m
                .description
                .as_deref()
                .unwrap()
                .ends_with("Verification: invalid, Google rejected the key (API_KEY_INVALID)"));
        }
        assert_eq!(requests.load(Ordering::SeqCst), 1);
        assert_eq!(
            urls.lock().unwrap()[0],
            format!("{}{key}", GoogleApiKeyVerifier::URL)
        );
    }

    #[test]
    fn error_bodies_like_python() {
        // GoogleAPIKeyVerifier().describe_error(code, body) in Python 3.10
        let cases: &[(u16, &[u8], &str)] = &[
            (400, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22SERVICE_DISABLED\x22}]}}", "valid, but Google refused the request (SERVICE_DISABLED)"),
            (429, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22RATE_LIMIT_EXCEEDED\x22}]}}", "valid, but Google refused the request (RATE_LIMIT_EXCEEDED)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22OTHER_REASON\x22}]}}", "unknown, Google answered HTTP 403 (OTHER_REASON)"),
            (502, b"<html>bad gateway</html>", "unknown, Google answered HTTP 502"),
            (500, b"", "unknown, Google answered HTTP 500"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 5}]}}", "unknown, Google answered HTTP 403 (5)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 0}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: -0.0}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: null}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: true}]}}", "unknown, Google answered HTTP 403 (True)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: false}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 1.5}]}}", "unknown, Google answered HTTP 403 (1.5)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 100000000000000000000}]}}", "unknown, Google answered HTTP 403 (100000000000000000000)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: -100000000000000000000}]}}", "unknown, Google answered HTTP 403 (-100000000000000000000)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 1e+300}]}}", "unknown, Google answered HTTP 403 (1e+300)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 1e+16}]}}", "unknown, Google answered HTTP 403 (1e+16)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: 100.0}]}}", "unknown, Google answered HTTP 403 (100.0)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22\x22}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22[bold]X[/bold]\x22}]}}", "unknown, Google answered HTTP 403 ([bold]X[/bold])"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22caf\x5cu00e9 \x5cu20bf\x22}]}}", "unknown, Google answered HTTP 403 (café ₿)"),
            (403, b"{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22}]}}", "unknown, Google answered HTTP 403"),
            (400, b"{\x22error\x22: {\x22details\x22: {\x22a\x22: 1}}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: [\x22x\x22, {\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: 5, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: [{\x22reason\x22: \x22SERVICE_DISABLED\x22}, {\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"[]", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: \x22x\x22}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: null}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: \x22\x22}}", "unknown, Google answered HTTP 400"),
            (400, b"{\x22error\x22: {\x22details\x22: {}}}", "unknown, Google answered HTTP 400"),
            (400, b"\xef\xbb\xbf{\x22error\x22: {\x22code\x22: 400, \x22message\x22: \x22m\x22, \x22details\x22: [{\x22@type\x22: \x22type.googleapis.com/google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"\xff\xfe{\x00\x22\x00e\x00r\x00r\x00o\x00r\x00\x22\x00:\x00 \x00{\x00\x22\x00c\x00o\x00d\x00e\x00\x22\x00:\x00 \x004\x000\x000\x00,\x00 \x00\x22\x00m\x00e\x00s\x00s\x00a\x00g\x00e\x00\x22\x00:\x00 \x00\x22\x00m\x00\x22\x00,\x00 \x00\x22\x00d\x00e\x00t\x00a\x00i\x00l\x00s\x00\x22\x00:\x00 \x00[\x00{\x00\x22\x00@\x00t\x00y\x00p\x00e\x00\x22\x00:\x00 \x00\x22\x00t\x00y\x00p\x00e\x00.\x00g\x00o\x00o\x00g\x00l\x00e\x00a\x00p\x00i\x00s\x00.\x00c\x00o\x00m\x00/\x00g\x00o\x00o\x00g\x00l\x00e\x00.\x00r\x00p\x00c\x00.\x00E\x00r\x00r\x00o\x00r\x00I\x00n\x00f\x00o\x00\x22\x00,\x00 \x00\x22\x00r\x00e\x00a\x00s\x00o\x00n\x00\x22\x00:\x00 \x00\x22\x00A\x00P\x00I\x00_\x00K\x00E\x00Y\x00_\x00I\x00N\x00V\x00A\x00L\x00I\x00D\x00\x22\x00}\x00]\x00}\x00}\x00", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"{\x00\x22\x00e\x00r\x00r\x00o\x00r\x00\x22\x00:\x00 \x00{\x00\x22\x00c\x00o\x00d\x00e\x00\x22\x00:\x00 \x004\x000\x000\x00,\x00 \x00\x22\x00m\x00e\x00s\x00s\x00a\x00g\x00e\x00\x22\x00:\x00 \x00\x22\x00m\x00\x22\x00,\x00 \x00\x22\x00d\x00e\x00t\x00a\x00i\x00l\x00s\x00\x22\x00:\x00 \x00[\x00{\x00\x22\x00@\x00t\x00y\x00p\x00e\x00\x22\x00:\x00 \x00\x22\x00t\x00y\x00p\x00e\x00.\x00g\x00o\x00o\x00g\x00l\x00e\x00a\x00p\x00i\x00s\x00.\x00c\x00o\x00m\x00/\x00g\x00o\x00o\x00g\x00l\x00e\x00.\x00r\x00p\x00c\x00.\x00E\x00r\x00r\x00o\x00r\x00I\x00n\x00f\x00o\x00\x22\x00,\x00 \x00\x22\x00r\x00e\x00a\x00s\x00o\x00n\x00\x22\x00:\x00 \x00\x22\x00A\x00P\x00I\x00_\x00K\x00E\x00Y\x00_\x00I\x00N\x00V\x00A\x00L\x00I\x00D\x00\x22\x00}\x00]\x00}\x00}\x00", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"\x00{\x00\x22\x00e\x00r\x00r\x00o\x00r\x00\x22\x00:\x00 \x00{\x00\x22\x00c\x00o\x00d\x00e\x00\x22\x00:\x00 \x004\x000\x000\x00,\x00 \x00\x22\x00m\x00e\x00s\x00s\x00a\x00g\x00e\x00\x22\x00:\x00 \x00\x22\x00m\x00\x22\x00,\x00 \x00\x22\x00d\x00e\x00t\x00a\x00i\x00l\x00s\x00\x22\x00:\x00 \x00[\x00{\x00\x22\x00@\x00t\x00y\x00p\x00e\x00\x22\x00:\x00 \x00\x22\x00t\x00y\x00p\x00e\x00.\x00g\x00o\x00o\x00g\x00l\x00e\x00a\x00p\x00i\x00s\x00.\x00c\x00o\x00m\x00/\x00g\x00o\x00o\x00g\x00l\x00e\x00.\x00r\x00p\x00c\x00.\x00E\x00r\x00r\x00o\x00r\x00I\x00n\x00f\x00o\x00\x22\x00,\x00 \x00\x22\x00r\x00e\x00a\x00s\x00o\x00n\x00\x22\x00:\x00 \x00\x22\x00A\x00P\x00I\x00_\x00K\x00E\x00Y\x00_\x00I\x00N\x00V\x00A\x00L\x00I\x00D\x00\x22\x00}\x00]\x00}\x00}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"\xff\xfe\x00\x00{\x00\x00\x00\x22\x00\x00\x00e\x00\x00\x00r\x00\x00\x00r\x00\x00\x00o\x00\x00\x00r\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00{\x00\x00\x00\x22\x00\x00\x00c\x00\x00\x00o\x00\x00\x00d\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x004\x00\x00\x000\x00\x00\x000\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00m\x00\x00\x00e\x00\x00\x00s\x00\x00\x00s\x00\x00\x00a\x00\x00\x00g\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00m\x00\x00\x00\x22\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00d\x00\x00\x00e\x00\x00\x00t\x00\x00\x00a\x00\x00\x00i\x00\x00\x00l\x00\x00\x00s\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00[\x00\x00\x00{\x00\x00\x00\x22\x00\x00\x00@\x00\x00\x00t\x00\x00\x00y\x00\x00\x00p\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00t\x00\x00\x00y\x00\x00\x00p\x00\x00\x00e\x00\x00\x00.\x00\x00\x00g\x00\x00\x00o\x00\x00\x00o\x00\x00\x00g\x00\x00\x00l\x00\x00\x00e\x00\x00\x00a\x00\x00\x00p\x00\x00\x00i\x00\x00\x00s\x00\x00\x00.\x00\x00\x00c\x00\x00\x00o\x00\x00\x00m\x00\x00\x00/\x00\x00\x00g\x00\x00\x00o\x00\x00\x00o\x00\x00\x00g\x00\x00\x00l\x00\x00\x00e\x00\x00\x00.\x00\x00\x00r\x00\x00\x00p\x00\x00\x00c\x00\x00\x00.\x00\x00\x00E\x00\x00\x00r\x00\x00\x00r\x00\x00\x00o\x00\x00\x00r\x00\x00\x00I\x00\x00\x00n\x00\x00\x00f\x00\x00\x00o\x00\x00\x00\x22\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00r\x00\x00\x00e\x00\x00\x00a\x00\x00\x00s\x00\x00\x00o\x00\x00\x00n\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00A\x00\x00\x00P\x00\x00\x00I\x00\x00\x00_\x00\x00\x00K\x00\x00\x00E\x00\x00\x00Y\x00\x00\x00_\x00\x00\x00I\x00\x00\x00N\x00\x00\x00V\x00\x00\x00A\x00\x00\x00L\x00\x00\x00I\x00\x00\x00D\x00\x00\x00\x22\x00\x00\x00}\x00\x00\x00]\x00\x00\x00}\x00\x00\x00}\x00\x00\x00", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"\x00\x00\x00{\x00\x00\x00\x22\x00\x00\x00e\x00\x00\x00r\x00\x00\x00r\x00\x00\x00o\x00\x00\x00r\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00{\x00\x00\x00\x22\x00\x00\x00c\x00\x00\x00o\x00\x00\x00d\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x004\x00\x00\x000\x00\x00\x000\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00m\x00\x00\x00e\x00\x00\x00s\x00\x00\x00s\x00\x00\x00a\x00\x00\x00g\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00m\x00\x00\x00\x22\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00d\x00\x00\x00e\x00\x00\x00t\x00\x00\x00a\x00\x00\x00i\x00\x00\x00l\x00\x00\x00s\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00[\x00\x00\x00{\x00\x00\x00\x22\x00\x00\x00@\x00\x00\x00t\x00\x00\x00y\x00\x00\x00p\x00\x00\x00e\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00t\x00\x00\x00y\x00\x00\x00p\x00\x00\x00e\x00\x00\x00.\x00\x00\x00g\x00\x00\x00o\x00\x00\x00o\x00\x00\x00g\x00\x00\x00l\x00\x00\x00e\x00\x00\x00a\x00\x00\x00p\x00\x00\x00i\x00\x00\x00s\x00\x00\x00.\x00\x00\x00c\x00\x00\x00o\x00\x00\x00m\x00\x00\x00/\x00\x00\x00g\x00\x00\x00o\x00\x00\x00o\x00\x00\x00g\x00\x00\x00l\x00\x00\x00e\x00\x00\x00.\x00\x00\x00r\x00\x00\x00p\x00\x00\x00c\x00\x00\x00.\x00\x00\x00E\x00\x00\x00r\x00\x00\x00r\x00\x00\x00o\x00\x00\x00r\x00\x00\x00I\x00\x00\x00n\x00\x00\x00f\x00\x00\x00o\x00\x00\x00\x22\x00\x00\x00,\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00r\x00\x00\x00e\x00\x00\x00a\x00\x00\x00s\x00\x00\x00o\x00\x00\x00n\x00\x00\x00\x22\x00\x00\x00:\x00\x00\x00 \x00\x00\x00\x22\x00\x00\x00A\x00\x00\x00P\x00\x00\x00I\x00\x00\x00_\x00\x00\x00K\x00\x00\x00E\x00\x00\x00Y\x00\x00\x00_\x00\x00\x00I\x00\x00\x00N\x00\x00\x00V\x00\x00\x00A\x00\x00\x00L\x00\x00\x00I\x00\x00\x00D\x00\x00\x00\x22\x00\x00\x00}\x00\x00\x00]\x00\x00\x00}\x00\x00\x00}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"{\x22error\x22: {\x22x\x22: NaN, \x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: NaN}]}}", "unknown, Google answered HTTP 403 (nan)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: -Infinity}]}}", "unknown, Google answered HTTP 403 (-inf)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: 1e400}]}}", "unknown, Google answered HTTP 403 (inf)"),
            (400, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22SERVICE_DISABLED\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}}", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (400, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22API_KEY_INVALID\x22}]}} trailing", "unknown, Google answered HTTP 400"),
            (400, b"\x80{\x22error\x22: 1}", "unknown, Google answered HTTP 400"),
            (400, b" \x09\x0a{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22\x5cu0041PI_KEY_INVALID\x22}]}} \x0d\x0a", "invalid, Google rejected the key (API_KEY_INVALID)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22\x5cud83d\x5cude00 x\x22}]}}", "unknown, Google answered HTTP 403 (😀 x)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22a\x5c\x22b\x5c\x5cc\x5c/d\x5cn\x22}]}}", "unknown, Google answered HTTP 403 (a\"b\\c/d\n)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: 012}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: 1.}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: -0}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: 2E3}]}}", "unknown, Google answered HTTP 403 (2000.0)"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22x\x22,}]}}", "unknown, Google answered HTTP 403"),
            (403, b"{\x22error\x22: {\x22details\x22: [{\x22@type\x22: \x22google.rpc.ErrorInfo\x22, \x22reason\x22: \x22tab\x09here\x22}]}}", "unknown, Google answered HTTP 403"),
        ];
        for &(code, body, expected) in cases {
            assert_eq!(
                GoogleApiKeyVerifier::describe_error(code, body),
                expected,
                "{}",
                String::from_utf8_lossy(body)
            );
        }
    }

    #[test]
    fn any_2xx_is_valid() {
        // urlopen() only raises HTTPError outside 200 to 299
        for status in [200, 204, 299] {
            let verifier =
                GoogleApiKeyVerifier::with_http(Box::new(move |_| Ok((status, Vec::new()))));
            assert_eq!(
                verifier.verify("k"),
                "valid, Google accepted the key",
                "{status}"
            );
        }
        let verifier = GoogleApiKeyVerifier::with_http(Box::new(|_| Ok((300, Vec::new()))));
        assert_eq!(verifier.verify("k"), "unknown, Google answered HTTP 300");
    }

    /// A local HTTP server that answers each request with the response of its path, and
    /// records the requests.
    #[cfg(feature = "verify")]
    fn serve(responses: Vec<(&'static str, String)>) -> (String, Arc<Mutex<Vec<String>>>) {
        use std::io::{BufRead, BufReader, Write};
        let listener = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let base = format!("http://{}", listener.local_addr().unwrap());
        let requests = Arc::new(Mutex::new(Vec::new()));
        let seen = requests.clone();
        std::thread::spawn(move || {
            for stream in listener.incoming() {
                let Ok(mut stream) = stream else { break };
                let mut reader = BufReader::new(stream.try_clone().unwrap());
                let mut request = String::new();
                loop {
                    let mut line = String::new();
                    if reader.read_line(&mut line).unwrap_or(0) == 0 || line == "\r\n" {
                        break;
                    }
                    request.push_str(&line);
                }
                let path = request.split_whitespace().nth(1).unwrap_or("").to_string();
                seen.lock().unwrap().push(request);
                let response = responses
                    .iter()
                    .find(|(prefix, _)| path.starts_with(prefix))
                    .map_or_else(
                        || "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n".to_string(),
                        |(_, r)| r.clone(),
                    );
                let _ = stream.write_all(response.as_bytes());
            }
        });
        (base, requests)
    }

    #[test]
    #[cfg(feature = "verify")]
    fn requests_like_urlopen() {
        let invalid = String::from_utf8(google_error("API_KEY_INVALID")).unwrap();
        let (base, requests) = serve(vec![
            ("/invalid", format!("HTTP/1.1 400 Bad Request\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{invalid}", invalid.len())),
            ("/moved", "HTTP/1.1 301 Moved\r\nLocation: /valid?key=K\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".to_string()),
            ("/nowhere", "HTTP/1.1 302 Found\r\nContent-Length: 5\r\nConnection: close\r\n\r\nmoved".to_string()),
            ("/valid", "HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\n{}".to_string()),
        ]);
        let answer = get(&format!("{base}/invalid?key=K")).unwrap();
        assert_eq!(answer, (400, invalid.into_bytes()));
        // The User-Agent of the Python package
        let first = requests.lock().unwrap()[0].clone();
        assert!(
            first.starts_with("GET /invalid?key=K HTTP/1.1\r\n"),
            "{first}"
        );
        assert!(
            first.to_lowercase().contains("\r\nuser-agent: pywhat\r\n"),
            "{first}"
        );
        // A redirect is followed, a redirect without a Location is the answer
        assert_eq!(
            get(&format!("{base}/moved?key=K")).unwrap(),
            (200, b"{}".to_vec())
        );
        assert_eq!(
            get(&format!("{base}/nowhere?key=K")).unwrap(),
            (302, b"moved".to_vec())
        );
        // Nothing listening: urllib's description of the error
        let closed = std::net::TcpListener::bind("127.0.0.1:0").unwrap();
        let port = closed.local_addr().unwrap().port();
        drop(closed);
        let error = get(&format!("http://127.0.0.1:{port}/x")).unwrap_err();
        assert!(error.starts_with("<urlopen error [Errno "), "{error}");
        assert!(
            error.ends_with("] Connection refused>") || cfg!(windows),
            "{error}"
        );
    }

    #[test]
    #[cfg(feature = "verify")]
    fn redirect_targets() {
        // urllib.parse.urljoin(base, location)
        let base = "https://www.googleapis.com/youtube/v3/i18nLanguages?part=snippet&key=K";
        assert_eq!(
            urljoin(base, "https://example.com/x"),
            "https://example.com/x"
        );
        assert_eq!(urljoin(base, "//example.com/x"), "https://example.com/x");
        assert_eq!(
            urljoin(base, "/x?key=K"),
            "https://www.googleapis.com/x?key=K"
        );
        assert_eq!(
            urljoin(base, "languages?key=K"),
            "https://www.googleapis.com/youtube/v3/languages?key=K"
        );
        assert_eq!(urljoin("http://h:8080", "x"), "http://h:8080/x");
    }

    #[test]
    fn quoting() {
        assert_eq!(quote("a-b_c.d~e/f g"), "a-b_c.d~e%2Ff%20g");
    }
}
