"""
PostToolUse hook: after Edit/Write touches backend/app/mcp/**, restart the
mcp-server container. It has no hot-reload (see CLAUDE.md "Standing decisions
& known gotchas -> MCP") -- editing it and testing against the stale running
container has caused a real misdiagnosed bug before (Day 4 note in
docs/CHANGELOG.md).
"""
import json
import subprocess
import sys

PROJECT_DIR = r"c:\Work\台灣世曦\ai-engineering-assistant"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    file_path = (data.get("tool_input") or {}).get("file_path") or ""
    normalized = file_path.replace("\\", "/")

    if "/backend/app/mcp/" not in normalized:
        return

    result = subprocess.run(
        ["docker", "compose", "restart", "mcp-server"],
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        message = "mcp-server restarted (edited file under backend/app/mcp/ -- no hot-reload)"
    else:
        message = (
            "mcp-server restart FAILED after editing backend/app/mcp/ -- "
            f"restart it manually: {result.stderr.strip()[:300]}"
        )

    print(json.dumps({"systemMessage": message}))


if __name__ == "__main__":
    main()
