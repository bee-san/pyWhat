//! `--verify`: asks Google whether the Google API keys found are valid, and adds the answer
//! to their description, like `GoogleAPIKeyVerifier` of `pywhat/processors.py`: "Verification:
//! invalid, Google rejected the key (API_KEY_INVALID)". Every key is sent once, however many
//! times it is found.

use crate::identify::Match;
use crate::processors::Processor;
use serde_json::Value;
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
    pub const URL: &'static str =
        "https://www.googleapis.com/youtube/v3/i18nLanguages?part=snippet&key=";

    /// The reasons of the `google.rpc.ErrorInfo` of the errors that Google answers when the
    /// key is valid but can't be used for the request.
    pub const VALID_KEY_REASONS: [&'static str; 9] = [
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

    /// A verifier that asks Google over HTTPS (10 s timeout).
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
            Some(Value::String(reason)) if reason == "API_KEY_INVALID" => {
                format!("invalid, Google rejected the key ({reason})")
            }
            Some(Value::String(reason)) if Self::VALID_KEY_REASONS.contains(&reason.as_str()) => {
                format!("valid, but Google refused the request ({reason})")
            }
            Some(reason) if truthy(reason) => {
                format!(
                    "unknown, Google answered HTTP {status} ({})",
                    python_str(reason)
                )
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
            let mut results = self.results.lock().unwrap_or_else(|e| e.into_inner());
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

/// Python's truth value of a JSON value.
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(value) => *value,
        Value::Number(number) => number.as_f64() != Some(0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(values) => !values.is_empty(),
        Value::Object(map) => !map.is_empty(),
    }
}

/// `str()` of a JSON value as Python loads it.
fn python_str(value: &Value) -> String {
    match value {
        Value::String(text) => text.clone(),
        Value::Bool(true) => "True".to_string(),
        Value::Bool(false) => "False".to_string(),
        other => crate::json::dumps(other),
    }
}

/// `google_error_reason()`: the reason of the `google.rpc.ErrorInfo` in the error that a
/// Google API answered, such as "API_KEY_INVALID", or `None`.
fn google_error_reason(body: &[u8]) -> Option<Value> {
    let json: Value = serde_json::from_slice(body).ok()?;
    let error = json.as_object()?.get("error")?.as_object()?;
    let details = error.get("details")?;
    for detail in details.as_array()? {
        let detail = detail.as_object()?;
        let kind = match detail.get("@type") {
            None => "",
            Some(Value::String(kind)) => kind,
            Some(_) => return None,
        };
        if kind.ends_with("google.rpc.ErrorInfo") {
            return detail.get("reason").cloned();
        }
    }
    None
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

/// A GET request over HTTPS.
#[cfg(feature = "verify")]
fn get(url: &str) -> Answer {
    use std::time::Duration;
    let agent: ureq::Agent = ureq::Agent::config_builder()
        .timeout_global(Some(Duration::from_secs(10)))
        .http_status_as_error(false)
        .user_agent("pywhat")
        .build()
        .into();
    let mut response = agent.get(url).call().map_err(|error| error.to_string())?;
    let status = response.status().as_u16();
    let body = response
        .body_mut()
        .read_to_vec()
        .map_err(|error| error.to_string())?;
    Ok((status, body))
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
    fn quoting() {
        assert_eq!(quote("a-b_c.d~e/f g"), "a-b_c.d~e%2Ff%20g");
    }
}
