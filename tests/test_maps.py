"""
Tests for linking coordinates to OpenStreetMap instead of Google Maps
(pywhat --map osm, issue #263), and for the links of matches.
"""
import io
import json
import re
from typing import List, Optional
from urllib.parse import parse_qs, urlsplit

import pytest
from click.testing import CliRunner

import pywhat.processors
from pywhat import Distribution, Filter, Identifier
from pywhat.helper import load_regexes
from pywhat.printer import get_link
from pywhat.processors import OpenStreetMapProcessor, default_processors
from pywhat.regex_identifier import RegexIdentifier
from pywhat.what import main

NAME = "Latitude & Longitude Coordinates"
COORDINATES = "52.6169586, -1.9779857"
GOOGLE_URL = "https://www.google.com/maps/place/"
GOOGLE_LINK = GOOGLE_URL + "52.6169586,-1.9779857"
OSM_URL = "https://www.openstreetmap.org/search?query="
OSM_LINK = OSM_URL + "52.6169586,-1.9779857"
COORDS = Distribution(Filter({"Tags": ["Coords"]}))
# Coordinates and Unix timestamps (which have a rarity of 0)
COORDS_AND_TIMESTAMPS = ["--rarity", "0:", "--include", "Coords,UNIX Timestamp"]
DATE = "Date: November 16, 2021 8:05:19 PM UTC"  # of 1637093119
WALLET = "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"  # a Ripple wallet, which has a URL
GOOGLE_API_KEY = "AIzaSyD7CQl6fRhagGok6CzFGOOPne2X1u1spoA"


def database_entry(name: str) -> dict:
    return next(regex for regex in load_regexes() if regex["Name"] == name)


def coordinates_match(matched: str = COORDINATES) -> dict:
    return {"Matched": matched, "Regex Pattern": dict(database_entry(NAME))}


def links(identified: dict, name: str = NAME) -> List[Optional[str]]:
    """The links of the matches of the regex called name."""
    return [
        get_link(match)
        for matches in (identified["Regexes"] or {}).values()
        for match in matches
        if match["Regex Pattern"]["Name"] == name
    ]


def run_cli(args: List[str], input: Optional[str] = None) -> str:
    # A wide terminal, so that rich does not fold the links
    result = CliRunner().invoke(main, args, input=input, env={"COLUMNS": "200"})
    assert result.exit_code == 0, result.output
    return result.output


def words(text: str) -> str:
    """text with every run of whitespace replaced by a space."""
    return " ".join(text.split())


# The search of OpenStreetMap


@pytest.mark.parametrize(
    "coordinates, query",
    [
        ("52.6169586, -1.9779857", "52.6169586,-1.9779857"),
        ("53.76297,-1.9388732", "53.76297,-1.9388732"),
        ("40.741895,-73.989308", "40.741895,-73.989308"),
        ("+52.6169586, +1.9779857", "52.6169586,1.9779857"),
        ("52.6169586,   -1.9779857 ", "52.6169586,-1.9779857"),
        ("N 32\u00b0 53.733 W 096\u00b0 48.358", "N32\u00b053.733W096\u00b048.358"),
        (
            "41\u00b024'12.2\" N 2\u00b010'26.5\" E",
            "41\u00b024'12.2\"N2\u00b010'26.5\"E",
        ),
        ("77\u00b0 30' 29.9988\" N", "77\u00b030'29.9988\"N"),
        # The space between two numbers is kept: 2 minutes 12.2 seconds
        ("41\u00b0 2 12.2 N 2\u00b0 10 26.5 E", "41\u00b02 12.2N2\u00b010 26.5E"),
        # The notation of Google Maps, which OpenStreetMap does not understand
        ("@13.923404,101.3395163,17z", "13.923404,101.3395163"),
        ("@13.923404,101.3395163,17Z", "13.923404,101.3395163"),
        ("@-33.8688,151.2093,12.5z", "-33.8688,151.2093"),
    ],
)
def test_query(coordinates, query):
    assert OpenStreetMapProcessor.query(coordinates) == query


