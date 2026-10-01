import io
import json
import os
import re

import pytest
from click.testing import CliRunner
from rich.console import Console

from pywhat.helper import Keys
from pywhat.identifier import Identifier
from pywhat.interactive import (
    NOTHING_LOADED,
    InteractiveShell,
    Query,
    QueryError,
    _readline_matches,
    complete_query,
    parse_rarity,
    query_from_options,
)
from pywhat.what import main


def match(matched, name, rarity, tags):
    return {
        "Matched": matched,
        "Regex Pattern": {"Name": name, "Rarity": rarity, "Tags": tags},
    }


FLAG = match("THM{hello}", "TryHackMe Flag Format", 1, ["CTF Flag"])
EMAIL = match("github@skerritt.blog", "Email Address", 0.5, ["Identifiers", "Email"])
KEY_VALUE = match("key:value", "Key:Value Pair", 0, ["Credentials"])


def run_shell(*commands, text_input="fixtures/file", **options):
    """
    Run interactive mode with the commands. Returns the shell and the output
    of each command, after the output of starting (and loading text_input).
    """
    stdout = io.StringIO()
    shell = InteractiveShell(
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
    )
    shell.run(text_input)
    return shell, stdout.getvalue().split(InteractiveShell.prompt)


def run_cli(args, commands):
    result = CliRunner().invoke(
        main, args, input="".join(command + "\n" for command in commands)
    )
    assert result.exit_code == 0, result.output
    return result.output


def test_query_from_issue():
    # The search of issue #233
    query = Query(
        'location:"/", includes:"bug bounty", excludes:"credit card", rarity:"0.1 - 0.6"'
    )
    assert (
        str(query)
        == 'location:"/", include:"bug bounty", exclude:"credit card", rarity:"0.1:0.6"'
    )
    assert Query(str(query)).parts == query.parts


def test_query_default_rarity():
    assert str(Query()) == 'rarity:"0.1:1"'
    assert str(Query("bitcoin")) == '"bitcoin", rarity:"0.1:1"'
    assert not Query().matches("text", KEY_VALUE)
    assert Query().matches("text", EMAIL)


@pytest.mark.parametrize(
    "rarity, expected",
    [
        ("0.1:0.6", (0.1, 0.6)),
        ("0.1 - 0.6", (0.1, 0.6)),
        ("0.2-0.4", (0.2, 0.4)),
        ("0.5:", (0.5, 1)),
        (":0.5", (0.1, 0.5)),
        ("0:", (0, 1)),
        (":", (0.1, 1)),
        ("0.5", (0.5, 0.5)),
        ("0.1 -0.6", (0.1, 0.6)),
        ("1e-05", (1e-05, 1e-05)),
    ],
)
def test_parse_rarity(rarity, expected):
    assert parse_rarity(rarity) == expected


@pytest.mark.parametrize("rarity", ["", "abc", "0.1:0.2:0.3", "0.1-0.2-0.3"])
def test_parse_invalid_rarity(rarity):
    with pytest.raises(QueryError):
        parse_rarity(rarity)


@pytest.mark.parametrize(
    "query, expected",
    [
        ("rarity:0.5", 'rarity:"0.5"'),
        ("rarity:0.5:", 'rarity:"0.5:1"'),
        ("rarity:0.2-0.4", 'rarity:"0.2:0.4"'),
        ("include:Identifiers,Media", 'include:"Identifiers,Media", rarity:"0.1:1"'),
        ('INCLUDE:" CTF Flag , Email"', 'include:"CTF Flag,Email", rarity:"0.1:1"'),
        ('rarity:0: "two words", one,', '"two words", "one", rarity:"0:1"'),
        ('"", word', '"word", rarity:"0.1:1"'),
        # Commas separate the parts, unquoted values can be lists of tags
        (
            'include:"AWS",exclude:"Credit Card"',
            'include:"AWS", exclude:"Credit Card", rarity:"0.1:1"',
        ),
        ("bitcoin,rarity:0.5", '"bitcoin", rarity:"0.5"'),
        ("include:AWS,Google,", 'include:"AWS,Google", rarity:"0.1:1"'),
        ("rarity:0.00001:", 'rarity:"1e-05:1"'),
        # Unknown keys are text
        ("http://example.com", '"http://example.com", rarity:"0.1:1"'),
        ('incldue:"Bug Bounty"', '"incldue:Bug Bounty", rarity:"0.1:1"'),
    ],
)
def test_query_str(query, expected):
    assert str(Query(query)) == expected
    assert str(Query(expected)) == expected


