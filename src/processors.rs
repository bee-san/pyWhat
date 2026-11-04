//! Processing of matches after a regex has found them, a port of `pywhat/processors.py`.
//!
//! A processor can change a match (its description, link, rarity, ...) or filter it out,
//! which a regex can't do: [`UnixTimestamp`] adds the date of a timestamp to its
//! description, and [`BitcoinAddress`] filters out addresses whose checksum is wrong.

use crate::identify::Match;

/// Processes the matches of the regexes named in [`Processor::names`], one at a time.
pub trait Processor: Send + Sync {
    /// The names of the regexes whose matches this processes.
    fn names(&self) -> &[&str];

    /// Returns the match, possibly changed, or `None` to filter it out.
    fn process(&self, found: Match) -> Option<Match>;
}

/// New instances of the processors that pyWhat uses by default
/// (`default_processors()`): [`UnixTimestamp`], [`BitcoinAddress`] and [`Validator`].
pub fn default_processors() -> Vec<Box<dyn Processor>> {
    vec![
        Box::new(UnixTimestamp),
        Box::new(BitcoinAddress),
        Box::new(Validator::new()),
    ]
}

/// Filters out the matches whose checksum is wrong, for the regexes that name one in their
/// `"Validator"` (`ValidatorProcessor`): card numbers must pass the Luhn check, a Litecoin
/// address must be Base58Check, and so on (see [`crate::validators`]).
#[derive(Debug, Clone)]
pub struct Validator {
    names: Vec<&'static str>,
}

impl Validator {
    pub fn new() -> Validator {
        Validator {
            names: crate::regexes()
                .iter()
                .filter(|entry| entry.validator.is_some())
                .map(|entry| entry.name.as_str())
                .collect(),
        }
    }
}

impl Default for Validator {
    fn default() -> Self {
        Validator::new()
    }
}

impl Processor for Validator {
    fn names(&self) -> &[&str] {
        &self.names
    }

    fn process(&self, found: Match) -> Option<Match> {
        let valid = found
            .regex
            .validator
            .as_deref()
            .and_then(crate::validators::validator)
            .is_none_or(|validator| validator(&found.matched));
        valid.then_some(found)
    }
}

const MONTHS: [&str; 12] = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
];

/// Adds the date and time of a Unix timestamp, in UTC, to its description:
/// "1637093119" gets "Date: November 16, 2021 8:05:19 PM UTC".
#[derive(Debug, Default, Clone, Copy)]
pub struct UnixTimestamp;

impl UnixTimestamp {
    /// The number of microseconds in a unit of the timestamps, by regex name.
    fn unit(name: &str) -> Option<i128> {
        match name {
            "Recent Unix Timestamp" | "Unix Timestamp" => Some(1_000_000),
            "Recent Unix Millisecond Timestamp" | "Unix Millisecond Timestamp" => Some(1000),
            _ => None,
        }
    }
}

impl Processor for UnixTimestamp {
    fn names(&self) -> &[&str] {
        &[
            "Recent Unix Timestamp",
            "Recent Unix Millisecond Timestamp",
            "Unix Timestamp",
            "Unix Millisecond Timestamp",
        ]
    }

    fn process(&self, mut found: Match) -> Option<Match> {
        let Some(unit) = Self::unit(&found.regex.name) else {
            return Some(found);
        };
        let Some(date) = timestamp_to_date(&found.matched, unit) else {
            return Some(found); // the regex matched something that isn't a date
        };
        let date = format!("Date: {date} UTC");
        found.description = Some(match found.description.as_deref() {
            Some(description) if !description.is_empty() => format!("{description}. {date}"),
            _ => date,
        });
        Some(found)
    }
}