@pytest.mark.parametrize("example", database_entry(NAME)["Examples"]["Valid"], ids=repr)
def test_links_of_the_examples(example):
    """Every example of the regex links to a search for its coordinates."""
    processed = OpenStreetMapProcessor().process(coordinates_match(example))
    assert processed is not None
    link = processed["Regex Pattern"]["Link"]
    assert link.startswith(OSM_URL)
    assert re.fullmatch(r"[A-Za-z0-9%,.:/?=_\-]+", link), link
    url = urlsplit(link)
    assert (url.scheme, url.netloc, url.path) == (
        "https",
        "www.openstreetmap.org",
        "/search",
    )
    assert parse_qs(url.query) == {"query": [OpenStreetMapProcessor.query(example)]}


def test_processor():
    match = coordinates_match()
    processed = OpenStreetMapProcessor().process(match)
    assert processed is match
    assert processed["Matched"] == COORDINATES
    assert processed["Regex Pattern"]["URL"] == OSM_URL
    assert processed["Regex Pattern"]["Link"] == OSM_LINK
    assert processed["Regex Pattern"]["Description"] is None


def test_processor_names_are_regexes_in_the_database():
    regex_names = {regex["Name"] for regex in load_regexes()}
    assert OpenStreetMapProcessor.names == [NAME]
    assert set(OpenStreetMapProcessor.names) <= regex_names
    # The default link is the one that OpenStreetMap replaces
    assert database_entry(NAME)["URL"] == GOOGLE_URL


def test_openstreetmap_is_not_a_default_processor():
    assert not any(
        isinstance(processor, OpenStreetMapProcessor)
        for processor in default_processors()
    )


# The links of matches


def test_get_link_of_a_processor():
    match = coordinates_match()
    match["Regex Pattern"]["Link"] = OSM_LINK
    assert get_link(match) == OSM_LINK


def test_get_link_from_the_url_of_the_regex():
    # Without the spaces of the match
    assert get_link(coordinates_match()) == GOOGLE_LINK


@pytest.mark.parametrize("regex", [{"URL": None}, {}, {"URL": "", "Link": None}])
def test_get_link_without_a_link(regex):
    assert get_link({"Matched": "THM{hello}", "Regex Pattern": regex}) is None


# Identifier and RegexIdentifier


def test_identifier_links_to_google_maps_by_default():
    identified = Identifier(dist=COORDS).identify(COORDINATES)
    assert links(identified) == [GOOGLE_LINK]
    for match in identified["Regexes"]["text"]:
        # Unchanged, e.g. in the JSON output
        assert "Link" not in match["Regex Pattern"]
        assert match["Regex Pattern"]["URL"] == GOOGLE_URL


def test_identifier_links_to_openstreetmap():
    identifier = Identifier(
        dist=COORDS, processors=[*default_processors(), OpenStreetMapProcessor()]
    )
    assert links(identifier.identify(COORDINATES)) == [OSM_LINK]
    # processors=[] turns it off
    assert links(identifier.identify(COORDINATES, processors=[])) == [GOOGLE_LINK]

    identified = Identifier(dist=COORDS).identify(
        COORDINATES, processors=[OpenStreetMapProcessor()]
    )
    assert links(identified) == [OSM_LINK]


def test_regex_identifier_links_to_openstreetmap():
    matches = RegexIdentifier(processors=[OpenStreetMapProcessor()]).check(
        ["@13.923404,101.3395163,17z"], dist=COORDS
    )
    assert [get_link(match) for match in matches] == [OSM_URL + "13.923404,101.3395163"]


def test_openstreetmap_only_changes_the_links_of_coordinates():
    identifier = Identifier(processors=[OpenStreetMapProcessor()])
    identified = identifier.identify_inputs([COORDINATES, WALLET])
    assert links(identified) == [OSM_LINK]
    assert links(identified, "Ripple (XRP) Wallet Address") == [
        "https://xrpscan.com/account/" + WALLET
    ]


def test_openstreetmap_does_not_change_the_database():
    identifier = Identifier(dist=COORDS, processors=[OpenStreetMapProcessor()])
    assert links(identifier.identify(COORDINATES)) == [OSM_LINK]
    entry = database_entry(NAME)
    assert entry["URL"] == GOOGLE_URL
    assert "Link" not in entry
    assert links(Identifier(dist=COORDS).identify(COORDINATES)) == [GOOGLE_LINK]


# Command line interface


@pytest.mark.parametrize("args", [[], ["--map", "google"], ["--map", "GOOGLE"]])
def test_cli_links_to_google_maps(args):
    output = words(run_cli(args + ["-db", COORDINATES]))
    assert f"Link: {GOOGLE_LINK}" in output
    assert "openstreetmap" not in output


