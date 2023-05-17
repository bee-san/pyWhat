import glob
import os.path
from typing import Callable, Optional

# import pywhat.magic_numbers
# from pywhat.filter import Distribution, Filter
# from pywhat.helper import Keys
# from pywhat.regex_identifier import RegexIdentifier

import magic_numbers
from filter import Distribution, Filter
from helper import Keys
from regex_identifier import RegexIdentifier


class Identifier:
    def __init__(
        self,
        *,
        dist: Optional[Distribution] = None,
        key=Keys.NONE,
        reverse=False,
        boundaryless: Optional[Filter] = None,
    ):
        self.distribution = Distribution() if dist is None else dist
        self.boundaryless = (
            Filter({"Tags": []}) if boundaryless is None else boundaryless
        )
        self._regex_id = RegexIdentifier()
        self._key = key
        self._reverse = reverse

    def identify(
        self,
        text: str,
        *,
        only_text=True,
        dist: Distribution = None,
        key: Optional[Callable] = None,
        reverse: Optional[bool] = None,
        boundaryless: Optional[Filter] = None,
        include_filenames=False,
    ) -> dict:
        if dist is None:
            dist = self.distribution
        if key is None:
            key = self._key
        if reverse is None:
            reverse = self._reverse
        if boundaryless is None:
            boundaryless = self.boundaryless

        identify_obj: dict = {"File Signatures": {}, "Regexes": {}}
        search = []

        if not only_text and os.path.isdir(text):
            # if input is a directory, recursively search for all of the files
            for myfile in glob.iglob(text + "/**", recursive=True):
                if os.path.isfile(myfile):
                    search.append(os.path.abspath(myfile))
        else:
            search = [text]

        for string in search:
            if not only_text and os.path.isfile(string):
                if os.path.isdir(text):
                    short_name = string.replace(os.path.abspath(text), "")
                else:
                    short_name = os.path.basename(string)

                magic_numberss = magic_numbers.get_magic_nums(string)
                with open(string, "r", encoding="utf-8", errors="ignore") as file:
                    contents = [file.read()]

                if include_filenames:
                    contents.append(os.path.basename(string))

                regex = self._regex_id.check(
                    contents, dist=dist, boundaryless=boundaryless
                )

                if not magic_numberss:
                    magic_numberss = magic_numbers.check_magic_nums(string)

                if magic_numberss:
                    identify_obj["File Signatures"][short_name] = magic_numberss
            else:
                short_name = "text"
                regex = self._regex_id.check(
                    search, dist=dist, boundaryless=boundaryless
                )

            if regex:
                identify_obj["Regexes"][short_name] = regex
            
            print("Processed a string or a file \'{}\'".format(string))

        for key_, value in identify_obj.items():
            # if there are zero regex or file signature matches, set it to None
            if not value:
                identify_obj[key_] = None

        if key != Keys.NONE:
            identify_obj["Regexes"][short_name] = sorted(
                identify_obj["Regexes"][short_name], key=key, reverse=reverse
            )

        return identify_obj
