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
            if re.compile(reg["Regex"], re.UNICODE).search(text):
                matches.append(reg)
        return matches
