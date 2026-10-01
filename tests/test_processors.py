"""
Tests for the non-regex processing of matches (issue #115) and the dates of
Unix timestamps (issue #234).
"""
import copy
import io
import json
import os
from datetime import datetime, timezone
from typing import List, Optional, Set

import pytest
from click.testing import CliRunner
from rich.console import Console

from pywhat import Distribution, Filter, Identifier, Processor
from pywhat.helper import load_regexes
from pywhat.interactive import InteractiveShell
from pywhat.processors import (
    EPOCH,
    BitcoinAddressProcessor,
    UnixTimestampProcessor,
    default_processors,
    format_datetime,
    processors_by_name,
    run_processors,
    timestamp_to_datetime,
)
from pywhat.regex_identifier import RegexIdentifier
from pywhat.what import main

UTC = timezone.utc
# Unix timestamps have a rarity of 0
TIMESTAMPS = Distribution(Filter({"MinRarity": 0, "Tags": ["UNIX Timestamp"]}))
TIMESTAMPS_OPTIONS = ["--rarity", "0:", "--include", "UNIX Timestamp"]
TIMESTAMPS_SEARCH = 'include:"UNIX Timestamp", rarity:"0:"'
DATE = "Date: November 16, 2021 8:05:19 PM UTC"  # of 1637093119, issue #234
URL = "Uniform Resource Locator (URL)"
THM = "TryHackMe Flag Format"


def database_entry(name: str) -> dict:
    return next(regex for regex in load_regexes() if regex["Name"] == name)


def description(name: str) -> str:
    """The description of the regex called name in regex.json."""
    return database_entry(name)["Description"]


def descriptions(identified: dict, location: str = "text") -> dict:
    """The description of each regex name that matched in location."""
    return {
        found["Regex Pattern"]["Name"]: found["Regex Pattern"]["Description"]
        for found in identified["Regexes"][location]
    }


def names(identified: dict) -> Set[str]:
    return {
        found["Regex Pattern"]["Name"]
        for matches in (identified["Regexes"] or {}).values()
        for found in matches
    }


def matched(matches: List[dict], name: str) -> List[str]:
    """The matched texts of the regex called name."""
    return [
        found["Matched"] for found in matches if found["Regex Pattern"]["Name"] == name
    ]


def run_cli(args: List[str], input: Optional[str] = None) -> str:
    result = CliRunner().invoke(main, args, input=input)
    assert result.exit_code == 0, result.output
    return result.output


def words(text: str) -> str:
    """text with every run of whitespace replaced by a space (rich wraps lines)."""
    return " ".join(text.split())


def run_shell(commands: List[str], text_input: str, **options) -> str:
    """Run interactive mode with the commands and return its output."""
    stdout = io.StringIO()
    InteractiveShell(
        stdin=io.StringIO("".join(command + "\n" for command in commands)),
        stdout=stdout,
        console=Console(
            file=stdout,
            width=200,
            highlight=False,
            color_system=None,
            force_terminal=False,
        ),
        **options,
    ).run(text_input)
    return stdout.getvalue()


class URLProcessor(Processor):
    """The example of issue #115: filter out the URLs of a site."""

    names = [URL]

    def process(self, match):
        if "trashurl.it" in match["Matched"]:
            return None
        return match


class FirstOnly(Processor):
    """Keeps state between matches: filters out repeated flags."""

    names = [THM]

    def __init__(self):
        self.seen: Set[str] = set()

    def process(self, match):
        if match["Matched"] in self.seen:
            return None
        self.seen.add(match["Matched"])
        return match


class Append(Processor):
    """Appends text to the description of every match of the regexes."""

    def __init__(self, text: str, names=(THM,)):
        self.text = text
        self.names = names
        self.calls = 0

    def process(self, match):
        self.calls += 1
        match["Regex Pattern"]["Description"] += self.text
        return match


class Drop(Processor):
    def __init__(self, names=(THM,)):
        self.names = names

    def process(self, match):
        return None


