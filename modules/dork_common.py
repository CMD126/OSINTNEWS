"""
Shared plumbing for the two dork builders:

  - modules/dorker.py        — GUI news tool  (numeric category keys 1..18)
  - modules/dorker_osint.py  — CLI identity tool  (U*/E*/P*/N* keys)

Only the mechanics live here (sanitising, placeholder substitution, phone
normalisation). The category tables stay in their own modules because they are
genuinely different search surfaces.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Country calling codes (ITU-T E.164)
# ---------------------------------------------------------------------------
# Longest-prefix-match wins, so "+441234567890" strips "44" (UK) and not the
# non-existent code "441". A naïve "1–3 greedy digits" regex got this wrong.
_CALLING_CODES: frozenset[str] = frozenset({
    "1", "7",
    "20", "27",
    "30", "31", "32", "33", "34", "36", "39",
    "40", "41", "43", "44", "45", "46", "47", "48", "49",
    "51", "52", "53", "54", "55", "56", "57", "58",
    "60", "61", "62", "63", "64", "65", "66",
    "81", "82", "84", "86",
    "90", "91", "92", "93", "94", "95", "98",
    "211", "212", "213", "216", "218",
    "220", "221", "222", "223", "224", "225", "226", "227", "228", "229",
    "230", "231", "232", "233", "234", "235", "236", "237", "238", "239",
    "240", "241", "242", "243", "244", "245", "246", "248", "249",
    "250", "251", "252", "253", "254", "255", "256", "257", "258",
    "260", "261", "262", "263", "264", "265", "266", "267", "268", "269",
    "290", "291", "297", "298", "299",
    "350", "351", "352", "353", "354", "355", "356", "357", "358", "359",
    "370", "371", "372", "373", "374", "375", "376", "377", "378", "379",
    "380", "381", "382", "383", "385", "386", "387", "389",
    "420", "421", "423",
    "500", "501", "502", "503", "504", "505", "506", "507", "508", "509",
    "590", "591", "592", "593", "594", "595", "596", "597", "598", "599",
    "670", "672", "673", "674", "675", "676", "677", "678", "679",
    "680", "681", "682", "683", "685", "686", "687", "688", "689",
    "690", "691", "692",
    "850", "852", "853", "855", "856",
    "880", "886",
    "960", "961", "962", "963", "964", "965", "966", "967", "968",
    "970", "971", "972", "973", "974", "975", "976", "977",
    "992", "993", "994", "995", "996", "998",
})


# ---------------------------------------------------------------------------
# Target helpers
# ---------------------------------------------------------------------------

def sanitize_target(target: str) -> str:
    """Strip characters that would break a quoted dork phrase."""
    return target.replace('"', "").strip()


def local_phone(target: str) -> str:
    """
    Return the national (local) form of a phone number by removing an
    international prefix ('+' or '00') and the country calling code.

        '+351 933 288 020' -> '933288020'
        '00351933288020'   -> '933288020'
        '+44 1234 567890'  -> '1234567890'   (strips '44', not '441')
        '+1 (555) 123-4567'-> '5551234567'
        '933288020'        -> '933288020'    (no prefix — digits returned as-is)

    Falls back to the digit-only string when no calling code can be identified,
    and to the original text when there are no digits at all.
    """
    stripped = target.strip()
    digits = re.sub(r"\D", "", stripped)
    if not digits:
        return stripped

    has_intl_prefix = stripped.startswith("+")
    if digits.startswith("00"):
        digits = digits[2:]
        has_intl_prefix = True

    if not has_intl_prefix:
        return digits

    for length in (3, 2, 1):
        if len(digits) > length and digits[:length] in _CALLING_CODES:
            return digits[length:]
    return digits


def email_domain(target: str) -> str:
    """Return the domain part of an email address, or '' when there is no '@'."""
    return target.split("@", 1)[1].strip() if "@" in target else ""


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def build_queries(target: str, selected_keys: list, categories: dict) -> list:
    """
    Turn selected category keys into ready-to-run dork dicts.

    A template may contain any of these placeholders:
        {target}        sanitised target, as typed
        {target_local}  phone number with the country calling code removed
        {domain}        domain part of an email address

    Each returned dict carries ``category``, ``query`` and ``target``; a
    ``mode`` key is copied through when the category defines one. Unknown keys
    are skipped silently.
    """
    safe = sanitize_target(target)
    subs = {
        "{target_local}": local_phone(safe),
        "{domain}":       email_domain(safe),
        "{target}":       safe,
    }

    out: list = []
    for key in selected_keys:
        cat = categories.get(key)
        if not cat:
            continue
        query = cat["template"]
        for token, value in subs.items():
            query = query.replace(token, value)
        entry = {"category": cat["name"], "query": query, "target": target}
        if "mode" in cat:
            entry["mode"] = cat["mode"]
        out.append(entry)
    return out
