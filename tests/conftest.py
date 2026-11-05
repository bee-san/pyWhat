"""
Run tests/test_click.py against another program, such as the Rust CLI:

    cargo build --release
    PYWHAT_CLI=target/release/what pytest -o addopts="" tests/test_click.py

With PYWHAT_CLI set, CliRunner.invoke() runs $PYWHAT_CLI with the arguments in a
subprocess, with the input on stdin and the environment changed like CliRunner changes
it, and returns its exit code and its output (stdout and stderr together, like
CliRunner's). The tests that call or patch the Python CLI's internals are skipped.
Without PYWHAT_CLI, nothing changes.
"""
import os
import shlex
import shutil
import subprocess
import sys
from typing import IO, Any, Mapping, Optional, Sequence, Union

import pytest
from click.testing import CliRunner, Result

# The program to test, as an absolute path, as tests may change the directory
_cli = os.environ.get("PYWHAT_CLI")
PYWHAT_CLI = (
    None
    if not _cli
    else os.path.abspath(_cli)
    if os.path.dirname(_cli)
    else shutil.which(_cli) or _cli
)

# The tests of tests/test_click.py that call or patch the Python CLI's internals, so
# that they can only test the Python CLI
PYTHON_ONLY = {
    "test_stream_prints_before_the_search_is_complete": "patches Identifier.iter_identify",
    "test_progress_bars": "patches pywhat.what.progress_bars",
    "test_no_progress": "patches pywhat.what.progress_bars",
    "test_print_stream_api": "calls Printing.print_stream() and Identifier",
}


def _is_click_test(item: Any) -> bool:
    module = getattr(item, "module", None)
    return module is not None and module.__name__.rsplit(".", 1)[-1] == "test_click"


def pytest_collection_modifyitems(config: Any, items: Sequence[Any]) -> None:
    if not PYWHAT_CLI:
        return
    for item in items:
        name = getattr(item, "originalname", None) or item.name
        if _is_click_test(item) and name in PYTHON_ONLY:
            reason = f"PYWHAT_CLI is set, and this test {PYTHON_ONLY[name]}"
            item.add_marker(pytest.mark.skip(reason=reason))


def _input_bytes(input: Optional[Union[str, bytes, IO]], charset: str) -> bytes:
    """The input as CliRunner gives it to the command (make_input_stream())."""
    if input is None:
        return b""
    if isinstance(input, str):
        return input.encode(charset)
    if isinstance(input, bytes):
        return input
    data = input.read()
    return data.encode(charset) if isinstance(data, str) else data


def _run_on_a_terminal(
    command: Sequence[str], data: bytes, env: Mapping[str, str], stderr: Any
) -> "subprocess.CompletedProcess[bytes]":
    """Run command with a terminal (a pseudo-terminal) as stdin, holding data."""
    # A check of sys.platform, so that mypy doesn't check the Unix part on Windows
    if sys.platform == "win32":
        pytest.skip("PYWHAT_CLI: no pseudo-terminal for stdin on Windows")
    import pty

    leader, follower = pty.openpty()
    try:
        os.write(leader, data)
        return subprocess.run(
            command,
            stdin=follower,
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=dict(env),
            timeout=600,
        )
    finally:
        os.close(follower)
        os.close(leader)


def invoke(
    self: CliRunner,
    cli: Any,
    args: Optional[Union[str, Sequence[str]]] = None,
    input: Optional[Union[str, bytes, IO]] = None,
    env: Optional[Mapping[str, Optional[str]]] = None,
    catch_exceptions: bool = True,
    color: bool = False,
    **extra: Any,
) -> Result:
    """CliRunner.invoke(), running $PYWHAT_CLI instead of cli."""
    assert PYWHAT_CLI is not None
    if isinstance(args, str):
        args = shlex.split(args)
    command = [PYWHAT_CLI, *(args or ())]
    environment = dict(os.environ)
    for name, value in {**self.env, **(env or {})}.items():
        if value is None:
            environment.pop(name, None)
        else:
            environment[name] = value
    # stderr in the output, in the order they were written, like CliRunner's
    stderr = subprocess.STDOUT if self.mix_stderr else subprocess.PIPE
    data = _input_bytes(input, self.charset)
    isatty = getattr(input, "isatty", None)
    if callable(isatty) and isatty():
        completed = _run_on_a_terminal(command, data, environment, stderr)
    else:
        completed = subprocess.run(
            command,
            input=data,
            stdout=subprocess.PIPE,
            stderr=stderr,
            env=environment,
            timeout=600,
        )
    exit_code = completed.returncode
    return Result(
        runner=self,
        stdout_bytes=completed.stdout,
        stderr_bytes=None if self.mix_stderr else completed.stderr,
        return_value=None,
        exit_code=exit_code,
        exception=None if exit_code == 0 else SystemExit(exit_code),
    )


@pytest.fixture(autouse=True)
def pywhat_cli(request: Any, monkeypatch: Any) -> None:
    """With PYWHAT_CLI set, the tests of test_click.py invoke $PYWHAT_CLI."""
    if PYWHAT_CLI and _is_click_test(request.node):
        monkeypatch.setattr(CliRunner, "invoke", invoke)
