"""Pytest suite for UE5 Doctor v1.1.0 zero-dependency stdio MCP server."""

from __future__ import annotations

import io
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import ue5_doctor  # noqa: E402


def _rpc(msg: dict) -> dict | None:
    return ue5_doctor.handle_rpc_message(msg)


def test_initialize_and_tools_list() -> None:
    init = _rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}})
    assert init is not None
    assert init["result"]["serverInfo"] == {"name": "ue5-doctor", "version": "1.1.0"}
    assert init["result"]["protocolVersion"] == "2025-03-26"

    # Notification emits None
    assert _rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None

    tl = _rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert tl is not None
    names = [t["name"] for t in tl["result"]["tools"]]
    assert "triage_ue5_log" in names
    assert "audit_ue5_ini" in names
    assert "trim_ue5_uproject" in names


def test_triage_ue5_log_lnk2019_private_vs_public() -> None:
    log_text = (
        "VXWeaponFX.cpp.obj : error LNK2019: unresolved external symbol "
        "\"public: static class UNiagaraComponent * __cdecl UNiagaraFunctionLibrary::SpawnSystemAtLocation\" "
        "referenced in function FireWeapon\n"
        "AutomationTool exiting with ExitCode=6\n"
    )
    resp = _rpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "triage_ue5_log", "arguments": {"text": log_text}},
        }
    )
    assert resp is not None
    sc = resp["result"]["structuredContent"]
    assert sc["ok"] is False
    assert sc["exitCode"] == 6
    assert sc["suggestedBuildCsModules"] == ["Niagara"]
    hint = sc["firstRootCause"]["hint"]
    assert "PrivateDependencyModuleNames" in hint
    assert "PublicDependencyModuleNames" in hint


def test_audit_ue5_ini_canonical_cvars_desktop_and_vr90() -> None:
    ini_text = "[/Script/Engine.RendererSettings]\nr.Streaming.PoolSize=12000\n"
    r_dt = _rpc(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "audit_ue5_ini", "arguments": {"text": ini_text, "vram_gb": 16, "mode": "desktop"}},
        }
    )
    assert r_dt is not None
    dt_cvars = {x["cvar"]: x["recommended"] for x in r_dt["result"]["structuredContent"]["recommendations"]}
    assert dt_cvars["r.Shadow.Virtual.MaxPhysicalPages"] == "4096"
    assert "r.VSM.MaxPhysicalPages" not in dt_cvars

    r_vr = _rpc(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "audit_ue5_ini", "arguments": {"text": ini_text, "vram_gb": 16, "mode": "vr90"}},
        }
    )
    assert r_vr is not None
    vr_cvars = {x["cvar"]: x["recommended"] for x in r_vr["result"]["structuredContent"]["recommendations"]}
    assert vr_cvars["r.Shadow.Virtual.MaxPhysicalPages"] == "2048"
    assert vr_cvars["vr.InstancedStereo"] == "True"
    assert "xr.InstancedStereo" not in vr_cvars


def test_stdio_newline_and_content_length_framing() -> None:
    msg1 = json.dumps({"jsonrpc": "2.0", "id": 10, "method": "ping"}).encode("utf-8") + b"\n"
    body2 = json.dumps({"jsonrpc": "2.0", "id": 11, "method": "tools/list"}).encode("utf-8")
    msg2 = f"Content-Length: {len(body2)}\r\n\r\n".encode("ascii") + body2

    inp = io.BytesIO(msg1 + msg2)
    out = io.BytesIO()
    assert ue5_doctor.serve_stdio(inp, out) == 0
    raw_out = out.getvalue().decode("utf-8")
    assert '"id":10' in raw_out
    assert "Content-Length:" in raw_out
    assert '"triage_ue5_log"' in raw_out
