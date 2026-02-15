
from typing import Any
from ..mcp_server import mcp
from ..utils import get_workspace, run_docker_cmd, tail, extract_error_details, logger
from ..config import OPENROAD_IMAGE, SKY130_TLEF, SKY130_LEF, SKY130_LIB

@mcp.tool()
def run_openroad_task(
    project_name: str,
    task: str,
    params: dict[str, Any] | None = None,
    tcl_body: str | None = None,
) -> str:
    """
    Run an OpenROAD physical-design task using templated TCL.

    Supports: floorplan, place, cts, route, timing, custom.
    Parameters (params dict) are injected as 'set key value' in the TCL script.
    For example: params={"utilization": 0.6} becomes "set utilization 0.6".

    Args:
        project_name: Project with synthesis outputs in reports/synth.v.
        task: One of: floorplan, place, cts, route, timing, custom.
        params: Dict of TCL variables to inject.
        tcl_body: Raw TCL code for 'custom' tasks only.
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    params = params or {}
    task_lower = task.strip().lower()
    container_ws = "/work"
    container_reports = f"{container_ws}/reports"

    # Parameter injection header
    param_lines = "\n".join(f"set {k} {v}" for k, v in params.items())
    param_header = f"# ── Injected parameters ──\n{param_lines}\n\n" if param_lines else ""

    preamble = f"""\
# Auto-generated OpenROAD script — task: {task_lower}
{param_header}\
read_lef {SKY130_TLEF}
read_lef {SKY130_LEF}
read_verilog {container_reports}/synth.v
link_design
"""

    task_bodies = {
        "floorplan": f"""\
initialize_floorplan \\
    -utilization [expr {{[info exists utilization] ? $utilization : 50}}] \\
    -aspect_ratio [expr {{[info exists aspect_ratio] ? $aspect_ratio : 1.0}}] \\
    -core_space [expr {{[info exists core_margin] ? $core_margin : 2}}]

source $::env(SCRIPTS_DIR)/io_placement_random.tcl
tap_cell_insertion
global_placement -skip_io

report_design_area
write_def {container_reports}/floorplan.def
""",
        "place": f"""\
read_def {container_reports}/floorplan.def

global_placement -density [expr {{[info exists density] ? $density : 0.6}}]
detailed_placement
check_placement

report_design_area
write_def {container_reports}/placed.def
""",
        "cts": f"""\
read_def {container_reports}/placed.def

clock_tree_synthesis \\
    -buf_list [expr {{[info exists cts_buf_list] ? $cts_buf_list : "sky130_fd_sc_hd__clkbuf_4"}}] \\
    -root_buf [expr {{[info exists cts_root_buf] ? $cts_root_buf : "sky130_fd_sc_hd__clkbuf_16"}}]

report_cts
write_def {container_reports}/cts.def
""",
        "route": f"""\
read_def {container_reports}/cts.def

global_route -verbose
detailed_route

check_antennas
report_design_area
write_def {container_reports}/routed.def
""",
        "timing": f"""\
read_def {container_reports}/routed.def
read_liberty {SKY130_LIB}

create_clock -name clk \\
    -period [expr {{[info exists clock_period] ? $clock_period : 10.0}}] \\
    [get_ports {{clk}}]

report_checks -path_delay min_max -format full_clock_expanded
report_wns
report_tns
report_worst_slack -max
report_worst_slack -min
""",
    }

    if task_lower == "custom":
        if not tcl_body:
            return "ERROR: `tcl_body` is required for custom tasks."
        body = tcl_body
    elif task_lower in task_bodies:
        body = task_bodies[task_lower]
    else:
        valid = ", ".join(list(task_bodies.keys()) + ["custom"])
        return f"ERROR: Unknown task `{task}`. Valid tasks: {valid}"

    full_tcl = preamble + body
    script_path = ws / "scripts" / f"openroad_{task_lower}.tcl"
    script_path.write_text(full_tcl, encoding="utf-8")
    logger.info("Generated OpenROAD script: %s", script_path)

    result = run_docker_cmd(
        image=OPENROAD_IMAGE,
        volumes={str(ws): container_ws},
        command=f"openroad -no_init {container_ws}/scripts/openroad_{task_lower}.tcl",
        workdir=container_ws,
    )

    combined_log = (result["stdout"] + "\n" + result["stderr"]).strip()
    
    if not result["success"]:
        log_detail = extract_error_details(combined_log)
        return (
            f"ERROR: OpenROAD `{task_lower}` failed "
            f"(exit {result['exit_code']}, {result['duration_s']}s).\n\n"
            f"### Diagnostic Log\n```\n{log_detail}\n```\n"
        )

    log_tail = tail(combined_log)
    return (
        f"## ✅ OpenROAD `{task_lower}` Complete\n\n"
        f"- **Duration:** {result['duration_s']}s\n"
        f"- **Script:** `{script_path}`\n"
        f"- **Injected params:** {params or 'none'}\n\n"
        f"### Log Tail\n```\n{log_tail}\n```\n"
    )
