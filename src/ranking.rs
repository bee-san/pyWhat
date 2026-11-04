//! Sorting the matches, and only the most likely ones: a port of `pywhat.helper.Keys` and
//! `pywhat/ranking.py`.

use crate::identify::Match;
use std::cmp::Ordering;

/// What to sort the matches by (`pywhat.Keys`).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum Key {
    Name,
    Rarity,
    Matched,
    /// The most likely matches first, see [`likelihood_order`].
    Likely,
    /// Not sorted (the default).
    #[default]
    None,
}

impl std::str::FromStr for Key {
    type Err = ();

    /// `str_to_key()`: "name", "rarity", "matched", "likely" or "none", in any case.
    fn from_str(text: &str) -> Result<Key, ()> {
        match text.to_uppercase().as_str() {
            "NAME" => Ok(Key::Name),
            "RARITY" => Ok(Key::Rarity),
            "MATCHED" => Ok(Key::Matched),
            "LIKELY" => Ok(Key::Likely),
            "NONE" => Ok(Key::None),
            _ => Err(()),
        }
    }
}

/// `likelihood()`: the most likely matches first. The higher the rarity, the more likely,
/// but a fragment of a longer word or match is less likely than the others unless its
/// rarity is 1.
pub fn likelihood_order(a: &Match, b: &Match) -> Ordering {
    let key = |m: &Match| (m.fragment && m.rarity < 1.0, -m.rarity);
    let (a, b) = (key(a), key(b));
    a.0.cmp(&b.0).then(a.1.total_cmp(&b.1))
}

fn compare(key: Key, a: &Match, b: &Match) -> Ordering {
    match key {
        Key::Name => a.regex.name.cmp(&b.regex.name),
        Key::Rarity => a.rarity.total_cmp(&b.rarity),
        Key::Matched => a.matched.cmp(&b.matched),
        Key::Likely => likelihood_order(a, b),
        Key::None => Ordering::Equal,
    }
}

/// Sorts matches like `list.sort(key=key, reverse=reverse)`: stable, and equal matches keep
/// their order with `reverse` too.
pub fn sort_matches(matches: &mut [Match], key: Key, reverse: bool) {
    sort_by_key(matches, key, reverse, |m| m);
}

/// Sorts items that contain a match, like [`sort_matches`].
pub(crate) fn sort_by_key<T>(items: &mut [T], key: Key, reverse: bool, get: impl Fn(&T) -> &Match) {
    if key == Key::None {
        return;
    }
    if reverse {
        items.sort_by(|a, b| compare(key, get(b), get(a)));
    } else {
        items.sort_by(|a, b| compare(key, get(a), get(b)));
    }
}

/// How many of the most likely matches to show (`ranking.Top`): a number, a percentage, or
/// all of them.
#[derive(Debug, Clone, PartialEq, Eq, Default)]
pub enum Top {
    #[default]
    All,
    Number(usize),
    /// A percentage, as written (digits with an optional decimal point).
    Percent(String),
}

impl Top {
    /// `parse_top()`: "10", "5%", "1.5 %" or "all". `Err` holds Python's message.
    pub fn parse(text: &str) -> Result<Top, String> {
        let text = text.trim();
        let error = || {
            format!(
                "Invalid top '{text}', use a number of matches such as 10, a percentage of them \
                 such as 5% or all"
            )
        };
        if text.eq_ignore_ascii_case("all") {
            return Ok(Top::All);
        }
        if !text.is_empty() && text.bytes().all(|b| b.is_ascii_digit()) {
            // Any number of digits: a top larger than usize::MAX shows everything
            let significant = text.trim_start_matches('0');
            return if significant.is_empty() {
                Err(error())
            } else {
                Ok(Top::Number(significant.parse().unwrap_or(usize::MAX)))
            };
        }
        // ([0-9]+(?:\.[0-9]+)?|\.[0-9]+)\s*%
        let Some(number) = text.strip_suffix('%') else {
            return Err(error());
        };
        let number = number.trim_end();
        let valid = match number.split_once('.') {
            Some((whole, fraction)) => {
                whole.bytes().all(|b| b.is_ascii_digit())
                    && !fraction.is_empty()
                    && fraction.bytes().all(|b| b.is_ascii_digit())
            }
            None => !number.is_empty() && number.bytes().all(|b| b.is_ascii_digit()),
        };
        if !valid {
            return Err(error());
        }
        // 0 < percent <= 100, compared as a decimal of any length
        if !percent_in_range(number) {
            return Err(error());
        }
        Ok(Top::Percent(number.to_string()))
    }

