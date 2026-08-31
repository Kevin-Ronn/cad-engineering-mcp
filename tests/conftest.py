"""Shared pytest fixtures for Phase 1 tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Ensure CAD_ENGINEERING_ROOT points at the actual repo so the
# engineering modules find their YAML manifests.
import os

os.environ.setdefault("CAD_ENGINEERING_ROOT", str(REPO_ROOT))

from cad_engineering_mcp.tools._paths import (  # noqa: E402
    glasses_root,
    project_root,
    reset_project_root_cache,
)


@pytest.fixture(autouse=True)
def _reset_caches():
    """Each test starts with a fresh project-root cache.

    This matters because :func:`project_root` memoises its result and a
    test that monkey-patches ``CAD_ENGINEERING_ROOT`` would otherwise
    leak into other tests.
    """
    reset_project_root_cache()
    yield
    reset_project_root_cache()


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def glasses() -> Path:
    return glasses_root()