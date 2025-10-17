"""
Test configuration: ensure project root is importable so tests can import from src/.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
	here = Path(__file__).resolve()
	repo_root = here.parent.parent
	if str(repo_root) not in sys.path:
		sys.path.insert(0, str(repo_root))


_ensure_repo_root_on_path()

