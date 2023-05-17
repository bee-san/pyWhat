"""Helper utilities"""
import collections.abc
import os.path
import re
from enum import Enum, auto
from functools import lru_cache
from datetime import date
import csv
from pathlib import Path

try:
    import orjson as json
except ImportError:
    import json  # type: ignore


class AvailableTags:
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


@lru_cache()
def read_json(path: str):
    fullpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data/" + path)
    with open(fullpath, "rb") as myfile:
        return json.loads(myfile.read())


@lru_cache()
def load_regexes() -> list:
    regexes = read_json("regex.json")
    for regex in regexes:
        regex["Boundaryless Regex"] = re.sub(
            r"(?<!\\)\^(?![^\[\]]*(?<!\\)\])", "", regex["Regex"]
        )
        regex["Boundaryless Regex"] = re.sub(
            r"(?<!\\)\$(?![^\[\]]*(?<!\\)\])", "", regex["Boundaryless Regex"]
        )
        children = regex.get("Children")
        if children is not None:
            try:
                children["Items"] = read_json(children["path"])
            except KeyError:
                pass
            children["lengths"] = set()
            for element in children["Items"]:
                children["lengths"].add(len(element))
    return regexes


class CaseInsensitiveSet(collections.abc.Set):
    def __init__(self, iterable=None):
        self._elements = set()
        if iterable is not None:
            self._elements = set(map(self._lower, iterable))

    def _lower(self, value):
        return value.lower() if isinstance(value, str) else value

    def __contains__(self, value):
        return self._lower(value) in self._elements

    def __iter__(self):
        return iter(self._elements)

    def __len__(self):
        return len(self._elements)

    def __repr__(self):
        return self._elements.__repr__()

    def issubset(self, other):
        return all(value in other for value in self)


class Keys(Enum):
    def NAME(match):
        return match["Regex Pattern"]["Name"]

    def RARITY(match):
        return match["Regex Pattern"]["Rarity"]

    def MATCHED(match):
        return match["Matched"]

    NONE = auto()


def str_to_key(s: str):
    try:
        return getattr(Keys, s.upper())
    except AttributeError:
        raise ValueError


class Query:
    def __init__(self, is_file: bool, content: str):
        if is_file:
            self.type = "File"
        else:
            self.type = "String"
        self.content = content
        self.query_date = (
            date.today()
        )  # record the date of the query in format "yyyy-mm-dd"

    def early_than_start_date(self, another_date) -> bool:
        return self.query_date < another_date

    def late_than_end_date(self, another_date) -> bool:
        return self.query_date > another_date

    def set_date(self, date_str):
        date_list = date_str.split("-")
        date_int_list = [int(s) for s in date_list]
        self.query_date = date(date_int_list[0], date_int_list[1], date_int_list[2])

    def is_file(self):
        return self.type == "File"

    def record(self):
        filename = Path(__file__).parent / "Data" / "record.csv"
        with open(filename, "a", newline="") as file:
            writer = csv.writer(file)
            row = [self.type, self.content, self.query_date]
            writer.writerow(row)


class Recorder:
    def __init__(self):
        self.csv_path = Path(__file__).parent / "Data" / "record.csv"

    def is_exist_csv(self):
        if os.path.exists(self.csv_path):
            return True
        else:
            return False

    def create_csv(self):
        with open(self.csv_path, "w", newline="") as file:
            writer = csv.writer(file, delimiter=",")
            row = ["type", "content", "date"]
            writer.writerow(row)

    def write_query(self, is_file: bool, content: str):
        query = Query(is_file, content)
        if not self.is_exist_csv():
            self.create_csv()
        query.record()

    def get_len_csv(self):
        if not self.is_exist_csv():
            return 0
        else:
            with open(self.csv_path, "r") as file:
                length = len(file.readlines())
                return length - 1

    def get_range_data(self, start_date, end_date):
        if not self.is_exist_csv():
            return []
        queries = []
        with open(self.csv_path, "r") as file:
            content = file.readlines()
            content = content[::-1]
            for row in content[:-1]:
                strings = row.split(",")
                query = Query(strings[0], strings[1])
                query.set_date(strings[2])
                if query.early_than_start_date(start_date):
                    break
                elif query.late_than_end_date(end_date):
                    continue
                else:
                    queries.append(row)
            return queries

    def print_csv(self, lines: int):
        if not self.is_exist_csv():
            print("No queries history so far")
            return
        else:
            length = self.get_len_csv()
            actual_lines = length
            if lines > 100 and length > 100:
                lines = 100
                print(
                    "The required number is large. The output will show the lastest 100 queries."
                )
            if length > lines:
                actual_lines = lines
            with open(self.csv_path, "r") as file:
                content = file.readlines()
                content = content[::-1]
                for row in content[:-1]:
                    if actual_lines == 0:
                        break
                    print(row)
                    actual_lines -= 1
