import os
import re

import yaml
import json


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
                matched_regex = re.findall(reg["Regex"], txt, re.UNICODE)

                if matched_regex:
                    for i in matched_regex:
                        matches.append({"Matched": i, "Regex Pattern": reg})
        return matches

    def clean_text(self, text):
        return text.replace("\n", "").replace("\t", "")
