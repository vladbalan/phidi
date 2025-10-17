"""
Unit tests for API models and validation.
Tests CompanyInput validation, field validators, model validators.
Verifies minimum field requirements and error messages.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.api.models import CompanyInput, CompanyResult, MatchResponse


class TestCompanyInputValidation:
    """Test CompanyInput validation logic."""

    def test_valid_minimal_input(self):
        """Test valid input with only company name."""
        input_data = CompanyInput(company_name="Test Company")
        assert input_data.company_name == "Test Company"
        assert input_data.website is None
        assert input_data.phone_number is None

    def test_valid_full_input(self):
        """Test valid input with all fields."""
        input_data = CompanyInput(
            company_name="Test Company",
            website="test.com",
            phone_number="555-1234",
            facebook_url="https://facebook.com/test",
            instagram_url="https://instagram.com/test"
        )
        assert input_data.company_name == "Test Company"
        assert input_data.website == "test.com"
        assert input_data.phone_number == "555-1234"
        assert input_data.facebook_url == "https://facebook.com/test"
        assert input_data.instagram_url == "https://instagram.com/test"

    def test_company_name_required(self):
        """Test that company_name is required."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyInput()
        
        error = exc_info.value
        assert "company_name" in str(error).lower()
        assert "required" in str(error).lower() or "missing" in str(error).lower()

    def test_company_name_not_empty(self):
        """Test that company_name cannot be empty string."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyInput(company_name="")
        
        error = exc_info.value
        assert "company_name" in str(error).lower()

    def test_company_name_not_whitespace_only(self):
        """Test that company_name cannot be whitespace-only."""
        with pytest.raises(ValidationError) as exc_info:
            CompanyInput(company_name="   ")
        
        error = exc_info.value
        assert "company_name" in str(error).lower()
        assert "whitespace" in str(error).lower() or "empty" in str(error).lower()

    def test_optional_fields_can_be_none(self):
        """Test that optional fields can be None."""
        input_data = CompanyInput(
            company_name="Test",
            website=None,
            phone_number=None,
            facebook_url=None,
            instagram_url=None
        )
        assert input_data.website is None
        assert input_data.phone_number is None
        assert input_data.facebook_url is None
        assert input_data.instagram_url is None

    def test_optional_fields_can_be_omitted(self):
        """Test that optional fields can be omitted from input."""
        input_data = CompanyInput(company_name="Test")
        assert input_data.website is None
        assert input_data.phone_number is None

    def test_accepts_empty_string_for_optional_fields(self):
        """Test that empty strings are accepted for optional fields."""
        input_data = CompanyInput(
            company_name="Test",
            website="",
            phone_number="",
            facebook_url="",
            instagram_url=""
        )
        assert input_data.website == ""
        assert input_data.phone_number == ""

    def test_minimum_fields_with_name_only(self):
        """Test that company name alone satisfies minimum requirement."""
        input_data = CompanyInput(company_name="Test Company")
        assert input_data.company_name == "Test Company"

    def test_minimum_fields_with_name_and_website(self):
        """Test valid input with name and website."""
        input_data = CompanyInput(
            company_name="Test",
            website="test.com"
        )
        assert input_data.company_name == "Test"
        assert input_data.website == "test.com"

    def test_minimum_fields_with_name_and_phone(self):
        """Test valid input with name and phone."""
        input_data = CompanyInput(
            company_name="Test",
            phone_number="555-1234"
        )
        assert input_data.company_name == "Test"
        assert input_data.phone_number == "555-1234"

    def test_minimum_fields_with_name_and_social(self):
        """Test valid input with name and social media."""
        input_data = CompanyInput(
            company_name="Test",
            facebook_url="https://facebook.com/test"
        )
        assert input_data.company_name == "Test"
        assert input_data.facebook_url == "https://facebook.com/test"


class TestCompanyInputEdgeCases:
    """Test edge cases for CompanyInput."""

    def test_very_long_company_name(self):
        """Test with very long company name."""
        long_name = "A" * 1000
        input_data = CompanyInput(company_name=long_name)
        assert input_data.company_name == long_name

    def test_special_characters_in_name(self):
        """Test company name with special characters."""
        special_name = "Test & Co. <Company> 'Name' \"Inc.\""
        input_data = CompanyInput(company_name=special_name)
        assert input_data.company_name == special_name

    def test_unicode_in_company_name(self):
        """Test company name with Unicode characters."""
        unicode_name = "Café München 北京 🏢"
        input_data = CompanyInput(company_name=unicode_name)
        assert input_data.company_name == unicode_name

    def test_newlines_in_company_name(self):
        """Test company name with newlines."""
        name_with_newlines = "Test\nCompany\nName"
        input_data = CompanyInput(company_name=name_with_newlines)
        assert input_data.company_name == name_with_newlines

    def test_numeric_company_name(self):
        """Test company name with only numbers."""
        input_data = CompanyInput(company_name="12345")
        assert input_data.company_name == "12345"

    def test_website_with_protocol(self):
        """Test website with protocol."""
        input_data = CompanyInput(
            company_name="Test",
            website="https://www.test.com"
        )
        assert input_data.website == "https://www.test.com"

    def test_website_without_protocol(self):
        """Test website without protocol."""
        input_data = CompanyInput(
            company_name="Test",
            website="test.com"
        )
        assert input_data.website == "test.com"

    def test_malformed_website(self):
        """Test that malformed website is accepted (normalization happens later)."""
        input_data = CompanyInput(
            company_name="Test",
            website="not-a-valid-url"
        )
        assert input_data.website == "not-a-valid-url"

    def test_phone_with_various_formats(self):
        """Test phone numbers in various formats."""
        formats = [
            "555-1234",
            "(555) 123-4567",
            "+1-555-123-4567",
            "555.123.4567",
            "5551234567"
        ]
        
        for phone_format in formats:
            input_data = CompanyInput(
                company_name="Test",
                phone_number=phone_format
            )
            assert input_data.phone_number == phone_format

    def test_facebook_url_formats(self):
        """Test various Facebook URL formats."""
        urls = [
            "https://facebook.com/test",
            "https://www.facebook.com/test",
            "facebook.com/test",
            "fb.com/test"
        ]
        
        for url in urls:
            input_data = CompanyInput(
                company_name="Test",
                facebook_url=url
            )
            assert input_data.facebook_url == url

    def test_instagram_url_formats(self):
        """Test various Instagram URL formats."""
        urls = [
            "https://instagram.com/test",
            "https://www.instagram.com/test",
            "instagram.com/test"
        ]
        
        for url in urls:
            input_data = CompanyInput(
                company_name="Test",
                instagram_url=url
            )
            assert input_data.instagram_url == url


class TestCompanyResult:
    """Test CompanyResult model."""

    def test_company_result_minimal(self):
        """Test CompanyResult with minimal data."""
        result = CompanyResult()
        assert result.domain is None
        assert result.company_name is None
        assert result.phones == []

    def test_company_result_full(self):
        """Test CompanyResult with all fields."""
        result = CompanyResult(
            domain="test.com",
            company_name="Test Company",
            phones=["+15551234567"],
            facebook="facebook.com/test",
            linkedin="linkedin.com/company/test",
            twitter="twitter.com/test",
            instagram="instagram.com/test"
        )
        assert result.domain == "test.com"
        assert result.company_name == "Test Company"
        assert result.phones == ["+15551234567"]
        assert result.facebook == "facebook.com/test"


class TestMatchResponse:
    """Test MatchResponse model."""

    def test_match_response_no_match(self):
        """Test MatchResponse for no match scenario."""
        response = MatchResponse(
            match_found=False,
            confidence=0.0,
            company=None,
            score_breakdown={}
        )
        assert response.match_found is False
        assert response.confidence == 0.0
        assert response.company is None

    def test_match_response_with_match(self):
        """Test MatchResponse with successful match."""
        company = CompanyResult(
            domain="test.com",
            company_name="Test Company",
            phones=["+15551234567"]
        )
        response = MatchResponse(
            match_found=True,
            confidence=0.85,
            company=company,
            score_breakdown={"domain": 1.0, "name": 0.9}
        )
        assert response.match_found is True
        assert response.confidence == 0.85
        assert response.company is not None
        assert response.company.domain == "test.com"

    def test_match_response_confidence_bounds(self):
        """Test that confidence is within valid range."""
        # Valid confidence values
        for conf in [0.0, 0.5, 1.0]:
            response = MatchResponse(
                match_found=True,
                confidence=conf,
                company=None,
                score_breakdown={}
            )
            assert 0.0 <= response.confidence <= 1.0

    def test_match_response_invalid_confidence_below_zero(self):
        """Test that confidence below 0 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MatchResponse(
                match_found=False,
                confidence=-0.1,
                company=None,
                score_breakdown={}
            )
        error = exc_info.value
        assert "confidence" in str(error).lower()

    def test_match_response_invalid_confidence_above_one(self):
        """Test that confidence above 1 is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            MatchResponse(
                match_found=False,
                confidence=1.1,
                company=None,
                score_breakdown={}
            )
        error = exc_info.value
        assert "confidence" in str(error).lower()
