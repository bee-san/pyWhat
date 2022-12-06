import unittest
from click.testing import CliRunner

import what
from helper import AvailableTags
from what import print_version

class TestStringMethods(unittest.TestCase):

    def test_nothing_found(self):
        runner = CliRunner()
        result = runner.invoke(what.run, [])
        assert result.exit_code == 0
        assert "Nothing found!" in result.output

    def test_tag_printing(self):
        runner = CliRunner()
        result = runner.invoke(what.run, ["--tags"])
        assert result.exit_code == 0
        for tag in sorted(AvailableTags().get_tags()):
            assert tag in result.output

    def test_print_version(self):
        runner = CliRunner()
        result = runner.invoke(what.run, ["-v"])
        assert result.exit_code == 0

    def test_phone_number(self):
        runner = CliRunner()
        result = runner.invoke(what.run, ["-db", "3378954589"])
        assert result.exit_code == 0
        assert "Phone Number" in result.output

    def test_youtube_link(self):
        runner = CliRunner()
        result = runner.invoke(what.run, ["-db", "dQw4w9WgXcQ"])
        assert result.exit_code == 0
        assert "Youtube" in result.output

    def test_ether_wallet_address(self):
        runner = CliRunner()
        result = runner.invoke(what.run, ["-db", "0x52908400098527886E0F7030069857D2E4169EE7"])
        assert result.exit_code == 0
        assert "Wallet" in result.output   


if __name__ == '__main__':
    unittest.main()