from src.common.social_utils import canonicalize_facebook, canonicalize_instagram


def test_facebook_canonical_basic():
    assert canonicalize_facebook("https://www.facebook.com/melatee") == "facebook.com/melatee"
    assert canonicalize_facebook("facebook.com/melatee") == "facebook.com/melatee"
    assert canonicalize_facebook("fb.com/melatee") == "facebook.com/melatee"


def test_facebook_canonical_no_duplication():
    assert canonicalize_facebook("facebook.com/facebook.com/melatee") == "facebook.com/melatee"


def test_facebook_canonical_handles_plain_handle():
    # Plain handle should map to facebook.com/<handle>
    assert canonicalize_facebook("melatee") == "facebook.com/melatee"
    assert canonicalize_facebook("www.facebook.com/melatee") == "facebook.com/melatee"
    assert canonicalize_facebook("FB.com/melatee") == "facebook.com/melatee"


def test_instagram_canonical_basic():
    """Test basic Instagram URL canonicalization."""
    assert canonicalize_instagram("https://www.instagram.com/company") == "instagram.com/company"
    assert canonicalize_instagram("instagram.com/company") == "instagram.com/company"
    assert canonicalize_instagram("www.instagram.com/company") == "instagram.com/company"


def test_instagram_canonical_with_path():
    """Test Instagram URLs with paths."""
    assert canonicalize_instagram("https://instagram.com/company/") == "instagram.com/company"
    assert canonicalize_instagram("instagram.com/company/reels") == "instagram.com/company/reels"


def test_instagram_canonical_null_handling():
    """Test Instagram canonicalization with null/invalid inputs."""
    assert canonicalize_instagram(None) is None
    assert canonicalize_instagram("") is None
    assert canonicalize_instagram("   ") is None
    assert canonicalize_instagram("twitter.com/company") is None
    assert canonicalize_instagram("facebook.com/company") is None


def test_instagram_canonical_case_insensitive():
    """Test Instagram canonicalization is case-insensitive."""
    assert canonicalize_instagram("https://WWW.INSTAGRAM.COM/Company") == "instagram.com/Company"
    assert canonicalize_instagram("INSTAGRAM.COM/BRAND") == "instagram.com/BRAND"
