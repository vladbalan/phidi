"""
Test suite for data extraction modules.

Tests extract.py (Python) functionality:
- Phone number parsing and normalization
- Social URL extraction (Facebook, LinkedIn, Twitter, Instagram)
- Address parsing from various HTML structures
- Edge cases and malformed input handling
"""
from __future__ import annotations

import pytest

from src.crawlers.python.extract import (
	extract_phones,
	extract_facebook,
	extract_linkedin,
	extract_twitter,
	extract_instagram,
	extract_address,
	extract_all,
)


# ---------- Phone Extraction Tests ----------

def test_extract_phones_basic():
	"""Test extraction of common US phone formats."""
	html = "Call us at (212) 555-1234 or +1-415-555-6789"
	phones = extract_phones(html)
	assert len(phones) == 2
	assert "+12125551234" in phones
	assert "+14155556789" in phones


def test_extract_phones_international():
	"""Test extraction of international phone formats."""
	html = "UK: +44 20 1234 5678, Germany: +49 30 12345678"
	phones = extract_phones(html)
	assert len(phones) == 2
	assert any("44" in p for p in phones)
	assert any("49" in p for p in phones)


def test_extract_phones_various_formats():
	"""Test extraction from different formatting styles."""
	html = """
		<p>123-456-7890</p>
		<p>123.456.7890</p>
		<p>(123) 456-7890</p>
		<p>+1 123 456 7890</p>
	"""
	phones = extract_phones(html)
	# All should normalize to same number
	assert len(phones) == 1
	assert phones[0] == "+11234567890"


def test_extract_phones_deduplicate():
	"""Test that duplicate phones are deduplicated."""
	html = "(212) 555-1234 or call 212-555-1234 or +1-212-555-1234"
	phones = extract_phones(html)
	assert len(phones) == 1
	assert phones[0] == "+12125551234"


def test_extract_phones_ignore_dates():
	"""Test that dates are not mistaken for phone numbers."""
	html = "Event on 2024-01-15 or 2024/12/31"
	phones = extract_phones(html)
	assert len(phones) == 0


def test_extract_phones_ignore_prices():
	"""Test that prices are not mistaken for phone numbers."""
	html = "Price: $1,234.56 or €999.99"
	phones = extract_phones(html)
	assert len(phones) == 0


def test_extract_phones_empty_input():
	"""Test extraction from empty input."""
	assert extract_phones("") == []
	assert extract_phones(None) == []  # type: ignore


def test_extract_phones_from_html():
	"""Test extraction with HTML tags present."""
	html = """
		<div class="contact">
			<p>Phone: <strong>(555) 123-4567</strong></p>
			<span>Fax: 555-123-4568</span>
		</div>
	"""
	phones = extract_phones(html)
	assert len(phones) == 2


# ---------- Facebook Extraction Tests ----------

def test_extract_facebook_from_href():
	"""Test extraction from href attribute."""
	html = '<a href="https://www.facebook.com/acme-corp">Facebook</a>'
	fb = extract_facebook(html)
	assert fb == "facebook.com/acme-corp"


def test_extract_facebook_fb_com_shorthand():
	"""Test extraction with fb.com shorthand."""
	html = '<a href="https://fb.com/acme">Follow us</a>'
	fb = extract_facebook(html)
	assert fb == "facebook.com/acme"


def test_extract_facebook_no_www():
	"""Test extraction without www prefix."""
	html = '<a href="https://facebook.com/company">Link</a>'
	fb = extract_facebook(html)
	assert fb == "facebook.com/company"


def test_extract_facebook_not_found():
	"""Test when no Facebook URL is present."""
	html = '<a href="https://twitter.com/acme">Twitter</a>'
	fb = extract_facebook(html)
	assert fb is None


def test_extract_facebook_empty_input():
	"""Test extraction from empty input."""
	assert extract_facebook("") is None
	assert extract_facebook(None) is None  # type: ignore


# ---------- LinkedIn Extraction Tests ----------

