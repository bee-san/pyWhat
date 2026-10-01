"""
Tests for the validation of Bitcoin wallet addresses (issue #239).

The Bitcoin regex can only check the characters and the length of an address,
so BitcoinAddressProcessor filters out the matches whose checksum is wrong.
The test vectors are from Bitcoin Core (Base58), BIP 173 and BIP 350.
"""
import time
from typing import Optional

import pytest
from click.testing import CliRunner

from pywhat import Distribution, Filter, Identifier
from pywhat.bitcoin import (
    BECH32_CHARSET,
    base58_decode,
    base58check_decode,
    convert_bits,
    is_bitcoin_address,
    segwit_decode,
)
from pywhat.processors import BitcoinAddressProcessor
from pywhat.what import main

BITCOIN = "Bitcoin (\u20bf) Wallet Address"
BITCOIN_ONLY = Distribution(Filter({"Tags": ["Bitcoin Wallet"]}))
# The false positive of issue #239
ISSUE = "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F"

VALID_ADDRESSES = [
    # P2PKH, including the address of the genesis block and the shortest one
    "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY",
    "1111111111111111111114oLvT2",
    # P2SH
    "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
    "3EmUH8Uh9EXE7axgyAeBsCc2vdUdKkDqWK",
    # P2WPKH and P2WSH (SegWit version 0, Bech32)
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
    "bc1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3qccfmv3",
    "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7",
    # P2TR (Taproot, SegWit version 1, Bech32m)
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
    "tb1pqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesf3hn0c",
]

# Matched by the regex, but not Bitcoin addresses
WRONG_CHECKSUMS = [
    ISSUE,
    "1111111111111111111111111111111111",
    "1AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    # One character changed
    "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYZ",
    "3EmUH8Uh9EXE7axgyAeBsCc2vdUdKkDqWk",
    "bc1qj89046x7zv6pm4n00qgqp505nvljnfp6xfznyq",
    # Bech32m instead of Bech32, and the other way around (BIP 350)
    "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh",
    "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd",
    "tb1q0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq24jc47",
    # A valid Base58Check checksum, but version 6, or a 21 byte hash
    "3R2e7gNMbRpjEZu5DCiLWBH8siHBC8immQ",
    "1QXEx2ZQ9mEdvMSaVKHznFv6iZq2LQbDz8",
]


def bitcoin_matches(text: str, **identify_options) -> list:
    """The Bitcoin addresses that pyWhat finds in text (boundaryless)."""
    identifier = Identifier(dist=BITCOIN_ONLY, boundaryless=Filter())
    identified = identifier.identify(text, **identify_options)
    return [
        match["Matched"]
        for matches in (identified["Regexes"] or {}).values()
        for match in matches
        if match["Regex Pattern"]["Name"] == BITCOIN
    ]


def run_cli(args: list) -> str:
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    return result.output


# Base58Check


@pytest.mark.parametrize(
    "data, text",
    [
        ("", ""),
        ("61", "2g"),
        ("626262", "a3gV"),
        ("73696d706c792061206c6f6e6720737472696e67", "2cFupjhnEsSn59qHXstmK2ffpLv2"),
        (
            "00eb15231dfceb60925886b67d065299925915aeb172c06647",
            "1NS17iag9jJgTHD1VXjvLCEnZuQ3rJDE9L",
        ),
        ("00000000000000000000", "1111111111"),
        ("271f359f", "zzzzz"),
        ("271f35a0", "211111"),
    ],
)
def test_base58_decode(data, text):
    assert base58_decode(text) == bytes.fromhex(data)


@pytest.mark.parametrize(
    "text", ["0", "O", "I", "l", "1KFHE7w8BhaENAswwryaoccDb6qcT6DbY+"]
)
def test_base58_decode_rejects_other_characters(text):
    with pytest.raises(ValueError):
        base58_decode(text)


def test_base58check_decode():
    assert base58check_decode("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa") == bytes.fromhex(
        "0062e907b15cbf27d5425399ebf6f0fb50ebb88f18"
    )
    assert base58check_decode("3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy") == bytes.fromhex(
        "05b472a266d0bd89c13706a4132ccfb16f7c3b9fcb"
    )


