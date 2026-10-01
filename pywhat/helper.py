"""Helper utilities"""
import collections.abc
import re
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path
from typing import List, Set, Tuple

try:
    import orjson as json
except ImportError:
    import json  # type: ignore


class AvailableTags:
    def __init__(self):
        self.tags = set()
        regexes = load_regexes()
        for regex in regexes:
            self.tags.update(regex["Tags"])

    def get_tags(self):
        return self.tags


class InvalidTag(Exception):
    """
    This exception should be raised when Distribution() gets a filter
    containing non-existent tags (or names, see get_names()).
    """

    pass


def get_names(regex: dict) -> List[str]:
    """
    The names of a regex (issue #184): its "Name", then its optional
    "Alternative Names", such as "ETH Wallet" for "Ethereum (ETH) Wallet
    Address". Filters take the names of regexes as well as tags.
    """
    names = [regex["Name"]] if "Name" in regex else []
    return names + list(regex.get("Alternative Names", ()))


def available_names() -> Set[str]:
    """Every name and alternative name of the regexes, see get_names()."""
    return {name for regex in load_regexes() for name in get_names(regex)}


def split_tags(text: str) -> List[str]:
    """
    Split a comma separated list of tags and names like text.split(","), but
    commas in parentheses do not separate, so that names such as "EUI-48
    Identifier (Ethernet, WiFi, Bluetooth, etc)" can be in the list.
    """
    parts = []
    depth = start = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        elif char == "," and not depth:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


@lru_cache()
def read_json(path: str):
    fullpath = Path(__file__).resolve().parent / "Data" / path
    with open(fullpath, "rb") as myfile:
        return json.loads(myfile.read())


def join_regexes(patterns: list) -> str:
    """
    Join a list of regexes in the ^(regex)$ format into a single regex.

    ["^(a)$", "^(b)$"] becomes "^(?:(a)|(b))$". If every regex starts with
    "(?i)" the result keeps one leading "(?i)", otherwise the flag is scoped
    to the regexes that had it: ["(?i)^(a)$", "^(b)$"] becomes
    "^(?:(?i:(a))|(b))$".

    Capturing groups are renumbered, so numbered backreferences (\\1) only
    work in the first regex of the list.
    """
    case_insensitive = [pattern.startswith("(?i)") for pattern in patterns]
    bodies = []
    for pattern, ignore_case in zip(patterns, case_insensitive):
        body = pattern[len("(?i)") :] if ignore_case else pattern
        if not (body.startswith("^") and body.endswith("$")):
            raise ValueError(f"Regex {pattern!r} is not in the ^(regex)$ format")
        body = body[1:-1]
        if ignore_case and not all(case_insensitive):
            body = f"(?i:{body})"
        bodies.append(body)
    prefix = "(?i)" if all(case_insensitive) else ""
    return prefix + "^(?:" + "|".join(bodies) + ")$"


@lru_cache()
def load_regexes() -> list:
    regexes = read_json("regex.json")
    for regex in regexes:
        # "Regex" may be a list of alternative formats (issue #227)
        if isinstance(regex["Regex"], list):
            regex["Regex"] = join_regexes(regex["Regex"])
        regex["Boundaryless Regex"] = re.sub(
            r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])", "", regex["Regex"]
        )
        regex["Boundaryless Regex"] = re.sub(
            r"(?<!\\)\$(?![^\[\]]*(?<!\\)\])", "", regex["Boundaryless Regex"]
        )
        children = regex.get("Children")
        if children is not None:
            try:
                children["Items"] = read_json(children["path"])
            except KeyError:
                pass
            children["lengths"] = set()
            for element in children["Items"]:
                children["lengths"].add(len(element))
    return regexes


class CaseInsensitiveSet(collections.abc.Set):
    def __init__(self, iterable=None):
        self._elements = set()
        if iterable is not None:
            self._elements = set(map(self._lower, iterable))

    def _lower(self, value):
        return value.lower() if isinstance(value, str) else value

    def __contains__(self, value):
        return self._lower(value) in self._elements

    def __iter__(self):
        return iter(self._elements)

    def __len__(self):
        return len(self._elements)

    def __repr__(self):
        return self._elements.__repr__()

    def issubset(self, other):
        return all(value in other for value in self)


# The key of a match that says whether it is a fragment of a longer word or
# of a longer match, see pywhat.ranking.mark_fragments()
FRAGMENT = "Fragment"


def likelihood(match: dict) -> Tuple[bool, float]:
    """
    The key to sort the most likely matches first (issue #232).

    The higher the rarity of a match, the less likely it is a false positive.
    A fragment of a longer word or match is less likely than the other
    matches, unless its rarity is 1 (its regex contains something unique to
    it, such as the THM{ in abcdTHM{hello}plze): the phone number in the
    Ethereum address 0x52908400098527886E0F7030069857D2E4169EE7 is not a
    phone number.
    """
    rarity = match["Regex Pattern"]["Rarity"]
    return bool(match.get(FRAGMENT)) and rarity < 1, -rarity


class Keys(Enum):
    def NAME(match):
        return match["Regex Pattern"]["Name"]

    def RARITY(match):
        return match["Regex Pattern"]["Rarity"]

    def MATCHED(match):
        return match["Matched"]

    def LIKELY(match):
        return likelihood(match)

    NONE = auto()


def str_to_key(s: str):
    try:
        return getattr(Keys, s.upper())
    except AttributeError:
        raise ValueError
