"""
Test cases for IPv6 address identification.

Covers '::' alone not matching (issue #201, with boundaries), upper- and
lowercase hex digits, and decimal-only ports.
"""

from pywhat import identifier

r = identifier.Identifier()


def _ipv6_matches(text):
    out = r.identify(text)
    if out["Regexes"] is None:
        return []
    matches = out["Regexes"]["text"]
    return [m for m in matches if "IPv6" in m["Regex Pattern"].get("Tags", [])]


def test_ipv6_rejects_lone_double_colon():
    """Verify that '::' alone is NOT identified as IPv6 (issue #201)."""
    assert _ipv6_matches("::") == [], "'::' should not match any regex patterns"


def test_ipv6_rejects_multiple_double_colons():
    """Verify that '::::' is not identified as IPv6."""
    assert _ipv6_matches("::::") == [], "'::::' should not match as IPv6"


def test_ipv6_matches_loopback():
    """Verify that '::1' is correctly identified as IPv6."""
    assert len(_ipv6_matches("::1")) > 0, "'::1' should match as IPv6"


def test_ipv6_matches_compressed_addresses():
    """Verify various compressed IPv6 addresses are matched."""
    test_addresses = [
        "2001:db8::1",
        "fe80::1",  # NOSONAR - documentation link-local example address
        "2001::",
        "fe80::",
    ]

    for address in test_addresses:
        assert len(_ipv6_matches(address)) > 0, f"{address} should match as IPv6"


def test_ipv6_matches_full_address():
    """Verify full IPv6 addresses are matched."""
    full_address = "2001:0db8:85a3:0000:0000:8a2e:0370:7334"  # NOSONAR - documentation example address
    assert len(_ipv6_matches(full_address)) > 0, f"{full_address} should match as IPv6"


def test_ipv6_matches_bracketed_with_numeric_port():
    """Verify IPv6 in brackets with a numeric port is matched."""
    assert len(_ipv6_matches("[2001:db8::1]:8080")) > 0


def test_ipv6_rejects_bracketed_with_hex_port():
    """Ports are decimal, so a hexadecimal port must not match."""
    assert _ipv6_matches("[2001:db8::1]:808a") == []


def test_ipv6_matches_uppercase_hex():
    """IPv6 hex digits are case-insensitive (RFC 4291)."""
    test_addresses = [
        "2001:DB8::1",
        "FE80::1",
        "2001:0DB8:85A3:0000:0000:8A2E:0370:7334",
        "2001:db8:3333:4444:CCCC:DDDD:EEEE:FFFF",
    ]

    for address in test_addresses:
        assert len(_ipv6_matches(address)) > 0, f"{address} should match as IPv6"
