
import os
from pathlib import Path

from ..mcp_server import mcp
from ..utils import get_workspace, logger
from ..config import WORKSPACE_ROOT

@mcp.tool()
def initialize_project(project_name: str) -> str:
    """
    Create a clean, isolated workspace for a new chip-design project.

    Sets up the directory structure required by subsequent tools:
      - src/       — Verilog / SystemVerilog source files
      - scripts/   — Auto-generated TCL scripts for Yosys & OpenROAD
      - reports/   — Synthesis and PnR report outputs
      - runs/      — OpenLane full-flow run directories

    Args:
        project_name: Alphanumeric name (hyphens/underscores OK). No path separators.
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    logger.info("Initialized project: %s", ws)
    return (
        f"## ✅ Project `{project_name}` Initialized\n\n"
        f"**Workspace:** `{ws}`\n\n"
        f"| Directory   | Purpose                              |\n"
        f"|-------------|--------------------------------------|\n"
        f"| `src/`      | Verilog / SystemVerilog source files  |\n"
        f"| `scripts/`  | Auto-generated TCL scripts           |\n"
        f"| `reports/`  | Synthesis & PnR reports               |\n"
        f"| `runs/`     | OpenLane full-flow runs               |\n\n"
        f"**Next step →** Use `write_file` to add your RTL sources to `src/`."
    )


@mcp.tool()
def write_file(project_name: str, filename: str, content: str) -> str:
    """
    Write a file into the project workspace.

    Supports Verilog RTL, TCL scripts, config files, constraints (.sdc), etc.
    Subdirectories in the filename (e.g. src/counter.v) are created automatically.

    Args:
        project_name: Name of an existing project.
        filename: Relative path within the workspace (e.g. src/counter.v).
        content: Full text content of the file.
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    clean_filename = Path(filename)
    if ".." in clean_filename.parts:
        return "ERROR: Filename must not contain '..' path components."

    target = ws / clean_filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")

    size = target.stat().st_size
    logger.info("Wrote %s (%d bytes)", target, size)
    return (
        f"## ✅ File Written\n\n"
        f"- **Path:** `{target}`\n"
        f"- **Size:** {size:,} bytes\n"
        f"- **Lines:** {len(content.splitlines())}\n"
    )

@mcp.tool()
def list_projects() -> str:
    """List all chip-design projects in the workspace with file counts and sizes."""
    if not WORKSPACE_ROOT.exists():
        return "No workspace directory found. Use `initialize_project` to create one."

    projects = sorted(d for d in WORKSPACE_ROOT.iterdir() if d.is_dir())
    if not projects:
        return "No projects found. Use `initialize_project` to create one."

    rows = []
    for proj in projects:
        files = list(proj.rglob("*"))
        file_count = sum(1 for f in files if f.is_file())
        total_size = sum(f.stat().st_size for f in files if f.is_file())
        has_netlist = (proj / "reports" / "synth.v").exists()
        rows.append(
            f"| `{proj.name}` | {file_count} | "
            f"{total_size:,} B | {'✅' if has_netlist else '—'} |"
        )

    return (
        f"## 🗂️ Projects ({len(projects)})\n\n"
        f"| Name | Files | Size | Netlist? |\n"
        f"|------|-------|------|----------|\n"
        + "\n".join(rows) + "\n"
    )


@mcp.tool()
def list_project_files(project_name: str) -> str:
    """List all files in a project workspace with their sizes.
    
    Filters out noisy directories like runs/*/tmp and runs/*/logs to reduce output size.
    Caps output at 200 files.

    Args:
        project_name: Name of the project to inspect.
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    files = []
    skipped_count = 0
    max_files = 200

    # Walk the directory manually to filter out noisy folders
    for root, dirs, filenames in os.walk(ws):
        rel_root = Path(root).relative_to(ws)
        
        # Skip noisy internal directories in runs/
        if "runs" in rel_root.parts:
            # identifying if we are in a run directory
            run_parts = list(rel_root.parts)
            try:
                run_idx = run_parts.index("runs")
                if len(run_parts) > run_idx + 1:
                    subdir = run_parts[run_idx + 2] if len(run_parts) > run_idx + 2 else ""
                    # Filter out tmp, logs, and other noisy folders
                    if subdir in ("tmp", "logs", "reports"):
                        dirs[:] = [] # Stop recursing
                        continue
            except (ValueError, IndexError):
                pass

        for f in filenames:
            if len(files) >= max_files:
                skipped_count += 1
                continue
            files.append(Path(root) / f)
    
    files.sort()
    
    lines = []
    for f in files:
        rel = f.relative_to(ws)
        lines.append(f"  📄 `{rel}` ({f.stat().st_size:,} B)")

    if skipped_count > 0:
        lines.append(f"\n  ... and {skipped_count} more files (hidden to reduce output size).")

    return (
        f"## 📁 Project `{project_name}`\n\n"
        f"**Root:** `{ws}`\n\n"
        + "\n".join(lines) + "\n"
    )
