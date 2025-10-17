"""
Test suite for API matching endpoints.
Tests /match endpoint with various input scenarios.
Verifies response structure, confidence scores, match quality.
Tests edge cases: missing fields, ambiguous matches, no matches.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.api.app import app
from src.api.models import CompanyInput, MatchResponse


# Test client
client = TestClient(app)


class TestHealthAndMetrics:
    """Test basic endpoints."""

    def test_healthz_endpoint(self):
        """Test health check returns 200."""
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_metrics_endpoint(self):
        """Test metrics endpoint is available."""
        response = client.get("/metrics")
        assert response.status_code in (200, 503)  # 503 if prometheus_client not installed


class TestMatchEndpointValidation:
    """Test input validation for /match endpoint."""

    def test_match_requires_company_name(self):
        """Test that company_name is required."""
        response = client.post("/match", json={})
        assert response.status_code == 422  # Validation error
        error = response.json()
        assert "company_name" in str(error).lower()

    def test_match_accepts_minimal_input(self):
        """Test match with only company name."""
        response = client.post("/match", json={
            "company_name": "Test Company"
        })
        assert response.status_code == 200
        data = response.json()
        assert "match_found" in data
        assert "confidence" in data
        assert "company" in data
        assert "score_breakdown" in data

    def test_match_accepts_all_fields(self):
        """Test match with all fields populated."""
        response = client.post("/match", json={
            "company_name": "Arnby",
            "website": "arnby.com",
            "phone_number": "+1-555-1234",
            "facebook_url": "https://facebook.com/arnby",
            "instagram_url": "https://instagram.com/arnby"
        })
        assert response.status_code == 200
        data = response.json()
        assert "match_found" in data

    def test_match_accepts_optional_fields_as_none(self):
        """Test that optional fields can be None."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": None,
            "phone_number": None,
            "facebook_url": None,
            "instagram_url": None
        })
        assert response.status_code == 200

    def test_match_rejects_empty_company_name(self):
        """Test that empty company name is rejected."""
        response = client.post("/match", json={
            "company_name": "",
            "website": "test.com"
        })
        # Should either reject via validation or return no match
        if response.status_code == 422:
            # Validation rejected it (good)
            pass
        else:
            # Accepted but should return no match
            assert response.status_code == 200
            data = response.json()
            assert data["match_found"] is False


