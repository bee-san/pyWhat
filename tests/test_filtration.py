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


def names_of(dist):
    return {regex["Name"] for regex in dist.get_regexes()}


def test_filter_by_names():
    # Names and alternative names work like tags (issue #184)
    dist = Distribution(
        {"Tags": ["DOGE Wallet", "ethereum (eth) wallet address"], "MinRarity": 0}
    )
    assert names_of(dist) == {
        "Dogecoin (DOGE) Wallet Address",
        "Ethereum (ETH) Wallet Address",
    }
    dist = Distribution(
        {"Tags": ["Cryptocurrency Wallet"], "ExcludeTags": ["XRP Wallet"]}
    )
    assert "Ripple (XRP) Wallet Address" not in names_of(dist)
    assert "Ethereum (ETH) Wallet Address" in names_of(dist)


@pytest.mark.parametrize(
    "filter", [{"Tags": ["Not A Name"]}, {"ExcludeTags": ["Networking", "ETH Walet"]}]
)
def test_invalid_names(filter):
    with pytest.raises(InvalidTag):
        Filter(filter)


@pytest.mark.parametrize("tag", sorted(pywhat_tags))
def test_tags_find_the_same_regexes(tag):
    # Names that are tags too, such as "Email Address", are tags of their
    # regex (see test_regex_database.py), so tags find what they used to
    with_tag = [regex for regex in regexes if tag in regex["Tags"]]
    without_tag = [regex for regex in regexes if tag not in regex["Tags"]]
    assert Distribution({"Tags": [tag], "MinRarity": 0}).get_regexes() == with_tag
    assert (
        Distribution({"ExcludeTags": [tag], "MinRarity": 0}).get_regexes()
        == without_tag
    )


def test_filter_names_without_alternative_names():
    # Regexes that are not from regex.json may have no "Alternative Names"
    regex = {"Name": "Email Address", "Rarity": 0.5, "Tags": ["Identifiers"]}
    assert regex in Filter({"Tags": ["email address"]})
    assert regex not in Filter({"Tags": ["Email"]})
    assert regex not in Filter({"ExcludeTags": ["Email Address"]})


def test_and_with_names():
    # Filter() has every tag, so it has every regex and its names
    filt = Filter() & Filter({"Tags": ["BTC Wallet"]})
    assert filt["Tags"] == CaseInsensitiveSet(["BTC Wallet"])
    # The name of a regex with the tag
    filt = Filter({"Tags": ["Finance"]}) & Filter({"Tags": ["BTC Wallet", "ARN"]})
    assert filt["Tags"] == CaseInsensitiveSet(["BTC Wallet"])
    # Two names of the same regex
    filt = Filter({"Tags": ["ETH Wallet", "ARN"]}) & Filter(
        {"Tags": ["Ethereum (ETH) Wallet Address"]}
    )
    assert filt["Tags"] == CaseInsensitiveSet(
        ["ETH Wallet", "Ethereum (ETH) Wallet Address"]
    )
    assert names_of(Distribution(filt)) == {"Ethereum (ETH) Wallet Address"}
    # A name that is a tag too is a tag, as before
    filt = Filter({"Tags": ["Identifiers"]}) & Filter({"Tags": ["UUID"]})
    assert filt["Tags"] == CaseInsensitiveSet()
    # The regexes that both exclude
    filt = Filter({"ExcludeTags": ["XRP Wallet", "ARN"]}) & Filter(
        {"ExcludeTags": ["Finance"]}
    )
    assert filt["ExcludeTags"] == CaseInsensitiveSet(["XRP Wallet"])


def test_or_with_names():
    filt = Filter({"Tags": ["BTC Wallet"], "ExcludeTags": ["ARN"]}) | Filter(
        {"Tags": ["Networking"], "ExcludeTags": ["DOI"]}
    )
    assert filt["Tags"] == CaseInsensitiveSet(["BTC Wallet", "Networking"])
    assert filt["ExcludeTags"] == CaseInsensitiveSet(["ARN", "DOI"])


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
