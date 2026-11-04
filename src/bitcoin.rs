//! Validation of Bitcoin addresses by their checksums, a port of `pywhat/bitcoin.py`.
//!
//! * P2PKH (`1...`) and P2SH (`3...`) addresses are Base58Check: a version byte and a 20 byte
//!   hash, followed by the first 4 bytes of their double SHA-256.
//! * SegWit addresses (`bc1...`, or `tb1...` on testnet) are Bech32 (BIP 173) for witness
//!   version 0, and Bech32m (BIP 350) for the others.

use sha2::{Digest, Sha256};

const BASE58_ALPHABET: &[u8] = b"123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
/// The version bytes of P2PKH (`1...`) and P2SH (`3...`) addresses.
const BASE58_VERSIONS: [u8; 2] = [0x00, 0x05];

const BECH32_CHARSET: &[u8] = b"qpzry9x8gf2tvdw0s3jn54khce6mua7l";
const BECH32_CONST: u32 = 1;
const BECH32M_CONST: u32 = 0x2BC8_30A3;
const BECH32_GENERATOR: [u32; 5] = [
    0x3B6A_57B2,
    0x2650_8E6D,
    0x1EA1_19FA,
    0x3D42_33DD,
    0x2A14_62B3,
];
/// The human-readable parts of SegWit addresses on mainnet and testnet.
const SEGWIT_HRPS: [&str; 2] = ["bc", "tb"];

/// Decodes Base58 text, or `None` if it isn't Base58.
pub(crate) fn base58_decode(text: &str) -> Option<Vec<u8>> {
    // Big-endian base-256 digits of the number
    let mut number: Vec<u8> = Vec::new();
    for c in text.bytes() {
        let digit = BASE58_ALPHABET.iter().position(|&b| b == c)? as u32;
        let mut carry = digit;
        for byte in number.iter_mut().rev() {
            let value = u32::from(*byte) * 58 + carry;
            *byte = (value & 0xFF) as u8;
            carry = value >> 8;
        }
        while carry > 0 {
            number.insert(0, (carry & 0xFF) as u8);
            carry >>= 8;
        }
    }
    // Every leading "1" stands for a leading zero byte
    let zeros = text.bytes().take_while(|&b| b == b'1').count();
    let leading = number.iter().take_while(|&&b| b == 0).count();
    let mut decoded = vec![0u8; zeros];
    decoded.extend_from_slice(&number[leading..]);
    Some(decoded)
}

/// The payload of Base58Check text, or `None` if its checksum is wrong.
pub(crate) fn base58check_decode(text: &str) -> Option<Vec<u8>> {
    let decoded = base58_decode(text)?;
    if decoded.len() < 4 {
        return None;
    }
    let (payload, checksum) = decoded.split_at(decoded.len() - 4);
    let hash = Sha256::digest(Sha256::digest(payload));
    (&hash[..4] == checksum).then(|| payload.to_vec())
}

fn bech32_polymod(values: &[u8]) -> u32 {
    let mut checksum: u32 = 1;
    for &value in values {
        let top = checksum >> 25;
        checksum = ((checksum & 0x1FF_FFFF) << 5) ^ u32::from(value);
        for (i, generator) in BECH32_GENERATOR.iter().enumerate() {
            if (top >> i) & 1 == 1 {
                checksum ^= generator;
            }
        }
    }
    checksum
}

fn bech32_hrp_expand(hrp: &str) -> Vec<u8> {
    let mut expanded: Vec<u8> = hrp.bytes().map(|b| b >> 5).collect();
    expanded.push(0);
    expanded.extend(hrp.bytes().map(|b| b & 31));
    expanded
}

