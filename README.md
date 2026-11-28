# Veristrux UE5 Build, Crash-Log & VRAM Doctor (`v1.1.0`)

Zero-dependency Python 3.10+ command-line diagnostic suite and local **`stdio` Model Context Protocol (MCP) server** for **Unreal Engine 5.4 – 5.9** developers and technical artists.

1. **`triage-log` / MCP `triage_ue5_log`** — Scans 100,000+ line UnrealBuildTool (UBT), UnrealAutomationTool (UAT), Cook, and Editor crash logs in `<50 ms`, isolating the **first root-cause error** and mapping `LNK2019`/`LNK2001` unresolved symbols to missing `<Module>.Build.cs` dependencies (`PrivateDependencyModuleNames` for `.cpp`-only vs `PublicDependencyModuleNames` for `Public/` headers).
2. **`audit-ini` / MCP `audit_ue5_ini`** — Audits `Config/DefaultEngine.ini` against `8 GB`–`32 GB` desktop deferred or `90 Hz` OpenXR VR (`11.1 ms` nominal frame interval) VRAM budgets and outputs ready-to-paste canonical UE 5.4–5.9 CVar overrides (`r.Streaming.PoolSize`, `r.Shadow.Virtual.MaxPhysicalPages`, `r.Lumen.Reflections.Allow`, `vr.InstancedStereo`).
3. **`trim-uproject` / MCP `trim_ue5_uproject`** — Flags high-bloat default plugins (`OpenImageDenoise`, `USDImporter`, editor-only leaks) inflating shipping `.pak` / IoStore binaries by `60–200+ MB`.
4. **`mcp`** — Zero-dependency JSON-RPC 2.0 `stdio` MCP server (`ue5-doctor mcp` / `ue5-doctor-mcp`).
5. **`selftest`** — Runs 10 built-in offline verification checks in `<0.1s`.

## Quickstart

```bash
# Run instantly via uvx (zero clone required):
uvx --from https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl ue5-doctor selftest

# Register as a local stdio MCP server in Claude Code:
claude mcp add ue5-doctor -- uvx --from https://github.com/argoness-prime/ue5-doctor/releases/download/v1.1.0/ue5_doctor-1.1.0-py3-none-any.whl ue5-doctor mcp

# Install as an Agent Skill (Claude Code, Cursor, Codex, Antigravity):
npx skills add argoness-prime/ue5-doctor

# Or clone and run directly:
git clone https://github.com/argoness-prime/ue5-doctor.git
python ue5-doctor/ue5_doctor.py selftest
python ue5-doctor/ue5_doctor.py triage-log Saved/Logs/MyProject.log
python ue5-doctor/ue5_doctor.py audit-ini Config/DefaultEngine.ini --vram-gb 16 --mode vr90
python ue5-doctor/ue5_doctor.py trim-uproject MyProject.uproject
```

## Companion Unreal Engine 5.8 / 5.9 Systems (`Veristrux Inc.`)
- **MCP Registry Identifier:** `mcp-name: io.github.argoness-prime/ue5-doctor`
- **Interactive 6-Wall 29-Prime Laguerre Spatial Fiducial Sandbox:** https://veristrux.com/viewdrift-demo.html
- **1080p & 9:16 Technical Walkthroughs:** [UE5 UBT `LNK2019`, Dual `audit-ini` & Standalone `-game` Cinema (1080p MP4)](https://veristrux.com/media/wave5/ue59_crash_and_cinema_16x9.mp4) · [9:16 Short](https://veristrux.com/media/wave5/ue59_crash_and_cinema_short.mp4) · [ViewDrift 29-Prime Chamber (1080p MP4)](https://veristrux.com/media/viewdrift_ue59_showcase.mp4)
- **UE 5.8 / 5.9 Seam (`<= 0.50 mm`) & VRAM Reference Checklist (Gist):** https://gist.github.com/argoness-prime/aeac84fe9a5ffd89dc989143a8e32572
- **ViewDrift (`/ppd v1.5.0` — UE 5.8/5.9 C++20/RDG Plugin + MCP Save Firewall), UE 5.9 Cinema Capture Kit & 48h UE5 Engineering Rescue:** https://veristrux.com/
- **License:** MIT License — Copyright (c) 2026 Veristrux Inc. (`argoness@veristrux.com`)
