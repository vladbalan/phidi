from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
import sys
from typing import Dict, Iterable, List, Optional
try:
	from src.common.console import Console
except Exception:  # pragma: no cover - fallback when run as a script
	import sys as _sys
	from pathlib import Path as _Path
	_repo_root = _Path(__file__).resolve().parents[2]
	if str(_repo_root) not in _sys.path:
		_sys.path.insert(0, str(_repo_root))
	from src.common.console import Console  # type: ignore


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


def completeness_score(r: Dict) -> int:
	# Similar heuristic as the example: phones count + presence of socials + address presence
	return int(bool(r.get("address"))) + int(bool(r.get("facebook"))) + int(bool(r.get("linkedin"))) + int(bool(r.get("twitter"))) + len(r.get("phones") or [])


def dedupe_by_domain(records: Iterable[Dict]) -> List[Dict]:
	groups: Dict[str, List[Dict]] = defaultdict(list)
	for r in records:
		d = (r.get("domain") or "").strip().lower()
		if not d:
			continue
		groups[d].append(r)

	winners: List[Dict] = []
	for d, recs in groups.items():
		if not recs:
			continue
		best = max(recs, key=completeness_score)
		winners.append(best)
	return winners


def main(argv: Optional[List[str]] = None) -> int:
	ap = argparse.ArgumentParser(description="ETL Step 3: Deduplicate merged records")
	ap.add_argument("--input", default="data/staging/crawl_results_merged.ndjson")
	ap.add_argument("--output", default="data/staging/companies_serving.ndjson")
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

	# Friendly preflight
	if not inp.exists():
		error("[ETL] Missing merged input: " + str(inp))
		info("[ETL] Run previous steps (normalize, merge_names) or pass --input explicitly.")
		return 2

	winners = dedupe_by_domain(read_ndjson(inp))
	write_ndjson(out, winners)
	success(f"[ETL] Wrote deduplicated records: {out} ({len(winners)} records)")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

