import io
import json
import os
import re
from contextlib import contextmanager

import pytest
from click.testing import CliRunner
from rich.console import Console

import pywhat.what
from pywhat import pywhat_tags
from pywhat.helper import FRAGMENT, get_names, load_regexes
from pywhat.identifier import Identifier
from pywhat.printer import Printing
from pywhat.what import main


# Helper function to run the command and check results
def run_cli_command(command_args, expected_pattern):
    runner = CliRunner()
    result = runner.invoke(main, command_args)
    assert result.exit_code == 0
    assert re.findall(expected_pattern, str(result.output))


@pytest.mark.parametrize(
    "command_args, expected_pattern",
    [
        (["-db", "52.6169586, -1.9779857"], "Latitude"),
        (["-db", "fixtures/file"], "Litecoin"),
        (["-db", "fixtures/file"], "live.block"),
        (["-db", "fixtures/file"], "Bitcoin Cash"),
        (
            ["-db", "bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"],
            "blockchain",
        ),
        (["-db", "fixtures/file"], "Ripple"),
        (["-db", "fixtures/file"], "thm"),
        (["-db", "fixtures/file"], "Ethereum"),
        (["-db", "fixtures/file"], 'thm{"'),
        (["-db", "fixtures/file"], "URL"),
        (["-db", "fixtures/file"], "etherscan"),
        (["-db", "fixtures/file"], "dogechain"),
        (["-db", "fixtures/file"], "Dogecoin"),
        (["-db", "fixtures/file"], "Bitcoin"),
        (["-db", "fixtures/file"], "Nano"),
        (["-db", "fixtures/file"], "Visa"),
        (["-db", "fixtures/file"], "MasterCard"),
        (["-db", "fixtures/file"], "American Express"),
        (["-db", "fixtures/file"], "Diners Club Card"),
        (["-db", "fixtures/file"], "Discover"),
        (["-db", "fixtures/file"], "Email"),
        (["fixtures/file"], "Phone Number"),
        (["-db", "fixtures/file"], "YouTube"),
        (["-db", "118.103.238.230"], "Address Version 4"),
        (["-db", "118.103.238.230"], "shodan"),
        (["-db", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"], "Address Version 6"),
        (["-db", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"], "shodan"),
        (["-db", "fixtures/file"], "Social"),
        (["-db", "fixtures/file"], "xrpscan"),
        (["-db", "fixtures/file"], "Monero"),
        (["-db", "fixtures/file"], "DOI"),
        (["-db", "fixtures/file"], "Mailchimp"),
        (["-db", "fixtures/file"], "de:ad:be:ef:ca:fe"),  # MAC address
        (["-db", "fixtures/file"], "DE:AD:BE:EF:CA:FE"),  # MAC address
        (["-db", "fixtures/file"], "ASIN"),  # ASIN
        (["-db", "Access-Control-Allow: *"], "Access"),
        (
            [
                "-db",
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
            ],
            "JWT",
        ),
        (["-db", "http://s3.amazonaws.com/bucket/"], "S3"),
        (["-db", "s3://bucket/path/key"], "S3"),
        (["-db", "s3://bucket/path/directory/"], "S3"),
        (["-db", "arn:partition:service:region:account-id:resource"], "ARN"),
        (
            ["-db", "arn:partition:service:region:account-id:resourcetype/resource"],
            "ARN",
        ),
        (
            ["-db", "arn:partition:service:region:account-id:resourcetype:resource"],
            "ARN",
        ),
        (["-db", "arn:aws:s3:::my_corporate_bucket/Development/*"], "ARN"),
        # key_value_min_rarity_0
        (["-db", "--rarity", "0:", "key:value"], "Key:Value"),
        (["-db", "--rarity", "0:", "key : value"], "Key:Value"),
        (["-db", "--rarity", "0:", "key: value"], "Key:Value"),
        (["--rarity", "0:", "--boundaryless-rarity", "0:", "a:b:c"], "a:b"),
        (["--rarity", "0:", "--boundaryless-rarity", "0:", "a : b:c"], "a : b"),
        # Encryption keys
        (["-db", "fixtures/file"], "SSH RSA"),
        (["-db", "fixtures/file"], "SSH ECDSA"),
        (["-db", "fixtures/file"], "SSH ED25519"),
        # PGP Keys
        (["-db", "fixtures/file"], "PGP Public Key"),
        (["-db", "fixtures/file"], "PGP Private Key"),
        # Turkish car plate
        (["--rarity", "0:", "fixtures/file"], "Turkish License Plate Number"),
        # Turkish Tax Number
        (["--rarity", "0:", "fixtures/file"], "Turkish Tax Number"),
        # date of birth
        (["-db", "fixtures/file"], "Date of Birth"),
        # Turkish ID #
        (["-db", "fixtures/file"], "Turkish Identification Number"),
        # arg parsing #1
        (["-db", "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"], "blockchain"),
        # arg parsing #2
        (["http://10.1.1.1"], "Internet Protocol"),
        (["-db", "firstname+lastname@example.com"], "Email"),
        (["fixtures/file"], "UUID"),  # UUID
        (["--rarity", "0:", "fixtures/file"], "ObjectID"),  # Object ID
        (["--rarity", "0:", "fixtures/file"], "ULID"),  # ULID
        (["fixtures/file"], "Time-Based One-Time Password [(]TOTP[)] URI"),  # TOTP
        (["fixtures/file"], "SSHPass Clear Password Argument"),  # SSHPass
        (["fixtures/file"], "Slack Webhook"),  # Slack webhook
        (["fixtures/file"], "Discord Webhook"),  # Discord webhook
        (["fixtures/file"], "Guilded Webhook"),  # Guilded webhook
        # borderless cases
        (["-o", "-db", "fixtures/file"], "Nothing found"),  # test_only_text
        (
            ["-be", "identifiers, token", "abc118.103.238.230abc"],
            "Nothing found",
        ),  # test_boundaryless
        (
            ["-bi", "media", "abc118.103.238.230abc"],
            "Nothing found",
        ),  # test_boundaryless2
        (["-db", "abc118.103.238.230abc"], "Nothing found"),  # test_boundaryless3
        (
            ["-db", "--format", " json ", "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"],
            '"File Signatures":',
        ),  # test_format
        (
            ["-db", "--format", " pretty ", "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"],
            "Possible Identification",
        ),  # test_format2
        (["-db", ""], "Nothing found!"),  # test_nothing_found
        (["-db", "THM{this is a flag}"], "THM{"),  # test_hello_world
    ],
)
def test_various_inputs(command_args, expected_pattern):
    run_cli_command(command_args, expected_pattern)


def test_filtration():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--rarity", "0.5:", "--include", "Identifiers,Media", "-db", "fixtures/file"],
    )
    assert result.exit_code == 0
    assert "THM{" not in result.output
    assert "ETH" not in result.output
    assert "Email Address" in result.output
    assert "IP" in result.output
    assert "URL" in result.output


def test_tag_printing():
    runner = CliRunner()
    result = runner.invoke(main, "--tags")
    assert result.exit_code == 0
    for tag in pywhat_tags:
        assert tag in result.output


def test_names_printing():
    result = CliRunner().invoke(main, ["--names"])
    assert result.exit_code == 0
    lines = result.output.splitlines()
    assert "Ethereum (ETH) Wallet Address: Ethereum Wallet, ETH Wallet" in lines
    assert "Key:Value Pair" in lines
    # One line per regex, sorted by name, however long the line is
    expected = []
    for regex in sorted(load_regexes(), key=lambda regex: regex["Name"].lower()):
        name, *alternative_names = get_names(regex)
        if alternative_names:
            name += ": " + ", ".join(alternative_names)
        expected.append(name)
    assert lines == expected


def found_names(output):
    return set(re.findall(r"^Name: (.*)$", output, re.MULTILINE))


def test_include_names():
    # Names and alternative names work like tags (issue #184)
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "--include",
            "DOGE Wallet, ethereum (eth) wallet address",
            "fixtures/file",
        ],
    )
    assert result.exit_code == 0
    assert found_names(result.output) == {
        "Dogecoin (DOGE) Wallet Address",
        "Ethereum (ETH) Wallet Address",
    }


def test_exclude_names():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "--include",
            "Cryptocurrency Wallet",
            "--exclude",
            "XRP Wallet,DOGE Wallet",
            "fixtures/file",
        ],
    )
    assert result.exit_code == 0
    names = found_names(result.output)
    assert "Ethereum (ETH) Wallet Address" in names
    assert "Ripple (XRP) Wallet Address" not in names
    assert "Dogecoin (DOGE) Wallet Address" not in names


