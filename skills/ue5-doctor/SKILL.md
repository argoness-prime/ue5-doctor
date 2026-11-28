---
name: ue5-doctor
description: "Triage 100k-line Unreal Engine 5.4-5.9 UBT/UAT/Cook logs, map LNK2019 Private vs Public Build.cs dependencies, audit DefaultEngine.ini desktop/90Hz OpenXR VR VRAM CVars (r.Shadow.Virtual.MaxPhysicalPages, vr.InstancedStereo), or run the stdio MCP server."
---

# UE5 Build, Crash-Log & VRAM Doctor (`v1.1.0`)

Use this skill or the `ue5-doctor mcp` (`stdio` JSON-RPC 2.0) server when triaging Unreal Engine 5.4–5.9 build/cook failures or tuning `Config/DefaultEngine.ini` for 8–32 GB desktop and 90 Hz OpenXR VR budgets.

## Quickstart

```bash
uvx --from https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl ue5-doctor selftest
claude mcp add ue5-doctor -- uvx --from https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl ue5-doctor mcp
```
