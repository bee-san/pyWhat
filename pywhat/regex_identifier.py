import copy
import re
from typing import Optional

from pywhat.filter import Distribution, Filter


class RegexIdentifier:
    def __init__(self):
        self.distribution = Distribution()

    def check(
        self,
        text,
        dist: Optional[Distribution] = None,
        *,
        boundaryless: Optional[Filter] = None
    ):
        if dist is None:
            dist = self.distribution
        if boundaryless is None:
            boundaryless = Filter({"Tags": []})
        matches = []

        for string in text:
            for reg in dist.get_regexes():
                regex = (
                    reg["Boundaryless Regex"] if reg in boundaryless else reg["Regex"]
                )

                for matched_regex in re.finditer(regex, string, re.MULTILINE):
                    reg = copy.copy(reg)
                    matched = self.clean_text(matched_regex.group(0))
                    processed_match = re.sub(
                        reg.get("removal_pattern", ""), "", matched
                    )
                    use_startswith = reg.get("use_startswith", False)

                    matched_children = []
                    for child in reg.get("Children", []):
                        if use_startswith:
                            if processed_match.startswith(child["Regex"]):
                                matched_children.append(child["Name"])
                        elif re.search(child["Regex"], processed_match, re.MULTILINE):
                            matched_children.append(child["Name"])

                    if matched_children:
                        reg["Description"] = reg.get("children_entry", "") + ", ".join(
                            matched_children
                        )

                    matches.append(
                        {
                            "Matched": matched,
                            "Regex Pattern": reg,
                        }
                    )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
