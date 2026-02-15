
from pathlib import Path
from ..mcp_server import mcp
from ..utils import get_workspace, run_docker_cmd, logger
from ..config import WORKSPACE_ROOT, OPENLANE_IMAGE, FILE_SERVER_PORT

@mcp.tool()
def get_file_url(project_name: str, file_path: str) -> str:
    """
    Get a downloadable URL for a file in the project workspace.

    Args:
        project_name: Name of the project.
        file_path: Relative path to the file (e.g. runs/run_1/results/signoff/top.gds).
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    clean_path = Path(file_path)
    if ".." in clean_path.parts:
        return "ERROR: Path must not contain '..' components."
    
    target = ws / clean_path
    if not target.exists():
        return f"ERROR: File not found: `{target}`"

    # URL relative to workspace root
    # e.g. http://localhost:8081/project_name/file_path
    rel_path = target.relative_to(WORKSPACE_ROOT)
    url = f"http://localhost:{FILE_SERVER_PORT}/{rel_path.as_posix()}"
    
    return (
        f"## 🔗 File Link\n\n"
        f"**File:** `{clean_path}`\n\n"
        f"[Download / View]({url})\n"
    )

@mcp.tool()
def render_gds_preview(project_name: str, gds_path: str) -> str:
    """
    Generate a PNG image preview of a GDSII layout file using KLayout.
    
    Uses KLayout (inside the OpenLane Docker image) in batch mode to render
    the layout to a PNG image.

    Args:
        project_name: Name of the project.
        gds_path: Relative path to the GDSII file (e.g. runs/run_1/results/signoff/top.gds).
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    gds_file = ws / gds_path
    if not gds_file.exists():
        return f"ERROR: GDS file not found: `{gds_file}`"

    # Output PNG path (on host)
    png_name = gds_file.stem + "_preview.png"
    png_path = gds_file.parent / png_name

    # KLayout batch-mode Python script (runs headless, no X11 needed)
    klayout_script = f"""
import klayout.db as db
import klayout.lay as lay

# Load the GDS
layout = db.Layout()
layout.read("{gds_file.name}")

# Create a LayoutView for rendering
view = lay.LayoutView()
view.load_layout(layout, 0, True)
view.max_hier()
view.zoom_fit()

# Save image
view.save_image("{png_name}", 1200, 900)
print("OK: rendered {png_name}")
"""
    
    # Write script next to the GDS file
    script_file = gds_file.parent / "_render_gds.py"
    script_file.write_text(klayout_script, encoding="utf-8")
    
    work_dir = gds_file.parent
    container_dir = "/work"

    # Run KLayout in batch mode with offscreen Qt platform
    result = run_docker_cmd(
        image=OPENLANE_IMAGE,
        volumes={str(work_dir): container_dir},
        command="klayout -b -r _render_gds.py",
        workdir=container_dir,
        env_vars={"QT_QPA_PLATFORM": "offscreen"},
    )
    
    if not result["success"]:
        return (
            f"ERROR: KLayout rendering failed (exit {result['exit_code']}).\n\n"
            f"### Log\n```\n{result['stderr']}\n{result['stdout']}\n```"
        )

    # Check if PNG was created
    if not png_path.exists():
        return (
            "ERROR: KLayout ran but PNG was not created.\n\n"
            f"### Log\n```\n{result['stdout']}\n{result['stderr']}\n```"
        )

    # Return markdown image + download link
    rel_path = png_path.relative_to(WORKSPACE_ROOT)
    url = f"http://localhost:{FILE_SERVER_PORT}/{rel_path.as_posix()}"
    
    return (
        f"## 🖼️ GDS Preview\n\n"
        f"**Source:** `{gds_path}`\n"
        f"![Layout Preview]({url})\n\n"
        f"[Download Original GDS]({get_file_url(project_name, gds_path)})"
    )
