from __future__ import annotations

import argparse
from pathlib import Path

# Prefer direct import; scripts are run from repo root
try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback for script execution
    import sys as _sys
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[1]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean Stage 2 ETL outputs")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    c = Console(no_color=args.no_color)
    c.info("[CLEAN] Stage 2: Removing ETL outputs...")

    targets = [
        root / "data/staging/crawl_results_normalized.ndjson",
        root / "data/staging/crawl_results_merged.ndjson",
        root / "data/staging/companies_serving.ndjson",
    ]

    removed = 0
    for p in targets:
        try:
            if p.exists():
                p.unlink()
                rel = p.relative_to(root)
                c.warn(f"[DEL] {rel}")
                removed += 1
        except Exception as e:
            c.error(f"[SKIP] {p} -> {e}")

    c.success(f"[CLEAN] Stage 2 complete. Files removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
