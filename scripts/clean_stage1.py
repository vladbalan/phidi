from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Robust import of shared console helper when run as a script
try:
    from src.common.console import Console
except Exception:  # pragma: no cover - fallback for script execution
    from pathlib import Path as _Path
    _repo_root = _Path(__file__).resolve().parents[1]
    if str(_repo_root) not in sys.path:
        sys.path.insert(0, str(_repo_root))
    from src.common.console import Console  # type: ignore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean Stage 1 generated files")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    c = Console(no_color=args.no_color)
    c.info("[CLEAN] Stage 1: Removing generated files...")

    targets = [
        root / "data/outputs/python_results.ndjson",
        root / "data/outputs/node_results.ndjson",
        root / "data/reports/metrics.csv",
        root / "data/reports/summary.md",
        root / "data/reports/api_match_results.csv",
        root / "data/reports/api_match_summary.json",
        root / "data/reports/api_match_report.md",
        root / "data/staging/crawl_results.ndjson",
        root / "data/staging/manifest.json",
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

    c.success(f"[CLEAN] Stage 1 complete. Files removed: {removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