@pytest.mark.parametrize("value", ["osm", "OSM", "Osm"])
def test_cli_map_osm(value):
    output = words(run_cli(["--map", value, "-db", COORDINATES]))
    assert f"Name: {NAME} Link: {OSM_LINK}" in output
    assert "google" not in output


@pytest.mark.parametrize(
    "args, link",
    [
        ([], GOOGLE_LINK),  # %l used to keep the space of the match
        (["--map", "osm"], OSM_LINK),
    ],
)
def test_cli_map_format(args, link):
    output = run_cli(args + ["-db", "--format", "%l", COORDINATES])
    assert output.strip() == link


def test_cli_map_format_degrees():
    output = run_cli(
        [
            "--map",
            "osm",
            "-db",
            "--format",
            "%l",
            "N 32\u00b0 53.733 W 096\u00b0 48.358",
        ]
    )
    assert output.strip() == OSM_URL + "N32%C2%B053.733W096%C2%B048.358"


def test_cli_map_json():
    output = run_cli(["--map", "osm", "-db", "--json", COORDINATES])
    regex = json.loads(output)["Regexes"]["text"][0]["Regex Pattern"]
    assert regex["Name"] == NAME
    assert regex["URL"] == OSM_URL
    assert regex["Link"] == OSM_LINK

    output = run_cli(["-db", "--json", COORDINATES])
    regex = json.loads(output)["Regexes"]["text"][0]["Regex Pattern"]
    assert regex["URL"] == GOOGLE_URL
    assert "Link" not in regex


def test_cli_map_pretty():
    output = run_cli(["--map", "osm", "-db", "--format", "pretty", COORDINATES])
    assert OSM_LINK in output
    assert "google" not in output


def test_cli_map_file(tmp_path):
    path = tmp_path / "coordinates.txt"
    path.write_text(f"The meeting point is at {COORDINATES} tomorrow.\n")
    output = words(run_cli(["--map", "osm", str(path)]))
    assert f"Link: {OSM_LINK}" in output


def test_cli_map_multiple_inputs():
    output = words(run_cli(["--map", "osm", "-db", COORDINATES, WALLET]))
    assert f"Link: {OSM_LINK}" in output
    assert f"Link: https://xrpscan.com/account/{WALLET}" in output


def test_cli_map_keeps_the_default_processors():
    output = words(run_cli(["--map", "osm"] + COORDS_AND_TIMESTAMPS + [COORDINATES]))
    assert f"Link: {OSM_LINK}" in output
    output = words(run_cli(["--map", "osm"] + COORDS_AND_TIMESTAMPS + ["1637093119"]))
    assert DATE in output


@pytest.mark.parametrize("flag", ["-dp", "--disable-processing"])
def test_cli_map_with_disable_processing(flag):
    args = [flag, "--map", "osm"] + COORDS_AND_TIMESTAMPS
    output = words(run_cli(args + [COORDINATES, "1637093119"]))
    # The map is asked for, so it is kept, but nothing else is processed
    assert f"Link: {OSM_LINK}" in output
    assert "Name: Unix Timestamp" in output
    assert "Date:" not in output


def test_cli_map_with_verify(monkeypatch):
    requests = []

    def urlopen(request, timeout):
        requests.append(request.full_url)
        return io.BytesIO(b'{"kind": "youtube#i18nLanguageListResponse"}')

    monkeypatch.setattr(pywhat.processors, "urlopen", urlopen)
    output = words(
        run_cli(["--verify", "--map", "osm", "-db", COORDINATES, GOOGLE_API_KEY])
    )
    assert f"Link: {OSM_LINK}" in output
    assert "Verification: valid, Google accepted the key" in output
    assert len(requests) == 1


def test_cli_map_interactive():
    output = words(
        run_cli(
            ["--interactive", "--map", "osm", "-db", COORDINATES],
            input="include:Coords\n",
        )
    )
    assert f"Link: {OSM_LINK}" in output
    assert "google" not in output


def test_cli_map_invalid():
    result = CliRunner().invoke(main, ["--map", "bing", COORDINATES])
    assert result.exit_code == 2
    assert "Invalid value for '--map'" in result.output


def test_cli_help():
    output = words(run_cli(["--help"]))
    assert "--map [google|osm]" in output
    assert "Maps:" in output
