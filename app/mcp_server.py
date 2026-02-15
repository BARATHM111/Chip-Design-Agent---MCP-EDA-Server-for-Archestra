
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from .config import PORT

# Create FastMCP instance
mcp = FastMCP(
    "chip-design-agent",
    instructions=(
        "Production-grade MCP server for RTL-to-GDSII chip design. "
        "Wraps Yosys (synthesis), OpenROAD (PnR), and OpenLane (full flow) "
        "via Docker on the Sky130 PDK."
    ),
)

# Configure settings
mcp.settings.port = PORT
mcp.settings.host = "0.0.0.0"

# Security (allow local network)
mcp.settings.transport_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=False,
)
