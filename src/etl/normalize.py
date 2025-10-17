from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional

try:
	from src.common.domain_utils import clean_domain
	from src.common.phone_utils import normalize_phone
	from src.common.social_utils import (
		canonicalize_facebook,
		canonicalize_instagram,
		canonicalize_linkedin,
		canonicalize_twitter,
	)
	from src.common.normalize_utils import normalize_address
except Exception:  # pragma: no cover
	import sys as _sys
	from pathlib import Path as _Path
	_repo_root = _Path(__file__).resolve().parents[2]
	if str(_repo_root) not in _sys.path:
		_sys.path.insert(0, str(_repo_root))
	from src.common.domain_utils import clean_domain  # type: ignore
	from src.common.phone_utils import normalize_phone  # type: ignore
	from src.common.social_utils import (  # type: ignore
		canonicalize_facebook,
		canonicalize_instagram,
		canonicalize_linkedin,
		canonicalize_twitter,
	)
	from src.common.normalize_utils import normalize_address  # type: ignore
from src.common.console import Console


def _derive_company_name(domain: Optional[str]) -> Optional[str]:
	if not domain:
		return None
	left = (domain or "").split(".")[0]
	# Replace non-alphanumeric with space, title-case tokens
	tokens = [t for t in "".join(ch if ch.isalnum() else " " for ch in left).strip().split() if t]
	name = " ".join(t[:1].upper() + t[1:] for t in tokens)
	return name or None


def read_ndjson(path: Path) -> Iterable[Dict]:
	with path.open("r", encoding="utf-8") as f:
		for line in f:
			line = line.strip()
			if not line:
				continue
			try:
				yield json.loads(line)
			except json.JSONDecodeError:
				continue


def write_ndjson(path: Path, records: Iterable[Dict]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", encoding="utf-8") as f:
		for rec in records:
			f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def normalize_record(r: Dict) -> Dict:
	domain = clean_domain(r.get("domain"))
	phones_raw = r.get("phones") or []
	phones = [p for p in (normalize_phone(p, default_country="US") for p in phones_raw) if p]

	facebook = canonicalize_facebook(r.get("facebook_url"))
	linkedin = canonicalize_linkedin(r.get("linkedin_url"))
	twitter = canonicalize_twitter(r.get("twitter_url"))
	instagram = canonicalize_instagram(r.get("instagram_url"))
	address = normalize_address(r.get("address"))
	company_name = r.get("company_name") or _derive_company_name(domain)

	return {
		"domain": domain,
		"phones": phones,
		"facebook": facebook,
		"linkedin": linkedin,
		"twitter": twitter,
		"instagram": instagram,
		"address": address,
		"company_name": company_name,
	}


def main(argv: Optional[List[str]] = None) -> int:
	ap = argparse.ArgumentParser(description="ETL Step 1: Normalize crawl results")
	ap.add_argument("--input", default="data/staging/crawl_results.ndjson")
	ap.add_argument("--output", default="data/staging/crawl_results_normalized.ndjson")
	ap.add_argument("--no-color", action="store_true", help="Disable colored output")
	args = ap.parse_args(argv)

	inp = Path(args.input)
	out = Path(args.output)

	# Console
	c = Console(no_color=args.no_color)
	info = c.info
	warn = c.warn
	error = c.error
	success = c.success

	# Friendly preflight: ensure staged input exists
	if not inp.exists():
		error("[ETL] Missing staged input: " + str(inp))
		info("[ETL] How to fix:")
		info("  - Run 'make stage1' to produce and stage crawl_results.ndjson, or")
		info("  - Provide a custom input via '--input <path-to-ndjson>'.")
		return 2

	write_ndjson(out, (normalize_record(r) for r in read_ndjson(inp)))
	success(f"[ETL] Wrote normalized records: {out}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