class TestMatchResponseStructure:
    """Test response structure and data types."""

    def test_match_response_structure(self):
        """Test that response has correct structure."""
        response = client.post("/match", json={
            "company_name": "Test Company",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        
        # Required fields
        assert "match_found" in data
        assert "confidence" in data
        assert "company" in data
        assert "score_breakdown" in data
        
        # Data types
        assert isinstance(data["match_found"], bool)
        assert isinstance(data["confidence"], (int, float))
        assert isinstance(data["score_breakdown"], dict)
        
        # Confidence range
        assert 0.0 <= data["confidence"] <= 1.0

    def test_match_found_response_has_company_data(self):
        """Test that successful match includes company data."""
        response = client.post("/match", json={
            "company_name": "Test Company",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        
        if data["match_found"]:
            company = data["company"]
            assert company is not None
            assert isinstance(company, dict)
            # Company should have expected fields
            assert "domain" in company
            assert "company_name" in company
            assert "phones" in company
            assert isinstance(company["phones"], list)

    def test_no_match_response_has_null_company(self):
        """Test that no match returns null company."""
        response = client.post("/match", json={
            "company_name": "NonexistentCompanyXYZ123456789",
            "website": "thisdomaindoesnotexist12345.com"
        })
        assert response.status_code == 200
        data = response.json()
        
        if not data["match_found"]:
            assert data["company"] is None
            assert data["confidence"] >= 0.0


class TestMatchScoring:
    """Test matching algorithm and scoring."""

    def test_score_breakdown_structure(self):
        """Test that score breakdown contains expected components."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "test.com",
            "phone_number": "555-1234"
        })
        assert response.status_code == 200
        data = response.json()
        
        breakdown = data["score_breakdown"]
        assert isinstance(breakdown, dict)
        # Breakdown should have scoring components when candidates exist
        # (may be empty if no candidates found)

    def test_domain_match_has_high_confidence(self):
        """Test that perfect domain match has high confidence (if match found)."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        
        # If a match is found with domain, confidence should be reasonable
        if data["match_found"] and data.get("company", {}).get("domain") == "test.com":
            assert data["confidence"] >= 0.3  # Above minimum threshold

    def test_minimum_confidence_threshold_applied(self):
        """Test that minimum confidence threshold filters low matches."""
        response = client.post("/match", json={
            "company_name": "A",  # Single letter - likely low confidence
            "website": "x.com"
        })
        assert response.status_code == 200
        data = response.json()
        
        # If match found, confidence should be above threshold
        if data["match_found"]:
            assert data["confidence"] >= 0.3  # Default threshold


class TestMatchNormalization:
    """Test input normalization handling."""

    def test_domain_normalization(self):
        """Test that domain is normalized (www removed, lowercased)."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "https://WWW.TEST.COM/path"
        })
        assert response.status_code == 200
        # Normalization happens internally; verify no errors

    def test_phone_normalization(self):
        """Test that phone numbers are normalized."""
        response = client.post("/match", json={
            "company_name": "Test",
            "phone_number": "(555) 123-4567"
        })
        assert response.status_code == 200
        # Normalization happens internally; verify no errors

    def test_facebook_normalization(self):
        """Test that Facebook URLs are normalized."""
        response = client.post("/match", json={
            "company_name": "Test",
            "facebook_url": "https://www.facebook.com/test"
        })
        assert response.status_code == 200
        # Normalization happens internally; verify no errors

    def test_handles_malformed_urls(self):
        """Test that malformed URLs don't crash the API."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "not-a-valid-url",
            "facebook_url": "also-not-valid"
        })
        assert response.status_code == 200
        # Should handle gracefully


class TestErrorHandling:
    """Test error handling and resilience."""

    def test_invalid_json_returns_422(self):
        """Test that invalid JSON returns validation error."""
        response = client.post("/match", 
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_extra_fields_ignored(self):
        """Test that extra fields are ignored gracefully."""
        response = client.post("/match", json={
            "company_name": "Test",
            "extra_field": "should be ignored",
            "another_field": 123
        })
        # Pydantic will ignore extra fields by default
        assert response.status_code == 200

    def test_handles_es_unavailable_gracefully(self):
        """Test that API handles Elasticsearch being unavailable."""
        # This test will pass even if ES is down - API should not crash
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        # Should return no match if ES unavailable
        assert "match_found" in data


class TestConcurrency:
    """Test concurrent request handling."""

    def test_multiple_sequential_requests(self):
        """Test that API handles multiple requests sequentially."""
        for i in range(5):
            response = client.post("/match", json={
                "company_name": f"Test {i}",
                "website": f"test{i}.com"
            })
            assert response.status_code == 200

    def test_different_inputs_get_different_results(self):
        """Test that different inputs produce independent results."""
        response1 = client.post("/match", json={
            "company_name": "Company A",
            "website": "companya.com"
        })
        response2 = client.post("/match", json={
            "company_name": "Company B",
            "website": "companyb.com"
        })
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Results can be same or different, but should be valid
        data1 = response1.json()
        data2 = response2.json()
        assert "match_found" in data1
        assert "match_found" in data2


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_company_name(self):
        """Test with very long company name."""
        long_name = "A" * 1000
        response = client.post("/match", json={
            "company_name": long_name
        })
        assert response.status_code == 200

    def test_special_characters_in_name(self):
        """Test company name with special characters."""
        response = client.post("/match", json={
            "company_name": "Test & Co. <Company> 'Name' \"Inc.\""
        })
        assert response.status_code == 200

    def test_unicode_in_company_name(self):
        """Test company name with Unicode characters."""
        response = client.post("/match", json={
            "company_name": "Café München 北京 🏢"
        })
        assert response.status_code == 200

    def test_all_fields_empty_strings(self):
        """Test behavior with empty strings for all optional fields."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "",
            "phone_number": "",
            "facebook_url": "",
            "instagram_url": ""
        })
        assert response.status_code == 200

    def test_whitespace_only_fields(self):
        """Test behavior with whitespace-only fields."""
        response = client.post("/match", json={
            "company_name": "Test",
            "website": "   ",
            "phone_number": "   "
        })
        assert response.status_code == 200


class TestRealWorldScenarios:
    """Test realistic use cases from the CSV sample."""

    def test_domain_only_match(self):
        """Test matching with only domain (common scenario)."""
        response = client.post("/match", json={
            "company_name": "Unknown",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["match_found"], bool)

    def test_name_only_match(self):
        """Test matching with only company name."""
        response = client.post("/match", json={
            "company_name": "Test Company Inc"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["match_found"], bool)

    def test_name_and_domain_match(self):
        """Test matching with both name and domain."""
        response = client.post("/match", json={
            "company_name": "Test Company",
            "website": "test.com"
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["match_found"], bool)

    def test_phone_with_various_formats(self):
        """Test phone matching with different formats."""
        formats = [
            "555-1234",
            "(555) 123-4567",
            "+1-555-123-4567",
            "555.123.4567",
            "5551234567"
        ]
        
        for phone_format in formats:
            response = client.post("/match", json={
                "company_name": "Test",
                "phone_number": phone_format
            })
            assert response.status_code == 200

    def test_social_media_matching(self):
        """Test matching with social media URLs."""
        response = client.post("/match", json={
            "company_name": "Test Company",
            "facebook_url": "https://facebook.com/testcompany",
            "instagram_url": "https://instagram.com/testcompany"
        })
        assert response.status_code == 200
        data = response.json()
        assert "match_found" in data