/// The date and time of a Unix timestamp such as "1637093119" or "1637093119.558717",
/// formatted like "November 16, 2021 8:05:19 PM" (`format_datetime()`), or `None` if it
/// isn't a number or the date is after the year 9999. `unit` is the number of
/// microseconds in a unit of the timestamp.
pub(crate) fn timestamp_to_date(timestamp: &str, unit: i128) -> Option<String> {
    let microseconds = decimal_times(timestamp, unit)?;
    // datetime(1970, 1, 1) + timedelta(microseconds=...), which is limited to the years
    // 1 to 9999
    const MAX: i128 = 253_402_300_799_999_999; // 9999-12-31 23:59:59.999999
    const MIN: i128 = -62_135_596_800_000_000; // 0001-01-01 00:00:00
    if !(MIN..=MAX).contains(&microseconds) {
        return None;
    }
    let days = microseconds.div_euclid(86_400_000_000);
    let of_day = microseconds.rem_euclid(86_400_000_000);
    let (year, month, day) = civil_from_days(days as i64);
    let hour = (of_day / 3_600_000_000) as u32;
    let minute = (of_day / 60_000_000 % 60) as u32;
    let second = (of_day / 1_000_000 % 60) as u32;
    let microsecond = (of_day % 1_000_000) as u32;
    let mut seconds = format!("{second:02}");
    if microsecond != 0 {
        let fraction = format!(".{microsecond:06}");
        seconds.push_str(fraction.trim_end_matches('0'));
    }
    let hour12 = if hour.is_multiple_of(12) {
        12
    } else {
        hour % 12
    };
    let am_pm = if hour < 12 { "AM" } else { "PM" };
    Some(format!(
        "{} {day}, {year} {hour12}:{minute:02}:{seconds} {am_pm}",
        MONTHS[(month - 1) as usize]
    ))
}

/// `int(Decimal(text) * unit)`: the decimal number `text` times `unit`, truncated toward
/// zero. Accepts what Python's `Decimal` accepts for the timestamp regexes: digits, with an
/// optional sign and an optional fraction.
fn decimal_times(text: &str, unit: i128) -> Option<i128> {
    let text = text.trim();
    let (negative, digits) = match text.as_bytes().first()? {
        b'-' => (true, &text[1..]),
        b'+' => (false, &text[1..]),
        _ => (false, text),
    };
    let (whole, fraction) = digits.split_once('.').unwrap_or((digits, ""));
    if (whole.is_empty() && fraction.is_empty())
        || !whole.bytes().all(|b| b.is_ascii_digit())
        || !fraction.bytes().all(|b| b.is_ascii_digit())
    {
        return None;
    }
    let mut value: i128 = 0;
    for b in whole.bytes() {
        value = value.checked_mul(10)?.checked_add(i128::from(b - b'0'))?;
    }
    value = value.checked_mul(unit)?;
    // The fraction times unit, truncated: unit is a power of ten
    let mut scale = unit;
    let mut extra: i128 = 0;
    for b in fraction.bytes() {
        if scale == 1 {
            break;
        }
        scale /= 10;
        extra += i128::from(b - b'0') * scale;
    }
    value = value.checked_add(extra)?;
    Some(if negative { -value } else { value })
}

/// The (year, month, day) of a number of days since 1970-01-01 (Howard Hinnant's
/// `civil_from_days`).
fn civil_from_days(days: i64) -> (i64, u32, u32) {
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z.rem_euclid(146_097);
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let m = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (if m <= 2 { y + 1 } else { y }, m, d)
}

/// Filters out the matches of the Bitcoin regex whose checksum is wrong, such as
/// "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F".
#[derive(Debug, Default, Clone, Copy)]
pub struct BitcoinAddress;

impl Processor for BitcoinAddress {
    fn names(&self) -> &[&str] {
        &["Bitcoin (\u{20bf}) Wallet Address"]
    }

    fn process(&self, found: Match) -> Option<Match> {
        crate::bitcoin::is_bitcoin_address(&found.matched).then_some(found)
    }
}

/// Links coordinates to OpenStreetMap instead of Google Maps (`--map osm`):
/// "52.6169586, -1.9779857" links to
/// <https://www.openstreetmap.org/search?query=52.6169586,-1.9779857>.
#[derive(Debug, Default, Clone, Copy)]
pub struct OpenStreetMap;

impl OpenStreetMap {
    pub const URL: &str = "https://www.openstreetmap.org/search?query=";

    /// The text to search OpenStreetMap for (`OpenStreetMapProcessor.query()`).
    pub fn query(coordinates: &str) -> String {
        let without_plus = coordinates.replace('+', "");
        let joined = without_plus
            .split_whitespace()
            .collect::<Vec<_>>()
            .join(" ");
        // re.sub(r"(?<!\d) | (?!\d)", "", query): a space stays only between two digits
        let chars: Vec<char> = joined.chars().collect();
        let mut query = String::with_capacity(joined.len());
        let mut i = 0;
        while i < chars.len() {
            let c = chars[i];
            if c == ' ' {
                // Python's \d is Unicode: any decimal digit
                let before_digit = i > 0 && is_python_digit(chars[i - 1]);
                let after_digit = chars.get(i + 1).is_some_and(|&next| is_python_digit(next));
                if !(before_digit && after_digit) {
                    i += 1;
                    continue;
                }
            }
            query.push(c);
            i += 1;
        }
        if let Some((latitude, longitude)) = google_maps_notation(&query) {
            return format!("{latitude},{longitude}");
        }
        query
    }
}

