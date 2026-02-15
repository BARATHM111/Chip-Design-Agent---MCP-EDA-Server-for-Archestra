# Chip Design Agent — MCP EDA Server

An MCP server that gives AI agents the ability to design, synthesize, and fabricate digital chips using open-source EDA tools — entirely through natural language.

## What it does

The Chip Design Agent turns Archestra's AI into a fabless chip design engineer. A user describes a digital circuit in plain English, and the agent autonomously:

1. **Writes synthesizable Verilog RTL** from the specification
2. **Synthesizes** the design to a gate-level netlist using **Yosys** (Sky130 PDK)
3. **Runs the full RTL-to-GDSII flow** via **OpenLane** (floorplanning → placement → CTS → routing → signoff)
4. **Analyzes PPA metrics** (Power, Performance, Area) from the run
5. **Renders a visual preview** of the final GDSII layout

## MCP Tools

| Tool | Description |
|------|-------------|
| `initialize_project` | Create a new project workspace |
| `write_file` | Write Verilog RTL or config files |
| `list_project_files` | Browse project outputs |
| `run_yosys_synthesis` | Synthesize RTL → gate-level netlist |
| `run_openroad_task` | Run OpenROAD physical design tasks |
| `run_openlane_flow` | Full automated RTL-to-GDSII flow |
| `read_metrics` | Analyze PPA reports |
| `get_file_url` | Get download links for outputs |
| `render_gds_preview` | Generate PNG preview of GDS layout |

## Architecture

```
┌─────────────────────┐     ┌──────────────────┐
│  Archestra Agent    │────▶│  MCP EDA Server   │
│  (Claude / LLM)     │◀────│  (FastMCP/Python)  │
└─────────────────────┘     └────────┬─────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
              ┌──────────┐   ┌────────────┐   ┌──────────────┐
              │  Yosys   │   │  OpenROAD  │   │  OpenLane    │
              │ (Docker) │   │  (Docker)  │   │  (Docker)    │
              └──────────┘   └────────────┘   └──────────────┘
                              Sky130 PDK
```

## Security

- 🔐 Timing-safe API key authentication (`hmac.compare_digest`)
- 🚦 Per-IP rate limiting (configurable RPM)
- 🌐 CORS with configurable origins
- 🛡️ File server path-traversal protection
- 🐳 Docker sandbox (memory/CPU/network/PID limits)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure (optional)
cp .env.example .env
# Edit .env with your API key

# 3. Run
python server.py
```

## Deployment

### Self-hosted (Archestra K8s)

```bash
docker build -t chip-mcp-server .
docker tag chip-mcp-server docker.io/<username>/chip-mcp-server:latest
docker push docker.io/<username>/chip-mcp-server:latest
```

Then add to Archestra Private Registry with `MCP_TRANSPORT=stdio`.

### Local with ngrok

```bash
run_live.bat
```

## Built With

`Python` · `FastMCP` · `Docker` · `Yosys` · `OpenLane` · `OpenROAD` · `Sky130 PDK` · `Archestra`

## License

MIT
