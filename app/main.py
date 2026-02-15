"""
MCP EDA Server — Application entry point.

Supports two transport modes (set via MCP_TRANSPORT env var):
  - "stdio"            : JSON-RPC over stdin/stdout (for K8s / Archestra self-hosted)
  - "streamable-http"  : HTTP server on PORT (for local / remote deployment)
"""

import os
import logging

import uvicorn

from .mcp_server import mcp
from .config import PORT, HOST, MCP_API_KEY, FILE_SERVER_PORT
from .auth import SecurityMiddleware
from .file_server import start_file_server

# Import tool modules to register them via @mcp.tool()
from .tools import workspace, synthesis, physical, reports, flow, visualization  # noqa: F401

logger = logging.getLogger("mcp-eda")

TRANSPORT = os.environ.get("MCP_TRANSPORT", "streamable-http").lower()


def main():
    """Start the MCP EDA Server."""

    logger.info("MCP EDA Server v2.0 starting")
    logger.info("  Transport : %s", TRANSPORT)

    if TRANSPORT == "stdio":
        # ── stdio mode (K8s / Archestra self-hosted) ─────────────────────
        # No file server, no HTTP, just JSON-RPC over stdin/stdout
        logger.info("  Mode      : stdio (K8s)")
        mcp.run(transport="stdio")

    else:
        # ── Streamable HTTP mode (local / remote) ────────────────────────
        start_file_server()

        logger.info("  MCP       : http://%s:%d/mcp", HOST, PORT)
        logger.info("  Files     : http://%s:%d", HOST, FILE_SERVER_PORT)
        logger.info("  Auth      : %s", "ENABLED" if MCP_API_KEY else "DISABLED")

        asgi_app = mcp.streamable_http_app()
        secured_app = SecurityMiddleware(asgi_app)

        uvicorn.run(
            secured_app,
            host=HOST,
            port=PORT,
            log_level="warning",
        )
