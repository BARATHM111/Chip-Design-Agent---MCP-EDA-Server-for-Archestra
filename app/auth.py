"""
Authentication & security middleware for the MCP EDA Server.

- Constant-time API key comparison (prevents timing attacks)
- Per-IP rate limiting (in-memory, configurable RPM)
- CORS headers
- Structured audit logging
"""

import hmac
import time
import logging
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import MCP_API_KEY, RATE_LIMIT_RPM, ALLOWED_ORIGINS

logger = logging.getLogger("mcp-eda.auth")


# ── Rate Limiter (in-memory, per-IP) ─────────────────────────────────────────

class _RateLimiter:
    """Simple sliding-window rate limiter keyed by client IP."""

    def __init__(self, max_rpm: int):
        self._max = max_rpm
        self._windows: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.monotonic()
        window = self._windows[client_ip]
        # Purge entries older than 60s
        self._windows[client_ip] = [t for t in window if now - t < 60]
        if len(self._windows[client_ip]) >= self._max:
            return False
        self._windows[client_ip].append(now)
        return True


_limiter = _RateLimiter(RATE_LIMIT_RPM)


# ── Middleware ────────────────────────────────────────────────────────────────

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Combined security middleware:
      1. CORS headers
      2. Rate limiting
      3. API key authentication (constant-time)
    """

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"

        # ── CORS preflight ───────────────────────────────────────────────
        if request.method == "OPTIONS":
            return self._cors_response(Response(status_code=204))

        # ── Rate limiting ────────────────────────────────────────────────
        if not _limiter.is_allowed(client_ip):
            logger.warning("Rate limit exceeded: %s", client_ip)
            return self._cors_response(JSONResponse(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
            ))

        # ── Authentication ───────────────────────────────────────────────
        if MCP_API_KEY:
            provided_key = self._extract_key(request)
            if not provided_key or not hmac.compare_digest(
                provided_key.encode(), MCP_API_KEY.encode()
            ):
                logger.warning("AUTH_FAIL ip=%s path=%s", client_ip, request.url.path)
                return self._cors_response(JSONResponse(
                    {"error": "Unauthorized: invalid or missing API key"},
                    status_code=401,
                ))

        # ── Proceed ──────────────────────────────────────────────────────
        response = await call_next(request)
        return self._cors_response(response)

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_key(request: Request) -> str | None:
        """Extract API key from header, bearer token, or query param."""
        # X-API-Key header (preferred)
        key = request.headers.get("X-API-Key")
        if key:
            return key

        # Authorization: Bearer <key>
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]

        # Query param fallback (for SSE/EventSource)
        return request.query_params.get("api_key")

    @staticmethod
    def _cors_response(response: Response) -> Response:
        """Inject CORS headers into any response."""
        origin = "*" if "*" in ALLOWED_ORIGINS else ", ".join(ALLOWED_ORIGINS)
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-API-Key, Authorization"
        return response
