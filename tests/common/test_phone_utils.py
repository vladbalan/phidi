"""Test suite for phone number utilities.

Tests normalize_phone from src/common/phone_utils.py
Verify international format conversion, validation, deduplication.
Test edge cases: extensions, toll-free numbers, invalid formats.
"""

from src.common.phone_utils import normalize_phone


class TestNormalizePhoneBasic:
    """Test basic phone number normalization."""

    def test_us_10_digit(self):
        """Test normalization of 10-digit US numbers."""
        assert normalize_phone("2025551234") == "+12025551234"
        assert normalize_phone("4155551234") == "+14155551234"
        assert normalize_phone("8005551234") == "+18005551234"

    def test_us_11_digit_with_country_code(self):
        """Test normalization of 11-digit US numbers with country code."""
        assert normalize_phone("12025551234") == "+12025551234"
        assert normalize_phone("14155551234") == "+14155551234"
        assert normalize_phone("18005551234") == "+18005551234"

    def test_us_number_with_plus_prefix(self):
        """Test US numbers that already have + prefix."""
        assert normalize_phone("+12025551234") == "+12025551234"
        assert normalize_phone("+14155551234") == "+14155551234"

    def test_formatted_us_number(self):
        """Test US numbers with common formatting."""
        assert normalize_phone("(202) 555-1234") == "+12025551234"
        assert normalize_phone("202-555-1234") == "+12025551234"
        assert normalize_phone("202.555.1234") == "+12025551234"
        assert normalize_phone("202 555 1234") == "+12025551234"


class TestNormalizePhoneFormatting:
    """Test phone number normalization with various formatting."""

    def test_parentheses_and_dashes(self):
        """Test numbers with parentheses and dashes."""
        assert normalize_phone("(415) 555-1234") == "+14155551234"
        assert normalize_phone("1-(415)-555-1234") == "+14155551234"
        assert normalize_phone("1(415)555-1234") == "+14155551234"

    def test_dots_and_spaces(self):
        """Test numbers with dots and spaces."""
        assert normalize_phone("202.555.1234") == "+12025551234"
        assert normalize_phone("1 202 555 1234") == "+12025551234"
        assert normalize_phone("1.202.555.1234") == "+12025551234"

    def test_mixed_separators(self):
        """Test numbers with mixed separator characters."""
        assert normalize_phone("+1 (202) 555-1234") == "+12025551234"
        assert normalize_phone("1-(202).555.1234") == "+12025551234"
        assert normalize_phone("+1.202.555-1234") == "+12025551234"

    def test_no_separators(self):
        """Test numbers without any separators."""
        assert normalize_phone("2025551234") == "+12025551234"
        assert normalize_phone("12025551234") == "+12025551234"
        assert normalize_phone("+12025551234") == "+12025551234"


class TestNormalizePhoneInternational:
    """Test international phone number normalization."""

    def test_uk_numbers(self):
        """Test UK phone numbers."""
        assert normalize_phone("+442071234567") == "+442071234567"
        assert normalize_phone("+447911123456") == "+447911123456"

    def test_australian_numbers(self):
        """Test Australian phone numbers."""
        assert normalize_phone("+61291234567") == "+61291234567"
        assert normalize_phone("+61412345678") == "+61412345678"

    def test_german_numbers(self):
        """Test German phone numbers."""
        assert normalize_phone("+493012345678") == "+493012345678"
        assert normalize_phone("+4915112345678") == "+4915112345678"

    def test_japanese_numbers(self):
        """Test Japanese phone numbers."""
        assert normalize_phone("+81312345678") == "+81312345678"
        assert normalize_phone("+819012345678") == "+819012345678"

    def test_international_with_formatting(self):
        """Test international numbers with formatting."""
        assert normalize_phone("+44 20 7123 4567") == "+442071234567"
        assert normalize_phone("+61 (2) 9123-4567") == "+61291234567"
        assert normalize_phone("+49 30 1234-5678") == "+493012345678"


