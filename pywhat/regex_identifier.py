import re
from typing import Any, Callable, Iterable, Iterator, List, Optional, Tuple

from pywhat.filter import Distribution, Filter
from pywhat.processors import (
    Processor,
    default_processors,
    processors_by_name,
    run_processors,
)
from pywhat.ranking import Span, mark_fragments


class RegexIdentifier:
    def __init__(self, processors: Optional[Iterable[Processor]] = None):
        self.distribution = Distribution()
        # Non-regex processing of the matches (issue #115)
        self.processors = (
            default_processors() if processors is None else list(processors)
        )

    def check(
        self,
        text,
        dist: Optional[Distribution] = None,
        *,
        boundaryless: Optional[Filter] = None,
        processors: Optional[Iterable[Processor]] = None,
    ):
        """The matches of the regexes of dist in every string of text."""
        return list(
            self.iter_check(
                text, dist, boundaryless=boundaryless, processors=processors
            )
        )

    def iter_check(
        self,
        text,
        dist: Optional[Distribution] = None,
        *,
        boundaryless: Optional[Filter] = None,
        processors: Optional[Iterable[Processor]] = None,
        progress: Optional[Callable[[str], Any]] = None,
    ) -> Iterator[dict]:
        """
        Like check(), but a generator, which yields every match as soon as it
        is found (issue #189). progress, if given, is called with the name of
        every regex before it is searched for in a string of text.
        """
        if dist is None:
            dist = self.distribution
        if boundaryless is None:
            boundaryless = Filter({"Tags": []})
        if processors is None:
            processors = self.processors
        by_name = processors_by_name(processors)

        for string in text:
            # The matches of string, with their spans to mark the fragments
            found: List[Tuple[dict, Span]] = []
            for reg in dist.get_regexes():
                if progress is not None:
                    progress(reg["Name"])
                regex = (
                    reg["Boundaryless Regex"] if reg in boundaryless else reg["Regex"]
                )
                reg_processors = by_name.get(reg["Name"])
                for matched_regex in re.finditer(regex, string, re.MULTILINE):
                    reg_match = dict(reg)
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

                    match = {
                        "Matched": matched,
                        "Regex Pattern": reg_match,
                    }
                    processed: Optional[dict] = match
                    if reg_processors:
                        processed = run_processors(match, reg_processors, dist)
                    if processed is not None:
                        found.append((processed, matched_regex.span()))
                        yield processed

            # Fragments of longer words or matches are less likely (issue
            # #232). That is only known once every regex has been searched
            # for in string, so the matches that were yielded get their
            # "Fragment" key now.
            mark_fragments(string, found)

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
