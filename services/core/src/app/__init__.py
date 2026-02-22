from __future__ import annotations

from pathlib import Path

# Transitional bridge for src layout migration.
_legacy_app_dir = Path(__file__).resolve().parents[2] / "app"
if _legacy_app_dir.is_dir():
    __path__.append(str(_legacy_app_dir))
