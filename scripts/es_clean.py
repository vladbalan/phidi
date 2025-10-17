from __future__ import annotations

import argparse
from typing import Optional, List

try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback for script execution
    import sys as _sys
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[1]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Delete Elasticsearch documents by removing indices behind an alias or a specific index.")
    ap.add_argument("--es", default="http://localhost:9200", help="Elasticsearch URL")
    ap.add_argument("--index", default="companies_v1", help="Index to delete if alias not present or as an additional target")
    ap.add_argument("--alias", default="companies", help="Alias whose backing indices should be deleted if present")
    ap.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = ap.parse_args(argv)

    c = Console(no_color=args.no_color)

    try:
        from elasticsearch import Elasticsearch
    except Exception:
        c.error("[ES] Python client not installed. Install 'elasticsearch>=8,<9' and retry.")
        return 2

    es = Elasticsearch([args.es])

    # Gather targets to delete: indices behind alias (if any), otherwise the provided index
    targets: List[str] = []
    try:
        if es.indices.exists_alias(name=args.alias):
            try:
                alias_info = es.indices.get_alias(name=args.alias)
                targets.extend(sorted(alias_info.keys()))
            except Exception as e:
                c.warn(f"[ES] Could not resolve alias '{args.alias}': {e}")
        else:
            c.warn(f"[ES] Alias '{args.alias}' not found. Will consider index '{args.index}'.")
    except Exception as e:
        c.warn(f"[ES] Failed to check alias '{args.alias}': {e}. Will consider index '{args.index}'.")

    # If no targets from alias, fall back to the explicit index
    if not targets:
        targets = [args.index]

    # Filter to only existing indices
    existing_targets: List[str] = []
    for idx in targets:
        try:
            if es.indices.exists(index=idx):
                existing_targets.append(idx)
            else:
                c.warn(f"[ES] Index '{idx}' does not exist; skipping.")
        except Exception as e:
            c.warn(f"[ES] Failed to check index '{idx}': {e}")

    if not existing_targets:
        c.info("[ES] Nothing to delete.")
        return 0

    c.info(f"[ES] Deleting indices: {', '.join(existing_targets)}")
    failed = False
    for idx in existing_targets:
        try:
            es.indices.delete(index=idx, ignore_unavailable=True)
            c.success(f"[ES] Deleted index '{idx}'")
        except Exception as e:
            failed = True
            c.error(f"[ES] Failed to delete index '{idx}': {e}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
