"""Tests for the portable MCP launch mechanism (P0-1 fix).

Verifies that:

* ``python -m cad_engineering_mcp`` can be invoked and the package's
  ``__main__`` module imports without host-specific paths.
* The installed console-script entry point resolves to the same
  function as ``__main__.main``.
* The package is importable from any cwd once ``CAD_ENGINEERING_ROOT``
  is set (no hard-coded ``/home/hackerman`` paths).

No actual MCP stdio server is started -- that would block. We only
verify that the launch surface is well-formed.
"""
from __future__ import annotations

import importlib
import importlib.metadata
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"


def _run(cmd, **kwargs):
    return subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CAD_ENGINEERING_ROOT": str(REPO_ROOT),
            "PYTHONPATH": str(SRC),
        },
        **kwargs,
    )


def test_package_is_importable():
    """The top-level package + its ``__main__`` module must import cleanly
    and expose a callable ``main()`` entry point."""
    import cad_engineering_mcp  # noqa: F401
    main_mod = importlib.import_module("cad_engineering_mcp.__main__")
    assert callable(getattr(main_mod, "main", None))


def test_main_module_has_callable_main():
    """The ``__main__`` module exposes a ``main()`` callable."""
    main_mod = importlib.import_module("cad_engineering_mcp.__main__")
    assert callable(getattr(main_mod, "main", None))


def test_console_script_entry_point_resolves():
    """The pyproject.toml console-script entry point resolves to
    ``cad_engineering_mcp.__main__:main``.

    This guards against an accidental rename or wrong target that
    would break ``pip install -e .`` consumers.
    """
    scripts = importlib.metadata.entry_points(group="console_scripts")
    candidates = [ep for ep in scripts if ep.name == "cad-engineering-mcp"]
    if not candidates:
        pytest.skip(
            "Package is not installed in the current environment "
            "(console_scripts entry point unavailable)"
        )
    ep = candidates[0]
    module, _, attr = ep.value.partition(":")
    assert module == "cad_engineering_mcp.__main__"
    assert attr == "main"


def test_python_m_cad_engineering_mcp_imports_without_hardcoded_paths():
    """The package must be importable via ``python -m
    cad_engineering_mcp`` (which is what ``.mcp.json`` now invokes).
    The actual MCP server would block on stdio so we only verify
    the module loads.
    """
    result = _run(
        [
            sys.executable,
            "-c",
            "import cad_engineering_mcp.__main__ as m; "
            "print(m.__file__); assert callable(m.main)",
        ],
    )
    assert result.returncode == 0, (
        f"python -c import failed:\nstdout={result.stdout}\n"
        f"stderr={result.stderr}"
    )
    # The resolved module path must live inside the package's src/
    # tree -- this confirms there is no host-specific hard-coding.
    assert "cad_engineering_mcp/__main__.py" in result.stdout


def test_no_host_specific_paths_in_launcher_metadata():
    """Explicit regression for P0-1: the launcher surface must not
    embed any host-specific path. We scan the four files a launcher
    ever touches: ``.mcp.json``, ``pyproject.toml``, ``__main__.py``,
    ``server.py``.
    """
    bad = ("/home/hackerman", "C:\\\\Users\\\\", "/Users/")
    sources = [
        REPO_ROOT / ".mcp.json",
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "src" / "cad_engineering_mcp" / "__main__.py",
        REPO_ROOT / "src" / "cad_engineering_mcp" / "server.py",
    ]
    for path in sources:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for needle in bad:
            candidates = {needle}
            if "\\" in needle:
                candidates.add(needle.replace("\\", "/"))
            for n in candidates:
                assert n not in text, (
                    f"{path} contains hard-coded host path {n!r}"
                )
