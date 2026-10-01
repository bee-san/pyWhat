"""
Test cases for phone number identification.

Runs of digits such as "3333333333" or "-1606586780" are not phone numbers
(issue #240). A phone number starts with "+" and a country code, like
"+44 20 7946 0958", or is a North American number with separators, like
"(202) 555-0178" or "202-555-0178".
"""
import re
import time

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Distribution, Filter
from pywhat.helper import load_regexes
from pywhat.what import main

PHONE = "Phone Number"
EVERYTHING = Filter({"MinRarity": 0.0})
r = identifier.Identifier(dist=Distribution(EVERYTHING))

# The false positives reported in issue #240
ISSUE_240 = [
    "0000000000000",
    "0123456789",
    "3333333333333",
    "3333333333",
    "4444444444444",
    "22223333333",
    "-1606586780",
]


def _phone_numbers(text, *, boundaryless=None):
    out = r.identify(text, boundaryless=boundaryless)
    if out["Regexes"] is None:
        return []
    return [
        match
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == PHONE
    ]


def _matched(text, *, boundaryless=None):
    return [
        match["Matched"] for match in _phone_numbers(text, boundaryless=boundaryless)
    ]


@pytest.mark.parametrize("text", ISSUE_240)
def test_issue_240_numbers_are_not_phone_numbers(text):
    assert _matched(text) == []
    assert _matched(text, boundaryless=EVERYTHING) == []


@pytest.mark.parametrize(
    "number",
    [
        # North American numbers with separators
        "202-555-0178",
        "202.555.0178",
        "202 555-0178",
        "(202) 555-0178",
        "(202)555-0178",
        "(202) 555 0178",
        "1-800-555-0199",
        "1 (800) 555-0199",
        "1.800.555.0199",
        # "+" and a country code
        "+1-202-555-0156",
        "+1 (202) 555-0156",
        "+1.202.555.0156",
        "+12025550156",
        "+1606586780",
        "+662025550156",
        "+356 202 555 0156",
        "+91 (385) 985 2821",
        "+91 98765 43210",
        "+44 20 7946 0958",
        "+44 (0)20 7946 0958",
        "+442079460958",
        "+49 30 901820",
        "+49 (0)30 901820",
        "+33 1 23 45 67 89",
        "+7 (495) 123-45-67",
        "+81 3-1234-5678",
        "+86 138 0013 8000",
        "+55 11 91234-5678",
        "+61 2 9876 5432",
        # the format of WHOIS records (RFC 5733)
        "+1.2025550156",
        "+44.2079460958",
        "+7.4951234567",
        "+356.21234567",
        # the longest numbers have 15 digits (ITU-T E.164)
        "+123456789012345",
        # extensions
        "202-555-0178 x123",
        "202-555-0178 ext. 1234",
        "+44 20 7946 0958 ext 12",
    ],
)
def test_phone_number_is_fully_matched(number):
    assert _matched(number) == [number]
    # Without the spaces around it, in boundaryless mode too
    assert _matched(f"Call {number} today", boundaryless=EVERYTHING) == [number]


@pytest.mark.parametrize(
    "text",
    [
        # digits without separators or a "+"
        "2025550178",
        "12025550178",
        "1637093119",
        # North American area and exchange codes do not start with 0 or 1
        "123-456-7890",
        "012-345-6789",
        "202-155-0178",
        "(102) 555-0178",
        # too short or too long
        "555-0178",
        "202-555-01789",
        "+1234567",
        "+123456789",
        "+1234567890123456",
        # country codes do not start with 0
        "+0123456789",
        # numbers with a sign
        "+3.14159265",
        "+3.14159265358979",
        "+12345678.90",
        "+1.2345678901e+02",
        "+40.7127753",
        "+192.168.100.200",
        # three numbers separated by spaces are common in tables
        "202 555 0178",
        # brackets have to be balanced
        "+1 (202 555 0156",
        "+1 202) 555 0156",
        "+1 202  555 0156",
        # dates, social security and credit card numbers
        "2021-12-02",
        "13-08-1987",
        "001-01-0001",
        "4111 1111 1111 1111",
        "4111-1111-1111-1111",
    ],
)
def test_text_is_not_a_phone_number(text):
    assert _matched(text) == []


@pytest.mark.parametrize(
    "text, numbers",
    [
        ("fajfdk;fa+91 (385) 985 2821kl;fajf;la", ["+91 (385) 985 2821"]),
        ("(+1 202 555 0156)", ["+1 202 555 0156"]),
        ("Phone: (202) 555-0178.", ["(202) 555-0178"]),
        ('{"phone": "+14155552671"}', ["+14155552671"]),
        ("tel:+1-202-555-0156;ext=1", ["+1-202-555-0156"]),
        ("Call +44 20 7946 0958 (9am-5pm)", ["+44 20 7946 0958"]),
        (
            "Tel: +44 20 7946 0958, Fax: +44 20 7946 0959",
            ["+44 20 7946 0958", "+44 20 7946 0959"],
        ),
        ("202-555-0156 or 202-555-0178", ["202-555-0156", "202-555-0178"]),
        ("Registrant Phone: +1.4155552671\n", ["+1.4155552671"]),
        # part of a longer number
        ("11-202-555-0178", []),
        ("2021-202-555-0178", []),
        ("202-555-0178-9", []),
        ("202-555-0178.5", []),
        ("id=12345678902", []),
        ("Order 3333333333 shipped", []),
        ("Balance: +12345678.90", []),
        ("x = 1.5e+1234567890", []),
        ("y = +1.2345678901e+02", []),
        ("0x52908400098527886E0F7030069857D2E4169EE7", []),
        ("1.0.0+20130313144700", []),
        ("800 900 1000", []),
    ],
)
def test_phone_numbers_in_text(text, numbers):
    assert _matched(text, boundaryless=EVERYTHING) == numbers


@pytest.mark.parametrize(
    "text, country",
    [
        ("+1-202-555-0156", "United States"),
        ("Tel: +44 20 7946 0958", "United Kingdom"),
        ("call +91 98765 43210 now", "India"),
        ("Phone: +44.2079460958", "United Kingdom"),
    ],
)
def test_country_of_phone_number_in_text(text, country):
    # The space before the "+" used to be part of the match, so the country
    # code was not found
    (match,) = _phone_numbers(text, boundaryless=EVERYTHING)
    assert match["Regex Pattern"]["Description"] == f"Location(s): {country}"


@pytest.mark.parametrize("text", ISSUE_240)
def test_cli_does_not_identify_issue_240_numbers(text):
    result = CliRunner().invoke(main, ["--rarity", "0:", "--", text])
    assert result.exit_code == 0
    assert PHONE not in result.output


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(" " * 50000, id="spaces"),
        pytest.param("1" * 50000, id="digits"),
        pytest.param("+" + "2" * 50000, id="plus and digits"),
        pytest.param("+1 " * 20000, id="country codes"),
        pytest.param("+1 (1)" * 10000, id="brackets"),
        pytest.param("(202) " * 10000, id="area codes"),
        pytest.param("202-555-" * 10000, id="unfinished numbers"),
        pytest.param("+1.2" * 10000, id="decimals"),
        pytest.param("+44." + "2" * 50000, id="long WHOIS number"),
        pytest.param("202-555-0178 x" + "1" * 50000, id="long extension"),
    ],
)
def test_phone_number_regex_does_not_backtrack_catastrophically(text):
    entry = next(regex for regex in load_regexes() if regex["Name"] == PHONE)
    start = time.perf_counter()
    list(re.finditer(entry["Boundaryless Regex"], text, re.MULTILINE))
    assert time.perf_counter() - start < 2
