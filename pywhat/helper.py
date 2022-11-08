"""Helper utilities"""
import collections.abc
import os.path
import re
from enum import Enum, auto
from functools import lru_cache
from datetime import date
import csv

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
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data/" + path)
    with open(fullpath, "rb") as myfile:
        return json.loads(myfile.read())


@lru_cache()
def load_regexes() -> list:
    regexes = read_json("regex.json")
    for regex in regexes:
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

class Query():
    def __init__(self, is_file: bool, content: str):
        if is_file:
            self.type = "File"
        else:
            self.type = "String"
        self.content = content
        self.date = date.today() # record the date of the query in format "yyyy-mm-dd"

    def is_in_peroid(self, start_date, end_date) -> bool:
        return (self.date >= start_date and self.date <= end_date)

    def is_file(self):
        return self.type == "File"

    def record(self):
        filename = "record.csv"
        with open(filename, 'w') as file:
            writer = csv.writer(file)
            row = [self.type, self.content, self.date]
            writer.writerow(row)      