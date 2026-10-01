from collections.abc import Mapping
from typing import List, Optional

from pywhat.helper import (
    AvailableTags,
    CaseInsensitiveSet,
    InvalidTag,
    available_names,
    get_names,
    load_regexes,
)


def _labels(regex: dict) -> List[str]:
    """What selects a regex in a filter: its tags and its names (issue #184)."""
    return [*regex["Tags"], *get_names(regex)]


def _intersection(
    first: CaseInsensitiveSet, second: CaseInsensitiveSet
) -> CaseInsensitiveSet:
    """
    The tags and names that are in both first and second. A name that is not
    a tag, such as "BTC Wallet", is in both if the other one has a tag or name
    of its regex too: "Finance" and "BTC Wallet" have "BTC Wallet" in common.
    """
    tags = CaseInsensitiveSet(AvailableTags().get_tags())
    shared = [value for value in first if value in second]
    for regex in load_regexes():
        labels = _labels(regex)
        for name in get_names(regex):
            if name not in tags and (
                (name in first and not second.isdisjoint(labels))
                or (name in second and not first.isdisjoint(labels))
            ):
                shared.append(name)
    return CaseInsensitiveSet(shared)


class Filter(Mapping):
    """
    A filter is an object containing the filtration information.
    The difference from Distribution object is
    that Filter object does not store regexes.

    "Tags" and "ExcludeTags" can contain the names and alternative names of
    regexes as well as tags (see pywhat.helper.get_names()).

    Example filters:
    * {"Tags": ["Networking"]}
    * {"Tags": ["Identifiers"], "ExcludeTags": ["Credentials"], "MinRarity": 0.6}
    * {"Tags": ["BTC Wallet", "ETH Wallet"]}
    """

    def __init__(self, filters_dict=None):
        tags = CaseInsensitiveSet(AvailableTags().get_tags())
        self._dict = {}
        if filters_dict is None:
            filters_dict = {}

        self._dict["Tags"] = CaseInsensitiveSet(filters_dict.setdefault("Tags", tags))
        self._dict["ExcludeTags"] = CaseInsensitiveSet(
            filters_dict.setdefault("ExcludeTags", set())
        )
        # We have regex with 0 rarity which trip false positive alarms all the time
        self._dict["MinRarity"] = filters_dict.setdefault("MinRarity", 0.1)
        self._dict["MaxRarity"] = filters_dict.setdefault("MaxRarity", 1)
        # The names of the regexes can be used like tags (issue #184)
        valid = CaseInsensitiveSet([*tags, *available_names()])
        if not self._dict["Tags"].issubset(valid) or not self._dict[
            "ExcludeTags"
        ].issubset(valid):
            raise InvalidTag(
                "Passed filter contains tags or names that are not used by 'what'"
            )

    def get_filter(self):
        return dict(self._dict)

    def __repr__(self):
        return f"{self.__class__.__name__}({self._dict})"

    def __and__(self, other):
        if type(self) != type(other):
            return NotImplemented
        tags = _intersection(self._dict["Tags"], other._dict["Tags"])
        exclude_tags = _intersection(
            self._dict["ExcludeTags"], other._dict["ExcludeTags"]
        )
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
        if not self["MinRarity"] <= item["Rarity"] <= self["MaxRarity"]:
            return False
        labels = _labels(item)
        included = not self["Tags"].isdisjoint(labels)
        return included and self["ExcludeTags"].isdisjoint(labels)

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