@pytest.mark.parametrize(
    "query",
    [
        'include:"Not A Tag"',
        "exclude:nope",
        "include:",
        'include:","',
        'location:""',
        "rarity:abc",
    ],
)
def test_invalid_query(query):
    with pytest.raises(QueryError):
        Query(query)


def test_query_include():
    # One of the tags of an include: part
    query = Query('include:"CTF Flag,Email", rarity:0:')
    assert query.matches("text", FLAG)
    assert query.matches("text", EMAIL)
    assert not query.matches("text", KEY_VALUE)


def test_query_every_part_has_to_match():
    query = Query("include:Identifiers include:Email rarity:0:")
    assert query.matches("text", EMAIL)
    assert not query.matches("text", match("1.1.1.1", "IP", 1, ["Identifiers"]))

    query = Query("rarity:0: rarity::0.5")
    assert query.matches("text", EMAIL)
    assert not query.matches("text", FLAG)
    assert not query.matches("text", KEY_VALUE)


def test_query_exclude():
    query = Query("exclude:Email,credentials rarity:0:")
    assert query.matches("text", FLAG)
    assert not query.matches("text", EMAIL)
    assert not query.matches("text", KEY_VALUE)


def test_query_rarity():
    assert Query("rarity:0:").matches("text", KEY_VALUE)
    assert Query("rarity:1").matches("text", FLAG)
    assert not Query("rarity:1").matches("text", EMAIL)


def test_query_location():
    query = Query("location:SUB/file")
    assert query.matches("/sub/file.txt", FLAG)
    assert query.matches("\\sub\\file.txt", FLAG)
    assert not query.matches("/other/file.txt", FLAG)
    assert query.matches_location("/sub/file.txt")


def test_query_text():
    # The matched text or the name contains each text
    assert Query("SKERRITT").matches("text", EMAIL)
    assert Query('"flag format" thm').matches("text", FLAG)
    assert not Query("flag skerritt").matches("text", FLAG)


def test_query_from_options():
    assert query_from_options("0.1:1", None, None) == 'rarity:"0.1:1"'
    query = query_from_options("0.5:", "Bug Bounty,AWS", "Credit Card")
    assert query == 'include:"Bug Bounty,AWS", exclude:"Credit Card", rarity:"0.5:"'
    assert (
        str(Query(query))
        == 'include:"Bug Bounty,AWS", exclude:"Credit Card", rarity:"0.5:1"'
    )


KEYS = ["location:", "include:", "exclude:", "rarity:"]


@pytest.mark.parametrize(
    "before, expected",
    [
        ("", (0, KEYS)),
        ("rar", (0, ["rarity:"])),
        ("bitcoin EXC", (8, ["exclude:"])),
        ("bitcoin,", (8, KEYS)),
        ('include:"AWS" ', (14, KEYS)),
        ('include:"AWS",', (14, KEYS)),
        ("include:Bu", (8, ['"Bug Bounty"'])),
        ("exclude:b", (8, ['"Bitcoin"', '"Bug Bounty"'])),
        ('include:"bug b', (9, ['Bug Bounty"'])),
        ('include:"AWS, Bu', (14, ['Bug Bounty"'])),
        ("include:AWS,Bu", (8, ['"AWS,Bug Bounty"'])),
        ("rarity:", (7, ['"0.3"', '"0.5"', '"1"'])),
        ("rarity:0.", (7, ['"0.3"', '"0.5"'])),
        ("location:/s", (9, ['"/sub/file"'])),
        # Nothing to complete
        ('include:"AWS"', (13, [])),
        ('"some text', (10, [])),
        ("http://exa", (0, [])),
    ],
)
def test_complete_query(before, expected):
    tags = ["Bug Bounty", "AWS", "Bitcoin", "Credit Card"]
    rarities = [1, 0.5, 0.3, 0.5]
    locations = ["/sub/file", "/other"]
    assert complete_query(before, tags, rarities, locations) == expected


def test_readline_matches():
    line = 'search include:"Bug Bo'
    # readline replaces the text after the last space...
    assert _readline_matches(line, 20, 16, ['Bug Bounty"']) == ['Bounty"']
    # ...or more, depending on its word delimiters
    assert _readline_matches(line, 7, 16, ['Bug Bounty"']) == ['include:"Bug Bounty"']
    # Completions that do not fit are left out
    assert _readline_matches("rarity:0.1:0", 11, 7, ['"0.1:0.5"']) == []


