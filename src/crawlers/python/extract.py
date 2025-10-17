"""
Data extraction module for Python crawler.

Extracts structured company data from HTML:
- Phone numbers (various international formats)
- Social media URLs (Facebook, LinkedIn, Twitter, Instagram)
- Physical addresses

Design: Simple regex patterns, reuses existing normalization utilities.
No external HTML parsers needed - keeps dependencies minimal.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

try:
	from src.common.phone_utils import normalize_phone
	from src.common.social_utils import (
		canonicalize_facebook,
		canonicalize_linkedin,
		canonicalize_twitter,
	)
	from src.common.normalize_utils import normalize_address
except ImportError:  # pragma: no cover - fallback for direct execution
	import sys
	from pathlib import Path
	_repo = Path(__file__).resolve().parents[3]
	if str(_repo) not in sys.path:
		sys.path.insert(0, str(_repo))
	from src.common.phone_utils import normalize_phone  # type: ignore
	from src.common.social_utils import (  # type: ignore
		canonicalize_facebook,
		canonicalize_linkedin,
		canonicalize_twitter,
	)
	from src.common.normalize_utils import normalize_address  # type: ignore


# ---------- Regex Patterns ----------

# Phone: Match common formats
# Examples: (212) 555-1234, 212-555-1234, +1-212-555-1234, +44 20 1234 5678
_PHONE_PATTERN = re.compile(
	r'\b(?:\+?\d{1,3}[-.\s()]*)?'  # Optional country code with word boundary
	r'(?:\(?\d{2,4}\)?[-.\s]*)?'  # Optional area code
	r'\d{2,4}[-.\s]*\d{2,4}[-.\s]*\d{2,4}\b',  # Main number with word boundary
	re.IGNORECASE
)

# Social URLs in href attributes
_FACEBOOK_PATTERN = re.compile(
	r'href=["\'](https?://(?:www\.)?(?:facebook\.com|fb\.com)/[^"\']+)["\']',
	re.IGNORECASE
)

_LINKEDIN_PATTERN = re.compile(
	r'href=["\'](https?://(?:www\.)?linkedin\.com/(?:company|in)/[^"\']+)["\']',
	re.IGNORECASE
)

_TWITTER_PATTERN = re.compile(
	r'href=["\'](https?://(?:www\.)?(?:twitter\.com|x\.com)/[^"\']+)["\']',
	re.IGNORECASE
)

_INSTAGRAM_PATTERN = re.compile(
	r'href=["\'](https?://(?:www\.)?instagram\.com/[^"\']+)["\']',
	re.IGNORECASE
)

# Address patterns
_ADDRESS_KEYWORD_PATTERN = re.compile(
	r'(?:address|location|visit\s+us|headquarters?|office)[:\s]+([^<]+?(?:street|st|ave|avenue|road|rd|blvd|boulevard|drive|dr)[^<]{0,100})',
	re.IGNORECASE | re.DOTALL
)

_ADDRESS_STRUCTURED_PATTERN = re.compile(
	r'\d+\s+[A-Za-z0-9\s]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\.?,?\s*'
	r'(?:Suite|Ste|Unit|#)?\s*[A-Za-z0-9]*,?\s*'
	r'[A-Za-z\s]+,\s*'
	r'(?:[A-Z]{2}|[A-Za-z\s]+)\s*'
	r'\d{4,5}(?:-\d{4})?',
	re.IGNORECASE
)

# Stop words that typically indicate end of address context
_ADDRESS_STOP_WORDS = re.compile(
	r'\b(?:business\s+hours?|hours?|open|closed|monday|tuesday|wednesday|thursday|friday|saturday|sunday|phone|email|fax|contact)\b',
	re.IGNORECASE
)


# ---------- Helper Functions ----------

def _strip_html_tags(html: str) -> str:
	"""Remove HTML tags, preserving whitespace structure."""
	if not html:
		return ""
	# Replace common block elements with spaces to preserve word boundaries
	text = re.sub(r'<(?:br|p|div|li|tr|td|th)[^>]*>', ' ', html, flags=re.IGNORECASE)
	# Remove all remaining tags
	text = re.sub(r'<[^>]+>', '', text)
	# Normalize whitespace
	text = re.sub(r'\s+', ' ', text)
	return text.strip()


def _clean_text(text: str) -> str:
	"""Clean text by decoding HTML entities and normalizing whitespace."""
	if not text:
		return ""
	# Decode common HTML entities
	text = re.sub(r'&nbsp;', ' ', text)
	text = re.sub(r'&amp;', '&', text)
	text = re.sub(r'&lt;', '<', text)
	text = re.sub(r'&gt;', '>', text)
	text = re.sub(r'&quot;', '"', text)
	text = re.sub(r'&#39;', "'", text)
	# Normalize whitespace
	text = re.sub(r'\s+', ' ', text)
	return text.strip()


def _remove_script_style_tags(html: str) -> str:
	"""Remove script, style, and noscript tags from HTML."""
	if not html:
		return ""
	# Remove script tags and content
	html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
	# Remove style tags and content
	html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
	# Remove noscript tags and content
	html = re.sub(r'<noscript[^>]*>.*?</noscript>', '', html, flags=re.DOTALL | re.IGNORECASE)
	return html


def _clean_phone_candidates(text: str) -> List[str]:
	"""Extract potential phone numbers, filter out obvious non-phones."""
	if not text:
		return []
	
	candidates = _PHONE_PATTERN.findall(text)
	cleaned = []
	
	for candidate in candidates:
		# Strip whitespace and common separators for digit counting
		digits_only = re.sub(r'\D', '', candidate)
		
		# Filter: Must have 8-15 digits (international range)
		if not (8 <= len(digits_only) <= 15):
			continue
		
		# Filter: Avoid dates (patterns like 2024-01-15)
		if re.match(r'^\d{4}[-/]\d{2}[-/]\d{2}$', candidate.strip()):
			continue
		
		# Filter: Avoid prices/numbers (patterns like $1,234.56)
		if re.match(r'^[$€£]\s*[\d,]+\.?\d*$', candidate.strip()):
			continue
		
		cleaned.append(candidate)
	
	return cleaned


# ---------- Extraction Functions ----------

def extract_phones(text: str) -> List[str]:
	"""
	Extract and normalize phone numbers from text.
	
	Args:
		text: Plain text or HTML content
	
	Returns:
		List of normalized phone numbers in E.164-like format, deduplicated and sorted
	"""
	if not text:
		return []
	
	# Strip HTML if present
	plain_text = _strip_html_tags(text)
	
	# Find candidates
	candidates = _clean_phone_candidates(plain_text)
	
	# Normalize and deduplicate
	normalized_set = set()
	for candidate in candidates:
		norm = normalize_phone(candidate)
		if norm:
			normalized_set.add(norm)
	
	# Return sorted for deterministic output
	return sorted(normalized_set)


def extract_company_name(html: str) -> Optional[str]:
	"""
	Extract company name from HTML using multiple strategies.
	
	Tries in order of reliability:
	1. JSON-LD structured data (Organization, LocalBusiness, Corporation)
	2. Open Graph site_name meta tag
	3. Title tag (cleaned of common suffixes)
	4. Returns None if no name found (caller should use domain fallback)
	
	Args:
		html: Raw HTML content
	
	Returns:
		Company name string or None
	"""
	if not html:
		return None
	
	def _is_valid_company_name(name: str) -> bool:
		"""Check if extracted name is a valid company name."""
		if not name or len(name) < 2:
			return False
		# Reject if it looks like a URL
		if any(pattern in name.lower() for pattern in ['http://', 'https://', 'www.', '.com/', '.org/', '.net/']):
			return False
		# Reject if too long (likely a sentence/paragraph)
		if len(name) > 80:
			return False
		return True
	
	# Strategy 1: Try JSON-LD structured data first (most reliable)
	json_ld_pattern = re.compile(
		r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
		re.DOTALL | re.IGNORECASE
	)
	
	for match in json_ld_pattern.finditer(html):
		try:
			import json
			data = json.loads(match.group(1))
			# Handle both single object and array of objects
			items = [data] if isinstance(data, dict) else data
			if not isinstance(items, list):
				continue
			
			for item in items:
				if not isinstance(item, dict):
					continue
				# Look for Organization types
				item_type = item.get('@type', '')
				if isinstance(item_type, list):
					item_type = ' '.join(item_type)
				
				if any(t in item_type for t in ['Organization', 'LocalBusiness', 'Corporation', 'LegalService']):
					# Try name, then legalName
					name = item.get('name') or item.get('legalName')
					if name and isinstance(name, str):
						cleaned = _clean_text(name)
						if _is_valid_company_name(cleaned):
							return cleaned
		except (json.JSONDecodeError, ValueError, TypeError):
			continue
	
	# Strategy 2: Try og:site_name meta tag
	og_match = re.search(
		r'<meta[^>]*property=["\']og:site_name["\'][^>]*content=["\']([^"\']+)["\']',
		html,
		re.IGNORECASE
	)
	if og_match:
		name = _clean_text(og_match.group(1))
		# Remove trailing punctuation/separators (e.g., "Company -", "Company |")
		name = re.sub(r'[\s\-–—|:.,!;]+$', '', name)
		if _is_valid_company_name(name):
			return name
	
	# Strategy 3: Try <title> tag (remove common suffixes/patterns)
	title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
	if title_match:
		title = title_match.group(1)
		
		# Remove common patterns with separators: " | Home", " - Welcome", etc.
		title = re.sub(
			r'\s*[|\-–—:]\s*(?:Home|About|Services|Contact|Welcome|Official|Site|Website|Estate|Planning|Law|Legal).*$',
			'',
			title,
			flags=re.IGNORECASE
		)
		
		# Remove anything after separator followed by a phrase (taglines, descriptions)
		# This catches patterns like " - Tech Support That Never Sleeps"
		title = re.sub(r'\s*[|\-–—]\s+.{15,}$', '', title)
		
		# Also remove anything after separator (more aggressive)
		title = re.sub(r'\s*[|\-–—]\s+[^|]+$', '', title)
		
		# Remove trailing separators and punctuation
		title = re.sub(r'\s*[|\-–—:.,!;]+\s*$', '', title)
		
		# Remove common suffixes without separators (e.g., "NCCA Home Page" → "NCCA")
		# This handles cases where the title has a suffix but no separator
		title = re.sub(
			r'\s+(?:Home\s+Page|Home|Website|Official\s+Site|Official\s+Website|Web\s+Site)$',
			'',
			title,
			flags=re.IGNORECASE
		)
		
		title = _clean_text(title)
		
		# Validate and return
		if _is_valid_company_name(title) and len(title) < 50:
			return title
	
	return None


def extract_facebook(html: str) -> Optional[str]:
	"""
	Extract Facebook URL from HTML.
	
	Args:
		html: Raw HTML content
	
	Returns:
		Canonicalized Facebook URL (e.g., "facebook.com/company-name") or None
	"""
	if not html:
		return None
	
	match = _FACEBOOK_PATTERN.search(html)
	if match:
		url = match.group(1)
		return canonicalize_facebook(url)
	
	return None


def extract_linkedin(html: str) -> Optional[str]:
	"""
	Extract LinkedIn URL from HTML.
	
	Args:
		html: Raw HTML content
	
	Returns:
		Canonicalized LinkedIn URL (e.g., "linkedin.com/company/acme") or None
	"""
	if not html:
		return None
	
	match = _LINKEDIN_PATTERN.search(html)
	if match:
		url = match.group(1)
		return canonicalize_linkedin(url)
	
	return None


def extract_twitter(html: str) -> Optional[str]:
	"""
	Extract Twitter/X URL from HTML.
	
	Args:
		html: Raw HTML content
	
	Returns:
		Canonicalized Twitter URL (e.g., "twitter.com/acmecorp") or None
	"""
	if not html:
		return None
	
	match = _TWITTER_PATTERN.search(html)
	if match:
		url = match.group(1)
		return canonicalize_twitter(url)
	
	return None


def extract_instagram(html: str) -> Optional[str]:
	"""
	Extract Instagram URL from HTML.
	
	Args:
		html: Raw HTML content
	
	Returns:
		Instagram URL path (e.g., "instagram.com/acmecorp") or None
	"""
	if not html:
		return None
	
	match = _INSTAGRAM_PATTERN.search(html)
	if match:
		url = match.group(1)
		# Basic canonicalization: lowercase, remove www
		url = url.lower().replace('www.', '')
		# Extract host/path
		url = re.sub(r'^https?://', '', url)
		# Remove trailing slash
		url = url.rstrip('/')
		return url if url.startswith('instagram.com/') else None
	
	return None


def extract_address(html: str) -> Optional[str]:
	"""
	Extract physical address from HTML.
	
	Tries in order of reliability:
	1. JSON-LD PostalAddress structured data
	2. HTML microdata (itemprop="address" and itemprop="streetAddress")
	3. HTML <address> tag
	4. Keyword-based patterns (on cleaned HTML)
	5. Structured address patterns (street + city + state + zip)
	
	Applies stop-word filtering to avoid capturing business hours,
	contact info, and other non-address content.
	
	Args:
		html: Raw HTML content
	
	Returns:
		Normalized address string (comma-separated components) or None
	"""
	if not html:
		return None
	
	# Strategy 1: Try JSON-LD PostalAddress first (most reliable)
	json_ld_pattern = re.compile(
		r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
		re.DOTALL | re.IGNORECASE
	)
	
	for match in json_ld_pattern.finditer(html):
		try:
			import json
			data = json.loads(match.group(1))
			# Handle both single object and array
			items = [data] if isinstance(data, dict) else data
			if not isinstance(items, list):
				continue
			
			for item in items:
				if not isinstance(item, dict):
					continue
				
				address = item.get('address')
				if address and isinstance(address, dict):
					# Extract PostalAddress components
					parts = [
						address.get('streetAddress'),
						address.get('addressLocality'),  # city
						address.get('addressRegion'),    # state
						address.get('postalCode')        # zip
					]
					filtered = [_clean_text(p) for p in parts if p]
					if filtered:
						return ', '.join(filtered)
		except (json.JSONDecodeError, ValueError, TypeError):
			continue
	
	# CRITICAL: Remove script/style tags before further processing
	clean_html = _remove_script_style_tags(html)
	
	# Strategy 2: Try microdata (itemprop="address") before <address> tag
	itemprop_match = re.search(
		r'<[^>]*itemprop=["\']address["\'][^>]*>(.*?)</[^>]+>',
		clean_html,
		re.DOTALL | re.IGNORECASE
	)
	if itemprop_match:
		addr_html = itemprop_match.group(1)
		# Look for streetAddress itemprop within this
		street_match = re.search(
			r'<[^>]*itemprop=["\']streetAddress["\'][^>]*>(.*?)</[^>]+>',
			addr_html,
			re.DOTALL | re.IGNORECASE
		)
		if street_match:
			addr_text = _strip_html_tags(street_match.group(1))
			addr_text = _clean_text(addr_text)
			# Sanity check: reasonable length
			if addr_text and 10 < len(addr_text) < 200:
				return addr_text
	
	# Strategy 3: Try <address> tag
	address_tag_match = re.search(
		r'<address[^>]*>(.*?)</address>',
		clean_html,
		re.DOTALL | re.IGNORECASE
	)
	if address_tag_match:
		addr_text = _strip_html_tags(address_tag_match.group(1))
		addr_text = _clean_text(addr_text)
		# Truncate at stop words
		stop_match = _ADDRESS_STOP_WORDS.search(addr_text)
		if stop_match:
			addr_text = addr_text[:stop_match.start()].strip()
		# Sanity check: reasonable length
		if addr_text and 10 < len(addr_text) < 200:
			return addr_text
	
	# Strip tags for pattern matching on visible text only
	text = _strip_html_tags(clean_html)
	
	# Strategy 4: Look for addresses near keywords
	keyword_match = _ADDRESS_KEYWORD_PATTERN.search(text)
	if keyword_match:
		addr_text = keyword_match.group(1).strip()
		# Clean up
		addr_text = _clean_text(addr_text)
		# Truncate at stop words (e.g., "Business Hours")
		stop_match = _ADDRESS_STOP_WORDS.search(addr_text)
		if stop_match:
			addr_text = addr_text[:stop_match.start()].strip()
		# Sanity check
		if addr_text and 10 < len(addr_text) < 200:
			# Try to normalize using existing utility
			addr_dict = normalize_address(addr_text)
			if addr_dict:
				# Format as comma-separated string
				parts = [
					addr_dict.get('street'),
					addr_dict.get('city'),
					addr_dict.get('state'),
					addr_dict.get('zip'),
				]
				filtered = [p for p in parts if p]
				if filtered:
					return ', '.join(filtered)
			# Return as-is if normalization didn't work
			return addr_text
	
	# Strategy 5: Look for structured address patterns
	structured_match = _ADDRESS_STRUCTURED_PATTERN.search(text)
	if structured_match:
		addr_text = structured_match.group(0).strip()
		addr_text = _clean_text(addr_text)
		# Sanity check
		if addr_text and 10 < len(addr_text) < 200:
			return addr_text
	
	return None


def extract_all(html: str, url: str) -> Dict[str, Optional[List[str] | str]]:
	"""
	Extract all company data from HTML.
	
	Main entry point for extraction. Runs all extraction functions and returns
	structured result dictionary.
	
	Args:
		html: Raw HTML content
		url: Source URL (for context, currently unused but available for future logic)
	
	Returns:
		Dictionary with keys:
			- phones: List[str] - normalized phone numbers
			- company_name: Optional[str] - extracted company name (or None for fallback)
			- facebook_url: Optional[str] - Facebook URL
			- linkedin_url: Optional[str] - LinkedIn URL
			- twitter_url: Optional[str] - Twitter URL
			- instagram_url: Optional[str] - Instagram URL
			- address: Optional[str] - physical address
	"""
	if not html:
		return {
			'phones': [],
			'company_name': None,
			'facebook_url': None,
			'linkedin_url': None,
			'twitter_url': None,
			'instagram_url': None,
			'address': None,
		}
	
	# Note: We pass HTML directly to social extractors (they search hrefs)
	# but strip HTML for phone extraction (plain text works better)
	return {
		'phones': extract_phones(html),
		'company_name': extract_company_name(html),
		'facebook_url': extract_facebook(html),
		'linkedin_url': extract_linkedin(html),
		'twitter_url': extract_twitter(html),
		'instagram_url': extract_instagram(html),
		'address': extract_address(html),
	}


# ---------- CLI for testing ----------

if __name__ == "__main__":  # pragma: no cover
	import sys
	
	if len(sys.argv) < 2:
		print("Usage: python extract.py <html_file>")
		sys.exit(1)
	
	html_path = sys.argv[1]
	with open(html_path, 'r', encoding='utf-8') as f:
		html = f.read()
	
	result = extract_all(html, html_path)
	
	print("Extraction Results:")
	print(f"  Company Name: {result.get('company_name')}")
	print(f"  Phones: {result['phones']}")
	print(f"  Facebook: {result['facebook_url']}")
	print(f"  LinkedIn: {result['linkedin_url']}")
	print(f"  Twitter: {result['twitter_url']}")
	print(f"  Instagram: {result['instagram_url']}")
	print(f"  Address: {result['address']}")
