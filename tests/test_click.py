import json
import re

import pytest
from click.testing import CliRunner

from pywhat import pywhat_tags
from pywhat.what import main


def test_nothing_found():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", ""])
    assert result.exit_code == 0
    assert "Nothing found!" in result.output


def test_hello_world():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "THM{this is a flag}"])
    assert result.exit_code == 0
    assert "THM{" in result.output


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


def test_file_fixture3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("thm", str(result.output))


def test_file_fixture4():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Ethereum", str(result.output))


def test_file_fixture5():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("thm{", str(result.output))


def test_file_fixture7():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall('thm{"', str(result.output))


def test_file_fixture8():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("URL", str(result.output))


def test_file_fixture9():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("etherscan", str(result.output))


def test_file_fixture10():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("dogechain", str(result.output))


def test_file_fixture11():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Dogecoin", str(result.output))


def test_file_fixture12():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Ethereum", str(result.output))


def test_file_fixture13():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Bitcoin", str(result.output))


def test_file_fixture14():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Nano", str(result.output))


def test_arg_parsing():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "1KFHE7w8BhaENAswwryaoccDb6qcT6DbYY"])
    assert result.exit_code == 0
    assert re.findall("blockchain", str(result.output))


def test_arg_parsing2():
    runner = CliRunner()
    result = runner.invoke(main, ["http://10.1.1.1"])
    assert result.exit_code == 0
    assert re.findall("Internet Protocol", str(result.output))


def test_file_fixture_visa():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Visa", str(result.output))


def test_file_fixture_master_card():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("MasterCard", str(result.output))


def test_file_fixture_master_amex():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("American Express", str(result.output))


def test_file_fixture_master_diners():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Diners Club Card", str(result.output))


def test_file_fixture_discover():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Discover", str(result.output))


@pytest.mark.skip("Key:value turned off")
def test_file_fixture_usernamepassword():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Key", str(result.output))


def test_file_fixture_email():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Email", str(result.output))


def test_file_fixture_email2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "firstname+lastname@example.com"])
    assert result.exit_code == 0
    assert re.findall("Email", str(result.output))


def test_file_fixture_phone_number():
    runner = CliRunner()
    result = runner.invoke(main, ["fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Phone Number", str(result.output))


def test_file_fixture_youtube():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("YouTube", str(result.output))


def test_file_fixture_youtube_id():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("YouTube", str(result.output))


def test_file_fixture_ip4():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "118.103.238.230"])
    assert result.exit_code == 0
    assert re.findall("Address Version 4", str(result.output))


def test_file_fixture_ip4_shodan():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "118.103.238.230"])
    assert result.exit_code == 0
    assert re.findall("shodan", str(result.output))


def test_file_fixture_ip6():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"])
    assert result.exit_code == 0
    assert re.findall("Address Version 6", str(result.output))


def test_file_fixture_ip6_shodan():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "2001:0db8:85a3:0000:0000:8a2e:0370:7334"])
    assert result.exit_code == 0
    assert re.findall("shodan", str(result.output))


def test_file_fixture_ssn():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Social", str(result.output))


@pytest.mark.skip("Key:value turned off")
def test_file_pcap():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/FollowTheLeader.pcap"])
    assert result.exit_code == 0
    assert re.findall("Host:", str(result.output))


def test_file_coords():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "52.6169586, -1.9779857"])
    assert result.exit_code == 0
    assert re.findall("Latitude", str(result.output))


def test_file_fixture_ltc():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Litecoin", str(result.output))


def test_file_fixture_ltc2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("live.block", str(result.output))


def test_file_fixture_bch():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Bitcoin Cash", str(result.output))


def test_file_fixture_bch2():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "bitcoincash:qzlg6uvceehgzgtz6phmvy8gtdqyt6vf359at4n3lq"]
    )
    assert result.exit_code == 0
    assert re.findall("blockchain", str(result.output))


def test_file_fixture_xrp():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Ripple", str(result.output))


def test_file_fixture_xrp2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("xrpscan", str(result.output))


def test_file_fixture_xmr():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Monero", str(result.output))


def test_file_fixture_doi():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("DOI", str(result.output))


def test_file_fixture_mailchimp():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Mailchimp", str(result.output))


def test_file_cors():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "Access-Control-Allow: *"])
    assert result.exit_code == 0
    assert re.findall("Access", str(result.output))


def test_file_jwt():
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "-db",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        ],
    )
    assert result.exit_code == 0
    assert re.findall("JWT", str(result.output))


def test_file_s3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "http://s3.amazonaws.com/bucket/"])
    assert result.exit_code == 0
    assert re.findall("S3", str(result.output))


def test_file_s3_2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "s3://bucket/path/key"])
    assert result.exit_code == 0
    assert re.findall("S3", str(result.output))


def test_file_s3_3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "s3://bucket/path/directory/"])
    assert result.exit_code == 0
    assert re.findall("S3", str(result.output))


def test_file_arn():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "arn:partition:service:region:account-id:resource"]
    )
    assert result.exit_code == 0
    assert re.findall("ARN", str(result.output))


