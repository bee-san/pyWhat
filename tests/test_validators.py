import pytest

from pywhat import Identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import load_regexes
from pywhat.processors import ValidatorProcessor
from pywhat.validators import (
    VALIDATORS,
    base58check,
    cashaddr,
    facebook_access_token,
    luhn,
    ripple_base58check,
    tc_kimlik,
)

ALL = Identifier(dist=Distribution(Filter({"MinRarity": 0})))


def names(text, identifier=ALL):
    found = identifier.identify(text)["Regexes"] or {}
    return [match["Regex Pattern"]["Name"] for match in found.get("text", [])]


@pytest.mark.parametrize(
    "validator, valid, invalid",
    [
        (
            luhn,
            ["4111111111111111", "4111 1111 1111 1111", "6011-0000-0000-0004"],
            ["4111111111111112", "", "  ", "4111x111111111111", "٤١١١"],
        ),
        (
            tc_kimlik,
            ["10000000146", "12345678950"],
            ["12345678902", "02345678902", "1000000014", "١٠٠٠٠٠٠٠١٤٦"],
        ),
        (
            base58check,
            [
                "DANHz6EQVoWyZ9rER56DwTXHWUxfkv9k2o",
                "LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m",
            ],
            ["LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7n", "0OIl", ""],
        ),
        (
            ripple_base58check,
            ["rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"],
            [
                "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkl",
                "r0PAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk",
            ],
        ),
        (
            cashaddr,
            [
                "bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq",
                "qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq",
                "BITCOINCASH:QPM2QSZNHKS23Z7629MMS6S4CWEF74VCWVY22GDX6A",
            ],
            [
                "qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lr",
                "bitcoincash:Qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq",
                "bchtest:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq",
                "q",
            ],
        ),
        (
            facebook_access_token,
            ["EAARE0ZATe"],
            ["EAHCHERBOTIC", "EA0123ABCDEF", "EAabcdef0123", "EA"],
        ),
    ],
)
def test_validators(validator, valid, invalid):
    for text in valid:
        assert validator(text), text
    for text in invalid:
        assert not validator(text), text


def test_every_validator_in_regex_json_exists():
    for regex in load_regexes():
        if "Validator" in regex:
            assert regex["Validator"] in VALIDATORS, regex["Name"]


def test_validator_processor_processes_the_regexes_with_a_validator():
    processor = ValidatorProcessor()
    assert "Visa Card Number" in processor.names
    assert "Turkish Identification Number" in processor.names
    assert "Email Address" not in processor.names


@pytest.mark.parametrize(
    "text, name",
    [
        ("4111111111111111", "Visa Card Number"),
        ("10000000146", "Turkish Identification Number"),
        ("LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7m", "Litecoin (LTC) Wallet Address"),
        ("rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk", "Ripple (XRP) Wallet Address"),
        (
            "qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq",
            "Bitcoin Cash (BCH) Wallet Address",
        ),
    ],
)
def test_checksums_keep_valid_matches(text, name):
    assert name in names(text)


@pytest.mark.parametrize(
    "text, name",
    [
        ("4111111111111112", "Visa Card Number"),
        ("12345678902", "Turkish Identification Number"),
        ("LRX8rSPVjifTxoLeoJtLf2JYdJFTQFcE7n", "Litecoin (LTC) Wallet Address"),
        ("rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkl", "Ripple (XRP) Wallet Address"),
        (
            "qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lr",
            "Bitcoin Cash (BCH) Wallet Address",
        ),
        # Ciphey issue #1104: Vigenère output, all upper case
        ("EA" + "HCHERBOTICFUVQZJYIGBWNXKALMOPDES" * 6, "Facebook Access Token"),
    ],
)
def test_checksums_filter_out_wrong_matches(text, name):
    assert name not in names(text)
    # Without processing, the regexes still match them
    assert name in names(text, Identifier(dist=ALL.distribution, processors=[]))
