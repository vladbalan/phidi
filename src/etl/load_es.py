from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
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


def main(argv: Optional[List[str]] = None) -> int:
	ap = argparse.ArgumentParser(description="ETL Step 4: Load normalized companies into Elasticsearch")
	ap.add_argument("--input", default="data/staging/companies_serving.ndjson")
	ap.add_argument("--index", default="companies_v1")
	ap.add_argument("--alias", default="companies")
	ap.add_argument("--mappings", default="configs/es.mappings.json")
	ap.add_argument("--es", default="http://localhost:9200")
	ap.add_argument("--dry-run", action="store_true", help="Do not connect to ES, just validate input file")
	ap.add_argument("--no-color", action="store_true", help="Disable colored output")
	args = ap.parse_args(argv)

	inp = Path(args.input)
	mappings = Path(args.mappings)

	# Console
	c = Console(no_color=args.no_color)
	info = c.info
	warn = c.warn
	error = c.error
	success = c.success

	# Preflight checks
	if not inp.exists():
		error("[ETL] Missing input for load: " + str(inp))
		info("[ETL] Run earlier ETL steps or use '--input' to specify a file.")
		return 2

	if args.dry_run:
		# Simple validation
		n = sum(1 for _ in read_ndjson(inp))
		info(f"[ETL] DRY RUN: would index {n} records into {args.index} and alias {args.alias}")
		return 0

	try:
		from elasticsearch import Elasticsearch
		from elasticsearch.helpers import bulk
	except Exception as e:
		error("[ETL] Elasticsearch client not available. Install 'elasticsearch' to load data.")
		return 2

	es = Elasticsearch([args.es])

	# Wait briefly for ES to be ready (helps right after 'make up')
	def _wait_for_es(client, timeout_s: int = 30) -> bool:
		deadline = time.time() + timeout_s
		while time.time() < deadline:
			try:
				if client.ping():
					return True
			except Exception:
				pass
			time.sleep(1)
		return False

	if not _wait_for_es(es, timeout_s=30):
		error(f"[ETL] Elasticsearch at {args.es} is not ready (timeout waiting for ping).")
		info("[ETL] Ensure ES is running (e.g., 'make up') and reachable, then retry.")
		return 3

	# Create index if not exists
	if not es.indices.exists(index=args.index):
		body = {}
		if mappings.exists():
			try:
				text = mappings.read_text(encoding="utf-8").strip()
				if text:
					body = json.loads(text)
				else:
					warn(f"[ETL] Warning: mappings file {mappings} is empty. Creating index with defaults.")
			except Exception as e:
				warn(f"[ETL] Warning: failed to parse mappings at {mappings}: {e}. Creating index with defaults.")
		else:
			warn(f"[ETL] Warning: mappings file not found at {mappings}. Creating index with defaults.")
		es.indices.create(index=args.index, body=body)

	def generate_docs():
		for r in read_ndjson(inp):
			doc_id = r.get("domain") or r.get("id")
			yield {
				"_index": args.index,
				"_id": doc_id,
				"_source": r,
			}

	indexed_count, _ = bulk(es, generate_docs(), chunk_size=500)
	es.indices.put_alias(index=args.index, name=args.alias)
	success(f"[ETL] Loaded {indexed_count} records into index '{args.index}' and alias '{args.alias}'")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())

