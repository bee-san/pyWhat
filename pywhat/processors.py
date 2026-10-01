"""
Non-regex processing of matches, see issue #115.

A regex finds something, then a processor can do what a regex cannot, such
as changing the description or the rarity of a match based on the matched
text, or filtering out a false positive.

Identifier and RegexIdentifier use default_processors() unless they are
given other processors. processors=[] turns processing off.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Collection, Dict, Iterable, List, Optional

from pywhat.filter import Filter

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
# Not calendar.month_name, which depends on the locale
MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


class Processor:
    """
    Processes the matches of the regexes named in names, one match at a time.

    A processor is an object, so it can keep state between matches. For
    example, a processor which filters out the URLs of a site:

        class URLProcessor(Processor):
            names = ["Uniform Resource Locator (URL)"]

            def process(self, match):
                if "trashurl.it" in match["Matched"]:
                    return None
                return match
    """

    # The names of the regexes (their "Name" in regex.json) to process
    names: Collection[str] = ()

    def process(self, match: dict) -> Optional[dict]:
        """
        Process a match, a dict such as {"Matched": "1637093119", "Regex
        Pattern": {"Name": "Unix Timestamp", ...}}, like the matches that
        Identifier.identify() returns. Return the match, which may be changed,
        or None to filter it out.
        """
        return match


def processors_by_name(processors: Iterable[Processor]) -> Dict[str, List[Processor]]:
    """The processors of each regex name, in the order of processors."""
    by_name: Dict[str, List[Processor]] = {}
    for processor in processors:
        for name in processor.names:
            by_name.setdefault(name, []).append(processor)
    return by_name


def run_processors(
    match: dict, processors: Iterable[Processor], dist: Filter
) -> Optional[dict]:
    """
    Run the processors on a match in order, each one on what the one before
    it returned. Returns the processed match, or None if a processor filtered
    it out or if it is no longer in dist, e.g. because its rarity was lowered.
    """
    # The "Regex Pattern" of a match is a copy, but its tags are shared with
    # the regex database, so a processor must not change them in place
    match["Regex Pattern"]["Tags"] = list(match["Regex Pattern"]["Tags"])
    for processor in processors:
        processed = processor.process(match)
        if processed is None:
            return None
        match = processed
    return match if match["Regex Pattern"] in dist else None


def timestamp_to_datetime(timestamp: str, unit: int = 1_000_000) -> datetime:
    """
    The date and time, in UTC, of a Unix timestamp such as "1637093119" or
    "1637093119.558717". unit is the number of microseconds in a unit of the
    timestamp: 1_000_000 for seconds, 1000 for milliseconds.

    Raises ValueError or ArithmeticError if timestamp is not a number or the
    date is out of range (after the year 9999).
    """
    # Decimal and timedelta, not datetime.fromtimestamp(), so that there are
    # no float rounding errors and no platform-dependent range
    return EPOCH + timedelta(microseconds=int(Decimal(timestamp) * unit))


def format_datetime(moment: datetime) -> str:
    """
    Format a date and time like "November 16, 2021 8:05:19 PM" (issue #234),
    in English whatever the locale. Fractions of a second are only shown if
    there are any, e.g. "8:05:19.558 PM".
    """
    seconds = f"{moment.second:02d}"
    if moment.microsecond:
        seconds += f".{moment.microsecond:06d}".rstrip("0")
    hour = moment.hour % 12 or 12
    am_pm = "AM" if moment.hour < 12 else "PM"
    return (
        f"{MONTHS[moment.month - 1]} {moment.day}, {moment.year} "
        f"{hour}:{moment.minute:02d}:{seconds} {am_pm}"
    )


class UnixTimestampProcessor(Processor):
    """
    Adds the date and time of a Unix timestamp, in UTC, to its description:
    "1637093119" is "... Date: November 16, 2021 8:05:19 PM UTC".
    """

    # The number of microseconds in a unit of the timestamps, by regex name
    units = {
        "Recent Unix Timestamp": 1_000_000,
        "Recent Unix Millisecond Timestamp": 1000,
        "Unix Timestamp": 1_000_000,
        "Unix Millisecond Timestamp": 1000,
    }
    names = tuple(units)

    def process(self, match: dict) -> Optional[dict]:
        regex = match["Regex Pattern"]
        try:
            moment = timestamp_to_datetime(match["Matched"], self.units[regex["Name"]])
        except (ValueError, ArithmeticError):
            return match  # the regex matched something that is not a date
        date = f"Date: {format_datetime(moment)} UTC"
        description = regex.get("Description")
        regex["Description"] = f"{description}. {date}" if description else date
        return match


def default_processors() -> List[Processor]:
    """New instances of the processors that pyWhat uses by default."""
    return [UnixTimestampProcessor()]