def test_extract_linkedin_company():
	"""Test extraction of company LinkedIn URLs."""
	html = '<a href="https://linkedin.com/company/acme-corp">LinkedIn</a>'
	li = extract_linkedin(html)
	assert li == "linkedin.com/company/acme-corp"


def test_extract_linkedin_personal():
	"""Test extraction of personal LinkedIn URLs."""
	html = '<a href="https://www.linkedin.com/in/john-doe">Profile</a>'
	li = extract_linkedin(html)
	assert li == "linkedin.com/in/john-doe"


def test_extract_linkedin_not_found():
	"""Test when no LinkedIn URL is present."""
	html = '<a href="https://facebook.com/acme">Facebook</a>'
	li = extract_linkedin(html)
	assert li is None


def test_extract_linkedin_empty_input():
	"""Test extraction from empty input."""
	assert extract_linkedin("") is None
	assert extract_linkedin(None) is None  # type: ignore


# ---------- Twitter Extraction Tests ----------

def test_extract_twitter_basic():
	"""Test extraction of Twitter URLs."""
	html = '<a href="https://twitter.com/acmecorp">Twitter</a>'
	tw = extract_twitter(html)
	assert tw == "twitter.com/acmecorp"


def test_extract_twitter_x_com():
	"""Test extraction with x.com domain."""
	html = '<a href="https://x.com/acmecorp">X</a>'
	tw = extract_twitter(html)
	assert tw == "x.com/acmecorp"


def test_extract_twitter_not_found():
	"""Test when no Twitter URL is present."""
	html = '<a href="https://facebook.com/acme">Facebook</a>'
	tw = extract_twitter(html)
	assert tw is None


def test_extract_twitter_empty_input():
	"""Test extraction from empty input."""
	assert extract_twitter("") is None
	assert extract_twitter(None) is None  # type: ignore


# ---------- Instagram Extraction Tests ----------

def test_extract_instagram_basic():
	"""Test extraction of Instagram URLs."""
	html = '<a href="https://instagram.com/acmecorp">Instagram</a>'
	ig = extract_instagram(html)
	assert ig == "instagram.com/acmecorp"


def test_extract_instagram_no_www():
	"""Test extraction without www prefix."""
	html = '<a href="https://www.instagram.com/company">IG</a>'
	ig = extract_instagram(html)
	assert ig == "instagram.com/company"


def test_extract_instagram_trailing_slash():
	"""Test extraction with trailing slash."""
	html = '<a href="https://instagram.com/acme/">Instagram</a>'
	ig = extract_instagram(html)
	assert ig == "instagram.com/acme"


def test_extract_instagram_not_found():
	"""Test when no Instagram URL is present."""
	html = '<a href="https://facebook.com/acme">Facebook</a>'
	ig = extract_instagram(html)
	assert ig is None


def test_extract_instagram_empty_input():
	"""Test extraction from empty input."""
	assert extract_instagram("") is None
	assert extract_instagram(None) is None  # type: ignore


# ---------- Address Extraction Tests ----------

def test_extract_address_keyword_based():
	"""Test extraction using address keywords."""
	html = "Address: 123 Main Street, San Francisco, CA 94105"
	addr = extract_address(html)
	assert addr is not None
	assert "Main Street" in addr or "Main St" in addr
	assert "San Francisco" in addr


def test_extract_address_structured():
	"""Test extraction of structured address."""
	html = "Visit us at 456 Broadway Ave, New York, NY 10012"
	addr = extract_address(html)
	assert addr is not None
	assert "456" in addr
	assert "Broadway" in addr


def test_extract_address_with_suite():
	"""Test extraction with suite/unit number."""
	html = "Location: 789 Oak Street Suite 200, Austin, TX 78701"
	addr = extract_address(html)
	assert addr is not None
	assert "Oak" in addr


def test_extract_address_headquarters():
	"""Test extraction with 'headquarters' keyword."""
	html = "Headquarters: 100 Tech Drive, Seattle, WA 98101"
	addr = extract_address(html)
	assert addr is not None
	assert "Tech Drive" in addr or "Tech Dr" in addr