def test_names_with_commas():
    # The commas in parentheses do not separate the tags and names
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "--include",
            "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc),UUID",
            "fixtures/file",
        ],
    )
    assert result.exit_code == 0
    assert found_names(result.output) == {
        "EUI-48 Identifier (Ethernet, WiFi, Bluetooth, etc)",
        "UUID",
    }


def test_boundaryless_names():
    runner = CliRunner()
    result = runner.invoke(main, ["-be", "IPv4 Address", "abc118.103.238.230abc"])
    assert result.exit_code == 0
    assert "Nothing found" in result.output
    result = runner.invoke(main, ["-bi", "IPv4 Address", "abc118.103.238.230abc"])
    assert result.exit_code == 0
    assert "Internet Protocol (IP) Address Version 4" in found_names(result.output)


@pytest.mark.parametrize("option", ["--include", "--exclude", "-bi", "-be"])
def test_invalid_names(option):
    result = CliRunner().invoke(main, [option, "ETH Walet", "fixtures/file"])
    assert result.exit_code == 1
    assert "Passed tags are not valid" in result.output
    assert "'pywhat --names'" in result.output


def test_json_printing():
    """Test for valid json"""
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "10.0.0.1", "--json"])
    assert json.loads(result.output.replace("\n", ""))


def test_json_printing2():
    """Test for empty json return"""
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "", "--json"])
    assert result.output.strip("\n") == '{"File Signatures": null, "Regexes": null}'


