from __future__ import annotations

import io
import csv
from pathlib import Path

import pytest

from src.crawlers.python.main import load_domains


@pytest.mark.parametrize(
    "header,values",
    [
        ("domain", ["example.com", "www.Foo.io", "https://bar.net"]),
        ("website", ["EXAMPLE.com", "http://www.foo.io", "bar.net/"]),
        ("website_url", ["https://example.com", "foo.io", "http://bar.net/page"]),
        ("url", ["example.com", "foo.io", "bar.net"]),
        ("site", ["example.com", "foo.io", "bar.net"]),
        ("homepage", ["example.com", "foo.io", "bar.net"]),
    ],
)
def test_header_variants(tmp_path: Path, header: str, values: list[str]) -> None:
    csv_path = tmp_path / "sites.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([header])
        for v in values:
            w.writerow([v])

    domains = load_domains(csv_path)
    assert domains == ["example.com", "foo.io", "bar.net"]


@pytest.mark.parametrize("delimiter", [",", ";", "\t"])
def test_bom_and_delimiters(tmp_path: Path, delimiter: str) -> None:
    csv_path = tmp_path / "sites.csv"
    header = delimiter.join(["domain"])
    rows = delimiter.join(["https://www.Example.com"]) + "\n" + delimiter.join(["foo.io"]) + "\n"
    content = "\ufeff" + header + "\n" + rows  # UTF-8 BOM
    csv_path.write_text(content, encoding="utf-8")

    domains = load_domains(csv_path)
    assert domains == ["example.com", "foo.io"]


def test_dedup_and_blanks(tmp_path: Path) -> None:
    csv_path = tmp_path / "sites.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain"])
        w.writerow([""])
        w.writerow(["example.com"])
        w.writerow(["example.com"])  # duplicate
        w.writerow(["www.foo.io"])   # www.
        w.writerow(["http://bar.net"])  # scheme

    domains = load_domains(csv_path)
    assert domains == ["example.com", "foo.io", "bar.net"]
