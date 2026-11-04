//! The WebAssembly API (feature `wasm`), for browsers and other JavaScript hosts:
//!
//! ```js
//! import init, { identify } from "./pywhat.js";
//! await init();
//! const found = JSON.parse(identify("thm{flag} bee@skerritt.blog", '{"boundaryless": true}'));
//! ```
//!
//! `identify` returns what `pywhat --json` prints for a text. Its options, as JSON (all
//! optional): `min_rarity` and `max_rarity` (0.1 and 1), `include` and `exclude` (lists of
//! tags or names), `boundaryless` (`true` for the CLI's default, rarity 0.1 to 1, `false`
//! for none, the default here, or `{"min_rarity": .., "max_rarity": .., "include": ..,
//! "exclude": ..}`), `key` (`name`, `rarity`, `matched`, `likely`), `reverse`, `top` (`10`,
//! `"5%"`), `processing` (`false` like `--disable-processing`) and `map` (`"osm"`).

use crate::processors::{default_processors, OpenStreetMap, Processor};
use crate::ranking::{sort_matches, Key, Top};
use crate::{Filter, Identifier};
use serde_json::Value;
use wasm_bindgen::prelude::*;

fn strings(value: Option<&Value>) -> Option<Vec<String>> {
    value.and_then(Value::as_array).map(|values| {
        values
            .iter()
            .filter_map(|v| v.as_str().map(str::to_string))
            .collect()
    })
}

fn filter(options: &Value, min: f64) -> Result<Filter, String> {
    let include = strings(options.get("include"));
    let exclude = strings(options.get("exclude")).unwrap_or_default();
    let min_rarity = options
        .get("min_rarity")
        .and_then(Value::as_f64)
        .unwrap_or(min);
    let max_rarity = options
        .get("max_rarity")
        .and_then(Value::as_f64)
        .unwrap_or(1.0);
    Filter::new(include.as_deref(), &exclude, min_rarity, max_rarity).map_err(|e| e.to_string())
}

/// Identifies `text` with the options in `options_json` (see the module docs) and returns
/// what `pywhat --json` prints, or `{"error": "..."}`.
#[wasm_bindgen]
pub fn identify(text: &str, options_json: &str) -> String {
    match try_identify(text, options_json) {
        Ok(json) => json,
        Err(error) => {
            let mut out = String::from("{\"error\": ");
            crate::json::write_str(&mut out, &error);
            out.push('}');
            out
        }
    }
}

fn try_identify(text: &str, options_json: &str) -> Result<String, String> {
    let options: Value = if options_json.trim().is_empty() {
        Value::Object(Default::default())
    } else {
        serde_json::from_str(options_json).map_err(|e| format!("options: {e}"))?
    };
    let dist = filter(&options, 0.1)?;
    let boundaryless = match options.get("boundaryless") {
        Some(Value::Bool(true)) => Filter::default(),
        Some(Value::Object(_)) => filter(&options["boundaryless"], 0.1)?,
        _ => Filter::none(),
    };
    let mut processors: Vec<Box<dyn Processor>> =
        if options.get("processing").and_then(Value::as_bool) == Some(false) {
            Vec::new()
        } else {
            default_processors()
        };
    if options.get("map").and_then(Value::as_str) == Some("osm") {
        processors.push(Box::new(OpenStreetMap));
    }
    let key: Key = match options.get("key").and_then(Value::as_str) {
        Some(key) => key.parse().map_err(|_| "Invalid key".to_string())?,
        None => Key::None,
    };
    let reverse = options
        .get("reverse")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    let top = match options.get("top") {
        Some(Value::Number(n)) => Some(Top::parse(&n.to_string())?),
        Some(Value::String(s)) => Some(Top::parse(s)?),
        _ => None,
    };
    let identifier = Identifier::new(dist, boundaryless, processors);
    let mut found = identifier.identify(text);
    match &top {
        Some(top) => {
            found = crate::ranking::top_matches(&found, top);
            sort_matches(&mut found, key, reverse);
        }
        None => sort_matches(&mut found, key, reverse),
    }
    let mut out = String::new();
    crate::identify::write_identify_json(&mut out, &[("text".to_string(), found)], None);
    Ok(out)
}

/// The tags of the regexes, as a JSON list (`pywhat --tags`).
#[wasm_bindgen]
pub fn tags() -> String {
    let tags: Vec<Value> = crate::tags()
        .into_iter()
        .map(|tag| Value::String(tag.to_string()))
        .collect();
    crate::json::dumps(&Value::Array(tags))
}

/// The version of the crate.
#[wasm_bindgen]
pub fn version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}
