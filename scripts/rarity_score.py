"""
Estimate the rarity of a regex from the regex itself (issue #238).

The rarity of a regex is how unlikely a match is to be a false positive. This
script measures it instead of guessing: it counts how many bits of information
a regex requires of the text that it matches, log2(1 / the chance that random
text matches it). 20 bits, a chance of about one in a million, is a rarity of
1, 10 bits is 0.5 and so on, rounded to one decimal place.

Random text is made of the same kinds of characters as a match: lowercase
letters, uppercase letters, digits and symbols. What makes a regex rare are the
specific characters that a match has to contain, not that it is made of
letters or digits, because text is full of hashes, IDs and numbers:

* A letter is 1 in 26 (4.7 bits), whatever its case, and a digit 1 in 10
  (3.3 bits). The separators " -._/:," are 4 in 59 (3.9 bits) each, any
  other symbol or character is 1 in 59 (5.9 bits).
* A character class counts the kind of characters that it matches the largest
  share of: [a-f] is 6 in 26 lowercase letters (2.1 bits) and [13] 2 in 10
  digits (2.3 bits). [0-9a-f], [A-Za-z0-9+/] and . match all digits, so they
  are 0 bits.
* x{3} is 3 times x, x+ is x, x? and x* are 0 bits.
* The chances of alternatives add up: abc|xyz is twice as likely to match as
  abc, which is 1 bit less.
* A lookahead and what follows it match the same text, so only the rarer of
  them counts. Lookbehinds, negative lookarounds, anchors and backreferences
  are 0 bits.

A list of regexes, which "Regex" in regex.json can be, matches if any of them
matches.

The estimate is a starting point for picking a rarity, not a replacement for
judgement: it only counts the characters that a match has to contain, so it
does not know how common a format or a word is in real text.

Usage:

    python scripts/rarity_score.py '^(ghp_[0-9a-zA-Z]{36})$'
    python scripts/rarity_score.py --database
    python scripts/rarity_score.py --database --min-difference 0.3
"""
import argparse
import io
import json
import math
import re
import string
import sys
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Set,
    Tuple,
    Union,
)

if sys.version_info >= (3, 11):
    from re import _parser as sre_parse  # type: ignore  # sre_parse is deprecated
else:
    import sre_parse

REGEX_JSON = Path(__file__).resolve().parent.parent / "pywhat" / "Data" / "regex.json"

# The number of bits of a regex with a rarity of 1: a chance of about one in a
# million (2 ** 20)
RARITY_1_BITS = 20

# The chance that a random character of a kind is a given character
LETTER = 1 / 26
DIGIT = 1 / 10
SEPARATORS = " -._/:,"
# There are 38 ASCII symbols, including whitespace. The 7 separators are 4
# times as common as the 31 others: 7 * 4 + 31 = 59
SEPARATOR = 4 / 59
SYMBOL = 1 / 59

# The characters that a part of a regex matches: a set of ASCII code points
# and the number of non-ASCII characters
Characters = Tuple[Set[int], int]

_ASCII = frozenset(range(128))
_NON_ASCII = sys.maxunicode + 1 - 128
_WHITESPACE = " \t\n\r\x0b\x0c\x1c\x1d\x1e\x1f"  # what \s matches in ASCII


def _categories() -> Dict[Any, Characters]:
    """The characters of \\d, \\D, \\s, \\S, \\w and \\W."""
    categories: Dict[Any, Characters] = {}
    for category, negation, characters in [
        (sre_parse.CATEGORY_DIGIT, sre_parse.CATEGORY_NOT_DIGIT, string.digits),
        (sre_parse.CATEGORY_SPACE, sre_parse.CATEGORY_NOT_SPACE, _WHITESPACE),
        (
            sre_parse.CATEGORY_WORD,
            sre_parse.CATEGORY_NOT_WORD,
            string.ascii_letters + string.digits + "_",
        ),
    ]:
        codes = set(map(ord, characters))
        categories[category] = (codes, 0)
        categories[negation] = (set(_ASCII - codes), _NON_ASCII)
    return categories


_CATEGORIES = _categories()
_REPEATS = [
    sre_parse.MAX_REPEAT,
    sre_parse.MIN_REPEAT,
    getattr(sre_parse, "POSSESSIVE_REPEAT", None),  # Python 3.11+
]
_ATOMIC_GROUP = getattr(sre_parse, "ATOMIC_GROUP", None)  # Python 3.11+
_LOOKAHEAD = 1  # the direction of an ASSERT, lookbehinds are -1


