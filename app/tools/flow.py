
import json
import time
from pathlib import Path

from ..mcp_server import mcp
from ..utils import get_workspace, run_docker_cmd, tail, extract_error_details, logger
from ..config import OPENLANE_IMAGE

@mcp.tool()
def run_openlane_flow(
    project_name: str,
    top_module: str,
    clock_period_ns: float = 10.0,
    core_utilization: int = 50,
    pdk: str = "sky130A",
) -> str:
    """
    Run a complete OpenLane RTL-to-GDSII flow in Docker.

    Full pipeline: synthesis → floorplan → placement → CTS → routing → signoff → GDSII.

    Args:
        project_name: Project with RTL sources in src/.
        top_module: Top-level module name.
        clock_period_ns: Target clock period in nanoseconds (default: 10).
        core_utilization: Core area utilisation percentage (default: 50).
        pdk: PDK — sky130A, sky130B, or gf180mcuD (default: sky130A).
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    src_dir = ws / "src"
    verilog_files = sorted(src_dir.glob("*.v"))
    if not verilog_files:
        return f"ERROR: No Verilog files found in `{src_dir}`."

    config = {
        "DESIGN_NAME": top_module,
        "VERILOG_FILES": "dir::src/*.v",
        "CLOCK_PORT": "clk",
        "CLOCK_PERIOD": clock_period_ns,
        "FP_CORE_UTIL": core_utilization,
        "PDK": pdk,
        # PDN fix: disable auto-adjust so our pitch values actually apply
        "FP_PDN_AUTO_ADJUST": 0,
        "FP_PDN_VPITCH": 50,
        "FP_PDN_HPITCH": 50,
        "FP_PDN_VOFFSET": 5,
        "FP_PDN_HOFFSET": 5,
        # Ensure die is large enough for the PDN grid (especially small designs)
        "FP_SIZING": "absolute",
        "DIE_AREA": "0 0 200 200",
    }

    config_path = ws / "config.json"
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    run_id = f"run_{int(time.time())}"
    
    # PDK cache is located in the parent folder of the app package (chip-mcp-server/pdk_cache)
    # This file is in app/tools/flow.py -> parent is app/tools -> parent is app -> parent is chip-mcp-server
    pdk_cache_dir = str(Path(__file__).resolve().parent.parent.parent / "pdk_cache")
    
    # Use a separate mount point for the host workspace to avoid running directly
    # on the mounted volume (which causes 'sed -i' permission errors on Windows)
    host_ws_mount = "/mnt/host_ws"
    internal_ws = "/work"

    result = run_docker_cmd(
        image=OPENLANE_IMAGE,
        volumes={
            str(ws): host_ws_mount,
            pdk_cache_dir: "/root/.volare",
        },
        command=(
            f"mkdir -p {internal_ws} && "
            f"cp -r {host_ws_mount}/src {internal_ws}/src && "
            f"cp {host_ws_mount}/config.json {internal_ws}/config.json && "
            f"flow.tcl -design {internal_ws} -tag {run_id} -overwrite && "
            f"cp -r {internal_ws}/runs/{run_id} {host_ws_mount}/runs/"
        ),
        workdir=internal_ws,
        env_vars={"PDK_ROOT": "/root/.volare"},
        timeout=3600,
    )

    combined_log = (result["stdout"] + "\n" + result["stderr"]).strip()
    
    if not result["success"]:
        log_detail = extract_error_details(combined_log)
        return (
            f"ERROR: OpenLane flow failed "
            f"(exit {result['exit_code']}, {result['duration_s']}s).\n\n"
            f"### Diagnostic Log\n```\n{log_detail}\n```\n"
        )

    log_tail = tail(combined_log, 30)
    return (
        f"## ✅ OpenLane Flow Complete\n\n"
        f"- **Run ID:** `{run_id}`\n"
        f"- **Top module:** `{top_module}`\n"
        f"- **PDK:** `{pdk}`\n"
        f"- **Clock period:** {clock_period_ns} ns\n"
        f"- **Core utilisation:** {core_utilization}%\n"
        f"- **Duration:** {result['duration_s']}s\n\n"
        f"### Log Tail\n```\n{log_tail}\n```\n\n"
        f"Use `read_metrics` to inspect reports in `runs/{run_id}/reports/`."
    )
