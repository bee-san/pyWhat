"""Script that prints the boundaryless versions of regexes in json format"""
import json
import re

from pywhat.helper import load_regexes

regexes = load_regexes()
for regex in regexes:
    regex["Regex"] = re.sub(r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])", "", regex["Regex"])
    regex["Regex"] = re.sub(r"(?<!\\)\$(?![^\[\]]*(?<!\\)\])", "", regex["Regex"])

print(json.dumps(regexes, indent=3))