fn is_python_digit(c: char) -> bool {
    use std::sync::OnceLock;
    static DIGIT: OnceLock<crate::charclass::CharClass> = OnceLock::new();
    c.is_ascii_digit()
        || (!c.is_ascii()
            && DIGIT
                .get_or_init(|| crate::charclass::CharClass::parse(r"\d", false).expect("valid"))
                .contains(c))
}

/// The latitude and longitude of the @latitude,longitude,zoom notation of Google Maps,
/// such as "@13.923404,101.3395163,17z" (the whole text, case-insensitive).
fn google_maps_notation(text: &str) -> Option<(String, String)> {
    use std::sync::OnceLock;
    static NOTATION: OnceLock<regex::Regex> = OnceLock::new();
    let regex = NOTATION.get_or_init(|| {
        regex::Regex::new(
            r"(?i)\A@(?P<lat>-?\d+(?:\.\d+)?),(?P<lon>-?\d+(?:\.\d+)?),\d+(?:\.\d+)?z\z",
        )
        .expect("valid regex")
    });
    let captures = regex.captures(text)?;
    Some((captures["lat"].to_string(), captures["lon"].to_string()))
}

impl Processor for OpenStreetMap {
    fn names(&self) -> &[&str] {
        &["Latitude & Longitude Coordinates"]
    }

    fn process(&self, mut found: Match) -> Option<Match> {
        found.url = Some(Self::URL.to_string());
        found.link = Some(format!(
            "{}{}",
            Self::URL,
            quote(&Self::query(&found.matched), b",")
        ));
        Some(found)
    }
}

/// `urllib.parse.quote(text, safe)`: percent-encodes the UTF-8 bytes of everything but
/// ASCII letters, digits, `_.-~` and the bytes in `safe`.
pub(crate) fn quote(text: &str, safe: &[u8]) -> String {
    let mut out = String::with_capacity(text.len());
    for &b in text.as_bytes() {
        if b.is_ascii_alphanumeric() || b"_.-~".contains(&b) || safe.contains(&b) {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn dates() {
        assert_eq!(
            timestamp_to_date("1637093119", 1_000_000).unwrap(),
            "November 16, 2021 8:05:19 PM"
        );
        assert_eq!(
            timestamp_to_date("1637093119.558717", 1_000_000).unwrap(),
            "November 16, 2021 8:05:19.558717 PM"
        );
        assert_eq!(
            timestamp_to_date("1637093119.5", 1_000_000).unwrap(),
            "November 16, 2021 8:05:19.5 PM"
        );
        assert_eq!(
            timestamp_to_date("1637093119.1234567", 1_000_000).unwrap(),
            "November 16, 2021 8:05:19.123456 PM"
        );
        assert_eq!(
            timestamp_to_date("0", 1_000_000).unwrap(),
            "January 1, 1970 12:00:00 AM"
        );
        assert_eq!(
            timestamp_to_date("1637093119558", 1000).unwrap(),
            "November 16, 2021 8:05:19.558 PM"
        );
        assert_eq!(
            timestamp_to_date("253402300799", 1_000_000).unwrap(),
            "December 31, 9999 11:59:59 PM"
        );
        assert!(timestamp_to_date("253402300800", 1_000_000).is_none());
        assert!(timestamp_to_date("abc", 1_000_000).is_none());
        assert_eq!(
            timestamp_to_date("951782400", 1_000_000).unwrap(),
            "February 29, 2000 12:00:00 AM"
        );
    }

    #[test]
    fn osm_queries() {
        assert_eq!(
            OpenStreetMap::query("52.6169586, -1.9779857"),
            "52.6169586,-1.9779857"
        );
        assert_eq!(
            OpenStreetMap::query("@13.923404,101.3395163,17z"),
            "13.923404,101.3395163"
        );
        assert_eq!(OpenStreetMap::query("41 deg 2 12.2 N"), "41deg2 12.2N");
        assert_eq!(
            OpenStreetMap::query("+52.6169586,  +1.9779857"),
            "52.6169586,1.9779857"
        );
        assert_eq!(quote("41°24'12.2\"N", b","), "41%C2%B024%2712.2%22N");
    }
}
