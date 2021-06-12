from typing import Optional

from pywhat.helper import AvailableTags, CaseInsensitiveSet, InvalidTag, load_regexes


class Distribution:
    """
    A distribution is an object containing the regex
    But the regex has gone through a filter process.

    Example filters:
    * {"Tags": ["Networking"]}
    * {"Tags": ["Identifiers"], "ExcludeTags": ["Credentials"], "MinRarity": 0.6}
    """

    def __init__(self, filters_dict: Optional[dict] = None):
        tags = CaseInsensitiveSet(AvailableTags().get_tags())
        self._dict = dict()
        if filters_dict is None:
            filters_dict = dict()

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

        self._regexes = load_regexes()
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

    def get_filter(self):
        return dict(self._dict)

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
        return Distribution(
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
