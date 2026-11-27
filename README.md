# Veristrux UE5 Build, Crash-Log & VRAM Doctor (`v1.0.0`)

Zero-dependency Python 3.10+ command-line diagnostic suite for **Unreal Engine 5.4 – 5.9** developers and technical artists:

1. **`triage-log <Saved/Logs/Project.log>`** — Scans 100,000+ line UnrealBuildTool (UBT), UnrealAutomationTool (UAT), Cook, and Editor crash logs in `<50 ms`, isolating the **first root-cause error** and suggesting missing `<Module>.Build.cs` dependencies (`UMG`, `Niagara`, `EnhancedInput`, `StateTreeModule`, `RenderCore`, etc.) for `LNK2019`/`LNK2001` unresolved symbols.
2. **`audit-ini <Config/DefaultEngine.ini> --vram-gb 16 --mode desktop|vr90`** — Audits renderer settings against `8 GB`–`24 GB` desktop or `90 Hz` OpenXR VR stereo VRAM budgets and outputs ready-to-paste `DefaultEngine.ini` CVar overrides (`r.Streaming.PoolSize`, `r.VSM.MaxPhysicalPages`, `xr.InstancedStereo`, Lumen/Strand caps).
3. **`trim-uproject <Game.uproject>`** — Flags high-bloat default plugins (`OpenImageDenoise`, `USDImporter`, editor-only leaks) inflating shipping `.pak` / IoStore binaries by `60–200+ MB`.
4. **`selftest`** — Runs 10 built-in offline verification checks in `<0.1s`.

## Quickstart

```bash
python ue5_doctor.py selftest
python ue5_doctor.py triage-log Saved/Logs/MyProject.log
python ue5_doctor.py audit-ini Config/DefaultEngine.ini --vram-gb 16 --mode vr90
python ue5_doctor.py trim-uproject MyProject.uproject
```

## License & Support
- **License:** MIT License — Copyright (c) 2026 Veristrux Inc.
- **Support & Custom UE5 C++ Rescue:** `argoness@veristrux.com` · https://argoness-prime.github.io/veristrux/
