from __future__ import annotations

from urllib.parse import urlparse


def _canonical_host_path(url: str | None) -> str | None:
	"""Return a normalized 'host[/path]' string for a URL or bare input.

	Handles inputs like:
	- https://facebook.com/melatee -> facebook.com/melatee
	- facebook.com/melatee         -> facebook.com/melatee
	- www.facebook.com/melatee     -> facebook.com/melatee
	- fb.com/melatee               -> fb.com/melatee (caller may rewrite host)
	- melatee                      -> melatee (caller decides what to do)
	"""
	if not url:
		return None
	v = str(url).strip()
	if not v:
		return None
	try:
		p = urlparse(v)
		host: str = ""
		path: str = ""
		if p.netloc:
			host = p.netloc.lower()
			path = p.path.strip("/")
		else:
			# Bare input: split at first '/'
			parts = v.split("/", 1)
			host = parts[0].lower()
			path = parts[1].strip("/") if len(parts) > 1 else ""
		if host.startswith("www."):
			host = host[4:]
		base = host if not path else f"{host}/{path}"
		return base or None
	except Exception:
		return None


def canonicalize_facebook(url: str | None) -> str | None:
	c = _canonical_host_path(url)
	if not c:
		return None
	# Normalize shorthand fb.com to facebook.com
	if c.startswith("fb.com/") or c == "fb.com":
		c = "facebook.com" + c[6:] if len(c) > 6 else "facebook.com"
	# Drop leading www.
	if c.startswith("www.facebook.com/"):
		c = c[4:]
	# If input was just a handle (no dot and no slash), assume a Facebook handle
	if "/" not in c and "." not in c:
		c = f"facebook.com/{c}"
	# If it doesn't start with facebook.com yet but is fb.com, rewrite to facebook.com
	if c.startswith("fb.com/") or c == "fb.com":
		c = "facebook.com" + c[6:] if len(c) > 6 else "facebook.com"
	if c == "facebook.com":
		return c
	if not c.startswith("facebook.com"):
		return c
	# Remove accidental duplicate prefixes
	while "facebook.com/facebook.com" in c:
		c = c.replace("facebook.com/facebook.com", "facebook.com")
	return c


def canonicalize_linkedin(url: str | None) -> str | None:
	c = _canonical_host_path(url)
	return c if c and "linkedin.com" in c else c


def canonicalize_twitter(url: str | None) -> str | None:
	c = _canonical_host_path(url)
	return c if c and (c.startswith("twitter.com") or c.startswith("x.com")) else c


def canonicalize_instagram(url: str | None) -> str | None:
	"""Canonicalize Instagram URL.
	
	Examples:
		https://www.instagram.com/company -> instagram.com/company
		instagram.com/company -> instagram.com/company
		www.instagram.com/company -> instagram.com/company
	"""
	c = _canonical_host_path(url)
	return c if c and c.startswith("instagram.com") else None

