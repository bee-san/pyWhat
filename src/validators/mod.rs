//! Checksums of the formats that have one, a port of `pywhat/validators/`. A regex names
//! its validator in its `"Validator"` in the regex files, and
//! [`crate::processors::Validator`] filters out the matches that fail it.

use crate::bitcoin::base58check_decode;

const BASE58_ALPHABET: &str = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const RIPPLE_ALPHABET: &str = "rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz";
const BECH32_CHARSET: &str = "qpzry9x8gf2tvdw0s3jn54khce6mua7l";
/// The prefixes of CashAddr addresses on mainnet, testnet and regtest.
const CASHADDR_PREFIXES: [&str; 3] = ["bitcoincash", "bchtest", "bchreg"];
const CASHADDR_GENERATOR: [u64; 5] = [
    0x98_F2BC_8E61,
    0x79_B76D_99E2,
    0xF3_3E5F_B3C4,
    0xAE_2EAB_E2A8,
    0x1E_4F43_E470,
];

/// The validator called `name` in the regex files, if there is one.
pub fn validator(name: &str) -> Option<fn(&str) -> bool> {
    Some(match name {
        "luhn" => luhn,
        "base58check" => base58check,
        "ripple-base58check" => ripple_base58check,
        "cashaddr" => cashaddr,
        "tc-kimlik" => tc_kimlik,
        "facebook-access-token" => facebook_access_token,
        _ => return area_validator(name),
    })
}

/// A table of validators: their names in the regex files, and their functions.
type Table = &'static [(&'static str, fn(&str) -> bool)];

// The validators of the regexes of each area (docs/adding-regexes.md) are in the module of
// the area, src/validators/<area>.rs, so that pull requests for different areas change
// different files.
mod cloud;
mod crypto;
mod ctf;
mod files;
mod ids;
mod network;
mod social;

fn area_validator(name: &str) -> Option<fn(&str) -> bool> {
    crypto::validator(name)
        .or_else(|| cloud::validator(name))
        .or_else(|| ctf::validator(name))
        .or_else(|| network::validator(name))
        .or_else(|| ids::validator(name))
        .or_else(|| files::validator(name))
        .or_else(|| social::validator(name))
}

/// The Luhn check of payment card numbers. Whitespace and dashes between the digits are
/// ignored; anything else that isn't an ASCII digit fails.
pub fn luhn(number: &str) -> bool {
    let mut total = 0;
    let mut count = 0;
    for c in number.chars().rev() {
        if c.is_ascii_digit() {
            let mut digit = c as u32 - '0' as u32;
            if count % 2 == 1 {
                digit *= 2;
                if digit > 9 {
                    digit -= 9;
                }
            }
            total += digit;
            count += 1;
        } else if !(is_python_space(c) || c == '-') {
            return false;
        }
    }
    count > 0 && total % 10 == 0
}

/// Python's `str.isspace()`.
fn is_python_space(c: char) -> bool {
    matches!(
        c,
        '\t' | '\n'
            | '\u{b}'
            | '\u{c}'
            | '\r'
            | '\u{1c}'..='\u{1f}'
            | ' '
            | '\u{85}'
            | '\u{a0}'
            | '\u{1680}'
            | '\u{2000}'..='\u{200a}'
            | '\u{2028}'
            | '\u{2029}'
            | '\u{202f}'
            | '\u{205f}'
            | '\u{3000}'
    )
}

/// Base58Check of a version byte and a 20 byte hash (P2PKH and P2SH addresses).
pub fn base58check(address: &str) -> bool {
    base58check_decode(address).is_some_and(|payload| payload.len() == 21)
}

/// Base58Check in Ripple's alphabet, of a version byte and a 20 byte hash (XRP addresses).
pub fn ripple_base58check(address: &str) -> bool {
    let translated: Option<String> = address
        .chars()
        .map(|c| {
            RIPPLE_ALPHABET
                .chars()
                .position(|r| r == c)
                .and_then(|i| BASE58_ALPHABET.chars().nth(i))
        })
        .collect();
    translated.is_some_and(|address| base58check(&address))
}

fn cashaddr_polymod(values: impl Iterator<Item = u8>) -> u64 {
    let mut checksum: u64 = 1;
    for value in values {
        let top = checksum >> 35;
        checksum = ((checksum & 0x07_FFFF_FFFF) << 5) ^ u64::from(value);
        for (i, generator) in CASHADDR_GENERATOR.iter().enumerate() {
            if (top >> i) & 1 == 1 {
                checksum ^= generator;
            }
        }
    }
    checksum ^ 1
}

