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
        matches = []
        for txt in text:
            for reg in self.regexes:
                matched_regex = re.search(reg["Regex"], txt, re.UNICODE)

                if matched_regex:
                    matches.append(
                        {
                            "Matched": self.clean_text(matched_regex.group(0)),
                            "Regex Pattern": reg,
                        }
                    )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
