from __future__ import annotations

import csv
from pathlib import Path

from src.crawlers.python.main import load_domains


def test_website_header(tmp_path: Path) -> None:
    p = tmp_path / "sites.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["website"])
        w.writerow(["http://A.com"])
        w.writerow(["WWW.B.org"])
    assert load_domains(p) == ["a.com", "b.org"]


def test_headerless_single_column(tmp_path: Path) -> None:
    p = tmp_path / "sites.csv"
    p.write_text("example.com\nfoo.io\nbar.net\n", encoding="utf-8")
    assert load_domains(p) == ["example.com", "foo.io", "bar.net"]


def test_headerless_delimited_first_column(tmp_path: Path) -> None:
    p = tmp_path / "sites.csv"
    p.write_text("example.com,extra\nwww.x.y/zzz,ignore\n", encoding="utf-8")
    assert load_domains(p) == ["example.com", "x.y"]


def test_dedupe_and_blanks_additional(tmp_path: Path) -> None:
    p = tmp_path / "sites.csv"
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["domain"])
        w.writerow([""])
        w.writerow(["example.com"])
        w.writerow(["example.com"])  # duplicate
        w.writerow(["www.foo.io"])   # www.
        w.writerow(["http://bar.net"])  # scheme
    assert load_domains(p) == ["example.com", "foo.io", "bar.net"]