def test_json_printing3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file", "--json"])
    assert json.loads(result.output.replace("\n", ""))


def test_file_fixture():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("thm", str(result.output))
    assert re.findall("Ethereum", str(result.output))
    assert "Dogecoin" in result.output


def test_file_fixture2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert "Dogecoin" in result.output


def test_key_value_min_rarity_0_3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", ":a:"])
    assert result.exit_code == 0
    assert not re.findall("Key:Value", str(result.output))


def test_key_value_min_rarity_0_4():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", ":::::"])
    assert result.exit_code == 0
    assert not re.findall("Key:Value", str(result.output))


def test_key_value_min_rarity_0_5():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", "a:b:c"])
    assert result.exit_code == 0
    assert not re.findall("a:b:c", str(result.output))


@pytest.mark.skip("Key:value turned off")
def test_file_fixture_usernamepassword():
    run_cli_command(["-db", "fixtures/file"], "Key")


@pytest.mark.skip("Key:value turned off")
def test_file_pcap():
    run_cli_command(["-db", "fixtures/FollowTheLeader.pcap"], "Host:")


def test_mac_tags():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--include", "Identifiers,Networking", "-db", "fixtures/file"],
    )
    assert result.exit_code == 0
    assert "Ethernet" in result.output
    assert "IP" in result.output


def test_format3():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "--format",
            r"%m 2%n %d --- -%e%r %l %t \%d",
            "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk",
        ],
    )
    assert result.exit_code == 0
    assert (
        "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk 2Ripple (XRP) Wallet Address  --- -0.3 https://xrpscan.com/account/rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk Finance, Cryptocurrency Wallet, Ripple Wallet, Ripple, XRP %d"
        in result.output.replace("\n", "")
    )


def test_format4():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "--include",
            "Bug Bounty",
            "--format",
            r"\\%e %l %z",
            "heroku00000000-0000-0000-0000-000000000000",
        ],
    )
    assert result.exit_code == 0
    assert (
        '\\Use the command below to verify that the API key is valid:\n  $ curl -X POST https://api.heroku.com/apps -H "Accept: application/vnd.heroku+json; version=3" -H "Authorization: Bearer heroku00000000-0000-0000-0000-000000000000"\n  %z'.split()
        == result.output.split()
    )


