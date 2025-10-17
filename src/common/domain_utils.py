from __future__ import annotations

from urllib.parse import urlparse


def clean_domain(value: str | None) -> str | None:
	"""Return a canonical domain (lowercase, no scheme/www/path/query/fragment/trailing dot).

	Examples:
	  https://www.Example.com/ -> example.com
	  example.com/             -> example.com
	  WWW.TEST.ORG.            -> test.org
	  https://https//acornlawpc.com/ -> acornlawpc.com (malformed URL fix)
	"""
	if not value:
		return None
	v = str(value).strip()
	if not v:
		return None
	
	# Handle malformed URLs with multiple protocols or protocol-like patterns
	# Examples: https://https//domain.com, http://http://domain.com, https:///domain.com
	# Strategy: Split by "//" and find the first part that looks like a domain
	if "//" in v:
		parts = v.split("//")
		# If we have more than 2 parts (normal is 2: ["https:", "domain.com"]),
		# or if the netloc part is empty/looks like a protocol, we have a malformed URL
		if len(parts) > 2 or (len(parts) == 2 and parts[1] and parts[1].split("/")[0] in ("http", "https", "http:", "https:")):
			# Find the first part that looks like a domain (contains a dot, not a protocol)
			for part in parts[1:]:  # Skip the first part (will be the scheme like "https:")
				# Clean up the part and check if it looks like a domain
				part = part.split("/")[0].strip()  # Get just the domain part, no paths
				if part and "." in part and part not in ("http", "https", "http:", "https:"):
					v = part
					break
		# Special case: if we have empty netloc (e.g., https:///domain.com -> ['https:', '', 'domain.com'])
		elif len(parts) >= 2 and not parts[1]:
			# Look for the first non-empty part with a dot
			for part in parts[2:]:
				part = part.split("/")[0].strip()
				if part and "." in part:
					v = part
					break
	
	try:
		if "://" in v:
			parsed = urlparse(v)
			host = parsed.netloc or parsed.path
		else:
			host = v
	except Exception:
		host = v
	# Strip leading slashes (handles cases like https:///example.com where path is /example.com)
	host = host.lstrip("/")
	host = host.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
	host = host.rstrip("./").lower()
	if host.startswith("www."):
		host = host[4:]
	
	# Reject domains with internal whitespace (invalid)
	if host and " " in host:
		return None
	
	return host or None

