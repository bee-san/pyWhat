"""Helper utilities"""
import json
import os.path


class AvailableTags():
    def __init__(self):
        self.tags = set()
        path = "Data/regex.json"
        fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
        with open(fullpath, "r", encoding="utf-8") as myfile:
            regexes = json.load(myfile)
        for regex in regexes:
            self.tags.update(regex["Tags"])

    def get_tags(self):
        return self.tags
