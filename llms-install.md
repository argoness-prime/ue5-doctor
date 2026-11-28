# LLM / Autonomous Agent Installation Guide (`ue5-doctor` v1.1.0)

Zero-dependency Python 3.10+ stdlib `stdio` MCP server for Unreal Engine 5.4–5.9 log triage and `DefaultEngine.ini` VRAM auditing. Zero API keys or external packages required.

## Option A — Zero-Clone `uvx` Configuration

```json
{
  "mcpServers": {
    "ue5-doctor": {
      "command": "uvx",
      "args": [
        "--from",
        "https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl",
        "ue5-doctor",
        "mcp"
      ]
    }
  }
}
```

## Option B — Pure-Python Wheel Installation via `pip`

```bash
python -m pip install --no-deps https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl
python -m ue5_doctor selftest
```

```json
{
  "mcpServers": {
    "ue5-doctor": {
      "command": "python",
      "args": ["-u", "-m", "ue5_doctor", "mcp"]
    }
  }
}
```
