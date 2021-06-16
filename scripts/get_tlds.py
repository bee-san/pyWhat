import re

import requests

tlds = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
final_string = "|".join(tlds.text.split("\n")[1:-1])


with open("pywhat/Data/regex.json", "r") as file:
    database = file.read()

database = re.sub(
    # what you want to replace
    r'("Name": "Uniform Resource Locator \(URL\)",\s*"Regex": ")[^"]+(")',
    # what you want to replace it with - need to be double slashes
    r"\1(?i)^(?:(?:https?|ftp):\/\/(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\\\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)(?::[0-9]{1,5})?)([a-z0-9-_\/]?\\\\.?)*$|^(?:(?:https?|ftp):\/\/)?(?:\\\\S+:\\\\S+@)?(?:[a-z0-9-_]?\\\\.?)+?(?:[a-z0-9-_][a-z0-9-_]{0,62})\\\\.(?:"
    + final_string
    + r")(?::\\\\d{2,5})?(?:[\/?#]\\\\S*)?$\2",
    database,
)

with open("pywhat/Data/regex.json", "w") as file:
    file.write(database)
