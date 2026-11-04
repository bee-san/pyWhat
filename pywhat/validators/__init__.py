"""
Checksums of the formats that have one.

A regex can only check which characters a match has and how long it is, so it also
matches random text with the right characters: 1 in 10 random 16-digit numbers that start
with 4 are Visa card numbers to a regex. The formats below have a checksum, which a match
must pass. A regex says which one in its "Validator" in regex.json, and
pywhat.processors.ValidatorProcessor filters out the matches whose checksum is wrong.

* luhn: the Luhn algorithm (ISO/IEC 7812) of payment card numbers, 1 in 10 random numbers
  pass it.
* base58check: Base58Check with a version byte and a 20 byte hash, like Bitcoin's P2PKH
  and P2SH addresses (Dogecoin, Litecoin), 1 in 2**32 random strings pass it.
* ripple-base58check: the same with Ripple's Base58 alphabet (XRP addresses).
* cashaddr: Bitcoin Cash's CashAddr, a BCH code with 40 check bits.
* tc-kimlik: the two check digits of a Turkish Identification Number, 1 in 100.
* facebook-access-token: not a checksum, but what the random part of a Facebook access
  token (after its EA) has: an ASCII lowercase letter, an uppercase letter and a digit
  (issue #1104 of bee-san/Ciphey).
"""
from typing import Callable, Dict, Sequence

from pywhat.bitcoin import BASE58_ALPHABET, BECH32_CHARSET, base58check_decode

RIPPLE_ALPHABET = "rpshnaf39wBUDNEGHJKLM4PQRST7VWXYZ2bcdeCg65jkm8oFqi1tuvAxyz"
_RIPPLE_TO_BITCOIN = str.maketrans(RIPPLE_ALPHABET, BASE58_ALPHABET)

# The prefixes of CashAddr addresses on mainnet, testnet and regtest
CASHADDR_PREFIXES = ("bitcoincash", "bchtest", "bchreg")
_CASHADDR_GENERATOR = (
    0x98F2BC8E61,
    0x79B76D99E2,
    0xF33E5FB3C4,
    0xAE2EABE2A8,
    0x1E4F43E470,
)


def luhn(number: str) -> bool:
    """
    Whether number passes the Luhn check. Spaces and dashes between the digits are
    ignored, anything else that isn't an ASCII digit fails.
    """
    digits = []
    for char in number:
        if "0" <= char <= "9":
            digits.append(int(char))
        elif not char.isspace() and char != "-":
            return False
    if not digits:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def facebook_access_token(token: str) -> bool:
    """
    Whether the random part of a Facebook access token, after its "EA", has an ASCII
    lowercase letter, an uppercase letter and a digit, as 190 or more random letters and
    digits have (the chance that they have no digit is under 1 in 10**14). Decoder output
    is often all one case.
    """
    rest = token[2:]
    return (
        any("a" <= char <= "z" for char in rest)
        and any("A" <= char <= "Z" for char in rest)
        and any("0" <= char <= "9" for char in rest)
    )


def base58check(address: str) -> bool:
    """Whether address is Base58Check of a version byte and a 20 byte hash."""
    payload = base58check_decode(address)
    return payload is not None and len(payload) == 21


def ripple_base58check(address: str) -> bool:
    """Whether address is Base58Check, in Ripple's alphabet, of a version and a hash."""
    if any(char not in RIPPLE_ALPHABET for char in address):
        return False
    return base58check(address.translate(_RIPPLE_TO_BITCOIN))


def _cashaddr_polymod(values: Sequence[int]) -> int:
    checksum = 1
    for value in values:
        top = checksum >> 35
        checksum = ((checksum & 0x07FFFFFFFF) << 5) ^ value
        for i, generator in enumerate(_CASHADDR_GENERATOR):
            if (top >> i) & 1:
                checksum ^= generator
    return checksum ^ 1


def cashaddr(address: str) -> bool:
    """
    Whether address is a CashAddr address with a valid checksum, with or without its
    prefix (bitcoincash:, bchtest: or bchreg:; without one, any of them).
    """
    if not address.isascii():
        return False  # e.g. the Kelvin sign, which lower() turns into k
    if address.lower() != address and address.upper() != address:
        return False  # mixed case
    address = address.lower()
    prefix, separator, payload = address.rpartition(":")
    prefixes = (prefix,) if separator else CASHADDR_PREFIXES
    if any(char not in BECH32_CHARSET for char in payload) or len(payload) < 8:
        return False
    data = [BECH32_CHARSET.index(char) for char in payload]
    return any(
        _cashaddr_polymod([ord(char) & 31 for char in prefix] + [0] + data) == 0
        for prefix in prefixes
    )


def tc_kimlik(number: str) -> bool:
    """Whether number is a Turkish Identification Number with valid check digits."""
    if len(number) != 11 or any(not "0" <= char <= "9" for char in number):
        return False
    digits = [int(char) for char in number]
    if digits[0] == 0:
        return False
    odd = sum(digits[0:9:2])
    even = sum(digits[1:8:2])
    return (odd * 7 - even) % 10 == digits[9] and sum(digits[:10]) % 10 == digits[10]


# The validators that the regex files can name in a regex's "Validator"
VALIDATORS: Dict[str, Callable[[str], bool]] = {
    "luhn": luhn,
    "base58check": base58check,
    "ripple-base58check": ripple_base58check,
    "cashaddr": cashaddr,
    "tc-kimlik": tc_kimlik,
    "facebook-access-token": facebook_access_token,
}

# The validators of the regexes of each area (docs/adding-regexes.md) are in the module of the
# area, pywhat/validators/<area>.py, so that pull requests for different areas change
# different files.
from pywhat.validators import (  # noqa: E402
    cloud,
    crypto,
    ctf,
    files,
    ids,
    network,
    social,
)

for _area in (crypto, cloud, ctf, network, ids, files, social):
    for _name in _area.VALIDATORS:
        assert _name not in VALIDATORS, f"two validators are called {_name}"
    VALIDATORS.update(_area.VALIDATORS)
