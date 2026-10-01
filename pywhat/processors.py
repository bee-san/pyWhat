"""
Non-regex processing of matches, see issue #115.

A regex finds something, then a processor can do what a regex cannot, such
as changing the description or the rarity of a match based on the matched
text, or filtering out a false positive.

Identifier and RegexIdentifier use default_processors() unless they are
given other processors. processors=[] turns processing off.

verifiers() are processors that ask a service if a key is valid (issue #245).
They are not default processors because they send the keys to the service.

OpenStreetMapProcessor links coordinates to OpenStreetMap instead of Google
Maps (issue #263), which pywhat --map osm does.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from http.client import HTTPException
from typing import Collection, Dict, Iterable, List, Optional
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from pywhat.bitcoin import is_bitcoin_address
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


class BitcoinAddressProcessor(Processor):
    """
    Filters out the matches of the Bitcoin regex whose checksum is wrong, such
    as "3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F3F" (issue #239).
    """

    names = ("Bitcoin (\u20bf) Wallet Address",)

    def process(self, match: dict) -> Optional[dict]:
        return match if is_bitcoin_address(match["Matched"]) else None


# The @latitude,longitude,zoom notation of Google Maps, such as
# "@13.923404,101.3395163,17z"
GOOGLE_MAPS_NOTATION = re.compile(
    r"@(?P<lat>-?\d+(?:\.\d+)?),(?P<lon>-?\d+(?:\.\d+)?),\d+(?:\.\d+)?z",
    re.IGNORECASE,
)


class OpenStreetMapProcessor(Processor):
    """
    Links coordinates to OpenStreetMap instead of Google Maps (issue #263),
    which pywhat --map osm does: "52.6169586, -1.9779857" links to
    https://www.openstreetmap.org/search?query=52.6169586,-1.9779857

    The search of OpenStreetMap finds coordinates in decimal degrees, and in
    degrees, minutes and seconds with N, S, E and W. It does not understand the
    @latitude,longitude,zoom notation of Google Maps, so the latitude and the
    longitude of "@13.923404,101.3395163,17z" are searched for.

    The link is the "Link" of the match, which the printer shows, and the "URL"
    of the match is the URL of the search.
    """

    names = ["Latitude & Longitude Coordinates"]
    url = "https://www.openstreetmap.org/search?query="

    def process(self, match: dict) -> Optional[dict]:
        regex = match["Regex Pattern"]
        regex["URL"] = self.url
        regex["Link"] = self.url + quote(self.query(match["Matched"]), safe=",")
        return match

    @staticmethod
    def query(coordinates: str) -> str:
        """
        The text to search OpenStreetMap for: "52.6169586,-1.9779857" for
        "52.6169586, -1.9779857" and "13.923404,101.3395163" for
        "@13.923404,101.3395163,17z". Plus signs, as in "+52.6169586", are
        left out, a "+" in a query string can mean a space.
        """
        # A space is only needed between two numbers, e.g. between the minutes
        # and the seconds of "41 deg 2 12.2 N", which is not 41 deg 21 2.2 N
        query = " ".join(coordinates.replace("+", "").split())
        query = re.sub(r"(?<!\d) | (?!\d)", "", query)
        notation = GOOGLE_MAPS_NOTATION.fullmatch(query)
        if notation:
            return f"{notation['lat']},{notation['lon']}"
        return query


def google_error_reason(body: bytes) -> Optional[str]:
    """
    The reason of the google.rpc.ErrorInfo in an error that a Google API
    answered, such as "API_KEY_INVALID", or None if there is none:
    {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.ErrorInfo",
    "reason": "API_KEY_INVALID", ...}, ...], ...}}
    """
    try:
        for detail in json.loads(body)["error"].get("details", []):
            if detail.get("@type", "").endswith("google.rpc.ErrorInfo"):
                return detail.get("reason")
    except (ValueError, TypeError, KeyError, AttributeError):
        pass  # not JSON (ValueError), or not a Google API error
    return None


class GoogleAPIKeyVerifier(Processor):
    """
    Asks Google if a Google API key is valid and adds the answer to the
    description of the match (issue #245), e.g. "Verification: invalid, Google
    rejected the key (API_KEY_INVALID)".

    Google answers API_KEY_INVALID for an invalid key. A valid key can be
    restricted to some APIs, so errors such as SERVICE_DISABLED (the API is not
    enabled for the key) mean that the key is valid too. The request is made
    to an API that does not cost money (the YouTube Data API's languages, 1
    unit of quota). Every key is sent to Google once, however many times it
    is found.
    """

    names = ["Google API Key"]
    url = "https://www.googleapis.com/youtube/v3/i18nLanguages?part=snippet&key="
    # The google.rpc.ErrorInfo reasons of the errors that Google answers when
    # the key is valid, but cannot be used for the request
    valid_key_reasons = frozenset(
        {
            "API_KEY_ANDROID_APP_BLOCKED",
            "API_KEY_HTTP_REFERRER_BLOCKED",
            "API_KEY_IOS_APP_BLOCKED",
            "API_KEY_IP_ADDRESS_BLOCKED",
            "API_KEY_SERVICE_BLOCKED",
            "BILLING_DISABLED",
            "RATE_LIMIT_EXCEEDED",
            "RESOURCE_QUOTA_EXCEEDED",
            "SERVICE_DISABLED",
        }
    )

    def __init__(self, timeout: float = 10):
        self.timeout = timeout
        # The verification of each key, so that it is only sent once
        self.results: Dict[str, str] = {}

    def process(self, match: dict) -> Optional[dict]:
        key = match["Matched"]
        if key not in self.results:
            self.results[key] = self.verify(key)
        regex = match["Regex Pattern"]
        result = f"Verification: {self.results[key]}"
        description = regex.get("Description")
        regex["Description"] = f"{description}. {result}" if description else result
        return match

    def verify(self, key: str) -> str:
        """Ask Google if key is valid. Returns the answer, e.g. "valid, ..."."""
        request = Request(
            self.url + quote(key, safe=""), headers={"User-Agent": "pywhat"}
        )
        try:
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    response.read()
            except HTTPError as error:
                return self.describe_error(error.code, error.read())
        except (OSError, HTTPException, ValueError) as error:
            # No connection, a timeout (URLError and socket.timeout are OSErrors)
            return f"unknown, could not ask Google ({error})"
        return "valid, Google accepted the key"

    def describe_error(self, code: int, body: bytes) -> str:
        """The verification of a key that Google answered an error for."""
        reason = google_error_reason(body)
        if reason == "API_KEY_INVALID":
            return f"invalid, Google rejected the key ({reason})"
        if reason in self.valid_key_reasons:
            return f"valid, but Google refused the request ({reason})"
        if reason:
            return f"unknown, Google answered HTTP {code} ({reason})"
        return f"unknown, Google answered HTTP {code}"


def default_processors() -> List[Processor]:
    """New instances of the processors that pyWhat uses by default."""
    return [UnixTimestampProcessor(), BitcoinAddressProcessor()]


def verifiers() -> List[Processor]:
    """
    New instances of the processors that ask a service if a key is valid,
    which pywhat --verify uses. They send the keys that are found to the
    service, so they are not default processors.
    """
    return [GoogleAPIKeyVerifier()]