@pytest.mark.parametrize("text", [ISSUE, "", "1", "2g", "zzzzz", "0x52908400098527"])
def test_base58check_decode_wrong_checksums(text):
    assert base58check_decode(text) is None


# Bech32 and Bech32m


@pytest.mark.parametrize(
    "address, hrp, version, program",
    [
        (
            "BC1QW508D6QEJXTDG4Y5R3ZARVARY0C5XW7KV8F3T4",
            "bc",
            0,
            "751e76e8199196d454941c45d1b3a323f1433bd6",
        ),
        (
            "tb1qrp33g0q5c5txsp9arysrx4k6zdkfs4nce4xj0gdcccefvpysxf3q0sl5k7",
            "tb",
            0,
            "1863143c14c5166804bd19203356da136c985678cd4d27a1b8c6329604903262",
        ),
        (
            "bc1pw508d6qejxtdg4y5r3zarvary0c5xw7kw508d6qejxtdg4y5r3zarvary0c5xw7kt5nd6y",
            "bc",
            1,
            "751e76e8199196d454941c45d1b3a323f1433bd6"
            "751e76e8199196d454941c45d1b3a323f1433bd6",
        ),
        ("BC1SW50QGDZ25J", "bc", 16, "751e"),
        (
            "bc1zw508d6qejxtdg4y5r3zarvaryvaxxpcs",
            "bc",
            2,
            "751e76e8199196d454941c45d1b3a323",
        ),
        (
            "tb1qqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesrxh6hy",
            "tb",
            0,
            "000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
        ),
        (
            "tb1pqqqqp399et2xygdj5xreqhjjvcmzhxw4aywxecjdzew6hylgvsesf3hn0c",
            "tb",
            1,
            "000000c4a5cad46221b2a187905e5266362b99d5e91c6ce24d165dab93e86433",
        ),
        (
            "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0",
            "bc",
            1,
            "79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798",
        ),
    ],
)
def test_segwit_decode(address, hrp, version, program):
    assert segwit_decode(address) == (hrp, version, bytes.fromhex(program))
    assert is_bitcoin_address(address)


@pytest.mark.parametrize(
    "address",
    [
        # Bech32 instead of Bech32m
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqh2y7hd",
        "tb1z0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqglt7rf",
        "BC1S0XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ54WELL",
        # Bech32m instead of Bech32
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kemeawh",
        "tb1q0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq24jc47",
        # Invalid character in checksum
        "bc1p38j9r5y49hruaue7wxjce0updqjuyyx0kh56v8s25huc6995vvpql3jow4",
        # Invalid witness version
        "BC130XLXVLHEMJA6C4DQV22UAPCTQUPFHLXM9H8Z3K2E72Q4K9HCZ7VQ7ZWS8R",
        # Invalid program lengths: 1 byte, 41 bytes, 16 bytes for version 0
        "bc1pw5dgrnzv",
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v8n0nx0muaewav253zgeav",
        "BC1QR508D6QEJXTDG4Y5R3ZARVARYV98GJ9P",
        # Mixed case
        "tb1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq47Zagq",
        # Zero padding of more than 4 bits, non-zero padding
        "bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7v07qwwzcrf",
        "tb1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vpggkg4j",
        # Empty data section
        "bc1gmk9yu",
        # No separator, empty human-readable part, too long
        "bcqw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        "1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        "bc1" + "q" * 88,
    ],
)
def test_segwit_decode_invalid(address):
    assert segwit_decode(address) is None
    assert not is_bitcoin_address(address)


def test_segwit_address_of_another_network():
    # A valid Bech32m checksum, but "tc" is not Bitcoin (BIP 350)
    address = "tc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vq5zuyut"
    decoded = segwit_decode(address)
    assert decoded is not None and decoded[:2] == ("tc", 1)
    assert not is_bitcoin_address(address)


