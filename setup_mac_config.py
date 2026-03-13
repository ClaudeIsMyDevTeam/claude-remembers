"""
Run this on Mac to write the Claude Desktop config with Turso credentials.
Usage: .venv/bin/python3 setup_mac_config.py
"""
import json
from pathlib import Path

TURSO_URL = "libsql://claude-remembers-rhrad.aws-us-east-1.turso.io"

print("Paste your Turso auth token and press Enter:")
TURSO_TOKEN = input().strip()

if not TURSO_TOKEN:
    print("Error: token cannot be empty")
    exit(1)

config_path = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"

existing = {}
if config_path.exists():
    existing = json.loads(config_path.read_text())

existing["mcpServers"] = {
    "memory": {
        "command": str(Path(__file__).parent / ".venv/bin/python"),
        "args": [str(Path(__file__).parent / "mcp_server.py")],
        "env": {
            "TURSO_URL": TURSO_URL,
            "TURSO_TOKEN": TURSO_TOKEN,
        }
    }
}

# Also save .env for local use
env_path = Path(__file__).parent / ".env"
env_path.write_text(f"TURSO_URL={TURSO_URL}\nTURSO_TOKEN={TURSO_TOKEN}\n")

config_path.write_text(json.dumps(existing, indent=2))
print(f"Done. Config written to {config_path}")
print(f"Token starts with: {TURSO_TOKEN[:20]}...")
