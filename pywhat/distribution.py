import json
import os
from typing import Optional

from pywhat.helper import AvailableTags


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

        # Load the regex
        path = "Data/regex.json"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r", encoding="utf8") as myfile:
            self._regexes = json.load(myfile)
        self.filter()

    def filter(self):
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