def test_extract_address_from_html():
	"""Test extraction with HTML tags."""
	html = """
		<div class="address">
			<p>Office Address:</p>
			<p>555 Market Street</p>
			<p>San Francisco, CA 94105</p>
		</div>
	"""
	addr = extract_address(html)
	assert addr is not None
	assert "Market" in addr


def test_extract_address_not_found():
	"""Test when no address is present."""
	html = "Contact us by phone or email only."
	addr = extract_address(html)
	assert addr is None


def test_extract_address_empty_input():
	"""Test extraction from empty input."""
	assert extract_address("") is None
	assert extract_address(None) is None  # type: ignore


# ---------- Extract All Tests ----------

def test_extract_all_complete_data():
	"""Test extraction with all data types present."""
	html = """
		<html>
		<body>
			<p>Call: (555) 123-4567</p>
			<a href="https://facebook.com/acme">Facebook</a>
			<a href="https://linkedin.com/company/acme">LinkedIn</a>
			<a href="https://twitter.com/acme">Twitter</a>
			<a href="https://instagram.com/acme">Instagram</a>
			<p>Address: 123 Main St, New York, NY 10001</p>
		</body>
		</html>
	"""
	result = extract_all(html, "https://acme.com")
	
	assert len(result['phones']) > 0
	assert result['facebook_url'] is not None
	assert result['linkedin_url'] is not None
	assert result['twitter_url'] is not None
	assert result['instagram_url'] is not None
	assert result['address'] is not None


def test_extract_all_partial_data():
	"""Test extraction with only some data present."""
	html = """
		<html>
		<body>
			<p>Phone: (555) 987-6543</p>
			<a href="https://linkedin.com/company/test">LinkedIn</a>
		</body>
		</html>
	"""
	result = extract_all(html, "https://test.com")
	
	assert len(result['phones']) > 0
	assert result['linkedin_url'] is not None
	assert result['facebook_url'] is None
	assert result['twitter_url'] is None
	assert result['instagram_url'] is None
	assert result['address'] is None


def test_extract_all_no_data():
	"""Test extraction when no data is found."""
	html = """
		<html>
		<body>
			<p>Welcome to our website!</p>
		</body>
		</html>
	"""
	result = extract_all(html, "https://example.com")
	
	assert result['phones'] == []
	assert result['facebook_url'] is None
	assert result['linkedin_url'] is None
	assert result['twitter_url'] is None
	assert result['instagram_url'] is None
	assert result['address'] is None


def test_extract_all_empty_html():
	"""Test extraction from empty HTML."""
	result = extract_all("", "https://example.com")
	
	assert result['phones'] == []
	assert result['facebook_url'] is None
	assert result['linkedin_url'] is None
	assert result['twitter_url'] is None
	assert result['instagram_url'] is None
	assert result['address'] is None


def test_extract_all_multiple_phones():
	"""Test extraction of multiple phone numbers."""
	html = """
		<p>Sales: (555) 111-2222</p>
		<p>Support: (555) 333-4444</p>
		<p>Main: +1-555-555-5555</p>
	"""
	result = extract_all(html, "https://example.com")
	
	assert len(result['phones']) == 3


def test_extract_all_structure_integrity():
	"""Test that extract_all returns expected structure."""
	result = extract_all("<html></html>", "https://test.com")
	
	# Verify all expected keys are present
	assert 'phones' in result
	assert 'facebook_url' in result
	assert 'linkedin_url' in result
	assert 'twitter_url' in result
	assert 'instagram_url' in result
	assert 'address' in result
	
	# Verify correct types
	assert isinstance(result['phones'], list)
	assert result['facebook_url'] is None or isinstance(result['facebook_url'], str)
	assert result['linkedin_url'] is None or isinstance(result['linkedin_url'], str)
	assert result['twitter_url'] is None or isinstance(result['twitter_url'], str)
	assert result['instagram_url'] is None or isinstance(result['instagram_url'], str)
	assert result['address'] is None or isinstance(result['address'], str)
