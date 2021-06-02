import json
import os
from typing import Optional

from pywhat.helper import AvailableTags, InvalidTag


class Distribution:
    """
    A distribution is an object containing the regex
    But the regex has gone through a filter process.

    Example filters:
    * {"Tags": ["Networking"]}
    * {"Tags": ["Identifiers"], "ExcludeTags": ["Credentials"], "MinRarity":0.6}
    """

    def __init__(self, filters_dict: Optional[dict] = None):
        tags = AvailableTags().get_tags()
        self._dict = dict()
        if filters_dict is None:
            filters_dict = dict()

        self._dict["Tags"] = set(filters_dict.setdefault("Tags", tags))
        self._dict["ExcludeTags"] = set(filters_dict.setdefault("ExcludeTags", set()))
        self._dict["MinRarity"] = filters_dict.setdefault("MinRarity", 0)
        self._dict["MaxRarity"] = filters_dict.setdefault("MaxRarity", 1)

        if len(self._dict["Tags"]) == 0:
            self._dict["Tags"] = tags

        if not self._dict["Tags"].issubset(tags) or not self._dict["ExcludeTags"].issubset(tags):
            raise InvalidTag("Passed filter contains tags that are not used by 'what'")

        self._load_regexes()

    def _load_regexes(self):
        path = "Data/regex.json"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r", encoding="utf-8") as myfile:
            self._regexes = json.load(myfile)
        self._filter()

    def _filter(self):
        temp_regexes = []
        min_rarity = self._dict["MinRarity"]
        max_rarity = self._dict["MaxRarity"]
        for regex in self._regexes:
            if (
                min_rarity <= regex["Rarity"] <= max_rarity
                and set(regex["Tags"]) & self._dict["Tags"]
                and not set(regex["Tags"]) & self._dict["ExcludeTags"]
            ):
                temp_regexes.append(regex)

        self._regexes = temp_regexes

    def get_regexes(self):
        return list(self._regexes)

    def __repr__(self):
        return f"Distribution({self._dict})"

    def __and__(self, other):
        if type(self) != type(other):
            return NotImplemented
        tags = self._dict["Tags"] & other._dict["Tags"]
        exclude_tags = self._dict["ExcludeTags"] & other._dict["ExcludeTags"]
        min_rarity = max(self._dict["MinRarity"], other._dict["MinRarity"])
        max_rarity = min(self._dict["MaxRarity"], other._dict["MaxRarity"])
        return Distribution(
            {"Tags": tags, "ExcludeTags": exclude_tags,
            "MinRarity": min_rarity, "MaxRarity": max_rarity})

    def __or__(self, other):
        if type(self) != type(other):
            return NotImplemented
        tags = self._dict["Tags"] | other._dict["Tags"]
        exclude_tags = self._dict["ExcludeTags"] | other._dict["ExcludeTags"]
        min_rarity = min(self._dict["MinRarity"], other._dict["MinRarity"])
        max_rarity = max(self._dict["MaxRarity"], other._dict["MaxRarity"])
        return Distribution(
            {"Tags": tags, "ExcludeTags": exclude_tags,
            "MinRarity": min_rarity, "MaxRarity": max_rarity})


    def __iand__(self, other):
        if type(self) != type(other):
            return NotImplemented
        self._dict["Tags"] &= other._dict["Tags"]
        self._dict["ExcludeTags"] &= other._dict["ExcludeTags"]
        self._dict["MinRarity"] = max(self._dict["MinRarity"], other._dict["MinRarity"])
        self._dict["MaxRarity"] = min(self._dict["MaxRarity"], other._dict["MaxRarity"])
        self._load_regexes()
        return self

    def __ior__(self, other):
        if type(self) != type(other):
            return NotImplemented
        self._dict["Tags"] |= other._dict["Tags"]
        self._dict["ExcludeTags"] |= other._dict["ExcludeTags"]
        self._dict["MinRarity"] = min(self._dict["MinRarity"], other._dict["MinRarity"])
        self._dict["MaxRarity"] = max(self._dict["MaxRarity"], other._dict["MaxRarity"])
        self._load_regexes()
        return self
