"""
Reporter — HTML escaping / link safety, Markdown→HTML, and the CSV / JSON /
Markdown / HTML file exports (written to tmp_path, no network).
"""

import csv
import json
import os
import re

import pytest

from modules import reporter
from modules.rag.models import AIAnalysis


def _item(**kw):
    base = {
        "target":   "alice",
        "category": "News",
        "title":    "A title",
        "href":     "https://example.com/a",
        "body":     "body text",
        "query":    '"alice" site:example.com',
    }
    base.update(kw)
    return base


def _analysis(**kw):
    base = dict(
        target="alice", summary="## Summary\nAll good [Source 1]\n\nRisk Level: LOW",
        risk_level="LOW", cited_sources=("https://example.com/a",),
        timestamp="2026-01-01T00:00:00", model="claude-test", source_count=1,
    )
    base.update(kw)
    return AIAnalysis(**base)


def _hrefs(html):
    return re.findall(r'href="([^"]*)"', html)


# ---------------------------------------------------------------------------
# _md_to_html
# ---------------------------------------------------------------------------

def test_md_escapes_raw_html_before_formatting():
    out = reporter._md_to_html("<script>alert(1)</script> **bold**")
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
    assert "<strong>bold</strong>" in out


def test_md_headings_bullets_and_citations():
    out = reporter._md_to_html("## Head\n### Sub\n- one\n- two\n\nSee [Source 3]")
    assert "<h2>Head</h2>" in out
    assert "<h3>Sub</h3>" in out
    assert re.search(r"<ul><li>one</li>\n?<li>two</li>\n?</ul>", out)
    assert '<span class="cite">[Source 3]</span>' in out


def test_md_wraps_plain_blocks_in_paragraphs():
    out = reporter._md_to_html("first\n\nsecond")
    assert "<p>first</p>" in out and "<p>second</p>" in out


def test_md_marks_insufficient_data_warning():
    out = reporter._md_to_html("⚠ Insufficient data.")
    assert '<span class="warn">⚠ Insufficient data.</span>' in out


# ---------------------------------------------------------------------------
# _build_html — escaping of untrusted search-result fields
# ---------------------------------------------------------------------------

def test_html_escapes_every_result_field():
    evil = '<img src=x onerror=alert(1)>'
    html = reporter._build_html(
        [_item(title=evil, body=evil, query=evil, target=evil, category=evil,
               confidence="LIKELY", evidence={"context": evil})],
        target=evil, timestamp="ts",
    )
    assert "<img" not in html
    assert html.count("&lt;img src=x onerror=alert(1)&gt;") >= 6


def test_html_escapes_quotes_in_href():
    html = reporter._build_html(
        [_item(href='https://e.com/"onmouseover="alert(1)')], "t", "ts")
    assert 'onmouseover="alert' not in html
    assert "&quot;onmouseover=&quot;" in html


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    "  javascript:alert(1)",
    "java\tscript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "vbscript:msgbox(1)",
])
def test_html_neutralises_dangerous_link_schemes(url):
    html = reporter._build_html([_item(href=url)], "t", "ts")
    for h in _hrefs(html):
        assert not re.match(r"\s*(java\s*script|data|vbscript):", h, re.I), h
    # the raw URL is still shown as text so the analyst can see it
    assert "card-url" in html


@pytest.mark.parametrize("url", [
    "https://example.com/a?b=1&c=2",
    "http://example.com",
])
def test_html_keeps_normal_links_clickable(url):
    html = reporter._build_html([_item(href=url)], "t", "ts")
    assert html.count(f'href="{url.replace("&", "&amp;")}"') == 1


def test_html_neutralises_dangerous_cited_source_links():
    html = reporter._build_html(
        [_item()], "t", "ts",
        analysis=_analysis(cited_sources=("javascript:alert(1)",)),
    )
    assert 'href="javascript:' not in html


def test_html_ai_block_success_and_error():
    ok = reporter._build_html([_item()], "t", "ts", analysis=_analysis())
    assert "AI Intelligence Report" in ok
    assert "claude-test" in ok
    assert "LOW" in ok

    err = reporter._build_html(
        [_item()], "t", "ts",
        analysis=_analysis(summary="", error="<b>boom</b>"),
    )
    assert "AI Analysis — Error" in err
    assert "&lt;b&gt;boom&lt;/b&gt;" in err


