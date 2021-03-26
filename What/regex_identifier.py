import re
import json

class RegexIdentifier:
    def __init__(self):
        with open("data.json", "r") as myfile:
            data = myfile.read()

        self.regexes = json.loads(data)
        print(self.regexes)

        print("ok it runs??")
    def check(self, text):
        for reg in self.regexes:
            if re.compile(reg["Regex"]).match(text):
                print(reg)
                print("it done it")