class Rarity(Processor):
    names = [THM]

    def __init__(self, rarity: float):
        self.rarity = rarity

    def process(self, match):
        match["Regex Pattern"]["Rarity"] = self.rarity
        return match


class Tagger(Processor):
    """Changes the tags and the description in place."""

    names = [THM]

    def process(self, match):
        match["Regex Pattern"]["Tags"].append("Checked")
        match["Regex Pattern"]["Description"] = "Checked"
        return match


def thm_match(description: str = "") -> dict:
    regex = dict(database_entry(THM))
    regex["Description"] = description
    return {"Matched": "THM{hello}", "Regex Pattern": regex}


def timestamp_match(
    matched: str,
    name: str = "Unix Timestamp",
    description: Optional[str] = "A timestamp",
) -> dict:
    return {
        "Matched": matched,
        "Regex Pattern": {
            "Name": name,
            "Description": description,
            "Rarity": 0,
            "Tags": ["UNIX Timestamp", "Timestamp", "UNIX"],
        },
    }


# Dates


@pytest.mark.parametrize(
    "timestamp, unit, expected",
    [
        ("1637093119", 1_000_000, datetime(2021, 11, 16, 20, 5, 19, tzinfo=UTC)),
        (
            "1637093119.558717",
            1_000_000,
            datetime(2021, 11, 16, 20, 5, 19, 558717, tzinfo=UTC),
        ),
        # Fractions smaller than a microsecond are cut off
        (
            "1637093119.123456789",
            1_000_000,
            datetime(2021, 11, 16, 20, 5, 19, 123456, tzinfo=UTC),
        ),
        ("1637093119558", 1000, datetime(2021, 11, 16, 20, 5, 19, 558000, tzinfo=UTC)),
        ("94694400", 1_000_000, datetime(1973, 1, 1, tzinfo=UTC)),
        ("9999999999", 1_000_000, datetime(2286, 11, 20, 17, 46, 39, tzinfo=UTC)),
        ("0", 1_000_000, EPOCH),
    ],
)
def test_timestamp_to_datetime(timestamp, unit, expected):
    assert timestamp_to_datetime(timestamp, unit) == expected


def test_timestamp_to_datetime_defaults_to_seconds():
    assert timestamp_to_datetime("1637093119") == datetime(
        2021, 11, 16, 20, 5, 19, tzinfo=UTC
    )


@pytest.mark.parametrize(
    "timestamp", ["not a number", "", "NaN", "Infinity", "99999999999999999999"]
)
def test_timestamp_to_datetime_errors(timestamp):
    with pytest.raises((ValueError, ArithmeticError)):
        timestamp_to_datetime(timestamp)


@pytest.mark.parametrize(
    "moment, expected",
    [
        (datetime(2021, 11, 16, 20, 5, 19), "November 16, 2021 8:05:19 PM"),
        (datetime(1970, 1, 1), "January 1, 1970 12:00:00 AM"),
        (datetime(2020, 1, 1, 12), "January 1, 2020 12:00:00 PM"),
        (datetime(2009, 2, 13, 23, 31, 30), "February 13, 2009 11:31:30 PM"),
        (datetime(2021, 11, 16, 20, 5, 19, 558000), "November 16, 2021 8:05:19.558 PM"),
        (
            datetime(2021, 11, 16, 20, 5, 19, 558717),
            "November 16, 2021 8:05:19.558717 PM",
        ),
        (datetime(2000, 2, 29, 9, 3, 7, 5), "February 29, 2000 9:03:07.000005 AM"),
    ],
)
def test_format_datetime(moment, expected):
    assert format_datetime(moment) == expected


# UnixTimestampProcessor