def test_format5():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--format", r"%e", "thm{2}"])
    assert result.exit_code == 0
    assert len(result.output) == 0


def test_print_tags():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "-pt", "thm{2}"])
    assert result.exit_code == 0
    assert "Tags: CTF Flag" in result.output


def test_print_tags2():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "--print-tags", "--format", "pretty", "thm{2}"]
    )
    assert result.exit_code == 0
    assert "Tags: CTF Flag" in result.output


# Multiple inputs (issue #171)


def test_multiple_files():
    # Used to fail with "Error: Got unexpected extra arguments"
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file", "fixtures/test/file"])
    assert result.exit_code == 0
    assert "File: fixtures/file" in result.output
    assert "Dogecoin" in result.output
    assert "File: fixtures/test/file" in result.output
    assert "https://google.com" in result.output


def test_multiple_texts():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "THM{hello}", "0x52908400098527886E0F7030069857D2E4169EE7"]
    )
    assert result.exit_code == 0
    assert "TryHackMe Flag Format" in result.output
    assert "Ethereum (ETH) Wallet Address" in result.output
    # Like for a single text, there are no files to show
    assert "File:" not in result.output


def test_multiple_inputs_file_and_text():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/test/file", "THM{hello}"])
    assert result.exit_code == 0
    assert "File: fixtures/test/file\nMatched on: https://google.com" in result.output
    assert "File: text\nMatched on: THM{hello}" in result.output


def test_multiple_inputs_nothing_found():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "nothing", "here"])
    assert result.exit_code == 0
    assert result.output.strip() == "Nothing found!"


def test_multiple_inputs_json():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "--json", "fixtures/test", "fixtures/file", "THM{hello}"]
    )
    assert result.exit_code == 0
    identified = json.loads(result.output)
    # One JSON object, with the file of every match
    assert set(identified["Regexes"]) == {
        os.path.join("fixtures/test", "file"),
        "fixtures/file",
        "text",
    }
    assert identified["Regexes"]["text"][0]["Matched"] == "THM{hello}"
    assert identified["File Signatures"] is None


def test_multiple_inputs_json_nothing_found():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--json", "nothing", "here"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"File Signatures": None, "Regexes": None}


def test_multiple_inputs_format():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "--format", "%m - %n", "fixtures/test/file", "THM{hello}"]
    )
    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "https://google.com - Uniform Resource Locator (URL)",
        "THM{hello} - TryHackMe Flag Format",
    ]


def test_multiple_inputs_pretty():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["-db", "--format", "pretty", "fixtures/test/file", "THM{hello}"],
        env={"COLUMNS": "200"},  # so that the table does not fold the text
    )
    assert result.exit_code == 0
    assert "Possible Identification" in result.output
    lines = result.output.splitlines()
    assert any(re.search(r"Description.+File", line) for line in lines)
    assert any(
        re.search(r"https://google\.com.+fixtures/test/file", line) for line in lines
    )
    assert any(re.search(r"THM\{hello\}.+text", line) for line in lines)


def test_multiple_texts_pretty():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["-db", "--format", "pretty", "THM{hello}", "github@skerritt.blog"],
        env={"COLUMNS": "200"},
    )
    assert result.exit_code == 0
    assert "Possible Identification" in result.output
    assert "github@skerritt.blog" in result.output
    # Like for a single text, there is no file column
    assert "File" not in result.output


def test_multiple_inputs_file_signatures(tmp_path, monkeypatch):
    # Relative paths, so that the output is not wrapped
    monkeypatch.chdir(tmp_path)
    (tmp_path / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nTHM{hello}\n")
    (tmp_path / "page.html").write_text("https://google.com\n")
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "image.png", "page.html"])
    assert result.exit_code == 0
    assert "File Identified: image.png with Magic Numbers .PNG...." in result.output
    assert "File: image.png\nMatched on: THM{hello}" in result.output
    assert "File: page.html\nMatched on: https://google.com" in result.output

    result = runner.invoke(main, ["-db", "--json", "image.png", "page.html"])
    identified = json.loads(result.output)
    assert list(identified["File Signatures"]) == ["image.png"]
    assert list(identified["Regexes"]) == ["image.png", "page.html"]


