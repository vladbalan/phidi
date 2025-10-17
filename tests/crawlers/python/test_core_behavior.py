from __future__ import annotations

import io
import sys
from dataclasses import asdict

import pytest

from src.crawlers.python.main import _domain_from_value, maybe_log_browser_fallback


@pytest.mark.parametrize(
    "inp,out",
    [
        ("HTTPS://WWW.Example.com/Path?Q=1#frag", "example.com"),
        ("www.foo.io.", "foo.io"),
        ("bar.net/", "bar.net"),
        ("http://sub.domain.co.uk/page", "sub.domain.co.uk"),
        ("", None),
        ("   ", None),
    ],
)
def test_canonical_domain(inp: str, out: str | None) -> None:
    assert _domain_from_value(inp) == out


# NOTE: Simulation tests removed after implementing real HTTP fetching
# The following tests were for simulate_fetch_and_extract which has been
# replaced with fetch_and_extract that does real HTTP requests + extraction.
# 
# def test_simulation_flags_redirect_and_note() -> None:
#     Test redirect chain and notes (was for placeholder simulation)
#     Now handled by real HTTP client redirect following
#
# These features are tested via end-to-end crawler runs instead.


def test_maybe_log_browser_fallback_caps() -> None:
    # Capture stdout to check for message
    buf = io.StringIO()
    orig = sys.stdout
    try:
        sys.stdout = buf
        maybe_log_browser_fallback("my-spa-app.com")
    finally:
        sys.stdout = orig
    assert "browser fallback" in buf.getvalue()
