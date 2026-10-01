"""Helper utilities"""
import collections.abc
import re
from enum import Enum, auto
from functools import lru_cache
from pathlib import Path

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
    containing non-existent tags.
    """

    pass


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


class Keys(Enum):
    def NAME(match):
        return match["Regex Pattern"]["Name"]

    def RARITY(match):
        return match["Regex Pattern"]["Rarity"]

    def MATCHED(match):
        return match["Matched"]

    NONE = auto()


def str_to_key(s: str):
    try:
        return getattr(Keys, s.upper())
    except AttributeError:
        raise ValueError
