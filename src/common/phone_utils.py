from __future__ import annotations

import re


_DIGITS = re.compile(r"\D+")
# Pattern to match common extension markers and everything after them
_EXTENSION = re.compile(r'\s*(?:ext(?:ension)?|x)\s*\.?\s*\d+.*$', re.IGNORECASE)


def normalize_phone(raw: str | None, default_country: str = "US") -> str | None:
	"""Very small phone normalizer to E.164-like strings.

	- Strips extensions (e.g., "ext 123", "x456", "extension 789")
	- Strips non-digits
	- If starts with country code (e.g., leading '1' for US) and has 11 digits -> +1XXXXXXXXXX
	- If US default and has 10 digits -> +1XXXXXXXXXX
	- Else if starts with '+' and digits follow, return as-is after condensing

	This is intentionally minimal to avoid external dependencies.
	"""
	if not raw:
		return None
	s = str(raw).strip()
	if not s:
		return None
	# Remove extensions before processing
	s = re.sub(_EXTENSION, '', s).strip()
	# Preserve leading '+' if present to detect intentional country code
	has_plus = s.startswith("+")
	digits = re.sub(_DIGITS, "", s)
	if not digits:
		return None

	# If explicitly had + and digits, trust that (basic sanity: length >= 8)
	if has_plus:
		return "+" + digits if len(digits) >= 8 else None

	# US handling
	if default_country.upper() == "US":
		if len(digits) == 11 and digits.startswith("1"):
			return "+" + digits
		if len(digits) == 10:
			return "+1" + digits

	# Fallback: treat as national number without country; return raw digits with '+'
	return "+" + digits if len(digits) >= 8 else None

