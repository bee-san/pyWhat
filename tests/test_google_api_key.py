"""
Tests for Google API keys and asking Google if they are valid (issue #245).

No request is sent to Google: urlopen() is replaced by FakeGoogle, which
answers like Google does.
"""
import io
import json
import socket
from email.message import Message
from typing import List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request

import pytest
from click.testing import CliRunner

import pywhat.processors
from pywhat import Distribution, Filter, Identifier
from pywhat.helper import load_regexes
from pywhat.processors import (
    GoogleAPIKeyVerifier,
    default_processors,
    google_error_reason,
    verifiers,
)
from pywhat.regex_identifier import RegexIdentifier
from pywhat.what import main

NAME = "Google API Key"
KEY = "AIzaSyD7CQl6fRhagGok6CzFGOOPne2X1u1spoA"
OTHER_KEY = "AIzaSyA-1b2C3d4E5f6G7h8I9j0K_LmNoPqRsTu"
GOOGLE = Distribution(Filter({"Tags": ["Google"]}))
VALID = "Verification: valid, Google accepted the key"
INVALID = "Verification: invalid, Google rejected the key (API_KEY_INVALID)"


def google_error(code: int, reason: str) -> bytes:
    """An error like the ones that Google APIs answer."""
    return json.dumps(
        {
            "error": {
                "code": code,
                "message": "API key not valid. Please pass a valid API key.",
                "status": "INVALID_ARGUMENT",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                        "reason": reason,
                        "domain": "googleapis.com",
                        "metadata": {"service": "youtube.googleapis.com"},
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.LocalizedMessage",
                        "locale": "en-US",
                        "message": "API key not valid. Please pass a valid API key.",
                    },
                ],
            }
        }
    ).encode()


class FakeGoogle:
    """Replaces urlopen(): answers like Google and records the requests."""

    def __init__(
        self,
        code: int = 200,
        body: bytes = b'{"kind": "youtube#i18nLanguageListResponse"}',
        error: Optional[Exception] = None,
    ):
        self.code = code
        self.body = body
        self.error = error
        self.requests: List[Tuple[Request, float]] = []

    def __call__(self, request: Request, timeout: float):
        self.requests.append((request, timeout))
        if self.error is not None:
            raise self.error
        if self.code != 200:
            raise pywhat.processors.HTTPError(
                request.full_url, self.code, "Error", Message(), io.BytesIO(self.body)
            )
        return io.BytesIO(self.body)

    @property
    def keys(self) -> List[str]:
        """The keys that were sent to Google."""
        prefix = GoogleAPIKeyVerifier.url
        return [request.full_url[len(prefix) :] for request, _ in self.requests]


@pytest.fixture
def google(monkeypatch) -> FakeGoogle:
    """Google answering that the keys are valid."""
    fake = FakeGoogle()
    monkeypatch.setattr(pywhat.processors, "urlopen", fake)
    return fake


@pytest.fixture
def invalid_google(monkeypatch) -> FakeGoogle:
    """Google answering that the keys are invalid."""
    fake = FakeGoogle(400, google_error(400, "API_KEY_INVALID"))
    monkeypatch.setattr(pywhat.processors, "urlopen", fake)
    return fake


def verify(text: str, verifier: Optional[GoogleAPIKeyVerifier] = None) -> List[dict]:
    """The Google API keys in text, verified."""
    verifier = GoogleAPIKeyVerifier() if verifier is None else verifier
    matches = RegexIdentifier().check([text], dist=GOOGLE, processors=[verifier])
    return [match for match in matches if match["Regex Pattern"]["Name"] == NAME]


def description(text: str) -> str:
    (match,) = verify(text)
    return match["Regex Pattern"]["Description"]


def run_cli(args: List[str], input: Optional[str] = None) -> str:
    result = CliRunner().invoke(main, args, input=input)
    assert result.exit_code == 0, result.output
    return " ".join(result.output.split())  # rich wraps long lines


# The regex and its exploit


def names_and_matches(found: dict) -> List[Tuple[str, str]]:
    return [
        (m["Regex Pattern"]["Name"], m["Matched"]) for m in found["Regexes"]["text"]
    ]


@pytest.mark.parametrize(
    "text, key",
    [
        (f"const key = '{KEY}';", KEY),
        (f"https://maps.googleapis.com/maps/api/js?key={KEY}&callback=init", KEY),
        (f'"api_key": "{OTHER_KEY}"', OTHER_KEY),
    ],
)
def test_google_api_key_in_text(text, key):
    found = Identifier(boundaryless=Filter()).identify(text, dist=GOOGLE)
    assert (NAME, key) in names_and_matches(found)


