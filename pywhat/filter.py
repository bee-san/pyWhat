from collections.abc import Mapping
from typing import Optional

from pywhat.helper import AvailableTags, CaseInsensitiveSet, InvalidTag, load_regexes


class Filter(Mapping):
    """
    A filter is an object containing the filtration information.
    The difference from Distribution object is
    that Filter object does not store regexes.

    Example filters:
    * {"Tags": ["Networking"]}
    * {"Tags": ["Identifiers"], "ExcludeTags": ["Credentials"], "MinRarity": 0.6}
    """

    def __init__(self, filters_dict: Optional[Mapping] = None):
        tags = CaseInsensitiveSet(AvailableTags().get_tags())
        self._dict = dict()
        if filters_dict is None:
            filters_dict = {}

        self._dict["Tags"] = CaseInsensitiveSet(filters_dict.setdefault("Tags", tags))
        self._dict["ExcludeTags"] = CaseInsensitiveSet(
            filters_dict.setdefault("ExcludeTags", set())
        )
        # We have regex with 0 rarity which trip false positive alarms all the time
        self._dict["MinRarity"] = filters_dict.setdefault("MinRarity", 0.1)
        self._dict["MaxRarity"] = filters_dict.setdefault("MaxRarity", 1)
        if not self._dict["Tags"].issubset(tags) or not self._dict[
            "ExcludeTags"
        ].issubset(tags):
            raise InvalidTag("Passed filter contains tags that are not used by 'what'")

    def get_filter(self):
        return dict(self._dict)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._dict})"

    def __and__(self, other):
        if type(self) != type(other):
            return NotImplemented
        tags = self._dict["Tags"] & other._dict["Tags"]
        exclude_tags = self._dict["ExcludeTags"] & other._dict["ExcludeTags"]
        min_rarity = max(self._dict["MinRarity"], other._dict["MinRarity"])
        max_rarity = min(self._dict["MaxRarity"], other._dict["MaxRarity"])
        return self.__class__(
            {
                "Tags": tags,
                "ExcludeTags": exclude_tags,
                "MinRarity": min_rarity,
                "MaxRarity": max_rarity,
            }
        )

    def __or__(self, other):
        if type(self) != type(other):
            return NotImplemented
        tags = self._dict["Tags"] | other._dict["Tags"]
        exclude_tags = self._dict["ExcludeTags"] | other._dict["ExcludeTags"]
        min_rarity = min(self._dict["MinRarity"], other._dict["MinRarity"])
        max_rarity = max(self._dict["MaxRarity"], other._dict["MaxRarity"])
        return self.__class__(
            {
                "Tags": tags,
                "ExcludeTags": exclude_tags,
                "MinRarity": min_rarity,
                "MaxRarity": max_rarity,
            }
        )

    def __iand__(self, other):
        if type(self) != type(other):
            return NotImplemented
        return self & other

    def __ior__(self, other):
        if type(self) != type(other):
            return NotImplemented
        return self | other

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __contains__(self, item):
        try:
            return (
                self["MinRarity"] <= item["Rarity"] <= self["MaxRarity"]
                and set(item["Tags"]) & self["Tags"]
                and not set(item["Tags"]) & self["ExcludeTags"]
            )
        except:
            return False

    def setdefault(self, key, default=None):
        return self._dict.setdefault(key, default)


class Distribution(Filter):
    """
    A distribution is an object containing the regex
    But the regex has gone through a filter process.

    Example filters:
    * {"Tags": ["Networking"]}
    * {"Tags": ["Identifiers"], "ExcludeTags": ["Credentials"], "MinRarity": 0.6}
    """

    def __init__(self, filter: Optional[Filter] = None):
        super().__init__(filter)
        self._filter()

    def _filter(self):
        self._regexes = load_regexes()
        temp_regexes = [regex for regex in self._regexes if regex in self]
        self._regexes = temp_regexes

    def get_regexes(self):
        return list(self._regexes)