@pytest.mark.parametrize(
    "matched, name, date",
    [
        ("1637093119", "Unix Timestamp", DATE),
        ("1637093119", "Recent Unix Timestamp", DATE),
        (
            "1637093119.558717",
            "Unix Timestamp",
            "Date: November 16, 2021 8:05:19.558717 PM UTC",
        ),
        (
            "1637093119558",
            "Unix Millisecond Timestamp",
            "Date: November 16, 2021 8:05:19.558 PM UTC",
        ),
        (
            "1637093119558",
            "Recent Unix Millisecond Timestamp",
            "Date: November 16, 2021 8:05:19.558 PM UTC",
        ),
        ("94694400", "Unix Timestamp", "Date: January 1, 1973 12:00:00 AM UTC"),
    ],
)
def test_unix_timestamp_processor(matched, name, date):
    processed = UnixTimestampProcessor().process(timestamp_match(matched, name))
    assert processed is not None
    assert processed["Matched"] == matched
    assert processed["Regex Pattern"]["Description"] == f"A timestamp. {date}"


def test_unix_timestamp_processor_without_description():
    processed = UnixTimestampProcessor().process(
        timestamp_match("1637093119", description=None)
    )
    assert processed is not None
    assert processed["Regex Pattern"]["Description"] == DATE


def test_unix_timestamp_processor_keeps_matches_that_are_not_dates():
    # After the year 9999, a datetime cannot be created
    match = timestamp_match("99999999999999999999")
    processed = UnixTimestampProcessor().process(copy.deepcopy(match))
    assert processed == match


def test_processor_names_are_regexes_in_the_database():
    regex_names = {regex["Name"] for regex in load_regexes()}
    for processor in default_processors():
        assert processor.names, f"{type(processor).__name__} processes nothing"
        for name in processor.names:
            assert name in regex_names, (
                f"{type(processor).__name__} processes '{name}', which is not "
                "the name of a regex in 'regex.json'"
            )


def test_default_processors_are_new_instances():
    assert [type(p) for p in default_processors()] == [
        UnixTimestampProcessor,
        BitcoinAddressProcessor,
    ]
    assert default_processors()[0] is not default_processors()[0]


# The processor framework


def test_base_processor_keeps_matches():
    match = thm_match()
    assert Processor().process(match) is match
    assert not Processor.names


def test_processors_by_name():
    first, second = Append("1", names=("A", "B")), Append("2", names=("B",))
    assert processors_by_name([first, second]) == {
        "A": [first],
        "B": [first, second],
    }
    assert processors_by_name([]) == {}


def test_run_processors_in_order():
    processed = run_processors(thm_match(), [Append("1"), Append("2")], Filter())
    assert processed is not None
    assert processed["Regex Pattern"]["Description"] == "12"


def test_run_processors_filtering_stops_processing():
    after = Append("1")
    assert run_processors(thm_match(), [Drop(), after], Filter()) is None
    assert after.calls == 0


@pytest.mark.parametrize(
    "rarity, kept", [(0.05, False), (0.1, True), (0.5, True), (1, True)]
)
def test_run_processors_filters_by_the_new_rarity(rarity, kept):
    processed = run_processors(thm_match(), [Rarity(rarity)], Filter())
    assert (processed is not None) == kept


def test_run_processors_filters_by_the_new_tags():
    class Retag(Processor):
        names = [THM]

        def process(self, match):
            match["Regex Pattern"]["Tags"] = ["Media"]
            return match

    dist = Filter({"Tags": ["CTF Flag"]})
    assert run_processors(thm_match(), [], dist) is not None
    assert run_processors(thm_match(), [Retag()], dist) is None


# Identifier and RegexIdentifier


@pytest.mark.parametrize(
    "text, name, date",
    [
        ("1637093119", "Unix Timestamp", DATE),
        ("1637093119", "Recent Unix Timestamp", DATE),
        (
            "1637093119.558717",
            "Unix Timestamp",
            "Date: November 16, 2021 8:05:19.558717 PM UTC",
        ),
        (
            "1637093119.558717",
            "Recent Unix Timestamp",
            "Date: November 16, 2021 8:05:19.558717 PM UTC",
        ),
        (
            "1637093119558",
            "Unix Millisecond Timestamp",
            "Date: November 16, 2021 8:05:19.558 PM UTC",
        ),
        (
            "1637093119558",
            "Recent Unix Millisecond Timestamp",
            "Date: November 16, 2021 8:05:19.558 PM UTC",
        ),
        ("94694400", "Unix Timestamp", "Date: January 1, 1973 12:00:00 AM UTC"),
    ],
)
def test_identify_adds_dates_to_unix_timestamps(text, name, date):
    identified = Identifier(dist=TIMESTAMPS).identify(text)
    assert descriptions(identified)[name] == f"{description(name)}. {date}"
    # The fraction of a second is part of the match (issue #234)
    assert matched(identified["Regexes"]["text"], name) == [text]


