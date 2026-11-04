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

try:
    # The regex engine of the Rust crate (py/ in the repository), which the wheel
    # contains
    from pywhat import _pywhat
except ImportError:  # pragma: no cover
    # A checkout in which the extension isn't built (pip install -e . builds it)
    _pywhat = None  # type: ignore[assignment]


def _re_spans(regex: str, string: str) -> Iterator[Span]:
    """The spans of the matches of regex in string, found by Python's re."""
    return (match.span() for match in re.finditer(regex, string, re.MULTILINE))


def _text(string: str) -> Optional["_pywhat.Text"]:
    """
    string, encoded once for the searches of the Rust engine, or None if Python's
    re searches it: without the engine, or if UTF-8 can't encode string, as it
    has lone surrogates (surrogateescape makes them of the bytes of command-line
    arguments that aren't UTF-8).
    """
    if _pywhat is None:
        return None
    try:
        return _pywhat.Text(string)
    except UnicodeEncodeError:
        return None


def _spans(regex: str, string: str, text: Optional["_pywhat.Text"]) -> Iterable[Span]:
    """
    The spans of the matches of regex in string, like re.finditer(regex, string,
    re.MULTILINE), found by the Rust engine in text, the string encoded by
    _text(). Python's re searches instead if text is None, if the engine can't
    compile regex, or if it gives up on the search (fancy-regex's limit of
    100,000,000 backtracking steps), so that nothing is lost.
    """
    if text is not None:
        try:
            return _pywhat.finditer(regex, text)
        except (ValueError, _pywhat.MatchError):
            pass
    return _re_spans(regex, string)


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
            encoded = _text(string)
            for reg in dist.get_regexes():
                if progress is not None:
                    progress(reg["Name"])
                regex = (
                    reg["Boundaryless Regex"] if reg in boundaryless else reg["Regex"]
                )
                reg_processors = by_name.get(reg["Name"])
                for start, end in _spans(regex, string, encoded):
                    reg_match = dict(reg)
                    matched = self.clean_text(string[start:end])

                    if (
                        reg_match.get("Exploit") is not None
                        and "curl" in reg_match["Exploit"]
                    ):
                        # Replace anything like XXXXX_XXXXXX_HERE with the match
                        reg_match["Exploit"] = re.sub(
                            r"[A-Z_]+_HERE", lambda _: matched, reg_match["Exploit"]
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
                        found.append((processed, (start, end)))
                        yield processed

            # Fragments of longer words or matches are less likely (issue
            # #232). That is only known once every regex has been searched
            # for in string, so the matches that were yielded get their
            # "Fragment" key now.
            mark_fragments(string, found)

    def clean_text(self, text):
        return re.sub(r"[\x00-\x1f\x7f-\x9f]", "", text)
