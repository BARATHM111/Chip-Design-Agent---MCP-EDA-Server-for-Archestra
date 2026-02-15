"""
Centralised configuration for the MCP EDA Server.

All settings are loaded from environment variables with sensible defaults.
A `.env` file in the project root is automatically loaded if present.
"""

import os
import re
from pathlib import Path

# Load .env file if present (before reading os.environ)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass  # python-dotenv is optional for local dev

# ── Paths ────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT / "workspace"

# ── Server ───────────────────────────────────────────────────────────────────

PORT = int(os.environ.get("PORT", "3334"))
HOST = os.environ.get("HOST", "0.0.0.0")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# ── Authentication ───────────────────────────────────────────────────────────

MCP_API_KEY = os.environ.get("MCP_API_KEY", "")

# ── Rate Limiting ────────────────────────────────────────────────────────────

RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "60"))

# ── CORS ─────────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get("ALLOWED_ORIGINS", "*").split(",")
    if o.strip()
]

# ── Docker ───────────────────────────────────────────────────────────────────

YOSYS_IMAGE = os.environ.get("YOSYS_DOCKER_IMAGE", "yosys:local")
OPENROAD_IMAGE = os.environ.get("OPENROAD_DOCKER_IMAGE", "openroad:local")
OPENLANE_IMAGE = os.environ.get("OPENLANE_DOCKER_IMAGE", "efabless/openlane:latest")

DOCKER_TIMEOUT = int(os.environ.get("EDA_TIMEOUT_SECONDS", "600"))
DOCKER_MEMORY_LIMIT = os.environ.get("DOCKER_MEMORY_LIMIT", "4g")
DOCKER_CPU_LIMIT = os.environ.get("DOCKER_CPU_LIMIT", "2")
DOCKER_NETWORK = os.environ.get("DOCKER_NETWORK", "none")

# ── File Server ──────────────────────────────────────────────────────────────

FILE_SERVER_PORT = int(os.environ.get("FILE_SERVER_PORT", "8081"))

# ── Validation ───────────────────────────────────────────────────────────────

SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")

# ── Sky130 PDK Paths (inside Docker images) ──────────────────────────────────

SKY130_LIB = "/opt/pdk/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
SKY130_LEF = "/opt/pdk/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
SKY130_TLEF = "/opt/pdk/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef"

# ── Log Limits ───────────────────────────────────────────────────────────────

MAX_LOG_TAIL_LINES = 20
MAX_LOG_LINE_CHARS = 500