    /// `Top.of()`: how many of `total` matches to show.
    pub fn of(&self, total: usize) -> usize {
        match self {
            Top::All => total,
            Top::Number(number) => (*number).min(total),
            Top::Percent(percent) => {
                // ceil(total * percent / 100), exact: with the first 30 significant digits
                // of the percentage, the error is below 1 match for any usize total, and
                // a nonzero rest still rounds up
                let (numerator, scale, rest) = decimal(percent);
                let denominator = 100 * 10u128.pow(scale);
                let product = (total as u128) * numerator;
                let mut shown = product.div_ceil(denominator);
                if rest && product.is_multiple_of(denominator) {
                    shown += 1;
                }
                usize::try_from(shown).unwrap_or(usize::MAX).min(total)
            }
        }
    }
}

/// A percentage such as "1.25" as (125, 2, false): its digits up to the 30th significant
/// one, the number of them after the point, and whether nonzero digits were cut off.
/// Percentages are at most 100, so 3 digits before the point and 27 after fit in a u128
/// whatever `total` is multiplied in.
fn decimal(text: &str) -> (u128, u32, bool) {
    let (whole, fraction) = text.split_once('.').unwrap_or((text, ""));
    let whole = whole.trim_start_matches('0');
    let kept = fraction.len().min(27);
    let digits = format!("{whole}{}", &fraction[..kept]);
    let numerator = if digits.is_empty() {
        0
    } else {
        digits.parse::<u128>().unwrap_or(u128::MAX)
    };
    let rest = fraction[kept..].bytes().any(|b| b != b'0');
    (numerator, kept as u32, rest)
}

/// Whether a decimal number (digits, an optional point and digits) is above 0 and at most
/// 100, whatever its length.
fn percent_in_range(text: &str) -> bool {
    let (whole, fraction) = text.split_once('.').unwrap_or((text, ""));
    let whole = whole.trim_start_matches('0');
    let fraction_nonzero = fraction.bytes().any(|b| b != b'0');
    if whole.is_empty() {
        return fraction_nonzero;
    }
    match whole.len() {
        1 | 2 => true,
        3 => whole < "100" || (whole == "100" && !fraction_nonzero),
        _ => false,
    }
}

/// `select()`: the `top` most likely items after the `start` most likely ones, most likely
/// first. With [`Top::All`], all items from `start`, in their order.
pub(crate) fn select<T: Clone>(
    found: &[T],
    top: &Top,
    start: usize,
    get: impl Fn(&T) -> &Match,
) -> Vec<T> {
    if *top == Top::All {
        return found.get(start..).map_or_else(Vec::new, <[T]>::to_vec);
    }
    let mut sorted: Vec<T> = found.to_vec();
    sorted.sort_by(|a, b| likelihood_order(get(a), get(b)));
    let count = top.of(found.len());
    sorted.into_iter().skip(start).take(count).collect()
}

/// The `top` most likely of the matches of one text, most likely first
/// (`top_matches()` for a single location).
pub fn top_matches(matches: &[Match], top: &Top) -> Vec<Match> {
    select(matches, top, 0, |m| m)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_top() {
        assert_eq!(Top::parse("10"), Ok(Top::Number(10)));
        assert_eq!(Top::parse(" ALL "), Ok(Top::All));
        assert_eq!(Top::parse("5%"), Ok(Top::Percent("5".into())));
        assert_eq!(Top::parse("1.5 %"), Ok(Top::Percent("1.5".into())));
        assert_eq!(Top::parse(".5%"), Ok(Top::Percent(".5".into())));
        for invalid in ["0", "0%", "150%", "-1", "1.%", "abc", "", "%"] {
            assert!(Top::parse(invalid).is_err(), "{invalid}");
        }
        assert!(Top::parse("100%").is_ok());
    }

    #[test]
    fn long_tops_like_python() {
        // Python's Decimal has no limit on the digits
        let tiny = format!(".{}1%", "0".repeat(38));
        assert!(Top::parse(&tiny).is_ok());
        assert_eq!(Top::parse(&tiny).unwrap().of(1000), 1);
        let almost_all = format!("99.{}%", "9".repeat(36));
        assert_eq!(Top::parse(&almost_all).unwrap().of(10), 10);
        assert!(Top::parse(&format!("100.{}1%", "0".repeat(40))).is_err());
        assert!(Top::parse(&format!("100.{}%", "0".repeat(40))).is_ok());
        assert_eq!(
            Top::parse(&"9".repeat(50)).unwrap(),
            Top::Number(usize::MAX)
        );
        assert_eq!(Top::parse("007"), Ok(Top::Number(7)));
        assert_eq!(Top::Percent("100".into()).of(usize::MAX), usize::MAX);
        assert_eq!(
            Top::Percent("0.5".into()).of(usize::MAX),
            usize::MAX / 200 + 1
        );
    }

    #[test]
    fn top_of() {
        assert_eq!(Top::Percent("1.1".into()).of(1000), 11);
        assert_eq!(Top::Percent("5".into()).of(3), 1);
        assert_eq!(Top::Percent("5".into()).of(0), 0);
        assert_eq!(Top::Number(10).of(3), 3);
        assert_eq!(Top::All.of(7), 7);
    }
}
