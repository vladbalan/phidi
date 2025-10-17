"""
Tests for scripts/api_batch_eval.py markdown report generation.
"""
from __future__ import annotations

import sys
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest


def test_write_markdown_report():
    """Test that write_markdown_report generates valid markdown with expected sections."""
    from scripts.api_batch_eval import write_markdown_report

    # Sample data matching actual script output format
    summary = {
        "total_queries": 10,
        "matches_found": 7,
        "match_rate": 0.7,
        "high_confidence_matches": 2,
        "medium_confidence_matches": 3,
        "low_confidence_matches": 2,
        "no_matches": 3,
        "avg_confidence": 0.6234,
        "avg_response_time_ms": 45.2,
    }

    results_rows = [
        {
            "input_company": "Acme Corp",
            "input_website": "acme.com",
            "matched": "true",
            "confidence": "0.9500",
            "matched_company": "Acme Corporation",
            "matched_domain": "acme.com",
        },
        {
            "input_company": "Unknown Inc",
            "input_website": "unknown.xyz",
            "matched": "false",
            "confidence": "0.1000",
            "matched_company": "",
            "matched_domain": "",
        },
    ]

    resp_times_ms = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "test_report.md"
        
        write_markdown_report(
            out_path=str(out_path),
            summary=summary,
            results_rows=results_rows,
            resp_times_ms=resp_times_ms,
            input_csv="test_input.csv",
            api_url="http://test:8000",
        )

        # Verify file was created
        assert out_path.exists(), "Markdown report file should be created"

        # Read and verify content
        content = out_path.read_text(encoding="utf-8")

        # Check for required sections
        assert "# API Match Evaluation Report" in content
        assert "## Summary" in content
        assert "## Match Quality Breakdown" in content
        assert "## Performance" in content
        
        # Check for data presence
        assert "Total Queries** | 10" in content
        assert "Matches Found** | 7" in content
        assert "70.0%" in content  # match rate
        
        # Check emoji indicators
        assert "🟢 High (≥0.9)" in content
        assert "🟡 Medium (≥0.7)" in content
        assert "🔴 Low (<0.7)" in content
        assert "⚪ No Match" in content
        
        # Check performance stats
        assert "Fastest Response:" in content
        assert "Slowest Response:" in content
        assert "Median Response:" in content
        
        # Check that high confidence example appears
        assert "Acme Corp" in content
        assert "0.9500" in content
        
        # Check that no-match example appears
        assert "Unknown Inc" in content
        assert "No match found" in content


def test_write_markdown_report_empty_results():
    """Test that write_markdown_report handles edge case with no results gracefully."""
    from scripts.api_batch_eval import write_markdown_report

    summary = {
        "total_queries": 0,
        "matches_found": 0,
        "match_rate": 0.0,
        "high_confidence_matches": 0,
        "medium_confidence_matches": 0,
        "low_confidence_matches": 0,
        "no_matches": 0,
        "avg_confidence": 0.0,
        "avg_response_time_ms": 0.0,
    }

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "empty_report.md"
        
        write_markdown_report(
            out_path=str(out_path),
            summary=summary,
            results_rows=[],
            resp_times_ms=[],
            input_csv="empty.csv",
            api_url="http://test:8000",
        )

        assert out_path.exists()
        content = out_path.read_text(encoding="utf-8")
        
        # Should still have structure
        assert "# API Match Evaluation Report" in content
        assert "## Summary" in content
        assert "Total Queries** | 0" in content


def test_categorize_confidence():
    """Test confidence categorization thresholds."""
    from scripts.api_batch_eval import categorize_confidence

    assert categorize_confidence(0.95) == "high"
    assert categorize_confidence(0.9) == "high"
    assert categorize_confidence(0.89) == "medium"
    assert categorize_confidence(0.7) == "medium"
    assert categorize_confidence(0.69) == "low"
    assert categorize_confidence(0.1) == "low"


def test_run_prints_markdown_report_to_terminal():
    """Test that run() prints a formatted report to stdout when out_report is provided."""
    from scripts.api_batch_eval import run
    
    with tempfile.TemporaryDirectory() as tmpdir:
        input_csv = Path(tmpdir) / "test_input.csv"
        out_csv = Path(tmpdir) / "results.csv"
        out_summary = Path(tmpdir) / "summary.json"
        out_report = Path(tmpdir) / "report.md"
        
        # Create minimal input CSV
        input_csv.write_text(
            "company_name,website,phone_number,facebook_url\n"
            "Test Corp,test.com,,,\n",
            encoding="utf-8"
        )
        
        # Capture stdout
        captured_output = StringIO()
        
        with patch("sys.stdout", captured_output), \
             patch("scripts.api_batch_eval.health_check"), \
             patch("scripts.api_batch_eval._http_post_json") as mock_post:
            
            # Mock API response
            mock_post.return_value = (
                200,
                b'{"match_found": true, "confidence": 0.85, "company": {"company_name": "Test Corp", "domain": "test.com"}}'
            )
            
            run(
                input_csv=str(input_csv),
                out_csv=str(out_csv),
                out_summary=str(out_summary),
                api_url="http://test:8000",
                out_report=str(out_report),
            )
        
        output = captured_output.getvalue()
        
        # Verify formatted report was printed (not raw markdown)
        assert "API Match Evaluation Report" in output
        assert "Summary:" in output
        assert "Match Quality:" in output
        assert "Performance:" in output
        assert "Total Queries:" in output
        assert "=" * 80 in output  # Separator lines
        # Should NOT contain markdown syntax
        assert "##" not in output  # No markdown headers
        assert "| Metric |" not in output  # No markdown tables

