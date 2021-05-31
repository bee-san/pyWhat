import copy
import json
import os
import re


class RegexIdentifier:
    def __init__(self):
        path = "Data/regex.json"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r") as myfile:
            self.regexes = json.load(myfile)

    def check(self, text):
        matches = {}
        for key, value in text.items():
            for txt in value:
                for reg in self.regexes:
                    matched_regex = re.search(reg["Regex"], txt, re.UNICODE)

                    if matched_regex:
                        # necessary, when checking phone
                        # numbers from file that may contain non-international numbers
                        reg = copy.copy(reg)
                        matched = self.clean_text(matched_regex.group(0))

                        if "Phone Number" in reg["Name"]:
                            number = re.sub(r"[-() ]", "", matched)
                            codes_path = "Data/phone_codes.json"
                            codes_fullpath = os.path.join(
                                os.path.dirname(os.path.abspath(__file__)), codes_path)
                            with open(codes_fullpath) as f:
                                codes = json.load(f)

                            locations = []
                            for code in codes:
                                if number.startswith(code["dial_code"]):
                                    locations.append(code["name"])
                            if len(locations):
                                reg["Description"] = (
                                    "Location(s)"
                                    + ": "
                                    + ", ".join(locations)
                                )

                        if key not in matches:
                            matches[key] = []

                        matches[key].append(
                            {
                                "Matched": matched,
                                "Regex Pattern": reg,
                            }
                        )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
