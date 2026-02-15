"""
Shared utilities for the MCP EDA Server.

- Workspace management (sanitisation, creation)
- Docker command execution (sandboxed: memory, CPU, network limits)
- Log extraction (smart error parsing, tail)
"""

import logging
import subprocess
import time
from pathlib import Path
from typing import Any

from .config import (
    SAFE_NAME_RE,
    WORKSPACE_ROOT,
    MAX_LOG_TAIL_LINES,
    MAX_LOG_LINE_CHARS,
    DOCKER_TIMEOUT,
    DOCKER_MEMORY_LIMIT,
    DOCKER_CPU_LIMIT,
    DOCKER_NETWORK,
)

logger = logging.getLogger("mcp-eda")


# ── Workspace ────────────────────────────────────────────────────────────────

def sanitize_name(name: str) -> str:
    """Validate a project/file name — only [a-zA-Z0-9_-] allowed."""
    name = name.strip()
    if not name:
        raise ValueError("Name must not be empty.")
    if len(name) > 64:
        raise ValueError("Name must be 64 characters or fewer.")
    if not SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Invalid name '{name}'. Use only letters, digits, hyphens, and underscores."
        )
    return name


def get_workspace(project_name: str) -> Path:
    """Return (and lazily create) the isolated workspace for a project."""
    safe = sanitize_name(project_name)
    ws = WORKSPACE_ROOT / safe
    for subdir in ("src", "scripts", "reports", "runs"):
        (ws / subdir).mkdir(parents=True, exist_ok=True)
    return ws


# ── Log Processing ───────────────────────────────────────────────────────────

def extract_error_details(log_text: str) -> str:
    """
    Intelligently extract error messages from EDA tool logs.

    Scans for ERROR/FATAL/Exception keywords and returns those lines
    with 2 lines of surrounding context. Falls back to tail() if
    no explicit errors are found.
    """
    if not log_text:
        return ""

    lines = log_text.splitlines()
    error_keywords = ("ERROR", "FATAL", "Error:", "Fatal:", "Exception:", "traceback")
    error_indices = [
        i for i, line in enumerate(lines)
        if any(kw in line for kw in error_keywords)
    ]

    if not error_indices:
        return tail(log_text)

    # Collect error lines + 2 lines of context
    context = set()
    for idx in error_indices:
        for i in range(max(0, idx - 2), min(len(lines), idx + 3)):
            context.add(i)

    snippet = []
    prev = -1
    for idx in sorted(context):
        if prev != -1 and idx > prev + 1:
            snippet.append("  ...")
        snippet.append(lines[idx].rstrip())
        prev = idx

    return "\n".join(snippet)


def tail(text: str, n: int = MAX_LOG_TAIL_LINES) -> str:
    """Return the last *n* non-empty lines, truncating long lines."""
    lines = [
        ln.strip()[:MAX_LOG_LINE_CHARS] + "…" if len(ln) > MAX_LOG_LINE_CHARS else ln.strip()
        for ln in text.splitlines() if ln.strip()
    ]
    return "\n".join(lines[-n:])


# ── Docker ───────────────────────────────────────────────────────────────────

def run_docker_cmd(
    image: str,
    volumes: dict[str, str],
    command: str,
    timeout: int = DOCKER_TIMEOUT,
    workdir: str | None = None,
    env_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Execute a command inside a sandboxed Docker container.

    Security: containers run with memory/CPU limits and network isolation.
    """
    docker_args = ["docker", "run", "--rm"]

    # Sandbox flags
    docker_args.extend(["--memory", DOCKER_MEMORY_LIMIT])
    docker_args.extend(["--cpus", DOCKER_CPU_LIMIT])
    docker_args.extend(["--network", DOCKER_NETWORK])
    docker_args.extend(["--pids-limit", "256"])

    # Volumes
    for host_path, container_path in volumes.items():
        docker_args.extend(["-v", f"{host_path}:{container_path}"])
    if workdir:
        docker_args.extend(["-w", workdir])
    if env_vars:
        for key, val in env_vars.items():
            docker_args.extend(["-e", f"{key}={val}"])

    docker_args.extend([image, "bash", "-c", command])
    logger.info("DOCKER_RUN image=%s cmd_len=%d", image, len(command))
    start = time.monotonic()

    try:
        proc = subprocess.run(
            docker_args, capture_output=True, text=True, timeout=timeout,
        )
        elapsed = round(time.monotonic() - start, 2)
        ok = proc.returncode == 0
        level = logging.INFO if ok else logging.WARNING
        logger.log(level, "DOCKER_EXIT code=%d duration=%.1fs", proc.returncode, elapsed)
        return {
            "success": ok,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exit_code": proc.returncode,
            "duration_s": elapsed,
        }
    except FileNotFoundError:
        return _docker_error(start, "Docker is not installed or not in PATH", -1)
    except subprocess.TimeoutExpired:
        return _docker_error(start, f"Docker command timed out after {timeout}s", -2)
    except PermissionError as exc:
        return _docker_error(start, f"Permission denied: {exc}", -3)
    except OSError as exc:
        return _docker_error(start, f"OS error: {exc}", -4)


def _docker_error(start: float, msg: str, code: int) -> dict[str, Any]:
    elapsed = round(time.monotonic() - start, 2)
    logger.error("DOCKER_ERROR %s", msg)
    return {
        "success": False,
        "stdout": "",
        "stderr": msg,
        "exit_code": code,
        "duration_s": elapsed,
    }