def test_identify_adds_dates_to_timestamps_in_files():
    identified = Identifier(dist=TIMESTAMPS).identify("fixtures/file", only_text=False)
    found = {
        (match["Matched"], match["Regex Pattern"]["Name"]): match["Regex Pattern"]
        for match in identified["Regexes"]["file"]
    }
    assert found["1234567890", "Unix Timestamp"]["Description"] == (
        f"{description('Unix Timestamp')}. Date: February 13, 2009 11:31:30 PM UTC"
    )
    assert found["12345678902", "Unix Millisecond Timestamp"]["Description"] == (
        f"{description('Unix Millisecond Timestamp')}. "
        "Date: May 23, 1970 9:21:18.902 PM UTC"
    )


def test_regex_identifier_uses_default_processors():
    matches = RegexIdentifier().check(["1637093119"], dist=TIMESTAMPS)
    assert matched(matches, "Unix Timestamp") == ["1637093119"]
    for found in matches:
        assert found["Regex Pattern"]["Description"].endswith(DATE)


def test_disable_processing():
    identifier = Identifier(dist=TIMESTAMPS, processors=[])
    identified = descriptions(identifier.identify("1637093119"))
    for name in ("Unix Timestamp", "Recent Unix Timestamp"):
        assert identified[name] == description(name)

    matches = RegexIdentifier(processors=[]).check(["1637093119"], dist=TIMESTAMPS)
    assert matched(matches, "Unix Timestamp") == ["1637093119"]
    for found in matches:
        assert "Date:" not in found["Regex Pattern"]["Description"]


def test_processors_of_identify_override_the_identifier_ones():
    identified = Identifier(dist=TIMESTAMPS).identify("1637093119", processors=[])
    assert descriptions(identified)["Unix Timestamp"] == description("Unix Timestamp")

    identified = Identifier(dist=TIMESTAMPS, processors=[]).identify(
        "1637093119", processors=default_processors()
    )
    assert descriptions(identified)["Unix Timestamp"].endswith(DATE)


def test_custom_processor_filters_out_matches():
    text = "https://trashurl.it/page https://skerritt.blog"
    found = Identifier(boundaryless=Filter()).identify(text)["Regexes"]["text"]
    assert matched(found, URL) == ["https://trashurl.it/page", "https://skerritt.blog"]

    identifier = Identifier(boundaryless=Filter(), processors=[URLProcessor()])
    found = identifier.identify(text)["Regexes"]["text"]
    assert matched(found, URL) == ["https://skerritt.blog"]


def test_custom_processor_with_the_default_processors():
    identifier = Identifier(
        dist=Distribution(Filter({"MinRarity": 0})),
        processors=[*default_processors(), Drop(names=(URL,))],
    )
    assert URL in names(identifier.identify("https://skerritt.blog", processors=[]))
    assert URL not in names(identifier.identify("https://skerritt.blog"))
    identified = identifier.identify("1637093119")
    assert descriptions(identified)["Unix Timestamp"].endswith(DATE)


def test_processor_keeps_state_between_matches():
    matches = RegexIdentifier(processors=[FirstOnly()]).check(
        ["THM{a}", "THM{a}", "THM{b}", "THM{a}"]
    )
    assert matched(matches, THM) == ["THM{a}", "THM{b}"]


def test_processor_changes_rarity():
    lowered = Identifier(processors=[Rarity(0.05)])
    # Below the default minimum rarity of 0.1, so it is filtered out
    assert THM not in names(lowered.identify("THM{hello}"))
    every_rarity = Distribution(Filter({"MinRarity": 0}))
    found = lowered.identify("THM{hello}", dist=every_rarity)["Regexes"]["text"]
    assert [
        match["Regex Pattern"]["Rarity"]
        for match in found
        if match["Regex Pattern"]["Name"] == THM
    ] == [0.05]