def test_load():
    shell, outputs = run_shell()
    assert f"Loaded {len(shell.matches)} matches from file 'fixtures/file'." in (
        outputs[0]
    )
    found = len(shell.search())
    assert f'Search: rarity:"0.1:1" ({found} of {len(shell.matches)} matches)' in (
        outputs[0]
    )
    assert "CTF Flag (" in outputs[0]
    # The input is identified with every regex, the search filters the matches
    rarities = [match["Regex Pattern"]["Rarity"] for _, match in shell.matches]
    assert 0 in rarities
    assert all(match["Regex Pattern"]["Rarity"] >= 0.1 for _, match in shell.search())


def test_search():
    shell, outputs = run_shell('search include:"CTF Flag"')
    assert 'Search: include:"CTF Flag", rarity:"0.1:1"' in outputs[1]
    assert "THM{this is a flag}" in outputs[1]
    assert "Email Address" not in outputs[1]
    assert shell.search()
    for _, found in shell.search():
        assert "CTF Flag" in found["Regex Pattern"]["Tags"]


def test_line_that_is_not_a_command_is_a_search():
    _, outputs = run_shell('include:"CTF Flag"', "hackthebox", "search")
    # include:... is not the include command
    assert 'Search: include:"CTF Flag", rarity:"0.1:1"' in outputs[1]
    assert 'Search: "hackthebox", rarity:"0.1:1"' in outputs[2]
    assert "htb{4111111111111111}" in outputs[2]
    assert "THM{this is a flag}" not in outputs[2]
    # 'search' alone shows the current search again
    assert outputs[3] == outputs[2]


def test_include_and_exclude():
    shell, outputs = run_shell("include Identifiers", "exclude Email")
    assert 'Search: include:"Identifiers", rarity:"0.1:1"' in outputs[1]
    assert "Name: Email Address" in outputs[1]
    assert (
        'Search: include:"Identifiers", exclude:"Email", rarity:"0.1:1"' in outputs[2]
    )
    assert "Name: Email Address" not in outputs[2]
    for _, found in shell.search():
        assert "Identifiers" in found["Regex Pattern"]["Tags"]
        assert "Email" not in found["Regex Pattern"]["Tags"]


def test_include_and_exclude_need_tags():
    _, outputs = run_shell("include", "exclude  ", "include nope")
    assert "Which tags? Use 'include TAG[,TAG...]'." in outputs[1]
    assert "Which tags? Use 'exclude TAG[,TAG...]'." in outputs[2]
    assert "Unknown tag 'nope'" in outputs[3]


def test_include_quoted_tags():
    _, outputs = run_shell('include "CTF Flag"', 'exclude ""')
    assert 'Search: include:"CTF Flag", rarity:"0.1:1"' in outputs[1]
    assert "Which tags?" in outputs[2]


def test_tags():
    shell, outputs = run_shell('include:"CTF Flag"', "tags")
    assert f"CTF Flag ({len(shell.search())})" in outputs[2]
    assert "Bug Bounty (" not in outputs[2]


def test_invalid_search():
    _, outputs = run_shell('include:"CTF Flag"', "include:nope", "rarity:abc", "search")
    assert "Unknown tag 'nope'" in outputs[2]
    assert "Invalid rarity 'abc'" in outputs[3]
    # The search has not changed
    assert outputs[4] == outputs[1]


def test_clear():
    _, outputs = run_shell("search rarity:0:", "clear", query='include:"CTF Flag"')
    assert 'Search: include:"CTF Flag", rarity:"0.1:1"' in outputs[0]
    assert 'Search: rarity:"0:1"' in outputs[1]
    assert 'Search: include:"CTF Flag", rarity:"0.1:1"' in outputs[2]


def test_directory():
    shell, outputs = run_shell("location:test", text_input="fixtures")
    assert "from directory 'fixtures'" in outputs[0]
    assert {location for location, _ in shell.matches} == {
        os.sep + "file",
        os.sep + os.path.join("test", "file"),
    }
    assert {location for location, _ in shell.search()} == {
        os.sep + os.path.join("test", "file")
    }
    assert "File: " in outputs[1]


def test_text():
    shell, outputs = run_shell(text_input="THM{hello} github@skerritt.blog")
    assert "from the text." in outputs[0]
    assert {found["Matched"] for _, found in shell.matches} >= {
        "THM{hello}",
        "github@skerritt.blog",
    }


