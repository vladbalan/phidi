from __future__ import annotations

from typing import Dict, Optional


def normalize_address(raw: str | dict | None) -> Optional[Dict[str, str]]:
	"""Very small address normalizer.

	Accepts a string (free-form) or a dict-like structure and returns a dict with
	lightweight fields where available. This is intentionally minimal.
	"""
	if raw is None:
		return None

	if isinstance(raw, dict):
		# Lowercase keys and pass through known components
		out: Dict[str, str] = {}
		for k in ["street", "city", "state", "zip", "country"]:
			v = raw.get(k) if isinstance(raw.get(k), str) else None
			if v and v.strip():
				out[k] = v.strip()
		return out or None

	if isinstance(raw, str):
		s = raw.strip()
		if not s:
			return None
		# Minimal heuristic: only keep city and country if separated by comma(s)
		parts = [p.strip() for p in s.split(",") if p.strip()]
		out: Dict[str, str] = {}
		if len(parts) >= 1:
			out["street"] = parts[0]
		if len(parts) >= 2:
			out["city"] = parts[1]
		if len(parts) >= 3:
			# Try to split state/zip if present
			rest = parts[2]
			tokens = rest.split()
			if len(tokens) == 2 and tokens[1].isdigit():
				out["state"] = tokens[0]
				out["zip"] = tokens[1]
			else:
				out["state"] = rest
		if len(parts) >= 4:
			out["country"] = parts[3]
		return out or None

	return None

