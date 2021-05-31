import os.path
from typing import List, Optional

from pywhat.magic_numbers import FileSignatures
from pywhat.nameThatHash import Nth
from pywhat.regex_identifier import RegexIdentifier


class Identifier:
    def __init__(self):
        self.regex_id = RegexIdentifier()
        self.file_sig = FileSignatures()
        self.name_that_hash = Nth()
        self.tags = set()
        for regex in self.regex_id.regexes:
            self.tags.update(regex["Tags"])

    def identify(self, text: str, api=False, filters_dict = {"Tags": "Networking"}) -> dict:
        identify_obj = {}

        magic_numbers = None
        if not api and self.file_exists(text):
            magic_numbers = self.file_sig.open_binary_scan_magic_nums(text)
            text = self.file_sig.open_file_loc(text)
            identify_obj["File Signatures"] = magic_numbers
        else:
            text = [text]

        if not magic_numbers:
            # If file doesn't exist, check to see if the inputted text is
            # a file in hex format
            identify_obj["File Signatures"] = self.file_sig.check_magic_nums(text)

        regexes = self.regex_id.check(text)
        identify_obj["Regexes"] = []
        used_tags = (
            set(self.tags) if included_tags is None else set(included_tags))
        unused_tags = (set() if excluded_tags is None else set(excluded_tags))

        for regex in regexes:
            if (min_rarity <= regex["Regex Pattern"]["Rarity"] <= max_rarity and
                used_tags & set(regex["Regex Pattern"]["Tags"]) and
                not unused_tags & set(regex["Regex Pattern"]["Tags"])
                ):
                identify_obj["Regexes"].append(regex)

        # get_hashes takes a list of hashes, we split to give it a list
        # identify_obj["Hashes"] = self.name_that_hash.get_hashes(text.split())

        return identify_obj

    def file_exists(self, text):
        return os.path.isfile(text)
