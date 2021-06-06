import os.path
from typing import List, Optional

from pywhat.distribution import Distribution
from pywhat.magic_numbers import FileSignatures
from pywhat.nameThatHash import Nth
from pywhat.regex_identifier import RegexIdentifier


class Identifier:
    def __init__(self, distribution: Optional[Distribution] = None):
        if distribution is None:
            self.distribution = Distribution()
        else:
            self.distribution = distribution
        self._regex_id = RegexIdentifier()
        self._file_sig = FileSignatures()
        self._name_that_hash = Nth()

    def identify(self, text: str, dist: Distribution = None,
                 api=False) -> dict:
        if dist is None:
            dist = self.distribution
        identify_obj = {}

        magic_numbers = None
        if not api and self._file_exists(text):
            magic_numbers = self._file_sig.open_binary_scan_magic_nums(text)
            text = self._file_sig.open_file_loc(text)
            identify_obj["File Signatures"] = magic_numbers
        else:
            text = [text]

        if not magic_numbers:
            # If file doesn't exist, check to see if the inputted text is
            # a file in hex format
            identify_obj["File Signatures"] = self._file_sig.check_magic_nums(text)

        identify_obj["Regexes"] = self._regex_id.check(text, dist)

        # get_hashes takes a list of hashes, we split to give it a list
        # identify_obj["Hashes"] = self._name_that_hash.get_hashes(text.split())

        return identify_obj

    def _file_exists(self, text):
        return os.path.isfile(text)