def test_html_correlation_table_is_escaped():
    html = reporter._build_html(
        [_item()], "t", "ts",
        correlations=[{"type": "email", "value": "<x>@e.com",
                       "found_on": ["github", "<gitlab>"], "confidence": "HIGH"}],
    )
    assert "Cross-correlation" in html
    assert "&lt;x&gt;@e.com" in html
    assert "&lt;gitlab&gt;" in html
    assert "corr-high" in html


def test_html_groups_results_by_category():
    html = reporter._build_html(
        [_item(category="A"), _item(category="B"), _item(category="A")], "t", "ts")
    assert re.search(r'A\s*<span class="badge">2</span>', html)
    assert re.search(r'B\s*<span class="badge">1</span>', html)


# ---------------------------------------------------------------------------
# file exports
# ---------------------------------------------------------------------------

def test_save_report_sanitises_filename(tmp_path):
    path = reporter.save_report([_item()], "../../evil name", output_dir=str(tmp_path))
    assert os.path.dirname(path) == str(tmp_path)
    assert os.path.basename(path).startswith("osintnews_______evil_name_")
    assert path.endswith(".html")
    assert os.path.isfile(path)


def test_save_report_to_creates_parent_dirs(tmp_path):
    dest = tmp_path / "nested" / "dir" / "r.html"
    assert reporter.save_report_to([_item()], "t", str(dest)) == str(dest)
    assert dest.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_save_csv_flattens_evidence_and_ignores_extra_keys(tmp_path):
    p = tmp_path / "r.csv"
    reporter.save_csv(
        [_item(confidence="VERIFIED", evidence={"context": "ctx", "reason": "why"},
               unexpected="dropped")],
        str(p),
    )
    rows = list(csv.DictReader(p.open(encoding="utf-8", newline="")))
    assert len(rows) == 1
    assert rows[0]["evidence_context"] == "ctx"
    assert rows[0]["evidence_reason"] == "why"
    assert rows[0]["confidence"] == "VERIFIED"
    assert "unexpected" not in rows[0]


def test_save_json_round_trips_unicode(tmp_path):
    p = tmp_path / "r.json"
    data = [_item(title="Ação — 東京")]
    reporter.save_json(data, str(p))
    assert "Ação — 東京" in p.read_text(encoding="utf-8")
    assert json.loads(p.read_text(encoding="utf-8")) == data


def test_save_markdown_with_and_without_analysis(tmp_path):
    p = tmp_path / "r.md"
    reporter.save_markdown([_item(body="x" * 250)], str(p), analysis=_analysis())
    md = p.read_text(encoding="utf-8")
    assert "# OSINTNEWS Plus — `alice`" in md
    assert "**Risk Level:** LOW" in md
    assert "- https://example.com/a" in md
    assert "#### [A title](https://example.com/a)" in md
    assert "…" in md

    p2 = tmp_path / "empty.md"
    reporter.save_markdown([], str(p2))
    md2 = p2.read_text(encoding="utf-8")
    assert "`Unknown`" in md2
    assert "AI Intelligence Report" not in md2


def test_save_excel_writes_header_and_rows(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    p = tmp_path / "r.xlsx"
    reporter.save_excel([_item(), _item(title="two")], str(p))
    ws = openpyxl.load_workbook(p).active
    assert ws.cell(1, 4).value == "Title"
    assert ws.max_row == 3
    assert ws.cell(3, 4).value == "two"


# ---------------------------------------------------------------------------
# terminal output
# ---------------------------------------------------------------------------

def test_print_results_empty(capsys):
    reporter.print_results([], "t")
    assert "No results found" in capsys.readouterr().out


def test_print_results_shows_verdicts_and_evidence(capsys):
    reporter.print_results([
        _item(confidence="VERIFIED", evidence={"context": "found handle"}),
        _item(confidence="FALSE_POSITIVE", evidence={"reason": "target absent"},
              body="y" * 200),
    ], "alice")
    out = capsys.readouterr().out
    assert "Total: " in out
    assert "VERIFIED" in out and "found handle" in out
    assert "FALSE_POSITIVE" in out and "target absent" in out
    assert "y" * 150 + "..." in out
