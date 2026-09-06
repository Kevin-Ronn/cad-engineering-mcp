"""Module entry point so the MCP server can be launched as:

    python -m cad_engineering_mcp

without any absolute path baked into the launch configuration.

Resolution of the project root is handled by
``cad_engineering_mcp.tools._paths.resolve_project_root``, which
honours the ``CAD_ENGINEERING_ROOT`` environment variable and falls
back to walking up from this file's location. No host-specific paths
are hard-coded.
"""
from __future__ import annotations

import sys


def main() -> int:
    """Launch the MCP server via ``python -m cad_engineering_mcp``.

    Importing is deferred so that ``--help`` style introspection
    does not require all heavy dependencies to load.
    """
    from .server import mcp  # noqa: WPS433 (intentional late import)

    # ``mcp.run()`` is the standard MCP server entry point. It honours
    # the stdio transport selected by Claude Code / Claude Desktop
    # via the .mcp.json configuration.
    mcp.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
