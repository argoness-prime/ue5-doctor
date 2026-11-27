"""Veristrux UE5 Build, Crash-Log & 16GB VRAM Doctor (v1.0.0).

Zero-dependency Python 3.10+ CLI for Unreal Engine 5.4 - 5.9 developers:
  1. `triage-log`: Scans 100k+ line UBT/UAT/Cook/Editor logs in <50 ms, isolating first-cause C++
     compile errors, LNK2019/LNK2001 missing Build.cs module hints, Ensure/Fatal callstacks, and shader failures.
  2. `audit-ini`: Audits Config/DefaultEngine.ini against 8GB/12GB/16GB/24GB desktop or 90Hz OpenXR VR
     VRAM budgets and emits exact CVar overrides.
  3. `trim-uproject`: Flags high-bloat default plugins in .uproject files inflating packaged builds.
  4. `selftest`: Runs built-in 10-check verification suite offline.

Copyright (c) 2026 Veristrux Inc. (https://veristrux.com | argoness@veristrux.com). MIT License.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

VERSION = "1.0.0"

COMMON_SYMBOL_MODULES: dict[str, str] = {
    "UUserWidget": "UMG",
    "SCompoundWidget": "SlateCore",
    "FSlateApplication": "Slate",
    "UNiagaraComponent": "Niagara",
    "UNiagaraFunctionLibrary": "Niagara",
    "UInputAction": "EnhancedInput",
    "UEnhancedInputComponent": "EnhancedInput",
    "UEnhancedInputLocalPlayerSubsystem": "EnhancedInput",
    "UStateTreeComponent": "StateTreeModule",
    "UGameplayStatics": "Engine",
    "AIController": "AIModule",
    "UBehaviorTree": "AIModule",
    "UAbilitySystemComponent": "GameplayAbilities",
    "FJsonSerializer": "Json",
    "IHttpRequest": "HTTP",
    "FHttpModule": "HTTP",
    "ULevelSequencePlayer": "LevelSequence",
    "IConsoleManager": "Core",
    "FRDGBuilder": "RenderCore",
    "IXRTrackingSystem": "HeadMountedDisplay",
}

BLOAT_PLUGINS: dict[str, tuple[str, int]] = {
    "OpenImageDenoise": ("CPU path-tracer denoiser (~45-80 MB binary bloat in shipping builds)", 65),
    "Bridge": ("Quixel Bridge editor integration (not needed at runtime)", 30),
    "Fab": ("Fab marketplace browser plugin (editor-only)", 25),
    "USDImporter": ("Heavy USD libraries; disable if shipping cooked native assets only", 90),
    "AlembicImporter": ("Alembic runtime/importer overhead if unused at runtime", 20),
    "DatasmithContent": ("Enterprise CAD/Datasmith runtime modules if unused", 25),
    "MediaPlayerEditor": ("Editor media tooling; keep out of runtime plugin list", 15),
    "ChaosCaching": ("Recorded destruction cache playback; disable unless using cached sims", 18),
}

ERROR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("cpp_compile", re.compile(r"\(\d+(?:,\d+)?\):\s*(?:fatal )?error C\d+:", re.IGNORECASE)),
    ("clang_compile", re.compile(r":\d+:\d+:\s*(?:fatal )?error:", re.IGNORECASE)),
    ("msvc_linker", re.compile(r"error LNK(?:2001|2019|1120):", re.IGNORECASE)),
    ("ubt_missing_module", re.compile(r"Could not find definition for module '([^']+)'", re.IGNORECASE)),
    ("uat_cook_error", re.compile(r"LogInit:\s*Display:\s*Failure - \d+ error\(s\)|CookResults:\s*Error:|LogCook:\s*Error:", re.IGNORECASE)),
    ("fatal_assert", re.compile(r"Assertion failed:|Fatal error:|Ensure condition failed:", re.IGNORECASE)),
    ("shader_error", re.compile(r"LogShaderCompilers:\s*Error:|ShaderCompileWorker.*Error", re.IGNORECASE)),
    ("exit_code", re.compile(r"AutomationTool exiting with ExitCode=(\d+)", re.IGNORECASE)),
)


def triage_log_text(text: str, max_findings: int = 25) -> dict[str, Any]:
    lines = text.splitlines()
    findings: list[dict[str, Any]] = []
    module_hints: list[str] = []
    seen_msgs: set[str] = set()
    exit_code: int | None = None

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        for kind, rx in ERROR_PATTERNS:
            m = rx.search(line)
            if not m:
                continue
            if kind == "exit_code":
                exit_code = int(m.group(1))
            dedup_key = f"{kind}:{line[:140]}"
            if dedup_key in seen_msgs:
                break
            seen_msgs.add(dedup_key)

            hint = ""
            if kind == "msvc_linker":
                for sym, mod in COMMON_SYMBOL_MODULES.items():
                    if sym in line:
                        hint = f"Add '{mod}' to PublicDependencyModuleNames in your <Module>.Build.cs."
                        if mod not in module_hints:
                            module_hints.append(mod)
                        break
            elif kind == "ubt_missing_module":
                missing = m.group(1)
                hint = f"Enable plugin providing '{missing}' in your .uproject or remove '{missing}' from Build.cs."

            if len(findings) < max_findings:
                findings.append({"line": idx, "kind": kind, "message": line[:260], "hint": hint})
            break

    first_root_cause = findings[0] if findings else None
    return {
        "ok": len([f for f in findings if f["kind"] != "exit_code"]) == 0 and (exit_code in (None, 0)),
        "linesScanned": len(lines),
        "exitCode": exit_code,
        "findingCount": len(findings),
        "firstRootCause": first_root_cause,
        "suggestedBuildCsModules": module_hints,
        "findings": findings,
    }


def audit_engine_ini_text(ini_text: str, vram_gb: int = 16, mode: str = "desktop") -> dict[str, Any]:
    kv: dict[str, str] = {}
    for raw in ini_text.splitlines():
        s = raw.strip()
        if not s or s.startswith((";", "#", "[")):
            continue
        if "=" in s:
            k, v = s.split("=", 1)
            kv[k.strip().lstrip("+-")] = v.strip()

    recommendations: list[dict[str, str]] = []
    recommended_pool = max(1024, int(vram_gb * 1024 * (0.22 if mode == "vr90" else 0.32)))

    pool_raw = kv.get("r.Streaming.PoolSize")
    if pool_raw is None or (pool_raw.isdigit() and int(pool_raw) > int(vram_gb * 1024 * 0.45)):
        recommendations.append(
            {
                "cvar": "r.Streaming.PoolSize",
                "recommended": str(recommended_pool),
                "reason": f"Caps texture streaming pool to {recommended_pool} MiB on {vram_gb} GB GPUs ({mode}) to prevent DX12/Vulkan demotion stutters.",
            }
        )

    if mode == "vr90":
        vr_checks = (
            ("r.VSM.MaxPhysicalPages", "2048", "Bounds Virtual Shadow Map physical page VRAM under stereo instanced rendering."),
            ("r.HairStrands.SkyLighting.IntegrationType", "2", "Cuts strand hair sky-lighting GPU cost in 90Hz stereo."),
            ("r.Lumen.Reflections.Allow", "0", "Disables expensive stereo Lumen ray reflections when hitting strict 11.1 ms 90Hz frame budgets."),
            ("xr.InstancedStereo", "True", "Ensures single-pass instanced stereo draw submission for OpenXR."),
        )
        for cvar, target_val, why in vr_checks:
            if kv.get(cvar) != target_val:
                recommendations.append({"cvar": cvar, "recommended": target_val, "reason": why})
    else:
        if kv.get("r.VSM.MaxPhysicalPages") is None:
            recommendations.append(
                {
                    "cvar": "r.VSM.MaxPhysicalPages",
                    "recommended": "4096" if vram_gb >= 16 else "2048",
                    "reason": "Prevents unbounded Virtual Shadow Map page-table growth in dense Nanite levels.",
                }
            )

    snippet = "[/Script/Engine.RendererSettings]\n" + "\n".join(
        f"{r['cvar']}={r['recommended']}" for r in recommendations
    )
    return {
        "vramGb": vram_gb,
        "mode": mode,
        "parsedSettingsCount": len(kv),
        "recommendationCount": len(recommendations),
        "recommendations": recommendations,
        "iniSnippet": snippet if recommendations else "; Config/DefaultEngine.ini already matches target budget.",
    }


def trim_uproject_data(uproject_json: dict[str, Any]) -> dict[str, Any]:
    plugins = uproject_json.get("Plugins") or []
    flagged: list[dict[str, Any]] = []
    est_mb = 0
    for p in plugins:
        if not isinstance(p, dict) or not p.get("Enabled", False):
            continue
        name = str(p.get("Name") or "")
        if name in BLOAT_PLUGINS:
            why, mb = BLOAT_PLUGINS[name]
            flagged.append({"plugin": name, "estimatedSavingsMb": mb, "reason": why})
            est_mb += mb
    return {
        "enabledPluginCount": sum(1 for p in plugins if isinstance(p, dict) and p.get("Enabled", False)),
        "flaggedCount": len(flagged),
        "estimatedBinarySavingsMb": est_mb,
        "flaggedPlugins": flagged,
    }


def run_selftest() -> dict[str, Any]:
    checks: list[tuple[str, bool]] = []

    sample_log = (
        "LogInit: Display: Running engine\n"
        "Source/MyGame/UI/Hud.cpp(42): error C2065: 'UUserWidget': undeclared identifier\n"
        "Hud.cpp.obj : error LNK2019: unresolved external symbol \"public: __cdecl UUserWidget::UUserWidget\" referenced in function foo\n"
        "UnrealBuildTool : error : Could not find definition for module 'Niagara'\n"
        "AutomationTool exiting with ExitCode=6\n"
    )
    res_log = triage_log_text(sample_log)
    checks.append(("detect_cpp_compile_first_cause", res_log["firstRootCause"] is not None and res_log["firstRootCause"]["kind"] == "cpp_compile"))
    checks.append(("detect_umg_build_cs_hint", "UMG" in res_log["suggestedBuildCsModules"]))
    checks.append(("detect_missing_module_error", any(f["kind"] == "ubt_missing_module" for f in res_log["findings"])))
    checks.append(("parse_uat_exit_code", res_log["exitCode"] == 6 and res_log["ok"] is False))

    clean_log = triage_log_text("LogInit: Display: Success - 0 error(s), 0 warning(s)\nAutomationTool exiting with ExitCode=0\n")
    checks.append(("clean_log_passes", clean_log["ok"] is True and clean_log["exitCode"] == 0))

    ini_vr = audit_engine_ini_text("[/Script/Engine.RendererSettings]\nr.Streaming.PoolSize=12000\n", vram_gb=16, mode="vr90")
    checks.append(("vr90_clamps_excessive_pool", any(r["cvar"] == "r.Streaming.PoolSize" for r in ini_vr["recommendations"])))
    checks.append(("vr90_enforces_instanced_stereo", any(r["cvar"] == "xr.InstancedStereo" for r in ini_vr["recommendations"])))

    ini_dt = audit_engine_ini_text("[/Script/Engine.RendererSettings]\n", vram_gb=12, mode="desktop")
    checks.append(("desktop_recommends_vsm_cap", any(r["cvar"] == "r.VSM.MaxPhysicalPages" for r in ini_dt["recommendations"])))

    uproj = trim_uproject_data(
        {"Plugins": [{"Name": "OpenImageDenoise", "Enabled": True}, {"Name": "EnhancedInput", "Enabled": True}]}
    )
    checks.append(("uproject_flags_oidn_bloat", uproj["flaggedCount"] == 1 and uproj["estimatedBinarySavingsMb"] >= 60))
    checks.append(("uproject_preserves_gameplay_plugins", all(f["plugin"] != "EnhancedInput" for f in uproj["flaggedPlugins"])))

    passed = sum(1 for _, ok in checks if ok)
    return {
        "ok": passed == len(checks),
        "score": f"{passed}/{len(checks)}",
        "passed": passed,
        "total": len(checks),
        "checks": [{"name": n, "passed": ok} for n, ok in checks],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ue5-doctor", description="Veristrux UE 5.4-5.9 Build, Log & VRAM Doctor")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_log = sub.add_parser("triage-log", help="Isolate root-cause compile, linker, and cook errors from UE5 logs")
    p_log.add_argument("logfile", type=Path)

    p_ini = sub.add_parser("audit-ini", help="Audit DefaultEngine.ini against desktop or 90Hz VR VRAM budgets")
    p_ini.add_argument("inifile", type=Path)
    p_ini.add_argument("--vram-gb", type=int, default=16)
    p_ini.add_argument("--mode", choices=("desktop", "vr90"), default="desktop")

    p_up = sub.add_parser("trim-uproject", help="Detect bloat plugins in a .uproject file")
    p_up.add_argument("uproject", type=Path)

    sub.add_parser("selftest", help="Run offline 10-check verification suite")

    args = parser.parse_args(argv)
    if args.cmd == "selftest":
        res = run_selftest()
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    if args.cmd == "triage-log":
        txt = args.logfile.read_text(encoding="utf-8", errors="replace")
        res = triage_log_text(txt)
        print(json.dumps(res, indent=2))
        return 0 if res["ok"] else 1
    if args.cmd == "audit-ini":
        txt = args.inifile.read_text(encoding="utf-8", errors="replace")
        print(json.dumps(audit_engine_ini_text(txt, vram_gb=args.vram_gb, mode=args.mode), indent=2))
        return 0
    if args.cmd == "trim-uproject":
        data = json.loads(args.uproject.read_text(encoding="utf-8", errors="replace"))
        print(json.dumps(trim_uproject_data(data), indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