def test_exploit_commands_contain_the_key():
    (match,) = [
        m for m in RegexIdentifier().check([KEY]) if m["Regex Pattern"]["Name"] == NAME
    ]
    exploit = match["Regex Pattern"]["Exploit"]
    assert f"i18nLanguages?part=snippet&key={KEY}" in exploit
    assert f"geocode/json?latlng=40,30&key={KEY}" in exploit
    assert "_HERE" not in exploit
    assert "--verify" in exploit


def test_exploit_command_is_the_verifier_request():
    entry = next(regex for regex in load_regexes() if regex["Name"] == NAME)
    assert GoogleAPIKeyVerifier.url + "API_KEY_HERE" in entry["Exploit"]


# Google's answers


@pytest.mark.parametrize(
    "body, reason",
    [
        (google_error(400, "API_KEY_INVALID"), "API_KEY_INVALID"),
        (google_error(403, "SERVICE_DISABLED"), "SERVICE_DISABLED"),
        (b'{"error": {"code": 500, "message": "Internal error"}}', None),
        (b'{"error": {"details": ["x"]}}', None),
        (b'{"error": "x"}', None),
        (b'{"kind": "youtube#i18nLanguageListResponse"}', None),
        (b"[]", None),
        (b"<html>Bad Gateway</html>", None),
        (b"\xff\xfe", None),
        (b"", None),
    ],
)
def test_google_error_reason(body, reason):
    assert google_error_reason(body) == reason


def test_valid_key(google):
    assert description(KEY) == VALID
    ((request, timeout),) = google.requests
    assert request.full_url == (
        "https://www.googleapis.com/youtube/v3/i18nLanguages?part=snippet&key=" + KEY
    )
    assert request.get_method() == "GET"
    assert request.get_header("User-agent") == "pywhat"
    assert timeout == 10


def test_invalid_key(invalid_google):
    assert description(KEY) == INVALID


@pytest.mark.parametrize(
    "reason",
    [
        "SERVICE_DISABLED",
        "API_KEY_SERVICE_BLOCKED",
        "API_KEY_HTTP_REFERRER_BLOCKED",
        "API_KEY_IP_ADDRESS_BLOCKED",
        "API_KEY_ANDROID_APP_BLOCKED",
        "API_KEY_IOS_APP_BLOCKED",
        "BILLING_DISABLED",
        "RATE_LIMIT_EXCEEDED",
        "RESOURCE_QUOTA_EXCEEDED",
    ],
)
def test_valid_key_that_cannot_be_used_for_the_request(monkeypatch, reason):
    monkeypatch.setattr(
        pywhat.processors, "urlopen", FakeGoogle(403, google_error(403, reason))
    )
    assert description(KEY) == (
        f"Verification: valid, but Google refused the request ({reason})"
    )


@pytest.mark.parametrize(
    "code, body, result",
    [
        (
            403,
            google_error(403, "CONSUMER_SUSPENDED"),
            "unknown, Google answered HTTP 403 (CONSUMER_SUSPENDED)",
        ),
        (500, b"<html>Server Error</html>", "unknown, Google answered HTTP 500"),
        (503, b"", "unknown, Google answered HTTP 503"),
    ],
)
def test_unknown_answer(monkeypatch, code, body, result):
    monkeypatch.setattr(pywhat.processors, "urlopen", FakeGoogle(code, body))
    assert description(KEY) == f"Verification: {result}"


@pytest.mark.parametrize(
    "error, result",
    [
        (
            URLError("[Errno -2] Name or service not known"),
            "<urlopen error [Errno -2] Name or service not known>",
        ),
        (socket.timeout("timed out"), "timed out"),
        (ConnectionResetError("Connection reset by peer"), "Connection reset by peer"),
    ],
)
def test_google_cannot_be_reached(monkeypatch, error, result):
    monkeypatch.setattr(pywhat.processors, "urlopen", FakeGoogle(error=error))
    assert description(KEY) == f"Verification: unknown, could not ask Google ({result})"


def test_connection_lost_while_reading_the_error(monkeypatch):
    class LostConnection(io.BytesIO):
        def read(self, *args):
            raise ConnectionResetError("Connection reset by peer")

    def urlopen(request, timeout):
        raise pywhat.processors.HTTPError(
            request.full_url, 400, "Bad Request", Message(), LostConnection()
        )

    monkeypatch.setattr(pywhat.processors, "urlopen", urlopen)
    assert description(KEY) == (
        "Verification: unknown, could not ask Google (Connection reset by peer)"
    )


def test_timeout(google):
    verify(KEY, GoogleAPIKeyVerifier(timeout=2.5))
    assert [timeout for _, timeout in google.requests] == [2.5]


