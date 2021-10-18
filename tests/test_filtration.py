import pytest

from pywhat import Distribution, Filter, pywhat_tags
from pywhat.helper import CaseInsensitiveSet, InvalidTag, load_regexes

regexes = load_regexes()


@pytest.mark.skip(
    "Dist.get_regexes() returns the regex list with the default filter of 0.1:1. \
    load_regexes() returns all regex without that filter. \
    This fails because one of them is filtered and the other is not."
)
def test_distribution():
    dist = Distribution()
    assert regexes == dist.get_regexes()


def test_distribution2():
    filter = {
        "MinRarity": 0.3,
        "MaxRarity": 0.8,
        "Tags": ["Networking"],
        "ExcludeTags": ["Identifiers"],
    }
    dist = Distribution(filter)
    for regex in regexes:
        if (
            0.3 <= regex["Rarity"] <= 0.8
            and "Networking" in regex["Tags"]
            and "Identifiers" not in regex["Tags"]
        ):
            assert regex in dist.get_regexes()


def test_distribution3():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter1) & Distribution(filter2)
    assert dist._dict["MinRarity"] == 0.4
    assert dist._dict["MaxRarity"] == 0.8
    assert dist._dict["Tags"] == CaseInsensitiveSet(["Networking"])
    assert dist._dict["ExcludeTags"] == CaseInsensitiveSet()

    for regex in regexes:
        if 0.4 <= regex["Rarity"] <= 0.8 and "Networking" in regex["Tags"]:
            assert regex in dist.get_regexes()


def test_distribution4():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter2)
    dist &= Distribution(filter1)
    assert dist._dict["MinRarity"] == 0.4
    assert dist._dict["MaxRarity"] == 0.8
    assert dist._dict["Tags"] == CaseInsensitiveSet(["Networking"])
    assert dist._dict["ExcludeTags"] == CaseInsensitiveSet()

    for regex in regexes:
        if 0.4 <= regex["Rarity"] <= 0.8 and "Networking" in regex["Tags"]:
            assert regex in dist.get_regexes()


def test_distribution5():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter1) | Distribution(filter2)
    assert dist._dict["MinRarity"] == 0.3
    assert dist._dict["MaxRarity"] == 1
    assert dist._dict["Tags"] == CaseInsensitiveSet(pywhat_tags)
    assert dist._dict["ExcludeTags"] == CaseInsensitiveSet(["Identifiers", "Media"])

    for regex in regexes:
        if (
            0.3 <= regex["Rarity"] <= 1
            and "Identifiers" not in regex["Tags"]
            and "Media" not in regex["Tags"]
        ):
            assert regex in dist.get_regexes()


def test_distribution6():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter2)
    dist |= Distribution(filter1)
    assert dist._dict["MinRarity"] == 0.3
    assert dist._dict["MaxRarity"] == 1
    assert dist._dict["Tags"] == CaseInsensitiveSet(pywhat_tags)
    assert dist._dict["ExcludeTags"] == CaseInsensitiveSet(["Identifiers", "Media"])

    for regex in regexes:
        if (
            0.3 <= regex["Rarity"] <= 1
            and "Identifiers" not in regex["Tags"]
            and "Media" not in regex["Tags"]
        ):
            assert regex in dist.get_regexes()


def test_distribution7():
    with pytest.raises(InvalidTag):
        Distribution({"Tags": "Media", "MinRarity": 0.7})


def test_filter():
    filter = {
        "MinRarity": 0.3,
        "MaxRarity": 0.8,
        "Tags": ["Networking"],
        "ExcludeTags": ["Identifiers"],
    }
    filt = Filter(filter)
    assert filt["MinRarity"] == 0.3
    assert filt["MaxRarity"] == 0.8
    assert filt["Tags"] == CaseInsensitiveSet(["networking"])
    assert filt["ExcludeTags"] == CaseInsensitiveSet(["identifiers"])


def test_filter2():
    filter1 = {
        "MinRarity": 0.3,
        "MaxRarity": 0.8,
        "Tags": ["Networking"],
        "ExcludeTags": ["Identifiers"],
    }
    filter2 = {"MinRarity": 0.5, "Tags": ["Networking", "Identifiers"]}
    filt = Filter(filter1) & Filter(filter2)
    assert filt["MinRarity"] == 0.5
    assert filt["MaxRarity"] == 0.8
    assert filt["Tags"] == CaseInsensitiveSet(["networking"])
    assert filt["ExcludeTags"] == CaseInsensitiveSet([])


def test_filter3():
    filter = {
        "MinRarity": 0.3,
        "MaxRarity": 0.8,
        "Tags": ["Networking"],
        "ExcludeTags": ["Identifiers"],
    }
    filt = Filter(filter)
    dist = Distribution(filt)
    for regex in regexes:
        if (
            0.3 <= regex["Rarity"] <= 0.8
            and "Networking" in regex["Tags"]
            and "Identifiers" not in regex["Tags"]
        ):
            assert regex in dist.get_regexes()
