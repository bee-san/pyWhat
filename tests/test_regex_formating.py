import re

from pywhat.helper import load_regexes

database = load_regexes()


def test_name_capitalization():
    for entry in database:
        entry_name = entry["Name"]
        for word in entry_name.split():
            upper_and_num_count = sum(1 for c in word if c.isupper() or c.isnumeric())
            if upper_and_num_count > 0:
                continue
            cleaned_word = word.translate({ord(c): None for c in "(),."})
            if cleaned_word in ["a", "of", "etc"]:
                continue

            assert word.title() == word, (
                f'Wrong capitalization in regex name: "{entry_name}"\n'
                f'Expected: "{entry_name.title()}"\n'
                "Please capitalize every the first letter of each word."
            )


def test_regex_format():
    for regex in database:
        assert re.findall(
            r"^(?:\(\?i\))?\^\(.*\)\$$", regex["Regex"]
        ), r"Please use ^(regex)$ regex format. If there is '\n' character, you have to escape it. If there is '(?i)', it is allowed and should be before the '^'."

        assert (
            re.findall(r"\^\||\|\^|\$\|\^|\$\||\|\$", regex["Regex"]) == []
        ), "Remove in-between boundaries. For example, '^|$' should only be '|'."


def test_sorted_by_rarity():
    rarity_num = [regex["Rarity"] for regex in database]

    assert rarity_num == sorted(
        rarity_num, reverse=True
    ), "Regexes should be sorted by rarity in 'regex.json'. Regexes with rarity '1' are at the top of the file and '0' is at the bottom."
