import os.path
import glob
from typing import Optional

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

    def identify(self, input: str, dist: Distribution = None,
                 api=False) -> dict:
        if dist is None:
            dist = self.distribution
        identify_obj = {}
        identify_obj["File Signatures"] = {}
        identify_obj["Regexes"] = {}
        search = []

        if os.path.isdir(input):
            # if input is a directory, recursively search for all of the files
            for myfile in glob.iglob(input + "**/**", recursive=True):
                if os.path.isfile(myfile):
                    search.append(myfile)
        else:
            search = [input]

        for string in search:
            if os.path.isfile(string):
                short_name = os.path.basename(string)
                magic_numbers = self._file_sig.open_binary_scan_magic_nums(string)
                text = self._file_sig.open_file_loc(string)
                text.append(short_name)
                regex = self._regex_id.check(text)
                short_name = os.path.basename(string)

                if not magic_numbers:
                    magic_numbers = self._file_sig.check_magic_nums(string)

                if magic_numbers:
                    identify_obj["File Signatures"][short_name] = magic_numbers
            else:
                short_name = "text"
                regex = self._regex_id.check(search)

            if regex:
                identify_obj["Regexes"][short_name] = regex

        for key, value in identify_obj.items():
            # if there are zero regex or file signature matches, set it to None
            if len(identify_obj[key]) == 0:
                identify_obj[key] = None

        return identify_obj