def test_every_key_is_sent_once(google):
    verifier = GoogleAPIKeyVerifier()
    matches = verify(f"{KEY}\n{OTHER_KEY}\n{KEY}", verifier)
    assert [match["Matched"] for match in matches] == [KEY, OTHER_KEY, KEY]
    assert all(m["Regex Pattern"]["Description"] == VALID for m in matches)
    verify(KEY, verifier)
    assert google.keys == [KEY, OTHER_KEY]


def test_verification_is_added_to_the_description(google):
    match = {"Matched": KEY, "Regex Pattern": {"Name": NAME, "Description": "Maps"}}
    processed = GoogleAPIKeyVerifier().process(match)
    assert processed is not None
    assert processed["Regex Pattern"]["Description"] == f"Maps. {VALID}"


def test_verification_does_not_change_the_database(google):
    description(KEY)
    entry = next(regex for regex in load_regexes() if regex["Name"] == NAME)
    assert entry["Description"] is None


# Verification is opt-in: no key is sent to Google unless asked for


def test_verifiers_are_not_default_processors(google):
    assert not any(isinstance(p, GoogleAPIKeyVerifier) for p in default_processors())
    found = Identifier().identify(KEY, dist=GOOGLE)
    (match,) = [
        m for m in found["Regexes"]["text"] if m["Regex Pattern"]["Name"] == NAME
    ]
    assert match["Regex Pattern"]["Description"] is None
    assert google.requests == []


def test_verifiers():
    first, second = verifiers(), verifiers()
    assert [type(p) for p in first] == [GoogleAPIKeyVerifier]
    assert all(a is not b for a, b in zip(first, second))
    names = {regex["Name"] for regex in load_regexes()}
    assert all(set(p.names) <= names for p in first)


def test_identifier_with_verifiers(invalid_google):
    found = Identifier(processors=[*default_processors(), *verifiers()]).identify(
        f"key={KEY}", dist=GOOGLE, boundaryless=Filter()
    )
    (match,) = [
        m for m in found["Regexes"]["text"] if m["Regex Pattern"]["Name"] == NAME
    ]
    assert match["Regex Pattern"]["Description"] == INVALID


# Command line interface


def test_cli_verify(invalid_google):
    output = run_cli(["--verify", KEY])
    assert f"Name: {NAME} Description: {INVALID}" in output
    assert invalid_google.keys == [KEY]


def test_cli_does_not_verify_by_default(google):
    output = run_cli([KEY])
    assert f"Name: {NAME}" in output
    assert "Verification:" not in output
    assert google.requests == []


@pytest.mark.parametrize("flag", ["-dp", "--disable-processing"])
def test_cli_verify_with_disable_processing(invalid_google, flag):
    output = run_cli([flag, "--verify", "--rarity", "0:", f"{KEY}\n1637093119"])
    assert INVALID in output
    assert "Name: Unix Timestamp" in output
    assert "Date:" not in output  # the default processors are still disabled


def test_cli_verify_keeps_the_default_processors(invalid_google):
    output = run_cli(["--verify", "--rarity", "0:", f"{KEY}\n1637093119"])
    assert INVALID in output
    assert "Date: November 16, 2021 8:05:19 PM UTC" in output


def test_cli_verify_json(google):
    output = json.loads(run_cli(["--verify", "--json", KEY]))
    (match,) = [
        m for m in output["Regexes"]["text"] if m["Regex Pattern"]["Name"] == NAME
    ]
    assert match["Regex Pattern"]["Description"] == VALID


def test_cli_verify_file(google, tmp_path):
    path = tmp_path / "config.js"
    path.write_text(f"apiKey: '{KEY}',\nother: '{KEY}'\n")
    output = run_cli(["--verify", "--include", "Google", str(path)])
    assert VALID in output
    assert google.keys == [KEY]


def test_cli_verify_multiple_inputs(google, tmp_path):
    path = tmp_path / "config.js"
    path.write_text(f"apiKey: '{KEY}'\n")
    output = run_cli(["--verify", "--include", "Google", str(path), KEY, OTHER_KEY])
    assert output.count(VALID) == 3
    assert google.keys == [KEY, OTHER_KEY]  # KEY is sent once


def test_cli_verify_interactive(invalid_google):
    output = run_cli(["--interactive", "--verify", KEY], input='include:"Google"\n')
    assert INVALID in output
    assert invalid_google.keys == [KEY]


def test_cli_help():
    output = run_cli(["--help"])
    assert "--verify" in output
    assert "Verification:" in output
    assert "sends the keys to the services" in output
