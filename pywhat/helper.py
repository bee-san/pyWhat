"""Helper utilities"""
import collections.abc
import os.path
import re
from enum import Enum, auto
from functools import lru_cache

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
    combined_regexes = []
    regex_index_mapping = {}
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
        # Check if multiple regex patterns present
        regex_name = regex["Name"]
        if(regex_name in regex_index_mapping):
            # Update regex pattern
            existing_regex = combined_regexes[regex_index_mapping[regex_name]]["Regex"]
            updated_regex = existing_regex + "|" + regex["Regex"]
            combined_regexes[regex_index_mapping[regex_name]]["Regex"] = updated_regex
            # Combine tags
            updated_tags = combined_regexes[regex_index_mapping[regex_name]]["Tags"]
            for tag in regex["Tags"]:
                if(tag not in updated_tags):
                    updated_tags.append(tag)
            # Combine examples
            updated_valid_examples = combined_regexes[regex_index_mapping[regex_name]]["Examples"]["Valid"]
            for valid_example in regex["Examples"]["Valid"]:
                if(valid_example not in updated_valid_examples):
                    updated_valid_examples.append(valid_example)
            updated_invalid_examples = combined_regexes[regex_index_mapping[regex_name]]["Examples"]["Invalid"]
            for invalid_example in regex["Examples"]["Invalid"]:
                if(invalid_example not in updated_invalid_examples):
                    updated_invalid_examples.append(invalid_example)
            # Update boundaryless regex pattern
            existing_boundaryless_regex = combined_regexes[regex_index_mapping[regex_name]]["Boundaryless Regex"]
            updated_boundaryless_regex = existing_boundaryless_regex + "|" + regex["Boundaryless Regex"]
            combined_regexes[regex_index_mapping[regex_name]]["Boundaryless Regex"] = updated_boundaryless_regex
        else:
            regex_index_mapping[regex_name] = len(combined_regexes)
            combined_regexes.append(regex)
    return combined_regexes

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
