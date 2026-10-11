"""Proof that every number in the calculator tables comes from the official page text.

For each table in data/tables/*.json:
- every ``row_text`` (and each of ``row_text_parts``) occurs verbatim, after whitespace
  normalisation, on the PDF page it names;
- every number stored next to a ``row_text`` (bounds, values, columns) occurs in that row's text,
  unless the field is listed in ``derived_fields`` (for example a value written as "Nil").
"""

import json
import re
from pathlib import Path

import pytest

from app.corpus.loader import DEFAULT_SOURCE_DIR, load_pages, normalize

TABLES_DIR = Path(__file__).resolve().parents[1] / "data" / "tables"
TABLE_FILES = sorted(TABLES_DIR.glob("*.json"))
NON_DATA_KEYS = {"page", "row_no", "no", "derived_fields"}
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")

EXPECTED_TABLES = {
    "12_a_instant_approval",
    "17_farm_house",
    "21_fees",
    "23_validity",
    "42_table4",
    "42_table5",
    "52_electric",
    "53_1_plot_types",
    "56_1_a_front_open_space",
    "56_2_a_rear_open_space",
    "56_3_side_open_space",
    "61_far",
}


@pytest.fixture(scope="module")
def pages():
    return load_pages(DEFAULT_SOURCE_DIR)


def walk(node, page, path=""):
    """Yield (path, dict, page) for every dict that carries a row_text."""
    if isinstance(node, dict):
        page = node.get("page", page)
        if "row_text" in node:
            yield path, node, page
        for key, value in node.items():
            yield from walk(value, page, f"{path}/{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, page, f"{path}[{i}]")


def numbers_in(text: str) -> set[float]:
    return {float(n.replace(",", "")) for n in NUMBER_RE.findall(text)}


def numeric_fields(node: dict, prefix=""):
    """Numeric values stored at this level (recursing into plain sub-dicts without row_text)."""
    for key, value in node.items():
        if key in NON_DATA_KEYS or key in node.get("derived_fields", []):
            continue
        if isinstance(value, bool) or value is None:
            continue
        if isinstance(value, (int, float)):
            yield f"{prefix}{key}", float(value)
        elif isinstance(value, dict) and "row_text" not in value:
            yield from numeric_fields(value, f"{prefix}{key}.")


def test_all_expected_tables_exist():
    assert {p.stem for p in TABLE_FILES} == EXPECTED_TABLES


@pytest.mark.parametrize("path", TABLE_FILES, ids=lambda p: p.stem)
def test_table_header(path):
    t = json.loads(path.read_text(encoding="utf-8"))
    assert t["table_id"] == path.stem
    assert t["rule"] and t["sub_rule"]
    assert 1 <= t["page"] <= 108
    assert "verified_by" in t and "verified_at" in t


@pytest.mark.parametrize("path", TABLE_FILES, ids=lambda p: p.stem)
def test_row_text_appears_on_its_page(path, pages):
    table = json.loads(path.read_text(encoding="utf-8"))
    rows = list(walk(table, table["page"]))
    assert rows, "table has no row_text to verify"
    for where, node, page in rows:
        assert 1 <= page <= 108, (path.stem, where)
        text = pages[page]
        for fragment in [node["row_text"], *node.get("row_text_parts", [])]:
            assert normalize(fragment) in text, (
                f"{path.stem}{where}: not found on page {page}: {fragment!r}"
            )


@pytest.mark.parametrize("path", TABLE_FILES, ids=lambda p: p.stem)
def test_stored_numbers_appear_in_their_row_text(path):
    table = json.loads(path.read_text(encoding="utf-8"))
    for where, node, _page in walk(table, table["page"]):
        pool = numbers_in(" ".join([node["row_text"], *node.get("row_text_parts", [])]))
        for field, value in numeric_fields(node):
            assert value in pool, f"{path.stem}{where}: {field}={value} not in row text"
        # row-level dicts with a nested "columns" mapping
        for field, value in numeric_fields(node.get("columns", {}), "columns."):
            assert value in pool, f"{path.stem}{where}: {field}={value} not in row text"


def test_fee_bands_are_contiguous_and_complete():
    t = json.loads((TABLES_DIR / "21_fees.json").read_text(encoding="utf-8"))
    rows = t["permission_fee_item1_residential"]["rows"]
    assert len(rows) == 13
    for prev, nxt in zip(rows[:-2], rows[1:-1], strict=True):
        assert nxt["from"] == prev["to"] + 1
    assert rows[-1]["gt"] == rows[-2]["to"]
    assert [r["value"] for r in rows] == sorted(r["value"] for r in rows)


def test_bands_have_no_overlap_or_gap():
    for name in ("56_1_a_front_open_space", "56_2_a_rear_open_space"):
        rows = json.loads((TABLES_DIR / f"{name}.json").read_text("utf-8"))["rows"]
        assert rows[0]["gt"] is None and rows[-1]["le"] is None
        for prev, nxt in zip(rows, rows[1:], strict=False):
            assert prev["le"] == nxt["gt"], name
