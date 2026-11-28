---
name: ue5-doctor
description: "Diagnose Unreal Engine 5.4-5.9 UBT, UAT, Cook, and Editor crash logs in <50 ms, map LNK2019/LNK2001 unresolved symbols to missing Build.cs modules, audit DefaultEngine.ini against desktop and 90 Hz OpenXR VR VRAM budgets, and flag high-bloat .uproject plugins."
---

# UE5 Build, Crash-Log & VRAM Doctor (`ue5-doctor`)

Use this skill when diagnosing Unreal Engine 5.4–5.9 C++ compile failures, `LNK2019`/`LNK2001` linker errors, `RunUAT BuildCookRun` cook crashes, `DefaultEngine.ini` GPU memory exhaustion (`8 GB`–`24 GB` desktop or `90 Hz` OpenXR stereo VR), or shipping `.pak` / IoStore plugin bloat.

`ue5_doctor.py` is a single-file, zero-dependency Python 3.10+ command-line tool (`MIT` license) that runs completely offline.

## Installation

```bash
git clone https://github.com/argoness-prime/ue5-doctor.git
python ue5-doctor/ue5_doctor.py selftest
```

## Core Diagnostic Commands

### 1. Isolate Root-Cause UBT / UAT / Cook Errors & Missing `Build.cs` Modules
Scans 100,000+ line UnrealBuildTool, UnrealAutomationTool, Cook, and Editor logs in `<50 ms`, extracting the **first root-cause error** before cascading secondary failures and mapping unresolved C++ symbols (`UUserWidget`, `UNiagaraComponent`, `UEnhancedInputComponent`, `UStateTreeComponent`, `FRDGBuilder`, `IXRTrackingSystem`, etc.) to the exact `<Module>.Build.cs` `PublicDependencyModuleNames` entry:

```bash
python ue5_doctor.py triage-log Saved/Logs/MyProject.log
```

### 2. Audit `Config/DefaultEngine.ini` Against Desktop or `90 Hz` OpenXR VR VRAM Budgets
Checks renderer CVars against target GPU VRAM (`8`, `12`, `16`, or `24` GB) and outputs copy-pasteable `[/Script/Engine.RendererSettings]` overrides (`r.Streaming.PoolSize`, `r.Shadow.Virtual.MaxPhysicalPages`, `r.Lumen.Reflections.Allow`, `r.HairStrands.SkyLighting.IntegrationType`, `vr.InstancedStereo`):

```bash
# 16 GB desktop workstation / shipping target:
python ue5_doctor.py audit-ini Config/DefaultEngine.ini --vram-gb 16 --mode desktop

# 16 GB 90 Hz OpenXR VR stereo target:
python ue5_doctor.py audit-ini Config/DefaultEngine.ini --vram-gb 16 --mode vr90
```

### 3. Flag Editor-Only & Heavy Runtime Plugin Bloat in `<Project>.uproject`
Identifies enabled default plugins (`OpenImageDenoise`, `USDImporter`, `Bridge`, `Fab`, `DatasmithContent`, `MediaPlayerEditor`) that add `60–200+ MB` to packaged shipping builds when unused at runtime:

```bash
python ue5_doctor.py trim-uproject MyProject.uproject
```

## Workflow Guidelines for Coding Agents

1. **Always inspect the first error first:** Unreal cook logs routinely emit hundreds of downstream asset/shader warnings after a single C++ compile or `Build.cs` failure; run `triage-log` before grepping the tail of a log.
2. **Verify `Build.cs` module visibility:** Editor-only modules must stay inside `if (Target.bBuildEditor)` guards in `<Module>.Build.cs` so shipping `Win64` / console cooks do not fail at link time.
3. **Preserve VRAM headroom:** Leave at least `1.25–1.50 GB` of OS compositor / driver headroom when setting `r.Streaming.PoolSize` and `r.Shadow.Virtual.MaxPhysicalPages` on 8–16 GB GPUs.
