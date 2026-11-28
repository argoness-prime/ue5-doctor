"""Veristrux UE5 Build, Crash-Log & VRAM Doctor (v1.1.0) — CLI & Zero-Dep Stdio MCP Server.

Zero-dependency Python 3.10+ CLI and Model Context Protocol (MCP) server for Unreal Engine 5.4 - 5.9:
  1. `triage-log` / MCP `triage_ue5_log`: Scans 100k+ line UBT/UAT/Cook/Editor logs, isolating first-cause
     C++ compile errors, LNK2019/LNK2001 Build.cs module hints (Private vs Public), Ensure/Fatal callstacks, and shader failures.
  2. `audit-ini` / MCP `audit_ue5_ini`: Audits Config/DefaultEngine.ini against 8GB-32GB desktop or 90Hz OpenXR VR
     VRAM budgets using canonical UE 5.4-5.9 CVars (r.Shadow.Virtual.MaxPhysicalPages, vr.InstancedStereo).
  3. `trim-uproject` / MCP `trim_ue5_uproject`: Flags high-bloat default plugins in .uproject files.
  4. `mcp`: Runs the JSON-RPC 2.0 stdio MCP server (newline-delimited JSON and Content-Length framing).
  5. `selftest`: Runs built-in 10-check verification suite offline.

Copyright (c) 2026 Veristrux Inc. (https://veristrux.com | argoness@veristrux.com). MIT License.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any, BinaryIO

VERSION = "1.1.0"
__version__ = VERSION

SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = (
    "2025-06-18",
    "2025-03-26",
    "2024-11-05",
)
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
MAX_LOG_FILE_BYTES = 32 * 1024 * 1024  # 32 MiB ceiling for file-backed log triage

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
                        hint = (
                            f"Add '{mod}' to PrivateDependencyModuleNames (if referenced only in .cpp) "
                            f"or PublicDependencyModuleNames (if exposed in Public/ headers) in <Module>.Build.cs."
                        )
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
            ("r.Shadow.Virtual.MaxPhysicalPages", "2048", "Bounds Virtual Shadow Map physical page VRAM under stereo instanced rendering."),
            ("r.HairStrands.SkyLighting.IntegrationType", "2", "Cuts strand hair sky-lighting GPU cost in 90Hz stereo."),
            ("r.Lumen.Reflections.Allow", "0", "Disables expensive stereo Lumen ray reflections when targeting 90Hz VR (11.1 ms nominal frame interval)."),
            ("vr.InstancedStereo", "True", "Ensures single-pass instanced stereo draw submission for OpenXR."),
        )
        for cvar, target_val, why in vr_checks:
            if kv.get(cvar) != target_val:
                recommendations.append({"cvar": cvar, "recommended": target_val, "reason": why})
    else:
        if kv.get("r.Shadow.Virtual.MaxPhysicalPages") is None:
            recommendations.append(
                {
                    "cvar": "r.Shadow.Virtual.MaxPhysicalPages",
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
    checks.append(("vr90_enforces_instanced_stereo", any(r["cvar"] == "vr.InstancedStereo" for r in ini_vr["recommendations"])))

    ini_dt = audit_engine_ini_text("[/Script/Engine.RendererSettings]\n", vram_gb=12, mode="desktop")
    checks.append(("desktop_recommends_vsm_cap", any(r["cvar"] == "r.Shadow.Virtual.MaxPhysicalPages" for r in ini_dt["recommendations"])))

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


# ---------------------------------------------------------------------------
# Zero-Dependency Stdio MCP Server (JSON-RPC 2.0)
# ---------------------------------------------------------------------------

TOOLS_SPEC: tuple[dict[str, Any], ...] = (
    {
        "name": "triage_ue5_log",
        "description": (
            "Scan Unreal Engine 5.4-5.9 UnrealBuildTool (UBT), UnrealAutomationTool (UAT), Cook, or Editor logs "
            "to isolate the originating root-cause error, map LNK2019/LNK2001 symbols to missing <Module>.Build.cs "
            "dependencies (PrivateDependencyModuleNames vs PublicDependencyModuleNames), and extract UAT exit codes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Raw UBT/UAT/Cook/Editor log text. Provide either `text` or `path`.",
                },
                "path": {
                    "type": "string",
                    "description": "Local path to a .log/.txt file (<= 32 MiB) when `text` is omitted.",
                },
                "max_findings": {
                    "type": "integer",
                    "description": "Maximum number of deduplicated error findings to return (1..100).",
                    "default": 25,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Triage UE5 Build/Cook Log",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "audit_ue5_ini",
        "description": (
            "Audit Unreal Engine 5.4-5.9 Config/DefaultEngine.ini against 8-32 GB desktop deferred or 90 Hz OpenXR VR "
            "(11.1 ms nominal frame interval) VRAM budgets, emitting canonical CVar overrides "
            "(r.Streaming.PoolSize, r.Shadow.Virtual.MaxPhysicalPages, r.Lumen.Reflections.Allow, vr.InstancedStereo)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Raw DefaultEngine.ini contents. Provide either `text` or `path`.",
                },
                "path": {
                    "type": "string",
                    "description": "Local path to Config/DefaultEngine.ini when `text` is omitted.",
                },
                "vram_gb": {
                    "type": "integer",
                    "description": "Target GPU VRAM capacity in GB (e.g. 8, 12, 16, 24, 32).",
                    "default": 16,
                    "minimum": 4,
                    "maximum": 192,
                },
                "mode": {
                    "type": "string",
                    "enum": ["desktop", "vr90"],
                    "description": "Target rendering profile: 'desktop' deferred or 'vr90' 90 Hz OpenXR stereo.",
                    "default": "desktop",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Audit UE5 DefaultEngine.ini VRAM Budget",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
    {
        "name": "trim_ue5_uproject",
        "description": (
            "Inspect a .uproject JSON descriptor for high-bloat default plugins (OpenImageDenoise, USDImporter, "
            "Bridge, Fab, MediaPlayerEditor) that inflate shipping .pak / IoStore builds."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Raw .uproject JSON text. Provide either `text` or `path`.",
                },
                "path": {
                    "type": "string",
                    "description": "Local path to a .uproject file when `text` is omitted.",
                },
            },
            "additionalProperties": False,
        },
        "annotations": {
            "title": "Audit UE5 .uproject Plugin Bloat",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    },
)


class _ToolParamError(ValueError):
    """Raised when MCP tool arguments fail schema validation."""


def _read_text_or_path(args: dict[str, Any], max_bytes: int = MAX_LOG_FILE_BYTES) -> str:
    has_text = "text" in args and args["text"] is not None
    has_path = "path" in args and args["path"] is not None
    if not has_text and not has_path:
        raise _ToolParamError("Either `text` or `path` must be provided.")
    if has_text:
        if not isinstance(args["text"], str):
            raise _ToolParamError("`text` must be a string.")
        return args["text"]
    if not isinstance(args["path"], str) or not args["path"].strip():
        raise _ToolParamError("`path` must be a non-empty string.")
    fp = Path(args["path"]).expanduser().resolve()
    if not fp.is_file():
        raise FileNotFoundError(f"File not found: {fp.name}")
    size = fp.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File exceeds {max_bytes} byte limit ({size} bytes).")
    return fp.read_text(encoding="utf-8", errors="replace")


def _call_triage_log(args: dict[str, Any]) -> dict[str, Any]:
    raw = _read_text_or_path(args)
    max_f = args.get("max_findings", 25)
    if isinstance(max_f, bool) or not isinstance(max_f, int) or not (1 <= max_f <= 100):
        raise _ToolParamError("`max_findings` must be an integer between 1 and 100.")
    payload = triage_log_text(raw, max_findings=max_f)
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def _call_audit_ini(args: dict[str, Any]) -> dict[str, Any]:
    raw = _read_text_or_path(args, max_bytes=4 * 1024 * 1024)
    vram_gb = args.get("vram_gb", 16)
    if isinstance(vram_gb, bool) or not isinstance(vram_gb, int) or not (4 <= vram_gb <= 192):
        raise _ToolParamError("`vram_gb` must be an integer between 4 and 192.")
    mode = str(args.get("mode", "desktop"))
    if mode not in ("desktop", "vr90"):
        raise _ToolParamError("`mode` must be 'desktop' or 'vr90'.")
    payload = {"ok": True, **audit_engine_ini_text(raw, vram_gb=vram_gb, mode=mode)}
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def _call_trim_uproject(args: dict[str, Any]) -> dict[str, Any]:
    raw = _read_text_or_path(args, max_bytes=4 * 1024 * 1024)
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("`.uproject` content must be a JSON object.")
    payload = {"ok": True, **trim_uproject_data(parsed)}
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "structuredContent": payload,
        "isError": False,
    }


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle_rpc_message(msg: Any) -> dict[str, Any] | None:
    if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0":
        req_id = msg.get("id") if isinstance(msg, dict) and "id" in msg else None
        return _jsonrpc_error(req_id, -32600, "Invalid JSON-RPC 2.0 request.")

    method = msg.get("method")
    if not isinstance(method, str) or not method:
        return _jsonrpc_error(msg.get("id"), -32600, "Missing string `method` in request.")

    is_notification = "id" not in msg
    req_id = msg.get("id")
    params = msg.get("params")
    if params is None:
        params = {}
    elif not isinstance(params, dict):
        return None if is_notification else _jsonrpc_error(req_id, -32602, "`params` must be a JSON object.")

    if is_notification:
        return None

    if method == "initialize":
        req_ver = str(params.get("protocolVersion") or "")
        negotiated = req_ver if req_ver in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return _jsonrpc_result(
            req_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "ue5-doctor", "version": VERSION},
            },
        )
    if method == "ping":
        return _jsonrpc_result(req_id, {})
    if method == "tools/list":
        return _jsonrpc_result(req_id, {"tools": list(TOOLS_SPEC)})
    if method == "resources/list":
        return _jsonrpc_result(req_id, {"resources": []})
    if method == "prompts/list":
        return _jsonrpc_result(req_id, {"prompts": []})

    if method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments") or {}
        if not isinstance(tool_name, str) or not tool_name:
            return _jsonrpc_error(req_id, -32602, "Missing string tool `name`.")
        if not isinstance(tool_args, dict):
            return _jsonrpc_error(req_id, -32602, "Tool `arguments` must be an object.")

        dispatch = {
            "triage_ue5_log": _call_triage_log,
            "audit_ue5_ini": _call_audit_ini,
            "trim_ue5_uproject": _call_trim_uproject,
        }
        handler = dispatch.get(tool_name)
        if handler is None:
            return _jsonrpc_error(req_id, -32602, f"Unknown tool: {tool_name}")

        try:
            return _jsonrpc_result(req_id, handler(tool_args))
        except _ToolParamError as exc:
            return _jsonrpc_error(req_id, -32602, str(exc))
        except Exception as exc:
            err_payload = {"ok": False, "error": str(exc)}
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(err_payload)}],
                    "structuredContent": err_payload,
                    "isError": True,
                },
            )

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


def process_payload(raw_bytes: bytes) -> bytes | None:
    try:
        parsed = json.loads(raw_bytes.decode("utf-8"))
    except Exception:
        return json.dumps(_jsonrpc_error(None, -32700, "Parse error: invalid JSON."), separators=(",", ":")).encode("utf-8")

    if isinstance(parsed, list):
        if not parsed:
            return json.dumps(_jsonrpc_error(None, -32600, "Empty JSON-RPC batch."), separators=(",", ":")).encode("utf-8")
        responses = [r for item in parsed if (r := handle_rpc_message(item)) is not None]
        return json.dumps(responses, separators=(",", ":")).encode("utf-8") if responses else None

    resp = handle_rpc_message(parsed)
    return json.dumps(resp, separators=(",", ":")).encode("utf-8") if resp is not None else None


def serve_stdio(stdin: BinaryIO | None = None, stdout: BinaryIO | None = None) -> int:
    in_stream = stdin if stdin is not None else sys.stdin.buffer
    out_stream = stdout if stdout is not None else sys.stdout.buffer

    while True:
        line = in_stream.readline()
        if not line:
            break
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.lower().startswith(b"content-length:"):
            try:
                length = int(stripped.split(b":", 1)[1].strip())
            except ValueError:
                err_b = json.dumps(_jsonrpc_error(None, -32700, "Invalid Content-Length header.")).encode("utf-8")
                out_stream.write(f"Content-Length: {len(err_b)}\r\n\r\n".encode("ascii") + err_b)
                out_stream.flush()
                continue
            while True:
                hdr = in_stream.readline()
                if not hdr or hdr in (b"\r\n", b"\n"):
                    break
            if length < 0 or length > 32 * 1024 * 1024:
                err_b = json.dumps(_jsonrpc_error(None, -32600, "Content-Length out of bounds.")).encode("utf-8")
                out_stream.write(f"Content-Length: {len(err_b)}\r\n\r\n".encode("ascii") + err_b)
                out_stream.flush()
                continue
            body = in_stream.read(length)
            if not body:
                break
            resp_b = process_payload(body)
            if resp_b is not None:
                out_stream.write(f"Content-Length: {len(resp_b)}\r\n\r\n".encode("ascii") + resp_b)
                out_stream.flush()
        else:
            resp_b = process_payload(stripped)
            if resp_b is not None:
                out_stream.write(resp_b + b"\n")
                out_stream.flush()

    return 0


def mcp_main() -> int:
    return serve_stdio()


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

    sub.add_parser("mcp", help="Run zero-dependency JSON-RPC 2.0 stdio MCP server")
    sub.add_parser("selftest", help="Run offline 10-check verification suite")

    args = parser.parse_args(argv)
    if args.cmd == "mcp":
        return serve_stdio()
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