/// A CashAddr address (Bitcoin Cash) with a valid checksum, with or without its prefix
/// (`bitcoincash:`, `bchtest:` or `bchreg:`; without one, any of them).
pub fn cashaddr(address: &str) -> bool {
    if !address.is_ascii() {
        return false; // e.g. the Kelvin sign, which lowercases to k
    }
    let lower = address.to_lowercase();
    if lower != address && address.to_uppercase() != address {
        return false; // mixed case
    }
    let (prefixes, payload): (Vec<&str>, &str) = match lower.rsplit_once(':') {
        Some((prefix, payload)) => (vec![prefix], payload),
        None => (CASHADDR_PREFIXES.to_vec(), lower.as_str()),
    };
    let Some(data) = payload
        .chars()
        .map(|c| BECH32_CHARSET.chars().position(|b| b == c).map(|i| i as u8))
        .collect::<Option<Vec<u8>>>()
    else {
        return false;
    };
    if data.len() < 8 {
        return false;
    }
    prefixes.iter().any(|prefix| {
        let values = prefix
            .chars()
            .map(|c| (c as u32 & 31) as u8)
            .chain(std::iter::once(0))
            .chain(data.iter().copied());
        cashaddr_polymod(values) == 0
    })
}

/// A Turkish Identification Number with valid check digits.
pub fn tc_kimlik(number: &str) -> bool {
    let digits: Vec<u32> = number.chars().filter_map(|c| c.to_digit(10)).collect();
    if number.len() != 11 || digits.len() != 11 || !number.is_ascii() || digits[0] == 0 {
        return false;
    }
    let odd: u32 = digits[0..9].iter().step_by(2).sum();
    let even: u32 = digits[1..8].iter().step_by(2).sum();
    (odd * 7 + 1000 - even) % 10 == digits[9] && digits[..10].iter().sum::<u32>() % 10 == digits[10]
}

/// Whether the random part of a Facebook access token, after its `EA`, has an ASCII lowercase
/// letter, an uppercase letter and a digit, as 190 or more random letters and digits have.
/// Decoder output is often all one case.
pub fn facebook_access_token(token: &str) -> bool {
    let rest = token.get(2..).unwrap_or("");
    rest.bytes().any(|b| b.is_ascii_lowercase())
        && rest.bytes().any(|b| b.is_ascii_uppercase())
        && rest.bytes().any(|b| b.is_ascii_digit())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn validators() {
        assert!(
            luhn("4111111111111111") && luhn("4111 1111 1111 1111") && luhn("4111-1111-1111-1111")
        );
        assert!(!luhn("4111111111111112") && !luhn("") && !luhn("41x1") && !luhn("  "));
        assert!(tc_kimlik("10000000146") && !tc_kimlik("12345678902") && !tc_kimlik("02345678902"));
        assert!(base58check("DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o"));
        assert!(base58check("LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m"));
        assert!(!base58check("LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7n"));
        assert!(ripple_base58check("rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"));
        assert!(!ripple_base58check("rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkl"));
        assert!(cashaddr(
            "bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"
        ));
        assert!(cashaddr("qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"));
        assert!(cashaddr(
            "BITCOINCASH:QZLG6UVCEEHGZGTZ6PHMVY8GTDQYT6VF359AT4N3LQ"
        ));
        assert!(!cashaddr("qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lr"));
        assert!(!cashaddr(
            "bitcoincash:Qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"
        ));
        assert!(facebook_access_token("EAARE0ZATe") && !facebook_access_token("EAHCHERBOTIC"));
        assert!(!facebook_access_token("EA0123ABCDEF"));
        // The EA prefix doesn't count as the upper-case letter
        assert!(!facebook_access_token("EAabcdef0123"));
        assert!(!cashaddr(
            "BITCOINCASH:QPM2QSZNH\u{212a}S23Z7629MMS6S4CWEF74VCWVY22GDX6A"
        ));
        assert!(cashaddr(
            "BITCOINCASH:QPM2QSZNHKS23Z7629MMS6S4CWEF74VCWVY22GDX6A"
        ));
        assert!(validator("luhn").is_some() && validator("nope").is_none());
    }
}
