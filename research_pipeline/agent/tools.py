"""Tool definitions for agents to interact with the filesystem and execute code."""

from __future__ import annotations

import subprocess
from pathlib import Path

import structlog

log = structlog.get_logger()

TOOL_DEFINITIONS = [
    {
        "name": "write_file",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to output directory"},
                "content": {"type": "string", "description": "File content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the content of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to output directory"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command and return its output. Use for running Python scripts, tests, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 30)",
                    "default": 30,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "list_files",
        "description": "List files in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path relative to output directory",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "report_analysis",
        "description": "Report structured analysis results. Used by reader agents to return paper analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "analysis": {
                    "type": "object",
                    "description": "Structured analysis object",
                },
            },
            "required": ["analysis"],
        },
    },
    {
        "name": "report_result",
        "description": "Report the final result of the agent's work.",
        "input_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean", "description": "Whether the task succeeded"},
                "summary": {"type": "string", "description": "Brief summary of what was done"},
                "data": {"type": "object", "description": "Any structured data to return"},
            },
            "required": ["success", "summary"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict, work_dir: Path) -> str:
    """Execute a tool call and return the result as a string."""
    match tool_name:
        case "write_file":
            return _write_file(tool_input, work_dir)
        case "read_file":
            return _read_file(tool_input, work_dir)
        case "run_command":
            return _run_command(tool_input, work_dir)
        case "list_files":
            return _list_files(tool_input, work_dir)
        case "report_analysis" | "report_result":
            return "Result recorded."
        case _:
            return f"Unknown tool: {tool_name}"


def _write_file(input: dict, work_dir: Path) -> str:
    path = work_dir / input["path"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(input["content"])
    log.info("tool_write_file", path=str(path))
    return f"Written to {input['path']}"


def _read_file(input: dict, work_dir: Path) -> str:
    path = work_dir / input["path"]
    if not path.exists():
        return f"File not found: {input['path']}"
    content = path.read_text()
    if len(content) > 50_000:
        return content[:50_000] + "\n\n... (truncated)"
    return content


def _run_command(input: dict, work_dir: Path) -> str:
    command = input["command"]
    timeout = input.get("timeout", 30)
    log.info("tool_run_command", command=command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
        if result.returncode != 0:
            output += f"\nExit code: {result.returncode}"
        return output.strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {e}"


def _list_files(input: dict, work_dir: Path) -> str:
    path = work_dir / input.get("path", ".")
    if not path.exists():
        return f"Directory not found: {input.get('path', '.')}"
    entries = sorted(path.iterdir())
    lines = []
    for entry in entries:
        prefix = "d " if entry.is_dir() else "f "
        lines.append(f"{prefix}{entry.name}")
    return "\n".join(lines) or "(empty directory)"