def test_multiple_inputs_sorting():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["-db", "--json", "-k", "name", "--reverse", "fixtures/file", "THM{hello}"],
    )
    assert result.exit_code == 0
    identified = json.loads(result.output)
    names = [
        match["Regex Pattern"]["Name"]
        for match in identified["Regexes"]["fixtures/file"]
    ]
    assert len(names) > 1
    assert names == sorted(names, reverse=True)


def test_sorting_without_matches():
    # Used to raise TypeError: 'NoneType' object is not subscriptable
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "-k", "name", "nothing"])
    assert result.exit_code == 0
    assert "Nothing found!" in result.output


def test_multiple_inputs_only_text():
    # With --only-text the paths are text, like for a single input
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "-o", "--json", "fixtures/file", "THM{hello}"])
    assert result.exit_code == 0
    identified = json.loads(result.output)
    assert list(identified["Regexes"]) == ["text"]
    assert [match["Matched"] for match in identified["Regexes"]["text"]] == [
        "THM{hello}"
    ]


def test_no_input():
    runner = CliRunner()
    result = runner.invoke(main, [])
    # Without input, stdin is read (it is empty here)
    assert result.exit_code == 0
    assert "Nothing found!" in result.output


def test_no_input_on_a_terminal():
    class Terminal(io.BytesIO):
        def isatty(self):
            return True

    runner = CliRunner()
    result = runner.invoke(main, [], input=Terminal())
    assert result.exit_code == 1
    assert "Text input expected" in result.output


def test_stdin_with_several_lines():
    runner = CliRunner()
    result = runner.invoke(main, ["-db"], input="THM{hello}\nfixtures/file\n")
    assert result.exit_code == 0
    # stdin is a single text, not a list of inputs
    assert "TryHackMe Flag Format" in result.output
    assert "File:" not in result.output


# Progress bars and --stream (issue #189)


def squeeze(output):
    """The output with every run of empty lines as a single empty line."""
    return re.sub(r"\n{3,}", "\n\n", output)


@pytest.mark.parametrize(
    "args",
    [
        ["-db", "fixtures/file"],
        ["fixtures"],
        ["-pt", "THM{hello} dad@gmail.com"],
        ["--format", "%m - %n", "fixtures"],
        ["fixtures/file", "fixtures/test/file", "THM{hello}"],
        ["THM{hello}", "THM{bye}"],
        ["-db", ""],
        ["-db", "--format", r"%e", "thm{2}"],
    ],
)
def test_stream(args):
    # What is printed once the search is complete, printed while searching
    runner = CliRunner()
    expected = runner.invoke(main, args)
    streamed = runner.invoke(main, ["--stream", *args])
    assert streamed.exit_code == expected.exit_code == 0
    assert squeeze(streamed.output) == squeeze(expected.output)


def test_stream_file_signature(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nTHM{hello}\n")
    runner = CliRunner()
    streamed = runner.invoke(main, ["--stream", str(image)])
    assert "File Identified" in streamed.output
    assert streamed.output == runner.invoke(main, [str(image)]).output

    # As soon as it is found, even if nothing is found in the file
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    streamed = runner.invoke(main, ["--stream", str(image)])
    assert "File Identified" in streamed.output
    assert streamed.output.rstrip().endswith("Nothing found!")


def test_stream_json():
    runner = CliRunner()
    expected = json.loads(runner.invoke(main, ["--json", "fixtures"]).output)
    result = runner.invoke(main, ["--stream", "--json", "fixtures"])
    assert result.exit_code == 0
    # A JSON object for every match, on its own line, in the format of --json
    regexes = {}
    for line in result.output.splitlines():
        found = json.loads(line)
        assert found["File Signatures"] is None
        [(location, [match])] = found["Regexes"].items()
        # Whether a match is a fragment is only known once its file has been
        # searched, after the match has been printed
        assert FRAGMENT not in match
        regexes.setdefault(location, []).append(match)
    for matches in expected["Regexes"].values():
        for match in matches:
            del match[FRAGMENT]
    assert regexes == expected["Regexes"]


def test_stream_json_file_signature(tmp_path):
    image = tmp_path / "image.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nTHM{hello}\n")
    result = CliRunner().invoke(main, ["--stream", "--format", "json", str(image)])
    assert result.exit_code == 0
    signature, match = map(json.loads, result.output.splitlines())
    assert signature["Regexes"] is None
    assert signature["File Signatures"]["image.png"]["Filename Extension"] == "png"
    assert match["File Signatures"] is None
    assert match["Regexes"]["image.png"][0]["Matched"] == "THM{hello}"