/// Regroups `from_bits`-bit integers into `to_bits`-bit integers; `None` if what is left
/// over isn't a zero padding of less than `from_bits` bits (BIP 173).
fn convert_bits(data: &[u8], from_bits: u32, to_bits: u32) -> Option<Vec<u8>> {
    let mut accumulator: u32 = 0;
    let mut bits: u32 = 0;
    let mut result = Vec::new();
    let max_value = (1u32 << to_bits) - 1;
    let max_accumulator = (1u32 << (from_bits + to_bits - 1)) - 1;
    for &value in data {
        accumulator = ((accumulator << from_bits) | u32::from(value)) & max_accumulator;
        bits += from_bits;
        while bits >= to_bits {
            bits -= to_bits;
            result.push(((accumulator >> bits) & max_value) as u8);
        }
    }
    if bits >= from_bits || (accumulator << (to_bits - bits)) & max_value != 0 {
        return None;
    }
    Some(result)
}

/// The human-readable part, witness version and witness program of a SegWit address.
fn segwit_decode(address: &str) -> Option<(String, u8, Vec<u8>)> {
    if address.chars().count() > 90 || address.chars().any(|c| !(33..=126).contains(&(c as u32))) {
        return None;
    }
    let lower = address.to_lowercase();
    if lower != address && address.to_uppercase() != address {
        return None; // mixed case
    }
    let (hrp, data_part) = lower.rsplit_once('1')?;
    // At least a witness version and the 6 characters of the checksum
    if hrp.is_empty() || data_part.len() < 7 {
        return None;
    }
    let data: Vec<u8> = data_part
        .bytes()
        .map(|b| BECH32_CHARSET.iter().position(|&c| c == b).map(|i| i as u8))
        .collect::<Option<_>>()?;
    let version = data[0];
    if version > 16 {
        return None;
    }
    // Version 0 uses Bech32 and the others Bech32m (BIP 350)
    let constant = if version == 0 {
        BECH32_CONST
    } else {
        BECH32M_CONST
    };
    let mut values = bech32_hrp_expand(hrp);
    values.extend_from_slice(&data);
    if bech32_polymod(&values) != constant {
        return None;
    }
    let program = convert_bits(&data[1..data.len() - 6], 5, 8)?;
    if !(2..=40).contains(&program.len()) || (version == 0 && ![20, 32].contains(&program.len())) {
        return None;
    }
    Some((hrp.to_string(), version, program))
}

/// Whether `address` is a Bitcoin address with a valid checksum: P2PKH (`1...`), P2SH
/// (`3...`), or SegWit on mainnet (`bc1...`) or testnet (`tb1...`).
pub fn is_bitcoin_address(address: &str) -> bool {
    // The longest address is 90 characters (BIP 173); longer text isn't one, and decoding
    // it would take time quadratic in its length
    if address.len() > 90 {
        return false;
    }
    let start: String = address.chars().take(3).collect::<String>().to_lowercase();
    if start == "bc1" || start == "tb1" {
        return segwit_decode(address)
            .is_some_and(|(hrp, _, _)| SEGWIT_HRPS.contains(&hrp.as_str()));
    }
    base58check_decode(address)
        .is_some_and(|payload| payload.len() == 21 && BASE58_VERSIONS.contains(&payload[0]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn addresses() {
        // From tests/test_bitcoin.py and BIP 173/350
        for valid in [
            "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY",
            "3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5",
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4",
            "bc1p5d7rjq7g6rdk2yhzks9smlaqtedr4dekq08ge8ztwac72sfr9rusxg3297",
            "tb1qw508d6qejxtdg4y5r3zarvary0c5xw7kxpjzsx",
        ] {
            assert!(is_bitcoin_address(valid), "{valid}");
        }
        for invalid in [
            "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F",
            "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYZ",
            "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdr",
            "bC1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq",
            "",
            "1",
        ] {
            assert!(!is_bitcoin_address(invalid), "{invalid}");
        }
    }

    #[test]
    fn base58_leading_zeros() {
        assert_eq!(base58_decode("111").unwrap(), vec![0, 0, 0]);
        assert_eq!(base58_decode("2").unwrap(), vec![1]);
        assert_eq!(base58_decode("1112").unwrap(), vec![0, 0, 0, 1]);
        assert!(base58_decode("0").is_none());
    }
}
