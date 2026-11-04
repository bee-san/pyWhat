//! pyWhat in Rust: identify anything, such as email addresses, IP addresses, API keys,
//! cryptocurrency wallets and CTF flags.
//!
//! The regexes are pyWhat's own `pywhat/Data/regex.json`, embedded at compile time, so the
//! Rust crate and the Python package find the same things.
//!
//! ```
//! use pywhat::Identifier;
//!
//! // Like `Identifier()` in Python: rarity 0.1 to 1, regexes with their boundaries
//! let identifier = Identifier::default();
//! let found = identifier.identify("thm{this_is_a_flag}");
//! assert_eq!(found[0].regex.name, "TryHackMe Flag Format");
//!
//! // What the whole text is (lemmeknow's `identify`)
//! let found = identifier.identify_whole("bee@skerritt.blog");
//! assert_eq!(found[0].regex.name, "Email Address");
//! ```

mod bitcoin;
mod charclass;
pub mod data;
pub mod engine;
#[cfg(feature = "files")]
pub mod files;
pub mod filter;
pub mod identify;
pub mod json;
pub mod processors;
pub mod ranking;
pub mod unicode;
#[cfg(feature = "wasm")]
pub mod wasm;

pub use bitcoin::is_bitcoin_address;
pub use data::{regexes, tags, RegexEntry};
pub use engine::{EngineKind, MatchError};
#[cfg(feature = "files")]
pub use files::{Found, Identified, InputOptions};
pub use filter::{split_tags, Filter, InvalidTag};
pub use identify::{compile_all, engine_of, Identifier, Match};
pub use processors::{default_processors, Processor};
pub use ranking::{Key, Top};
