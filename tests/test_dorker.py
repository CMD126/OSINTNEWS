"""
Dork builders + shared query mechanics (modules/dork_common.py).
"""

import pytest

from modules.dork_common import (
    build_queries,
    email_domain,
    local_phone,
    sanitize_target,
)
from modules.dorker import DORK_CATEGORIES, build_dorks
from modules.dorker_osint import (
    OSINT_CATEGORIES,
    build_osint_dorks,
    categories_for_mode,
)


# ---------------------------------------------------------------------------
# sanitize_target
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ('  John Doe  ', 'John Doe'),
    ('"quoted"', 'quoted'),
    ('a"b"c', 'abc'),
    ('', ''),
    ('   ', ''),
])
def test_sanitize_target(raw, expected):
    assert sanitize_target(raw) == expected


# ---------------------------------------------------------------------------
# local_phone — the country-calling-code stripper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("+351933288020",        "933288020"),   # Portugal
    ("+351 933 288 020",     "933288020"),   # with spaces
    ("00351933288020",       "933288020"),   # 00 international prefix
    ("+44 1234 567890",      "1234567890"),  # UK — must strip 44, NOT 441
    ("+1 (555) 123-4567",    "5551234567"),  # NANP
    ("+49-30-12345678",      "3012345678"),  # Germany
    ("+55 11 91234-5678",    "11912345678"), # Brazil
    ("933288020",            "933288020"),   # already local, no prefix
    ("933 288 020",          "933288020"),   # local with separators
    ("not a phone",          "not a phone"), # no digits -> original text
])
def test_local_phone(raw, expected):
    assert local_phone(raw) == expected


def test_local_phone_unknown_code_falls_back_to_digits():
    # 999 is not an assigned calling code -> return digits unchanged
    assert local_phone("+9991234567") == "9991234567"


# ---------------------------------------------------------------------------
# email_domain
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("john@example.com", "example.com"),
    ("a.b+tag@sub.domain.co.uk", "sub.domain.co.uk"),
    ("nodomain", ""),
    ("weird@", ""),
])
def test_email_domain(raw, expected):
    assert email_domain(raw) == expected


# ---------------------------------------------------------------------------
# build_queries / build_osint_dorks
# ---------------------------------------------------------------------------

def test_build_osint_dorks_username_substitutes_target():
    dorks = build_osint_dorks("torvalds", ["U5"])
    assert len(dorks) == 1
    d = dorks[0]
    assert d["mode"] == "username"
    assert d["category"] == OSINT_CATEGORIES["U5"]["name"]
    assert '"torvalds"' in d["query"]
    assert "{target}" not in d["query"]


def test_build_osint_dorks_phone_expands_target_local():
    dorks = build_osint_dorks("+351933288020", ["P1"])
    q = dorks[0]["query"]
    assert '"+351933288020"' in q          # full form
    assert '"933288020"' in q              # local form
    assert "{target_local}" not in q


def test_build_osint_dorks_email_domain_placeholder():
    dorks = build_osint_dorks("jane@acme.io", ["E6"])
    q = dorks[0]["query"]
    assert "@acme.io" in q
    assert "{domain}" not in q


def test_build_osint_dorks_skips_unknown_keys():
    assert build_osint_dorks("x", ["NOPE", "U1"]) == build_osint_dorks("x", ["U1"])
    assert build_osint_dorks("x", ["NOPE"]) == []


def test_build_osint_dorks_quotes_are_stripped():
    q = build_osint_dorks('a"b', ["U1"])[0]["query"]
    assert '"ab"' in q


def test_categories_for_mode_partitions_cleanly():
    for mode in ("username", "email", "phone", "person"):
        cats = categories_for_mode(mode)
        assert cats
        assert all(v["mode"] == mode for v in cats.values())
    # every category belongs to exactly one of the four modes
    total = sum(len(categories_for_mode(m))
                for m in ("username", "email", "phone", "person"))
    assert total == len(OSINT_CATEGORIES)


# ---------------------------------------------------------------------------
# GUI news builder (numeric keys, no mode field)
# ---------------------------------------------------------------------------

def test_build_dorks_news_has_no_mode_field():
    dorks = build_dorks("Iran War", ["1", "2"])
    assert len(dorks) == 2
    assert all("mode" not in d for d in dorks)
    assert all(d["target"] == "Iran War" for d in dorks)
    assert '"Iran War"' in dorks[0]["query"]


def test_build_dorks_skips_unknown_keys():
    assert build_dorks("x", ["999"]) == []


def test_build_queries_is_the_shared_engine():
    # build_dorks is now a thin wrapper over build_queries
    assert build_dorks("abc", ["1"]) == build_queries("abc", ["1"], DORK_CATEGORIES)
