"""
Validation of Bitcoin addresses, see issue #239.

A regex can only check the characters and the length of an address, so it
also matches text like "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F". But every
Bitcoin address has a checksum, which wallets check to catch typing errors:

* P2PKH ("1...") and P2SH ("3...") addresses are Base58Check: a version byte
  and a 20 byte hash, followed by the first 4 bytes of their double SHA-256.
* SegWit addresses ("bc1...", or "tb1..." on testnet) are Bech32 (BIP 173)
  for witness version 0, and Bech32m (BIP 350), e.g. Taproot, for the others.
"""
import hashlib
from typing import List, Optional, Sequence, Tuple

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
# The version bytes of P2PKH ("1...") and P2SH ("3...") addresses
BASE58_VERSIONS = (0x00, 0x05)

BECH32_CHARSET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
BECH32_CONST = 1
BECH32M_CONST = 0x2BC830A3
BECH32_GENERATOR = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)
# The human-readable parts of SegWit addresses on mainnet and testnet
SEGWIT_HRPS = ("bc", "tb")


def base58_decode(text: str) -> bytes:
    """Decode Base58 text. Raises ValueError if it is not Base58."""
    number = 0
    for char in text:
        digit = BASE58_ALPHABET.find(char)
        if digit < 0:
            raise ValueError(f"{char!r} is not a Base58 character")
        number = number * 58 + digit
    # Every leading "1" stands for a leading zero byte
    zeros = len(text) - len(text.lstrip(BASE58_ALPHABET[0]))
    return bytes(zeros) + number.to_bytes((number.bit_length() + 7) // 8, "big")


def base58check_decode(text: str) -> Optional[bytes]:
    """The payload of Base58Check text, or None if its checksum is wrong."""
    try:
        decoded = base58_decode(text)
    except ValueError:
        return None
    if len(decoded) < 4:
        return None
    payload, checksum = decoded[:-4], decoded[-4:]
    if hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4] != checksum:
        return None
    return payload


def bech32_polymod(values: Sequence[int]) -> int:
    """The checksum of Bech32 and Bech32m, a BCH code (BIP 173)."""
    checksum = 1
    for value in values:
        top = checksum >> 25
        checksum = (checksum & 0x1FFFFFF) << 5 ^ value
        for i, generator in enumerate(BECH32_GENERATOR):
            if (top >> i) & 1:
                checksum ^= generator
    return checksum


def bech32_hrp_expand(hrp: str) -> List[int]:
    """The human-readable part of Bech32 text, as checksummed (BIP 173)."""
    return [ord(char) >> 5 for char in hrp] + [0] + [ord(char) & 31 for char in hrp]


def convert_bits(
    data: Sequence[int], from_bits: int, to_bits: int
) -> Optional[List[int]]:
    """
    Regroup data, a sequence of from_bits-bit integers, into to_bits-bit
    integers. None if what is left over is not a zero padding of less than
    from_bits bits (BIP 173).
    """
    accumulator = 0
    bits = 0
    result = []
    max_value = (1 << to_bits) - 1
    max_accumulator = (1 << (from_bits + to_bits - 1)) - 1
    for value in data:
        accumulator = ((accumulator << from_bits) | value) & max_accumulator
        bits += from_bits
        while bits >= to_bits:
            bits -= to_bits
            result.append((accumulator >> bits) & max_value)
    if bits >= from_bits or (accumulator << (to_bits - bits)) & max_value:
        return None
    return result


def segwit_decode(address: str) -> Optional[Tuple[str, int, bytes]]:
    """
    The human-readable part, the witness version and the witness program of a
    SegWit address, or None if it is not one (BIP 173 and BIP 350).
    """
    if len(address) > 90 or any(not 33 <= ord(char) <= 126 for char in address):
        return None
    if address.lower() != address and address.upper() != address:
        return None  # mixed case
    hrp, separator, data_part = address.lower().rpartition("1")
    # At least a witness version and the 6 characters of the checksum
    if not separator or not hrp or len(data_part) < 7:
        return None
    if any(char not in BECH32_CHARSET for char in data_part):
        return None
    data = [BECH32_CHARSET.index(char) for char in data_part]
    version = data[0]
    if version > 16:
        return None
    # Version 0 uses Bech32 and the others Bech32m (BIP 350)
    const = BECH32_CONST if version == 0 else BECH32M_CONST
    if bech32_polymod(bech32_hrp_expand(hrp) + data) != const:
        return None
    program = convert_bits(data[1:-6], 5, 8)
    if program is None or not 2 <= len(program) <= 40:
        return None
    if version == 0 and len(program) not in (20, 32):
        return None
    return hrp, version, bytes(program)


def is_bitcoin_address(address: str) -> bool:
    """
    Whether address is a Bitcoin address with a valid checksum: a P2PKH
    ("1...") or P2SH ("3...") address, or a SegWit address on mainnet
    ("bc1...") or testnet ("tb1...").
    """
    if address[:3].lower() in ("bc1", "tb1"):
        decoded = segwit_decode(address)
        return decoded is not None and decoded[0] in SEGWIT_HRPS
    payload = base58check_decode(address)
    return payload is not None and len(payload) == 21 and payload[0] in BASE58_VERSIONS
