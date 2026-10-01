"""
Update the top-level domains (TLDs) of the URL regex in regex.json from the
list of IANA. The regex has two lists: all TLDs, with the internationalized ones
in punycode (XN--P1AI), and the internationalized TLDs in Unicode, written as
\\u escapes (\\u0440\\u0444 for .рф).
"""
import codecs
import json
import re

import requests

# A TLD of the Unicode list in regex.json, where the backslash of every \u
# escape is escaped
UNICODE_TLD = r"(?:[a-z]|\\\\u[0-9a-f]{4})*\\\\u[0-9a-f]{4}(?:[a-z]|\\\\u[0-9a-f]{4})*"


def unicode_name(tld: str) -> str:
    """The Unicode form of a TLD in punycode: XN--P1AI becomes рф."""
    return codecs.decode(tld[len("XN--") :].lower().encode("ascii"), "punycode")


def unicode_regex(name: str) -> str:
    """рф becomes \\u0440\\u0444, like the other regexes write non-ASCII letters."""
    return "".join(c if c.isascii() else f"\\u{ord(c):04x}" for c in name)


response = requests.get("https://data.iana.org/TLD/tlds-alpha-by-domain.txt")
tlds = response.text.split("\n")[1:-1]
final_string = "|".join(sorted(tlds, key=len, reverse=True))

# The longest TLDs first, so that the regex does not stop at a shorter TLD
names = {unicode_name(tld) for tld in tlds if tld.startswith("XN--")}
unicode_string = "|".join(
    unicode_regex(name) for name in sorted(names, key=lambda name: (-len(name), name))
)
# The JSON string of the regex escapes its backslashes
unicode_string = json.dumps(unicode_string)[1:-1]


with open("pywhat/Data/regex.json", "r") as file:
    database = file.read()

database = re.sub(
    r"(?:[A-Z0-9-]+\|){500,}[A-Z0-9-]+",
    final_string,
    database,
)
database = re.sub(
    rf"(?:{UNICODE_TLD}\|){{100,}}{UNICODE_TLD}",
    lambda match: unicode_string,
    database,
)

with open("pywhat/Data/regex.json", "w") as file:
    file.write(database)