def _kind(code: int) -> Tuple[str, float]:
    """The kind of a character and the chance that a character of the kind is it."""
    char = chr(code)
    if "a" <= char <= "z":
        return "lowercase", LETTER
    if "A" <= char <= "Z":
        return "uppercase", LETTER
    if "0" <= char <= "9":
        return "digit", DIGIT
    return "symbol", SEPARATOR if char in SEPARATORS else SYMBOL


def _characters_bits(characters: Characters) -> float:
    """The bits of matching one of characters: the largest share of a kind."""
    ascii_codes, non_ascii = characters
    shares: Dict[str, float] = {"symbol": non_ascii * SYMBOL}
    for code in ascii_codes:
        kind, chance = _kind(code)
        shares[kind] = shares.get(kind, 0) + chance
    share = min(1.0, max(shares.values()))
    # A class that matches no character at all never matches, count it as 0
    return math.log2(1 / share) if share > 0 else 0.0


def _with_other_case(ascii_codes: Set[int]) -> Set[int]:
    letters = {code for code in ascii_codes if chr(code).isalpha()}
    return ascii_codes | {ord(chr(code).swapcase()) for code in letters}


def _literal(code: int, ignore_case: bool) -> Characters:
    if code >= 128:
        return set(), 1
    return (_with_other_case({code}) if ignore_case else {code}), 0


def _class(items: Any, ignore_case: bool) -> Characters:
    """The characters that a character class such as [^a-z\\d] matches."""
    ascii_codes: Set[int] = set()
    non_ascii = 0
    negate = False
    for op, av in items:
        if op is sre_parse.NEGATE:
            negate = True
        elif op is sre_parse.LITERAL:
            codes, count = _literal(av, False)
            ascii_codes |= codes
            non_ascii += count
        elif op is sre_parse.RANGE:
            low, high = av
            ascii_codes.update(range(low, min(high, 127) + 1))
            non_ascii += max(0, high - max(low, 128) + 1)
        elif op is sre_parse.CATEGORY:
            # The other categories are not used in str regexes
            codes, count = _CATEGORIES.get(av, (set(_ASCII), _NON_ASCII))
            ascii_codes |= codes
            non_ascii += count
    if ignore_case:
        ascii_codes = _with_other_case(ascii_codes)
    non_ascii = min(non_ascii, _NON_ASCII)
    if negate:
        return set(_ASCII - ascii_codes), _NON_ASCII - non_ascii
    return ascii_codes, non_ascii


def either(bits: Iterable[float]) -> float:
    """The bits of matching any of alternatives with these bits: chances add up."""
    alternatives = sorted(bits)
    if not alternatives:
        return 0.0
    # log2(1 / the sum of the chances), relative to the most likely alternative
    # so that the chances of very rare alternatives do not round to 0
    most_likely = alternatives[0]
    chance = sum(2.0 ** (most_likely - other) for other in alternatives)
    return max(0.0, most_likely - math.log2(chance))


def _bits(pattern: Any, ignore_case: bool) -> float:
    """The bits of a parsed regex, a sequence of (opcode, argument) pairs."""
    tokens = list(pattern)
    bits = 0.0
    for index, (op, av) in enumerate(tokens):
        if op is sre_parse.LITERAL:
            bits += _characters_bits(_literal(av, ignore_case))
        elif op is sre_parse.IN:
            bits += _characters_bits(_class(av, ignore_case))
        elif op in _REPEATS:
            minimum, _maximum, item = av
            bits += minimum * _bits(item, ignore_case)
        elif op is sre_parse.SUBPATTERN:  # a group, maybe with flags: (?i:...)
            _group, add_flags, del_flags, item = av
            item_ignore_case = (
                ignore_case or bool(add_flags & re.IGNORECASE)
            ) and not (del_flags & re.IGNORECASE)
            bits += _bits(item, item_ignore_case)
        elif op is sre_parse.BRANCH:
            bits += either(_bits(item, ignore_case) for item in av[1])
        elif op is sre_parse.GROUPREF_EXISTS:  # (?(group)yes|no)
            _group, yes, no = av
            bits += either([_bits(yes, ignore_case), _bits(no or [], ignore_case)])
        elif op is _ATOMIC_GROUP:
            bits += _bits(av, ignore_case)
        elif op is sre_parse.ASSERT and av[0] == _LOOKAHEAD:
            # The lookahead and the rest of the regex match the same text
            lookahead = _bits(av[1], ignore_case)
            rest = _bits(tokens[index + 1 :], ignore_case)
            return bits + max(lookahead, rest)
        # Anything else matches any character (., [^\n]) or does not match a
        # character (anchors, lookbehinds, negative lookarounds) or is a
        # backreference: 0 bits
    return bits


