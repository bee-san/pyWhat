"""Helper utilities"""
import json
import os.path


class AvailableTags():
    def __init__(self):
        self.tags = set()
        regexes = load_regexes()
        for regex in regexes:
            self.tags.update(regex["Tags"])

    def get_tags(self):
        return self.tags


class InvalidTag(Exception):
    """
    This exception should be raised when Distribution() gets a filter
    containing non-existent tags.
    """
    pass



def load_regexes() -> list:
    path = "Data/regex.json"
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(fullpath, "r", encoding="utf-8") as myfile:
        return json.load(myfile)