def test_processors_only_process_their_regexes():
    processor = Append("!", names=(URL,))
    identified = Identifier(processors=[processor]).identify("THM{hello}")
    assert processor.calls == 0
    assert descriptions(identified)[THM] == description(THM)


def test_processors_are_used_for_every_file_of_a_directory():
    files = [os.sep + "file", os.sep + os.path.join("test", "file")]
    identified = Identifier().identify("fixtures", only_text=False)
    for location in files:
        assert matched(identified["Regexes"][location], URL)

    # A generator can only be iterated once
    processors = (processor for processor in [Drop(names=(URL,))])
    identified = Identifier().identify(
        "fixtures", only_text=False, processors=processors
    )
    assert URL not in names(identified)


def test_processing_does_not_change_the_database():
    entries = [database_entry(THM), database_entry("Unix Timestamp")]
    before = copy.deepcopy(entries)
    identifier = Identifier(processors=[Tagger()])
    for _ in range(2):
        found = identifier.identify("THM{hello}")["Regexes"]["text"]
        regex = next(match for match in found if match["Regex Pattern"]["Name"] == THM)
        assert regex["Regex Pattern"]["Tags"].count("Checked") == 1
        assert regex["Regex Pattern"]["Description"] == "Checked"
    Identifier(dist=TIMESTAMPS).identify("1637093119")
    assert entries == before


# Command line interface


def test_cli_adds_dates_to_unix_timestamps():
    output = words(run_cli(TIMESTAMPS_OPTIONS + ["1637093119"]))
    for name in ("Unix Timestamp", "Recent Unix Timestamp"):
        assert f"Name: {name} Description: {description(name)}. {DATE}" in output


def test_cli_fractional_unix_timestamp():
    output = words(run_cli(TIMESTAMPS_OPTIONS + ["1637093119.558717"]))
    assert "Matched on: 1637093119.558717" in output
    assert "Date: November 16, 2021 8:05:19.558717 PM UTC" in output


def test_cli_json():
    output = run_cli(["--json"] + TIMESTAMPS_OPTIONS + ["1637093119"])
    assert descriptions(json.loads(output))["Unix Timestamp"] == (
        f"{description('Unix Timestamp')}. {DATE}"
    )


def test_cli_format():
    output = words(
        run_cli(["--format", "%n: %d"] + TIMESTAMPS_OPTIONS + ["1637093119"])
    )
    assert f"Unix Timestamp: {description('Unix Timestamp')}. {DATE}" in output


@pytest.mark.parametrize("flag", ["-dp", "--disable-processing"])
def test_cli_disable_processing(flag):
    args = [flag] + TIMESTAMPS_OPTIONS + ["1637093119"]
    output = words(run_cli(args))
    assert "Name: Unix Timestamp" in output
    assert "Date:" not in output

    identified = descriptions(json.loads(run_cli(["--json"] + args)))
    for name in ("Unix Timestamp", "Recent Unix Timestamp"):
        assert identified[name] == description(name)


def test_cli_help():
    output = words(run_cli(["--help"]))
    assert "-dp, --disable-processing" in output
    assert "Processing:" in output


# Interactive mode


def test_interactive_adds_dates_to_unix_timestamps():
    output = run_shell([TIMESTAMPS_SEARCH], "1637093119")
    assert f"Description: {description('Unix Timestamp')}. {DATE}\n" in output


def test_interactive_disable_processing():
    output = run_shell([TIMESTAMPS_SEARCH], "1637093119", processors=[])
    assert f"Description: {description('Unix Timestamp')}\n" in output
    assert "Date:" not in output


def test_cli_interactive_disable_processing():
    search = TIMESTAMPS_SEARCH + "\n"
    output = words(run_cli(["--interactive", "1637093119"], input=search))
    assert DATE in output
    output = words(run_cli(["--interactive", "-dp", "1637093119"], input=search))
    assert "Name: Unix Timestamp" in output
    assert "Date:" not in output
