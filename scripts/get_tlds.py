import re

import requests

tlds = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
final_string = "|".join(sorted(tlds.text.split("\n")[1:-1], key=len, reverse=True))


with open("pywhat/Data/regex.json", "r") as file:
    database = file.read()

database = re.sub(
    r"(?:[A-Z0-9-]+\|){500,}[A-Z0-9-]+",
    final_string,
    database,
)

with open("pywhat/Data/regex.json", "w") as file:
    file.write(database)
