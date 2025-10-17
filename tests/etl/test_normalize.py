"""Test suite for data normalization logic."""
from src.etl.normalize import normalize_record


def test_normalize_record_with_instagram():
    """Test that normalize_record properly handles Instagram URLs."""
    raw = {
        "domain": "example.com",
        "phones": ["+1-555-123-4567", "(555) 987-6543"],
        "facebook_url": "https://www.facebook.com/example",
        "instagram_url": "https://www.instagram.com/example_official",
        "linkedin_url": "https://linkedin.com/company/example",
        "twitter_url": "https://twitter.com/example",
        "address": "123 Main St, San Francisco, CA 94105",
        "company_name": "Example Corp",
    }
    
    result = normalize_record(raw)
    
    assert result["domain"] == "example.com"
    assert result["instagram"] == "instagram.com/example_official"
    assert result["facebook"] == "facebook.com/example"
    assert len(result["phones"]) == 2
    assert result["company_name"] == "Example Corp"


def test_normalize_record_instagram_null():
    """Test normalize_record when Instagram is missing."""
    raw = {
        "domain": "example.com",
        "phones": [],
        "company_name": "Test"
    }
    
    result = normalize_record(raw)
    
    assert result["instagram"] is None
    assert result["facebook"] is None
    assert result["domain"] == "example.com"


def test_normalize_record_instagram_various_formats():
    """Test Instagram normalization with various URL formats."""
    test_cases = [
        ("instagram.com/brand", "instagram.com/brand"),
        ("https://instagram.com/brand", "instagram.com/brand"),
        ("www.instagram.com/brand/", "instagram.com/brand"),
        ("INSTAGRAM.COM/BRAND", "instagram.com/BRAND"),
    ]
    
    for input_url, expected in test_cases:
        raw = {"domain": "test.com", "instagram_url": input_url}
        result = normalize_record(raw)
        assert result["instagram"] == expected, f"Failed for input: {input_url}"


def test_normalize_record_all_fields():
    """Integration test: normalize all fields including Instagram."""
    raw = {
        "domain": "WWW.EXAMPLE.COM",
        "phones": ["555-1234", "+1 (555) 987-6543"],
        "facebook_url": "fb.com/example",
        "instagram_url": "www.instagram.com/example",
        "linkedin_url": "linkedin.com/company/example",
        "twitter_url": "x.com/example",
        "address": "  123 Main St  ",
        "company_name": None,
    }
    
    result = normalize_record(raw)
    
    assert result["domain"] == "example.com"
    assert result["instagram"] == "instagram.com/example"
    assert result["facebook"] == "facebook.com/example"
    assert result["company_name"] == "Example"  # Derived from domain
    assert len(result["phones"]) >= 1
    assert result["address"] is not None
