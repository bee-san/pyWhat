"""
Tests for the preparation of the Rust port (issue #291, phase 0): substitutions are
literal, output isn't hard-wrapped when it isn't a terminal, and Children are listed
longest prefix first.
"""
import io

from click.testing import CliRunner
from rich.console import Console

from pywhat import Identifier
from pywhat.printer import Printing
from pywhat.what import main

TWITTER = 'twitter\\q_api_secret = "L8qq9PZyRg6ieKGEKhZolGC0vJWLw8iEJ88DRdyOg"'


def test_format_substitutes_matches_literally():
    # A backslash in a match was read as a group reference: re.error
    result = CliRunner().invoke(main, ["--format", "%m", "thm{a\\1\\g<0>\\n}"])
    assert result.exit_code == 0
    assert result.output == "thm{a\\1\\g<0>\\n}\n"


def test_exploit_substitutes_matches_literally():
    # A backslash in a match was read as an escape: re.error: bad escape \q
    found = Identifier().identify(TWITTER)["Regexes"]["text"]
    exploits = [match["Regex Pattern"]["Exploit"] for match in found]
    assert any(TWITTER in exploit for exploit in exploits if exploit)


def printing(width=80):
    printer = Printing()
    printer.console = Console(
        file=io.StringIO(), width=width, highlight=False, force_terminal=False
    )
    return printer


def test_raw_output_is_not_wrapped():
    printer = printing()
    identified = Identifier().identify(TWITTER)
    printer.print_raw(identified, TWITTER)
    lines = printer.console.file.getvalue().splitlines()
    assert any(TWITTER in line and len(line) > 80 for line in lines)


def test_format_output_is_not_wrapped():
    printer = printing()
    identified = Identifier().identify(TWITTER)
    printer.format_print(identified, "%m %n %e")
    lines = printer.console.file.getvalue().splitlines()
    assert any(TWITTER in line and len(line) > 80 for line in lines)


def test_mac_vendors_longest_prefix_first():
    found = Identifier().identify("24:15:10:C0:00:00")["Regexes"]["text"]
    descriptions = [match["Regex Pattern"]["Description"] for match in found]
    assert (
        "Vendor(s): Shenzhen Xtooltech Co, Ltd, Ieee Registration Authority"
        in descriptions
    )