def test_stream_json_nothing_found():
    result = CliRunner().invoke(main, ["--stream", "--json", "-db", ""])
    assert result.exit_code == 0
    assert result.output == ""


@pytest.mark.parametrize(
    "args, option",
    [
        (["--key", "name"], "--key"),
        (["--format", "pretty"], "--format pretty"),
        (["--top", "1"], "--top"),
        (["--interactive"], "--interactive"),
    ],
)
def test_stream_with_options_that_need_all_matches(args, option):
    result = CliRunner().invoke(main, ["--stream", *args, "THM{hello}"])
    assert result.exit_code == 1
    assert option in result.output


def test_stream_without_sorting():
    result = CliRunner().invoke(main, ["--stream", "--key", "none", "THM{hello}"])
    assert result.exit_code == 0
    assert "Matched on: THM{hello}" in result.output


def test_stream_prints_before_the_search_is_complete(monkeypatch):
    match = Identifier().identify("THM{hello}")["Regexes"]["text"][0]

    def iter_identify(self, text, **options):
        yield "Regexes", "text", match
        raise KeyboardInterrupt  # Ctrl+C before the search is complete

    monkeypatch.setattr(Identifier, "iter_identify", iter_identify)
    runner = CliRunner()
    streamed = runner.invoke(main, ["--stream", "THM{hello}"])
    assert "Matched on: THM{hello}" in streamed.output
    assert "Aborted!" in streamed.output
    complete = runner.invoke(main, ["THM{hello}"])
    assert "Aborted!" in complete.output
    assert "THM{hello}" not in complete.output


@pytest.fixture
def progress_bars(monkeypatch):
    """Records the options of the progress bars, and the progress they get."""
    shown = []

    @contextmanager
    def record(console, **options):
        progress = []
        shown.append((console, options, progress))
        yield progress.append

    monkeypatch.setattr(pywhat.what, "progress_bars", record)
    return shown


@pytest.mark.parametrize("args", [[], ["--stream"], ["--json"], ["--stream", "--json"]])
def test_progress_bars(progress_bars, args):
    result = CliRunner().invoke(main, [*args, "fixtures"])
    assert result.exit_code == 0
    [(console, options, progress)] = progress_bars
    # On the terminal of the output, or on stderr if the output is redirected
    assert options == {"enabled": True, "stderr": True}
    assert progress[-1].files_done == progress[-1].files == 2


def test_no_progress(progress_bars):
    result = CliRunner().invoke(main, ["--no-progress", "fixtures"])
    assert result.exit_code == 0
    [(console, options, progress)] = progress_bars
    assert options["enabled"] is False


def test_no_progress_bars_in_the_output():
    # The output is not a terminal here, so there are no progress bars
    result = CliRunner().invoke(main, ["-db", "--json", "fixtures"])
    assert json.loads(result.output)


def test_print_stream_api():
    # Printing.print_stream() with what Identifier.iter_identify() yields
    printer = Printing()
    printer.console = Console(file=io.StringIO(), width=200, color_system=None)
    for text_input in ["fixtures", ["fixtures"]]:
        printer.console.file = io.StringIO()
        printer.print_stream(
            Identifier().iter_identify(text_input, only_text=False), text_input
        )
        output = printer.console.file.getvalue()
        location = os.path.join(os.sep, "test", "file")  # \test\file on Windows
        assert f"File: {location}\nMatched on: https://google.com" in output

        printer.console.file = io.StringIO()
        printer.print_raw(
            Identifier().identify("fixtures", only_text=False), text_input
        )
        assert squeeze(output) == squeeze(printer.console.file.getvalue())