def test_file_arn2():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "arn:partition:service:region:account-id:resourcetype/resource"]
    )
    assert result.exit_code == 0
    assert re.findall("ARN", str(result.output))


def test_file_arn3():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "arn:partition:service:region:account-id:resourcetype:resource"]
    )
    assert result.exit_code == 0
    assert re.findall("ARN", str(result.output))


def test_file_arn4():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "arn:aws:s3:::my_corporate_bucket/Development/*"]
    )
    assert result.exit_code == 0
    assert re.findall("ARN", str(result.output))


def test_key_value_min_rarity_0():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", "key:value"])
    assert result.exit_code == 0
    assert re.findall("Key:Value", str(result.output))


def test_key_value_min_rarity_0_1():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", "key : value"])
    assert result.exit_code == 0
    assert re.findall("Key:Value", str(result.output))


def test_key_value_min_rarity_0_2():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "--rarity", "0:", "key: value"])
    assert result.exit_code == 0
    assert re.findall("Key:Value", str(result.output))


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


def test_key_value_min_rarity_0_6():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--rarity", "0:", "--boundaryless-rarity", "0:", "a:b:c"]
    )
    assert result.exit_code == 0
    assert re.findall("a:b", str(result.output))


def test_key_value_min_rarity_0_7():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--rarity", "0:", "--boundaryless-rarity", "0:", "a : b:c"]
    )
    assert result.exit_code == 0
    assert re.findall("a : b", str(result.output))


def test_only_text():
    runner = CliRunner()
    result = runner.invoke(main, ["-o", "-db", "fixtures/file"])
    assert result.exit_code == 0
    assert "Nothing found" in result.output


def test_boundaryless():
    runner = CliRunner()
    result = runner.invoke(main, ["-be", "identifiers, token", "abc118.103.238.230abc"])
    assert result.exit_code == 0
    assert "Nothing found" in result.output


def test_boundaryless2():
    runner = CliRunner()
    result = runner.invoke(main, ["-bi", "media", "abc118.103.238.230abc"])
    assert result.exit_code == 0
    assert "Nothing found" in result.output


def test_boundaryless3():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "abc118.103.238.230abc"])
    assert result.exit_code == 0
    assert "Nothing found" in result.output


def test_ssh_rsa_key():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("SSH RSA", str(result.output))


def test_ssh_ecdsa_key():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("SSH ECDSA", str(result.output))


def test_ssh_ed25519_key():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("SSH ED25519", str(result.output))


def test_asin():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("ASIN", str(result.output))


def test_mac():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("de:ad:be:ef:ca:fe", str(result.output))
    assert re.findall("DE:AD:BE:EF:CA:FE", str(result.output))


def test_mac_tags():
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--include", "Identifiers,Networking", "-db", "fixtures/file"],
    )
    assert result.exit_code == 0
    assert "Ethernet" in result.output
    assert "IP" in result.output


def test_pgp_public_key():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("PGP Public Key", str(result.output))


def test_pgp_private_key():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("PGP Private Key", str(result.output))


def test_file_fixture_turkish_car_plate():
    runner = CliRunner()
    result = runner.invoke(main, ["--rarity", "0:", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Turkish License Plate Number", str(result.output))


def test_file_fixture_date_of_birth():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Date of Birth", str(result.output))


def test_file_fixture_turkish_id_number():
    runner = CliRunner()
    result = runner.invoke(main, ["-db", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Turkish Identification Number", str(result.output))


def test_file_fixture_turkish_tax_number():
    runner = CliRunner()
    result = runner.invoke(main, ["--rarity", "0:", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Turkish Tax Number", str(result.output))


def test_file_fixture_uuid():
    runner = CliRunner()
    result = runner.invoke(main, ["fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("UUID", str(result.output))


def test_file_fixture_objectid():
    runner = CliRunner()
    result = runner.invoke(main, ["--rarity", "0:", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("ObjectID", str(result.output))


def test_file_fixture_ulid():
    runner = CliRunner()
    result = runner.invoke(main, ["--rarity", "0:", "fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("ULID", str(result.output))


def test_file_fixture_totp_URI():
    runner = CliRunner()
    result = runner.invoke(main, ["fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Time-Based One-Time Password [(]TOTP[)] URI", str(result.output))


def test_file_fixture_sshpass():
    runner = CliRunner()
    result = runner.invoke(main, ["fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("SSHPass Clear Password Argument", str(result.output))


def test_file_fixture_slack_webhook():
    runner = CliRunner()
    result = runner.invoke(main, ["fixtures/file"])
    assert result.exit_code == 0
    assert re.findall("Slack Webhook", str(result.output))


def test_format():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "--format", " json ", "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"]
    )
    assert result.exit_code == 0
    assert '"File Signatures":' in result.output


def test_format2():
    runner = CliRunner()
    result = runner.invoke(
        main, ["-db", "--format", " pretty ", "rBPAQmwMrt7FDDPNyjwFgwSqbWZPf6SLkk"]
    )
    assert result.exit_code == 0
    assert "Possible Identification" in result.output


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