@pytest.mark.parametrize(
    "data, expected",
    [
        (
            [BECH32_CHARSET.index(char) for char in "w508d6qejxtdg4y5r3zarvary0c5xw7k"],
            list(bytes.fromhex("751e76e8199196d454941c45d1b3a323f1433bd6")),
        ),
        ([0, 0], [0]),
        ([], []),
        # A whole 5 bit group of padding, non-zero padding
        ([31], None),
        ([0, 1], None),
    ],
)
def test_convert_bits(data, expected):
    assert convert_bits(data, 5, 8) == expected


# is_bitcoin_address and BitcoinAddressProcessor


@pytest.mark.parametrize("address", VALID_ADDRESSES)
def test_valid_addresses(address):
    assert is_bitcoin_address(address)
    assert bitcoin_matches(address) == [address]


@pytest.mark.parametrize("text", WRONG_CHECKSUMS)
def test_wrong_checksums_are_filtered_out(text):
    assert not is_bitcoin_address(text)
    assert bitcoin_matches(text) == []
    # Without processing, they are matched by the regex
    assert bitcoin_matches(text, processors=[]) == [text]


@pytest.mark.parametrize(
    "address",
    [
        # Other cryptocurrencies use Base58Check with other versions
        "LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m",
        "DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o",
        # A 19 byte hash
        "12D2adLM3UKy4Z4giRbReR6gjWx1w6Dz",
    ],
)
def test_other_base58check_addresses(address):
    assert base58check_decode(address) is not None
    assert not is_bitcoin_address(address)


def processed(text: str) -> Optional[dict]:
    match = {"Matched": text, "Regex Pattern": {"Name": BITCOIN}}
    return BitcoinAddressProcessor().process(match)


def test_bitcoin_address_processor():
    assert processed("1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY") == {
        "Matched": "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY",
        "Regex Pattern": {"Name": BITCOIN},
    }
    assert processed(ISSUE) is None


def test_addresses_in_text():
    text = (
        "Send it to bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4 or "
        f"3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy, not {ISSUE}."
    )
    # A SegWit address used not to match if the rest of the line contained a
    # "1", "b", "i" or "o"
    assert bitcoin_matches(text) == [
        "bc1qw508d6qejxtdg4y5r3zarvary0c5xw7kv8f3t4",
        "3J98t1WpEZ73CNmQviecrnyiWrnqRhWNLy",
    ]


def test_addresses_in_a_file():
    found = bitcoin_matches("fixtures/file", only_text=False)
    unprocessed = bitcoin_matches("fixtures/file", only_text=False, processors=[])
    for address in [
        "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY",
        "16ftSEQ4ctQFDtVZiUBusQUjRrGhM3JYwe",
    ]:
        assert address in found
    # Parts of the Monero address, the SSH and PGP keys, the Nano address and
    # the Mailchimp API key in the file used to be found as Bitcoin addresses
    for text in [
        "1hhi2jZcbfcwoPbkhMrrED6zqJRfeYpXFf",
        "3NzaC1tc2EAAAADAQABAAACAQDrnjkGtf3",
        "3AwtLQvjxwLDuzk4dUtUwvUYibL2sAHwj2",
        "1c46rz7xnk98ozhzdjq7thwty844sgnqxk",
        "122b2565c3e26a61cbf58d1d1aad7",
    ]:
        assert text in unprocessed
        assert text not in found
    assert all(is_bitcoin_address(address) for address in found)


@pytest.mark.parametrize(
    "text",
    ["bc1" * 20000, "1" * 50000, "3F" * 25000, "bc1q" + "q" * 50000],
)
def test_no_catastrophic_backtracking(text):
    start = time.perf_counter()
    bitcoin_matches(text)
    assert time.perf_counter() - start < 5


# Command line interface


def test_cli_issue_example():
    output = run_cli([ISSUE])
    assert BITCOIN not in output
    assert "blockchain.com" not in output


@pytest.mark.parametrize("flag", ["-dp", "--disable-processing"])
def test_cli_disable_processing(flag):
    output = run_cli([flag, ISSUE])
    assert f"Name: {BITCOIN}" in output


def test_cli_valid_address():
    output = run_cli(["bc1p0xlxvlhemja6c4dqv22uapctqupfhlxm9h8z3k2e72q4k9hcz7vqzk5jj0"])
    assert f"Name: {BITCOIN}" in output