def specificity(regex: Union[str, Sequence[str]]) -> float:
    """
    The number of bits of information that regex requires of the text that it
    matches, log2(1 / the chance that random text matches it). regex can be a
    list of regexes, then any of them can match.

    Raises re.error if regex is not a valid regex.
    """
    if not isinstance(regex, str):
        return either(specificity(alternative) for alternative in regex)
    ignore_case = bool(re.compile(regex).flags & re.IGNORECASE)
    return _bits(sre_parse.parse(regex), ignore_case)


def rarity(bits: float) -> float:
    """
    The rarity of a regex with this specificity in bits: bits / 20, at most 1,
    rounded half up to one decimal place like the rarities in regex.json.
    """
    return min(10, math.floor(bits * 10 / RARITY_1_BITS + 0.5)) / 10


def estimate_rarity(regex: Union[str, Sequence[str]]) -> float:
    """The rarity that regex (a regex or a list of regexes) should have."""
    return rarity(specificity(regex))


class Row(NamedTuple):
    name: str
    rarity: float
    estimate: float
    bits: float


def database_rows(min_difference: float = 0.0) -> List[Row]:
    """
    The rarity and the estimated rarity of the regexes in regex.json, in the
    order of regex.json, whose rarity differs from the estimate by at least
    min_difference.
    """
    with open(REGEX_JSON, encoding="utf-8") as file:
        database = json.load(file)
    rows = []
    for entry in database:
        bits = specificity(entry["Regex"])
        row = Row(entry["Name"], entry["Rarity"], rarity(bits), bits)
        # Rarities are multiples of 0.1, round away the float errors
        if round(abs(row.rarity - row.estimate), 6) >= min_difference:
            rows.append(row)
    return rows


def _table(header: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    """Columns of numbers, aligned to the right, then a column of text."""
    lines = [header, *rows]
    widths = [max(len(line[i]) for line in lines) for i in range(len(header) - 1)]
    return "\n".join(
        "  ".join([*(cell.rjust(width) for cell, width in zip(line, widths)), line[-1]])
        for line in lines
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "regexes",
        nargs="*",
        metavar="REGEX",
        help="a regex to estimate the rarity of, e.g. '^(ghp_[0-9a-zA-Z]{36})$'",
    )
    parser.add_argument(
        "--database",
        action="store_true",
        help="compare the rarity of every regex in regex.json with its estimate",
    )
    parser.add_argument(
        "--min-difference",
        type=float,
        default=0.0,
        metavar="DIFFERENCE",
        help="with --database, only show the regexes whose rarity differs from "
        "the estimate by at least DIFFERENCE, e.g. 0.3",
    )
    args = parser.parse_args(argv)
    if not args.regexes and not args.database:
        parser.error("give a regex or --database")

    # Print the regex names that the terminal cannot show, such as "Bitcoin (₿)
    # Wallet Address" on Windows, with escape sequences instead of crashing.
    # The default error handler is "strict", or "surrogateescape" on Windows
    # and in the C locale, which cannot encode them either
    if isinstance(sys.stdout, io.TextIOWrapper) and sys.stdout.errors in (
        "strict",
        "surrogateescape",
    ):
        sys.stdout.reconfigure(errors="backslashreplace")

    tables = []
    if args.regexes:
        estimates = []
        for regex in args.regexes:
            try:
                bits = specificity(regex)
            except re.error as error:
                parser.error(f"invalid regex {regex!r}: {error}")
            estimates.append((f"{rarity(bits):g}", f"{bits:.1f}", regex))
        tables.append(_table(("Estimate", "Bits", "Regex"), estimates))
    if args.database:
        comparisons = [
            (f"{row.rarity:g}", f"{row.estimate:g}", f"{row.bits:.1f}", row.name)
            for row in database_rows(args.min_difference)
        ]
        tables.append(_table(("Rarity", "Estimate", "Bits", "Name"), comparisons))
    print("\n\n".join(tables))
    return 0


if __name__ == "__main__":
    sys.exit(main())
