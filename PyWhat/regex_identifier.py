import os
import re

import yaml


class RegexIdentifier:
    def __init__(self):
        path = "Data\\regex.yaml"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r") as myfile:
            data = myfile.read()
            self.regexes = yaml.load(data, Loader=yaml.FullLoader)

    def check(self, text):
        matches = []
        for reg in self.regexes:
            matched_regex = re.findall(reg["Regex"], text, re.UNICODE)

            if matched_regex:
                for i in matched_regex:
                    matches.append({"Matched": i, "Regex Pattern": reg})
        return matches

    def clean_text(self, text):
        return text.replace("\n", "").replace("\t", "")