class TestNormalizePhoneEdgeCases:
    """Test edge cases and invalid inputs."""

    def test_none_input(self):
        """Test None input returns None."""
        assert normalize_phone(None) is None

    def test_empty_string(self):
        """Test empty string returns None."""
        assert normalize_phone("") is None
        assert normalize_phone("   ") is None
        assert normalize_phone("\t\n") is None

    def test_non_digit_only(self):
        """Test strings with no digits return None."""
        assert normalize_phone("abc") is None
        assert normalize_phone("---") is None
        assert normalize_phone("()()()") is None

    def test_too_short_numbers(self):
        """Test numbers that are too short (< 8 digits)."""
        assert normalize_phone("1234567") is None
        assert normalize_phone("123-456") is None
        assert normalize_phone("+1234567") is None
        assert normalize_phone("12345") is None

    def test_us_numbers_with_extensions(self):
        """Test US numbers with extensions (digits extracted)."""
        assert normalize_phone("202-555-1234 ext 123") == "+12025551234"
        assert normalize_phone("202-555-1234x456") == "+12025551234"
        assert normalize_phone("202-555-1234 extension 789") == "+12025551234"

    def test_international_numbers_with_extensions(self):
        """Test international numbers with explicit extension markers."""
        assert normalize_phone("+1 202 555 1234 ext 555") == "+12025551234"
        assert normalize_phone("+44 20 7123 4567 x99") == "+442071234567"

    def test_toll_free_numbers(self):
        """Test toll-free US numbers."""
        assert normalize_phone("8005551234") == "+18005551234"
        assert normalize_phone("8885551234") == "+18885551234"
        assert normalize_phone("8775551234") == "+18775551234"
        assert normalize_phone("1-800-555-1234") == "+18005551234"

    def test_special_characters(self):
        """Test numbers with special characters."""
        assert normalize_phone("+1 (202) 555-1234#") == "+12025551234"
        assert normalize_phone("202*555*1234") == "+12025551234"
        assert normalize_phone("202~555~1234") == "+12025551234"


class TestNormalizePhoneDefaultCountry:
    """Test default country parameter."""

    def test_us_default_country(self):
        """Test with US as default country (default behavior)."""
        assert normalize_phone("2025551234", default_country="US") == "+12025551234"
        assert normalize_phone("4155551234", default_country="us") == "+14155551234"

    def test_non_us_default_country(self):
        """Test with non-US default country."""
        # With non-US default, 10-digit number won't get +1 prefix
        result = normalize_phone("2025551234", default_country="UK")
        assert result == "+2025551234"  # Treated as raw digits

    def test_explicit_country_code_overrides_default(self):
        """Test explicit country code overrides default."""
        # When number has + prefix, default country is ignored
        assert normalize_phone("+442071234567", default_country="US") == "+442071234567"
        assert normalize_phone("+61291234567", default_country="US") == "+61291234567"


class TestNormalizePhoneWhitespace:
    """Test whitespace handling."""

    def test_string_with_whitespace(self):
        """Test strings with leading/trailing whitespace."""
        assert normalize_phone("  2025551234  ") == "+12025551234"
        assert normalize_phone("\t202-555-1234\n") == "+12025551234"
        assert normalize_phone("  +1 202 555 1234  ") == "+12025551234"
        assert normalize_phone(" \n 415-555-1234 \t ") == "+14155551234"


class TestNormalizePhoneBoundaryConditions:
    """Test boundary conditions and limits."""

    def test_exactly_8_digits(self):
        """Test minimum valid length (8 digits)."""
        assert normalize_phone("+12345678") == "+12345678"
        assert normalize_phone("12345678", default_country="UK") == "+12345678"

    def test_exactly_7_digits(self):
        """Test below minimum valid length (7 digits)."""
        assert normalize_phone("1234567") is None
        assert normalize_phone("+1234567") is None

    def test_very_long_numbers(self):
        """Test very long phone numbers."""
        # Valid if has + prefix and >= 8 digits
        assert normalize_phone("+123456789012345") == "+123456789012345"
        # US 10-digit number with extra digits stripped during parsing won't work
        # But raw long number with + should work
        assert normalize_phone("+12025551234567") == "+12025551234567"
