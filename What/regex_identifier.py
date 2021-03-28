import re
import yaml


class RegexIdentifier:
    def __init__(self):
        with open("What/data.yaml", "r") as myfile:
            data = myfile.read()
            self.regexes = yaml.load(data, Loader=yaml.FullLoader)

    def check(self, text):
        matches = []
        for reg in self.regexes:
            matched_regex = re.compile(reg["Regex"], re.UNICODE).search(text)
            if matched_regex:
                matches.append({"Matched": matched_regex.group(), "Regex Pattern": reg})
        return matches
