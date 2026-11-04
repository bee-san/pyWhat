"""Rewrite the regex files in pywhat/Data in their format: json.dump(indent=3)."""
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "pywhat" / "Data"

for path in [DATA / "regex.json", *sorted((DATA / "regexes").glob("*.json"))]:
    with open(path, encoding="utf-8") as file:
        database = json.load(file)
    with open(path, "w", encoding="utf-8") as file:
        file.write(json.dumps(database, indent=3) + "\n")
