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
                    reg_match = copy.deepcopy(reg)
                    matched = self.clean_text(matched_regex.group(0))

                    if (
                        reg_match.get("Exploit") is not None
                        and "curl" in reg_match["Exploit"]
                    ):
                        # Replace anything like XXXXX_XXXXXX_HERE with the match
                        reg_match["Exploit"] = re.sub(
                            r"[A-Z_]+_HERE", matched, reg_match["Exploit"]
                        )

                    children = reg_match.get("Children")
                    if children is not None:
                        processed_match = re.sub(
                            children.get("deletion_pattern", ""), "", matched
                        )
                        matched_children = []
                        if children["method"] == "hashmap":
                            for length in children["lengths"]:
                                try:
                                    matched_children.append(
                                        children["Items"][processed_match[:length]]
                                    )
                                except KeyError:
                                    continue
                        else:
                            for element in children["Items"]:
                                if (
                                    children["method"] == "regex"
                                    and re.search(
                                        element, processed_match, re.MULTILINE
                                    )
                                ) or (
                                    children["method"] == "startswith"
                                    and processed_match.startswith(element)
                                ):
                                    matched_children.append(children["Items"][element])

                        if matched_children:
                            reg_match["Description"] = children.get(
                                "entry", ""
                            ) + ", ".join(matched_children)
                    reg_match.pop("Children", None)

                    matches.append(
                        {
                            "Matched": matched,
                            "Regex Pattern": reg_match,
                        }
                    )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
