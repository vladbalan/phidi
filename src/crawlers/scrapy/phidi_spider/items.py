"""
Scrapy Items for company data extraction.
Defines data structures with field processors for normalization.
"""
import sys
from pathlib import Path
from typing import List, Optional

import scrapy
from itemloaders.processors import TakeFirst, MapCompose, Join, Compose

# Add repo root to path
_repo_root = Path(__file__).resolve().parents[4]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Import existing normalization utilities (DRY principle)
from src.common.phone_utils import normalize_phone
from src.common.social_utils import (
    canonicalize_facebook,
    canonicalize_linkedin,
    canonicalize_twitter,
)
from src.common.normalize_utils import normalize_address


def _filter_empty(values: List[str]) -> List[str]:
    """Remove empty strings and None values."""
    return [v for v in values if v and v.strip()]


def _clean_phone(value: str) -> str:
    """Clean phone from tel: link or raw text."""
    if value.startswith('tel:'):
        value = value[4:]  # Remove 'tel:' prefix
    return value.strip()


def _deduplicate_phones(phones: List[str]) -> List[str]:
    """Normalize and deduplicate phone numbers."""
    normalized = []
    seen = set()
    for phone in phones:
        norm = normalize_phone(phone)
        if norm and norm not in seen:
            normalized.append(norm)
            seen.add(norm)
    return normalized


def _normalize_address_field(value) -> Optional[str]:
    """Normalize address value - handle strings and skip non-strings."""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped:
            # normalize_address may return dict or str, convert dict to string
            normalized = normalize_address(stripped)
            if isinstance(normalized, dict):
                # Join dict values into a string
                return ' '.join(str(v) for v in normalized.values() if v)
            elif isinstance(normalized, str):
                return normalized
    return None


def _first_valid_address(values: List) -> Optional[str]:
    """Take first valid normalized address."""
    for val in values:
        result = _normalize_address_field(val)
        if result:
            return result
    return None


def _first_or_none(values: List[str]) -> Optional[str]:
    """Take first non-empty value or None."""
    filtered = _filter_empty(values)
    return filtered[0] if filtered else None


def _canonicalize_social(url: str, platform: str) -> Optional[str]:
    """Canonicalize social media URL based on platform."""
    if not url:
        return None
    if platform == 'facebook':
        return canonicalize_facebook(url)
    elif platform == 'linkedin':
        return canonicalize_linkedin(url)
    elif platform == 'twitter':
        return canonicalize_twitter(url)
    return url


class CompanyItem(scrapy.Item):
    """
    Company data item with field processors.
    Fields match the output format of existing crawlers.
    """
    # Required fields
    domain = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    final_url = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    status_code = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    crawled = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    response_time_ms = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    # Data fields
    company_name = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=_first_or_none
    )
    
    phones = scrapy.Field(
        input_processor=MapCompose(str.strip, _clean_phone),
        output_processor=Compose(_filter_empty, _deduplicate_phones)
    )
    
    facebook = scrapy.Field(
        input_processor=MapCompose(str.strip, lambda x: _canonicalize_social(x, 'facebook')),
        output_processor=_first_or_none
    )
    
    linkedin = scrapy.Field(
        input_processor=MapCompose(str.strip, lambda x: _canonicalize_social(x, 'linkedin')),
        output_processor=_first_or_none
    )
    
    twitter = scrapy.Field(
        input_processor=MapCompose(str.strip, lambda x: _canonicalize_social(x, 'twitter')),
        output_processor=_first_or_none
    )
    
    instagram = scrapy.Field(
        input_processor=MapCompose(str.strip),
        output_processor=_first_or_none
    )
    
    address = scrapy.Field(
        output_processor=_first_valid_address
    )
    
    # Error fields (optional)
    error = scrapy.Field(
        output_processor=TakeFirst()
    )
    
    error_message = scrapy.Field(
        output_processor=TakeFirst()
    )
