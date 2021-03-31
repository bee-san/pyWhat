from click.testing import CliRunner
from What.what import main

def test_hello_world():
  runner = CliRunner()
  result = runner.invoke(main, ['1981328391THM{this is a flag}asdasda'])
  assert result.exit_code == 0
  assert "THM{" in result.output