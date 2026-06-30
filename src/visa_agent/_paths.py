"""Path resolution that works both in development and under PyInstaller."""
from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[2]


def app_dir() -> Path:
    return project_root() / "app"


def docs_dir() -> Path:
    return project_root() / "docs"


def sample_data_dir() -> Path:
    return project_root() / "sample_data"