def test_several_inputs():
    # Issue #171
    inputs = ["fixtures/file", "fixtures/test/file", "THM{hello}"]
    shell, outputs = run_shell("location:test", text_input=inputs)
    assert shell.input == inputs
    assert f"Loaded {len(shell.matches)} matches from 3 inputs." in outputs[0]
    assert {location for location, _ in shell.matches} == {
        "fixtures/file",
        "fixtures/test/file",
        "text",
    }
    assert {location for location, _ in shell.search()} == {"fixtures/test/file"}
    assert "File: fixtures/test/file" in outputs[1]


def test_single_input_in_a_list():
    shell, outputs = run_shell(text_input=["fixtures/file"])
    assert shell.input == "fixtures/file"
    assert "from file 'fixtures/file'." in outputs[0]


def test_json():
    _, outputs = run_shell('include:"CTF Flag"', json_output=True)
    identified = json.loads(outputs[1].splitlines()[-1])
    assert identified["File Signatures"] is None
    assert {
        found["Regex Pattern"]["Name"] for found in identified["Regexes"]["file"]
    } >= {"TryHackMe Flag Format"}
    for found in identified["Regexes"]["file"]:
        assert "CTF Flag" in found["Regex Pattern"]["Tags"]


def test_sorting():
    _, outputs = run_shell("search", key=Keys.NAME, reverse=True)
    names = re.findall(r"^Name: (.*)$", outputs[1], re.MULTILINE)
    assert names
    assert names == sorted(names, reverse=True)


def test_nothing_loaded():
    shell, outputs = run_shell(
        "search", "tags", "clear", "load fixtures/file", text_input=None
    )
    for output in outputs[:4]:
        assert NOTHING_LOADED in output
    assert "Loaded " in outputs[4]
    assert shell.input == "fixtures/file"


def test_load_errors(monkeypatch):
    identify = Identifier.identify

    def denied(self, text, **kwargs):
        if text == "secret.txt":
            raise PermissionError(13, "Permission denied")
        return identify(self, text, **kwargs)

    monkeypatch.setattr(Identifier, "identify", denied)
    shell, outputs = run_shell("load", "load secret.txt")
    assert "What should be loaded?" in outputs[1]
    assert "Could not load 'secret.txt': [Errno 13] Permission denied" in outputs[2]
    # What was loaded before is kept
    assert shell.input == "fixtures/file"
    assert shell.matches


def test_empty_line():
    # does not repeat the last command
    _, outputs = run_shell('include:"CTF Flag"', "")
    assert outputs[2] == ""


def test_help():
    _, outputs = run_shell("help", "help search", "?include")
    assert "search" in outputs[1]
    assert "EOF" not in outputs[1]
    assert outputs[2].startswith("search [SEARCH]\n")
    assert (
        'location:"/", include:"Bug Bounty", exclude:"Credit Card", rarity:"0.1:0.6"'
        in outputs[2]
    )
    assert outputs[3].startswith("include TAG[,TAG...]\n")


@pytest.mark.parametrize("command", ["quit", "exit"])
def test_quit(command):
    _, outputs = run_shell(command, "tags")
    # 'tags' is not run
    assert len(outputs) == 2


def test_ctrl_c(monkeypatch):
    def interrupted(self, arg):
        raise KeyboardInterrupt

    monkeypatch.setattr(InteractiveShell, "do_load", interrupted)
    _, outputs = run_shell("load fixtures", "tags", text_input=None)
    # Ctrl+C does not leave interactive mode
    assert NOTHING_LOADED in outputs[2]


def test_completion():
    shell, _ = run_shell()
    # The first word: a command or a search key
    assert shell.completenames("in", "in", 0, 2) == ["include", "include:"]
    assert shell.completenames("rar", "rar", 0, 3) == ["rarity:"]
    assert shell.completenames('include:"CTF F', 'include:"CTF F', 0, 14) == [
        'include:"CTF Flag"'
    ]
    rarities = shell.completenames("rarity:", "rarity:", 0, 7)
    assert 'rarity:"0.5"' in rarities
    assert all(rarity.startswith('rarity:"') for rarity in rarities)
    # Searches
    line = 'search include:"CTF F'
    assert shell.complete_search("F", line, 20, len(line)) == ['Flag"']
    assert shell.complete_search("F", line[7:], 13, len(line[7:])) == ['Flag"']
    assert shell.completedefault("rar", "bitcoin rar", 8, 11) == ["rarity:"]
    # tags, clear and quit have no arguments
    assert shell.completedefault("", "tags ", 5, 5) == []
    # include and exclude
    assert shell.complete_include("B", "include Bug B", 12, 13) == ["Bounty"]
    line = "exclude Bug Bounty, Cred"
    assert shell.complete_exclude("Cred", line, 20, len(line)) == [
        "Credentials",
        "Credit Card",
    ]
    # Paths
    assert shell.complete_load("fixtures/fi", "load fixtures/fi", 5, 16) == [
        os.path.join("fixtures", "file")
    ]
    assert shell.complete_load("fixt", "load fixt", 5, 9) == ["fixtures" + os.sep]
    # help completes commands only
    assert shell.complete_help("in", "help in", 5, 7) == ["include"]


