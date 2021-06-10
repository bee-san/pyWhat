"""Helper utilities"""
import collections.abc
import json
import os.path
from enum import Enum, auto


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


def load_regexes() -> list:
    path = "Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        return json.load(myfile)


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
        for value in self:
            if value not in other:
                return False
        return True


class Keys(Enum):
    NAME = lambda match: match["Regex Pattern"]["Name"]
    RARITY = lambda match: match["Regex Pattern"]["Rarity"]
    MATCHED = lambda match: match["Matched"]
    NONE = auto()
