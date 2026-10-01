"""
The most likely matches first, and only the top ones (issue #232).

The most likely matches have the highest rarity, they are the least likely to
be false positives. Fragments of a longer word or of a longer match, which
boundaryless mode finds, are less likely than the other matches unless their
rarity is 1: the card number in the Ethereum address
0x52908400098527886E0F7030069857D2E4169EE7 is not a card number. See
pywhat.helper.likelihood().

--top, the 'top' and 'more' commands of interactive mode and the 'likely'
sort key show the most likely matches first.
"""
import bisect
import math
import re
from decimal import Decimal
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Sequence,
    Tuple,
    Union,
)

from pywhat.helper import FRAGMENT, Keys, likelihood

# A match and where it was found: a key of the "Regexes" that
# Identifier.identify() returns ("text" or a file) and an item of its list
Found = Tuple[str, dict]
# The start and the end of a match in the text that it was found in
Span = Tuple[int, int]

# "There are 157 results, would you like to only show the top 10?": without
# --top, pyWhat suggests showing the SUGGESTED_TOP most likely matches when
# it finds more than SUGGEST_TOP_AFTER of them
SUGGESTED_TOP = 10
SUGGEST_TOP_AFTER = 20

_NUMBER = re.compile(r"[0-9]+")
_PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?|\.[0-9]+)\s*%")


def _is_word_character(character: str) -> bool:
    return character.isalnum() or character == "_"


def inside_word(text: str, span: Span) -> bool:
    """
    Whether the span of text is inside a longer word: it starts with a
    letter, digit or underscore right after another one, or ends with one
    right before another one, like the card number 5290840009852788 in
    0x52908400098527886E0F7030069857D2E4169EE7.
    """
    start, end = span
    if start >= end:
        return False
    return (
        start > 0
        and _is_word_character(text[start - 1])
        and _is_word_character(text[start])
    ) or (
        end < len(text)
        and _is_word_character(text[end - 1])
        and _is_word_character(text[end])
    )


def mark_fragments(text: str, found: Sequence[Tuple[dict, Span]]) -> None:
    """
    Set the FRAGMENT key of the matches found in text, which are given with
    their spans: whether a match is inside a longer word (see inside_word())
    or inside a longer match, like the URL skerritt.blog in the email address
    github@skerritt.blog. Matches with a rarity of 0 match almost anything,
    so being inside one of them does not make a match a fragment.
    """
    containers = sorted(
        span for match, span in found if match["Regex Pattern"]["Rarity"] > 0
    )
    starts = [start for start, _ in containers]
    # furthest[i] is the furthest end of containers[:i + 1]
    furthest: List[int] = []
    for _, end in containers:
        furthest.append(max(end, furthest[-1]) if furthest else end)
    for match, (start, end) in found:
        before = bisect.bisect_left(starts, start)
        same_start = bisect.bisect_right(starts, start)
        match[FRAGMENT] = (
            # A container that starts before the match and does not end before it
            (before > 0 and furthest[before - 1] >= end)
            # A container that starts with the match and ends after it
            or (same_start > before and containers[same_start - 1][1] > end)
            or inside_word(text, (start, end))
        )


class Top(NamedTuple):
    """
    How many of the most likely matches to show: number matches, the most
    likely percent percent of the matches, or all matches if both are None.
    """

    number: Optional[int] = None
    percent: Optional[Decimal] = None

    @property
    def is_all(self) -> bool:
        return self.number is None and self.percent is None

    def of(self, total: int) -> int:
        """How many of total matches to show, at least 1 unless total is 0."""
        if self.number is not None:
            return min(self.number, total)
        if self.percent is not None:
            # Decimal, so that 1.1% of 1000 matches is 11 matches, not 12
            return min(total, math.ceil(total * self.percent / 100))
        return total

    def __str__(self) -> str:
        if self.number is not None:
            return str(self.number)
        if self.percent is not None:
            return f"{self.percent}%"
        return "all"


def parse_top(top: Union[Top, int, str]) -> Top:
    """
    Parse how many of the most likely matches to show: a number of matches
    such as 10 or "10", a percentage of the matches such as "5%", or "all".

    Raises ValueError for anything else, such as 0 or "150%".
    """
    if isinstance(top, Top):
        return top
    text = str(top).strip()
    if text.lower() == "all":
        return Top()
    if _NUMBER.fullmatch(text) and int(text) > 0:
        return Top(number=int(text))
    percent = _PERCENT.fullmatch(text)
    if percent and 0 < Decimal(percent.group(1)) <= 100:
        return Top(percent=Decimal(percent.group(1)))
    raise ValueError(
        f"Invalid top '{text}', use a number of matches such as 10, "
        "a percentage of them such as 5% or all"
    )


def most_likely_first(found: Iterable[Found]) -> List[Found]:
    """
    The (location, match) pairs, the most likely matches first (see
    pywhat.helper.likelihood()). Matches that are as likely as each other
    stay in the order they were found.
    """
    return sorted(found, key=lambda pair: likelihood(pair[1]))


def select(found: List[Found], top: Top, start: int = 0) -> List[Found]:
    """
    The top most likely of the found (location, match) pairs, most likely
    first, after the start most likely ones (to page through them). For a
    directory, these are the most likely matches of all of its files.

    All matches, Top(), are left in the order they were found.
    """
    if top.is_all:
        return found[start:]
    return most_likely_first(found)[start : start + top.of(len(found))]


def located_matches(identified: dict) -> List[Found]:
    """
    The (location, match) pairs of identified, a dict that
    Identifier.identify() returns, in the order they were found.
    """
    return [
        (location, match)
        for location, matches in (identified.get("Regexes") or {}).items()
        for match in matches
    ]


def group_by_location(
    found: Iterable[Found], key: Any = Keys.NONE, reverse: bool = False
) -> Dict[str, List[dict]]:
    """
    The "Regexes" of Identifier.identify() for (location, match) pairs: the
    matches of each location, in the order of found or sorted by key like
    identify() sorts them. The locations are in the order of their first
    match.
    """
    regexes: Dict[str, List[dict]] = {}
    for location, match in found:
        regexes.setdefault(location, []).append(match)
    if key != Keys.NONE:
        for matches in regexes.values():
            matches.sort(key=key, reverse=reverse)
    return regexes


def top_matches(
    identified: dict,
    top: Union[Top, int, str],
    *,
    start: int = 0,
    key: Any = Keys.NONE,
    reverse: bool = False,
) -> dict:
    """
    identified, a dict that Identifier.identify() returns, with only the top
    most likely of its matches (see parse_top()), for example
    top_matches(identified, 10) or top_matches(identified, "5%").

    The most likely matches are first: the location (file) of the most likely
    match, with its matches, then the location of the most likely of the
    others, and so on. key sorts the matches of each location like identify()
    does instead. start leaves out the start most likely matches, to see the
    next ones. The file signatures are kept.
    """
    found = select(located_matches(identified), parse_top(top), start)
    return {**identified, "Regexes": group_by_location(found, key, reverse) or None}
