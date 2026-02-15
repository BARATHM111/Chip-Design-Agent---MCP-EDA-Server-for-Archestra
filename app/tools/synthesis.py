
from ..mcp_server import mcp
from ..utils import get_workspace, run_docker_cmd, tail, extract_error_details, logger
from ..config import YOSYS_IMAGE, MAX_LOG_TAIL_LINES

@mcp.tool()
def run_yosys_synthesis(project_name: str, top_module: str) -> str:
    """
    Synthesise Verilog RTL to a gate-level netlist using Yosys and the
    Sky130 standard-cell library (sky130_fd_sc_hd, TT corner, 1.8V).

    Auto-generates a synth.tcl script that reads all *.v files from src/,
    runs synthesis targeting Sky130 cells, and writes the netlist to
    reports/synth.v.

    Args:
        project_name: Project whose src/ contains Verilog files.
        top_module: Name of the top-level Verilog module.
    """
    try:
        ws = get_workspace(project_name)
    except ValueError as exc:
        return f"ERROR: {exc}"

    src_dir = ws / "src"
    verilog_files = sorted(src_dir.glob("*.v"))
    if not verilog_files:
        return (
            f"ERROR: No Verilog files (*.v) found in `{src_dir}`.\n\n"
            "Use `write_file` to add your RTL sources first."
        )

    container_ws = "/work"
    container_src = f"{container_ws}/src"
    container_reports = f"{container_ws}/reports"
    container_scripts = f"{container_ws}/scripts"

    read_cmds = "\n".join(
        f"read_verilog {container_src}/{f.name}" for f in verilog_files
    )

    synth_tcl = f"""\
# Auto-generated Yosys synthesis script
# Generic synthesis (technology-independent)
# Top module: {top_module}

{read_cmds}

# Elaborate
hierarchy -check -top {top_module}

# Technology-independent optimisations
proc; opt; fsm; opt; memory; opt

# Synthesise
synth -top {top_module}

# Clean
opt_clean -purge

# Reports
stat
tee -a {container_reports}/synth_stats.txt stat

# Write netlist
write_verilog -noattr {container_reports}/synth.v
"""

    script_path = ws / "scripts" / "synth.tcl"
    script_path.write_text(synth_tcl, encoding="utf-8")
    logger.info("Generated synth.tcl for top=%s", top_module)

    result = run_docker_cmd(
        image=YOSYS_IMAGE,
        volumes={str(ws): container_ws},
        command=f"yosys -s {container_scripts}/synth.tcl",
        workdir=container_ws,
    )

    combined_log = (result["stdout"] + "\n" + result["stderr"]).strip()
    
    # Use smart error extraction if failed, otherwise just tail
    if not result["success"]:
        log_tail = extract_error_details(combined_log)
    else:
        log_tail = tail(combined_log)

    netlist = ws / "reports" / "synth.v"
    stats_file = ws / "reports" / "synth_stats.txt"

    if result["success"]:
        return (
            f"## ✅ Yosys Synthesis Complete\n\n"
            f"- **Top module:** `{top_module}`\n"
            f"- **Duration:** {result['duration_s']}s\n"
            f"- **Netlist:** `{netlist}` "
            f"({'exists' if netlist.exists() else 'NOT FOUND'})\n"
            f"- **Stats:** `{stats_file}`\n\n"
            f"### Log Tail (last {MAX_LOG_TAIL_LINES} lines)\n"
            f"```\n{log_tail}\n```\n"
        )
    else:
        return (
            f"ERROR: Yosys synthesis failed (exit {result['exit_code']}, "
            f"{result['duration_s']}s).\n\n"
            f"### Diagnostic Log\n```\n{log_tail}\n```\n"
        )
