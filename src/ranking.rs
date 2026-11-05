//! Sorting the matches, and only the most likely ones: a port of `pywhat.helper.Keys` and
//! `pywhat/ranking.py`.

use crate::identify::Match;
use crate::validators::is_python_space;
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
    /// A percentage, as written (digits with an optional decimal point), as [`Top::parse`]
    /// returns it. [`Top::of`] shows all matches for a text that isn't such a number.
    Percent(String),
}

impl Top {
    /// `parse_top()`: "10", "5%", "1.5 %" or "all". `Err` holds Python's message.
    pub fn parse(text: &str) -> Result<Top, String> {
        // str.strip() and \s: Python's whitespace, which includes U+001C to U+001F
        let text = text.trim_matches(is_python_space);
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
        let number = number.trim_end_matches(is_python_space);
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
            Top::Percent(percent) => percent_of(total, percent),
        }
    }
}

/// `min(total, math.ceil(total * percent / 100))` as Python computes it: `Decimal` rounds the
/// product to 28 significant digits (its default context, half to even), and the division by
/// 100 and the ceiling are exact. A `percent` that isn't digits with an optional point shows
/// all matches.
fn percent_of(total: usize, percent: &str) -> usize {
    let (whole, fraction) = percent.split_once('.').unwrap_or((percent, ""));
    let is_digits = |part: &str| part.bytes().all(|b| b.is_ascii_digit());
    if whole.is_empty() && fraction.is_empty() || !is_digits(whole) || !is_digits(fraction) {
        return total;
    }
    // total × percent × 10^scale, exactly, as decimal digits
    let product = times(&format!("{whole}{fraction}"), total as u64);
    let product = product.trim_start_matches('0');
    if product.is_empty() {
        return 0;
    }
    let (kept, dropped) = product.split_at(product.len().min(28));
    let mut coefficient: u128 = kept.parse().expect("at most 28 digits");
    let half = match dropped.as_bytes().first() {
        None => Ordering::Less,
        Some(&first) => match first.cmp(&b'5') {
            Ordering::Equal if dropped[1..].bytes().any(|b| b != b'0') => Ordering::Greater,
            order => order,
        },
    };
    if half == Ordering::Greater || half == Ordering::Equal && coefficient % 2 == 1 {
        coefficient += 1;
    }
    // The rounded product is coefficient × 10^(dropped − scale); divided by 100, rounded up
    let exponent = dropped.len() as i64 - fraction.len() as i64 - 2;
    let shown = if exponent >= 0 {
        u32::try_from(exponent)
            .ok()
            .and_then(|e| 10u128.checked_pow(e))
            .and_then(|power| coefficient.checked_mul(power))
            .unwrap_or(u128::MAX)
    } else {
        match u32::try_from(-exponent)
            .ok()
            .and_then(|e| 10u128.checked_pow(e))
        {
            Some(power) => coefficient.div_ceil(power),
            // 10^39 or more: above the coefficient, which is not 0
            None => 1,
        }
    };
    usize::try_from(shown).unwrap_or(usize::MAX).min(total)
}

/// The decimal digits of `digits × by`.
fn times(digits: &str, by: u64) -> String {
    let mut out = Vec::with_capacity(digits.len() + 20);
    let mut carry: u128 = 0;
    for digit in digits.bytes().rev() {
        let value = u128::from(digit - b'0') * u128::from(by) + carry;
        out.push(b'0' + (value % 10) as u8);
        carry = value / 10;
    }
    while carry > 0 {
        out.push(b'0' + (carry % 10) as u8);
        carry /= 10;
    }
    out.reverse();
    String::from_utf8(out).expect("digits")
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
        // Python parses a percentage of any length; Top.of() rounds total × percent to 28
        // significant digits (Decimal's default context)
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
    fn percentages_of_like_python() {
        let of = |percent: &str, total| Top::parse(percent).unwrap().of(total);
        // Exact where 28 digits are enough, also for the largest totals
        assert_eq!(of("50.000000000000000000%", usize::MAX), usize::MAX / 2 + 1);
        assert_eq!(of("1.5000000000000000000000000001%", 999), 15);
        assert_eq!(of("33.333333333333333333334%", 3), 2);
        // Where they aren't, Python's rounding: 3 × 33.33…334 = 100.00…002 has 31 digits,
        // and rounds to 100
        assert_eq!(of("33.3333333333333333333333333334%", 3), 1);
        assert_eq!(of("1.0000000000000000000000000001%", 100), 1);
        assert_eq!(of("1.0000000000000000000000000001%", 1_000_000), 10_000);
        // Ties round to even: 100 × 1.00…005 keeps 28 digits, 100.0…00 (even), and
        // 100 × 1.00…015 becomes 100.0…02 (from the odd …01)
        assert_eq!(of("1.0000000000000000000000000005%", 100), 1);
        assert_eq!(of("1.0000000000000000000000000015%", 100), 2);
        // str.strip() and \s are Python's whitespace, U+001C to U+001F included
        assert_eq!(Top::parse("\u{1c}5%"), Ok(Top::Percent("5".into())));
        assert_eq!(Top::parse("5\u{1f}%"), Ok(Top::Percent("5".into())));
        assert_eq!(Top::parse("5\u{3000}%"), Ok(Top::Percent("5".into())));
        // A Percent that parse() doesn't return shows everything, without a panic
        for odd in ["\u{e9}5", "", ".", "5..5", "x"] {
            assert_eq!(Top::Percent(odd.into()).of(10), 10, "{odd:?}");
        }
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
