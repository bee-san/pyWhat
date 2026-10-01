import json
import re

import pytest
from click.testing import CliRunner

from pywhat import pywhat_tags
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
