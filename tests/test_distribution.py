import json
import os

import pytest
from pywhat import pywhat_tags, Distribution
from pywhat.helper import InvalidTag


def test_distribution():
    dist = Distribution()
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
    assert regexes == dist.get_regexes()


def test_distribution2():
    filter = {
        "MinRarity": 0.3,
        "MaxRarity": 0.8,
        "Tags": ["Networking"],
        "ExcludeTags": ["Identifiers"],
    }
    dist = Distribution(filter)
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
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
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
    assert dist._dict["MinRarity"] == 0.4
    assert dist._dict["MaxRarity"] == 0.8
    assert dist._dict["Tags"] == {"Networking"}
    assert dist._dict["ExcludeTags"] == set()

    for regex in regexes:
        if 0.4 <= regex["Rarity"] <= 0.8 and "Networking" in regex["Tags"]:
            assert regex in dist.get_regexes()


def test_distribution4():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter2)
    dist &= Distribution(filter1)
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
    assert dist._dict["MinRarity"] == 0.4
    assert dist._dict["MaxRarity"] == 0.8
    assert dist._dict["Tags"] == {"Networking"}
    assert dist._dict["ExcludeTags"] == set()

    for regex in regexes:
        if 0.4 <= regex["Rarity"] <= 0.8 and "Networking" in regex["Tags"]:
            assert regex in dist.get_regexes()


def test_distribution5():
    filter1 = {"MinRarity": 0.3, "Tags": ["Networking"], "ExcludeTags": ["Identifiers"]}
    filter2 = {"MinRarity": 0.4, "MaxRarity": 0.8, "ExcludeTags": ["Media"]}
    dist = Distribution(filter1) | Distribution(filter2)
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
    assert dist._dict["MinRarity"] == 0.3
    assert dist._dict["MaxRarity"] == 1
    assert dist._dict["Tags"] == pywhat_tags
    assert dist._dict["ExcludeTags"] == {"Identifiers", "Media"}

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
    path = "../pywhat/Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        regexes = json.load(myfile)
    assert dist._dict["MinRarity"] == 0.3
    assert dist._dict["MaxRarity"] == 1
    assert dist._dict["Tags"] == pywhat_tags
    assert dist._dict["ExcludeTags"] == {"Identifiers", "Media"}

    for regex in regexes:
        if (
            0.3 <= regex["Rarity"] <= 1
            and "Identifiers" not in regex["Tags"]
            and "Media" not in regex["Tags"]
        ):
            assert regex in dist.get_regexes()


def test_distribution7():
    with pytest.raises(InvalidTag):
        dist = Distribution({"Tags": "Media", "MinRarity": 0.7})
