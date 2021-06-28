import copy
import json
import os
import re
from typing import Optional

from pywhat.filter import Distribution, Filter


class RegexIdentifier:
    def __init__(self):
        self.distribution = Distribution()

    def check(
        self,
        text,
        dist: Optional[Distribution] = None,
        *,
        boundaryless: Optional[Filter] = None
    ):
        if dist is None:
            dist = self.distribution
        if boundaryless is None:
            boundaryless = Filter({"Tags": []})
        matches = []

        for string in text:
            for reg in dist.get_regexes():
                regex = reg["Regex"]
                if reg in boundaryless:
                    regex = re.sub(r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])", "", regex)
                    regex = re.sub(r"(?<!\\)\$(?![^\[\]]*(?<!\\)\])", "", regex)
                matched_regex = re.search(regex, string, re.UNICODE)

                if matched_regex:
                    reg = copy.copy(reg)  # necessary, when checking phone
                    # numbers from file that may contain
                    # non-international numbers
                    matched = self.clean_text(matched_regex.group(0))

                    if "Phone Number" in reg["Name"]:
                        number = re.sub(r"[-() ]", "", matched)
                        codes_path = "Data/phone_codes.json"
                        codes_fullpath = os.path.join(
                            os.path.dirname(os.path.abspath(__file__)), codes_path
                        )
                        with open(codes_fullpath, "r", encoding="utf-8") as myfile:
                            codes = json.load(myfile)

                        locations = []
                        for code in codes:
                            if number.startswith(code["dial_code"]):
                                locations.append(code["name"])
                        if len(locations) > 0:
                            reg["Description"] = (
                                "Location(s)" + ": " + ", ".join(locations)
                            )

                    matches.append(
                        {
                            "Matched": matched,
                            "Regex Pattern": reg,
                        }
                    )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