def test_completion_of_locations():
    shell, _ = run_shell(text_input="fixtures")
    line = "location:" + os.sep + "t"
    assert shell.completenames(line, line, 0, len(line)) == [
        'location:"' + os.sep + os.path.join("test", "file") + '"'
    ]


def test_completer_delims(monkeypatch):
    readline = pytest.importorskip("readline")
    delims = readline.get_completer_delims()
    seen = []

    def read_line(prompt):
        seen.append(readline.get_completer_delims())
        return "quit"

    monkeypatch.setattr("builtins.input", read_line)
    InteractiveShell(console=Console(file=io.StringIO())).cmdloop(intro="")
    # Only whitespace separates the words to complete while the shell runs
    assert seen == [" \t\n"]
    assert readline.get_completer_delims() == delims


def test_cli():
    output = run_cli(["--interactive", "fixtures/file"], ['include:"CTF Flag"', "quit"])
    assert "pyWhat interactive mode" in output
    assert "TryHackMe Flag Format" in output


def test_cli_without_input():
    # The commands come from stdin, it is not the text to identify
    output = run_cli(["--interactive"], ["load fixtures/file", 'include:"CTF Flag"'])
    assert NOTHING_LOADED in output
    assert "Loaded " in output
    assert "TryHackMe Flag Format" in output


def test_cli_stdin_is_text_input_without_interactive_mode():
    result = CliRunner().invoke(main, ["-db"], input="THM{hello}")
    assert result.exit_code == 0
    assert "TryHackMe Flag Format" in result.output


def test_cli_several_inputs():
    # Issue #171
    output = run_cli(
        ["--interactive", "fixtures/file", "fixtures/test/file", "THM{hello}"],
        ["location:test"],
    )
    assert "from 3 inputs." in output
    assert "File: fixtures/test/file\nMatched on: https://google.com" in output


def test_cli_single_input():
    output = run_cli(["--interactive", "fixtures/file"], [])
    assert "from file 'fixtures/file'." in output


def test_cli_options_are_the_search_to_start_with():
    output = run_cli(
        ["--interactive", "--include", "CTF Flag", "--rarity", "0.5:", "fixtures/file"],
        ["clear"],
    )
    assert output.count('include:"CTF Flag", rarity:"0.5:1"') == 2


def test_cli_boundaryless():
    output = run_cli(["--interactive", "abc118.103.238.230abc"], ["search"])
    assert "Internet Protocol" in output
    output = run_cli(["--interactive", "-db", "abc118.103.238.230abc"], ["search"])
    assert "Internet Protocol" not in output
    assert "Nothing found!" in output


def test_cli_json():
    output = run_cli(
        ["--interactive", "--json", "fixtures/file"], ['include:"CTF Flag"']
    )
    identified = json.loads(
        next(line for line in output.splitlines() if line.startswith("{"))
    )
    assert identified["Regexes"]["file"]
    for found in identified["Regexes"]["file"]:
        assert "CTF Flag" in found["Regex Pattern"]["Tags"]


def test_cli_pretty():
    output = run_cli(
        ["--interactive", "--format", "pretty", "fixtures/file"], ['include:"CTF Flag"']
    )
    assert "Possible Identification" in output
    # The table may fold "TryHackMe Flag Format", depending on the width
    assert "TryHackMe" in output


def test_cli_format():
    output = run_cli(
        ["--interactive", "--format", "%n: %m", "fixtures/file"], ['include:"CTF Flag"']
    )
    assert "TryHackMe Flag Format: THM{this is a flag}" in output


def test_cli_invalid_options():
    result = CliRunner().invoke(
        main, ["--interactive", "--include", "nope", "fixtures/file"]
    )
    assert result.exit_code == 1
    assert "Passed tags are not valid" in result.output


def test_cli_pretty_format_of_file():
    # The pretty format of a file without file signatures (used by
    # interactive mode too) raised KeyError: 'text'
    result = CliRunner().invoke(main, ["--format", "pretty", "fixtures/file"])
    assert result.exit_code == 0
    assert "Possible Identification" in result.output
