import json
import os
import re

from pywhat.filtration_distribution.distribution import Distribution


class RegexIdentifier:
    def __init__(self, filters_dict):
        self.distribution = Distribution(filters_dict)

    def check(self, text):
        matches = []
        for txt in text:
            for reg in self.distribution.get_regexes():
                matched_regex = re.search(reg["Regex"], txt, re.UNICODE)

                if matched_regex:
                    matches.append(
                        {
                            "Matched": self.clean_text(matched_regex.group(0)),
                            "Regex Pattern": reg,
                        }
                    )

        return matches

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
