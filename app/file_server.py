"""
Secure static file server for workspace artifacts.

- Serves files from WORKSPACE_ROOT without os.chdir()
- Rejects path traversal attempts
- Requires API key authentication (via query param or header)
- CORS enabled
"""

import hmac
import logging
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from pathlib import Path
from urllib.parse import unquote

from .config import WORKSPACE_ROOT, MCP_API_KEY, FILE_SERVER_PORT

logger = logging.getLogger("mcp-eda.files")


class SecureFileHandler(SimpleHTTPRequestHandler):
    """
    HTTP handler that:
      - Serves from WORKSPACE_ROOT (no os.chdir needed)
      - Blocks directory traversal (..) 
      - Requires API key if configured
      - Adds CORS headers
    """

    def do_GET(self):
        # Auth check
        if not self._check_auth():
            self.send_error(401, "Unauthorized: provide ?api_key= query parameter")
            return

        # Path traversal check
        decoded = unquote(self.path.split("?")[0])
        if ".." in decoded:
            self.send_error(403, "Forbidden: path traversal detected")
            logger.warning("Path traversal blocked: %s from %s", decoded, self.client_address[0])
            return

        super().do_GET()

    def translate_path(self, path: str) -> str:
        """Override to serve from WORKSPACE_ROOT instead of cwd."""
        # Strip query string and decode
        clean = unquote(path.split("?")[0]).lstrip("/")
        resolved = (WORKSPACE_ROOT / clean).resolve()

        # Ensure resolved path is still under WORKSPACE_ROOT
        try:
            resolved.relative_to(WORKSPACE_ROOT.resolve())
        except ValueError:
            logger.warning("Path escape attempt blocked: %s", resolved)
            return str(WORKSPACE_ROOT / "FORBIDDEN")

        return str(resolved)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def log_message(self, fmt, *args):
        """Route HTTP logs through the app logger."""
        logger.debug(fmt, *args)

    def _check_auth(self) -> bool:
        """Validate API key from query param or header."""
        if not MCP_API_KEY:
            return True  # No key configured → open access

        # Check query param
        if "?" in self.path:
            params = dict(
                p.split("=", 1) for p in self.path.split("?", 1)[1].split("&") if "=" in p
            )
            key = params.get("api_key", "")
            if hmac.compare_digest(key.encode(), MCP_API_KEY.encode()):
                return True

        # Check header
        key_header = self.headers.get("X-API-Key", "")
        if key_header and hmac.compare_digest(key_header.encode(), MCP_API_KEY.encode()):
            return True

        return False


def start_file_server():
    """Launch the file server in a daemon thread."""
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)

    def _serve():
        with TCPServer(("", FILE_SERVER_PORT), SecureFileHandler) as httpd:
            logger.info("File server listening on :%d", FILE_SERVER_PORT)
            httpd.serve_forever()

    thread = threading.Thread(target=_serve, daemon=True, name="file-server")
    thread.start()
