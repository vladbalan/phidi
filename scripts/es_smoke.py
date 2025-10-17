from __future__ import annotations

import argparse
from typing import Optional
try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback for script execution
    import sys as _sys
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[1]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Elasticsearch smoke test: ping, count, sample docs")
    ap.add_argument("--es", default="http://localhost:9200", help="Elasticsearch URL")
    ap.add_argument("--index", default="companies_v1", help="Index to check (used if alias not present)")
    ap.add_argument("--alias", default="companies", help="Alias to check and query")
    ap.add_argument("--size", type=int, default=5, help="Number of sample docs to print")
    args = ap.parse_args(argv)

    c = Console(no_color=False)
    try:
        from elasticsearch import Elasticsearch
    except Exception:
        c.error("[ES] Python client not installed. Install 'elasticsearch>=8,<9' and retry.")
        return 2

    es = Elasticsearch([args.es])

    # Ping
    try:
        ok = es.ping()
    except Exception as e:
        c.error(f"[ES] Ping failed: {e}")
        return 3
    (c.success if ok else c.error)(f"[ES] Ping: {'OK' if ok else 'FAILED'} -> {args.es}")
    if not ok:
        return 3

    # Resolve alias or index
    use_target = args.alias
    try:
        alias_exists = es.indices.exists_alias(name=args.alias)
    except Exception:
        alias_exists = False
    if not alias_exists:
        c.warn(f"[ES] Alias '{args.alias}' not found. Falling back to index '{args.index}'.")
        use_target = args.index

    # Count
    try:
        cnt = es.count(index=use_target)["count"]
    except Exception as e:
        c.error(f"[ES] Count failed on '{use_target}': {e}")
        return 4
    c.info(f"[ES] Docs in '{use_target}': {cnt}")

    # Sample
    try:
        resp = es.search(index=use_target, query={"match_all": {}}, size=max(0, args.size))
        hits = resp.get("hits", {}).get("hits", [])
    except Exception as e:
        c.error(f"[ES] Search failed on '{use_target}': {e}")
        return 5

    if not hits:
        c.warn("[ES] No documents to sample.")
        return 0

    c.info("[ES] Sample docs:")
    for h in hits:
        _id = h.get("_id")
        src = h.get("_source", {})
        domain = src.get("domain") or _id
        phones = src.get("phones")
        linkedin = src.get("linkedin")
        print(f"  - id={_id} domain={domain} phones={len(phones) if isinstance(phones, list) else 0} linkedin={'yes' if linkedin else 'no'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
