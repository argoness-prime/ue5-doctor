# Veristrux UE5 Build, Crash-Log & VRAM Doctor (`v1.0.0`)

Zero-dependency Python 3.10+ command-line diagnostic suite for **Unreal Engine 5.4 – 5.9** developers and technical artists.

1. **`triage-log <Saved/Logs/Project.log>`** — Scans 100,000+ line UnrealBuildTool (UBT), UnrealAutomationTool (UAT), Cook, and Editor crash logs in `<50 ms`, isolating the **first root-cause error** and mapping `LNK2019`/`LNK2001` unresolved symbols to missing `<Module>.Build.cs` dependencies (`UMG`, `Niagara`, `EnhancedInput`, `StateTreeModule`, `RenderCore`, etc.).
2. **`audit-ini <Config/DefaultEngine.ini> --vram-gb 16 --mode desktop|vr90`** — Audits renderer settings against `8 GB`–`24 GB` desktop or `90 Hz` OpenXR VR stereo VRAM budgets and outputs ready-to-paste `DefaultEngine.ini` CVar overrides (`r.Streaming.PoolSize`, `r.Shadow.Virtual.MaxPhysicalPages`, `vr.InstancedStereo`, Lumen/Strand caps).
3. **`trim-uproject <Game.uproject>`** — Flags high-bloat default plugins (`OpenImageDenoise`, `USDImporter`, editor-only leaks) inflating shipping `.pak` / IoStore binaries by `60–200+ MB`.
4. **`selftest`** — Runs 10 built-in offline verification checks in `<0.1s`.

## Quickstart

```bash
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
- **Interactive 6-Wall 29-Prime Laguerre Spatial Fiducial Sandbox:** https://veristrux.com/viewdrift-demo.html
- **UE 5.8 / 5.9 Seam (`<= 0.50 mm`) & VRAM Reference Checklist (Gist):** https://gist.github.com/argoness-prime/aeac84fe9a5ffd89dc989143a8e32572
- **ViewDrift (`/ppd v1.5.0` — UE 5.8/5.9 C++20/RDG Plugin + MCP Save Firewall), UE 5.9 Cinema Capture Kit & 48h UE5 Engineering Rescue:** https://veristrux.com/
- **License:** MIT License — Copyright (c) 2026 Veristrux Inc. (`argoness@veristrux.com`)
