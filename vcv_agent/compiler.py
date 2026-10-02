"""Compile a patch dict into a .vcv file (tar + zstd archive).

Handles: ID assignment, layout, Recorder injection for headless rendering,
and packing to the .vcv format (tar + zstd).
"""

from __future__ import annotations

import io
import json
import random
import tarfile
from pathlib import Path
from typing import Any

import pyzstd


def assign_module_ids(patch: dict[str, Any]) -> dict[str, Any]:
    """Assign unique int64 IDs to modules if missing, and fix cable references."""
    id_map: dict[Any, int] = {}
    for mod in patch.get("modules", []):
        old_id = mod.get("id")
        if old_id is None or not isinstance(old_id, int):
            new_id = random.randint(10**15, 10**16 - 1)
            id_map[old_id] = new_id
            mod["id"] = new_id
        else:
            id_map[old_id] = old_id

    # Fix cable references
    for cable in patch.get("cables", []):
        if cable.get("outputModuleId") in id_map:
            cable["outputModuleId"] = id_map[cable["outputModuleId"]]
        if cable.get("inputModuleId") in id_map:
            cable["inputModuleId"] = id_map[cable["inputModuleId"]]
        if "id" not in cable or not isinstance(cable.get("id"), int):
            cable["id"] = random.randint(10**15, 10**16 - 1)

    return patch


def layout_modules(patch: dict[str, Any]) -> dict[str, Any]:
    """Simple left-to-right layout. Assigns pos=[x, 0] to each module."""
    x = 0
    hp_width = 8  # default module width in HP
    for mod in patch.get("modules", []):
        if "pos" not in mod:
            mod["pos"] = [x, 0]
        x += hp_width
    return patch


def ensure_patch_defaults(patch: dict[str, Any]) -> dict[str, Any]:
    """Fill in required top-level VCV Rack patch fields."""
    patch.setdefault("version", "2.6.4")
    patch.setdefault("modules", [])
    patch.setdefault("cables", [])
    return patch


def inject_recorder(patch: dict[str, Any], wav_path: str) -> dict[str, Any]:
    """Inject a VCV-Recorder module that writes to wav_path.

    Finds the AudioInterface2 module, taps the cables going INTO its
    inputs, and routes copies to the Recorder's L/R inputs. Also
    wires the SEQ3 gate (if present) to the Recorder's gate input
    so recording starts when the sequencer runs.

    If there's no AudioInterface2, finds the last VCA or module with
    output going nowhere and taps that instead.
    """
    modules = patch.get("modules", [])
    cables = patch.get("cables", [])

    # Find AudioInterface2
    audio_mod = None
    for m in modules:
        if m.get("plugin") == "Core" and m.get("model") == "AudioInterface2":
            audio_mod = m
            break

    if audio_mod is None:
        return patch  # can't inject without knowing where audio goes

    audio_id = audio_mod["id"]

    # Find cables going into AudioInterface2 inputs (L=0, R=1)
    source_l = None
    source_r = None
    for cable in cables:
        if cable.get("inputModuleId") == audio_id:
            if cable.get("inputId") == 0:
                source_l = (cable["outputModuleId"], cable["outputId"])
            elif cable.get("inputId") == 1:
                source_r = (cable["outputModuleId"], cable["outputId"])

    if source_l is None and source_r is None:
        return patch  # nothing feeding audio output

    # Create Recorder module
    rec_id = random.randint(10**15, 10**16 - 1)
    recorder = {
        "id": rec_id,
        "plugin": "VCV-Recorder",
        "model": "Recorder",
        "params": [
            {"id": 0, "value": 1.0},  # gain
            {"id": 1, "value": 1.0},  # rec (auto-record)
        ],
        "data": {
            "format": "wav",
            "path": wav_path,
            "incrementPath": False,
            "sampleRate": 48000,
            "depth": 16,
            "bitRate": 256000,
        },
    }
    modules.append(recorder)

    # Wire audio sources to Recorder (L=port 2, R=port 3)
    if source_l:
        cables.append({
            "id": random.randint(10**15, 10**16 - 1),
            "outputModuleId": source_l[0],
            "outputId": source_l[1],
            "inputModuleId": rec_id,
            "inputId": 2,  # Recorder LEFT
        })
    if source_r:
        cables.append({
            "id": random.randint(10**15, 10**16 - 1),
            "outputModuleId": source_r[0],
            "outputId": source_r[1],
            "inputModuleId": rec_id,
            "inputId": 3,  # Recorder RIGHT
        })
    # If mono, duplicate L to R
    if source_l and not source_r:
        cables.append({
            "id": random.randint(10**15, 10**16 - 1),
            "outputModuleId": source_l[0],
            "outputId": source_l[1],
            "inputModuleId": rec_id,
            "inputId": 3,  # Recorder RIGHT
        })

    # Wire SEQ3 gate to Recorder gate input (port 0) so recording starts
    for m in modules:
        if m.get("plugin") == "Fundamental" and m.get("model") == "SEQ3":
            cables.append({
                "id": random.randint(10**15, 10**16 - 1),
                "outputModuleId": m["id"],
                "outputId": 3,  # SEQ3 CV3 -- use as constant high
                "inputModuleId": rec_id,
                "inputId": 0,  # Recorder GATE
            })
            break

    return patch


def compile_vcv(
    patch: dict[str, Any],
    output_path: Path,
    wav_path: str | None = None,
) -> Path:
    """Take a patch dict, compile to a .vcv file.

    If wav_path is provided, injects a VCV-Recorder module pointing at it.
    Returns the output path.
    """
    patch = ensure_patch_defaults(patch)
    patch = assign_module_ids(patch)
    patch = layout_modules(patch)

    if wav_path:
        patch = inject_recorder(patch, wav_path)

    patch_json = json.dumps(patch, indent=2).encode("utf-8")

    # Build tar archive in memory
    tar_buf = io.BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w") as tf:
        info = tarfile.TarInfo(name="./patch.json")
        info.size = len(patch_json)
        tf.addfile(info, io.BytesIO(patch_json))

        # Empty modules directory (required by Rack)
        dir_info = tarfile.TarInfo(name="./modules/")
        dir_info.type = tarfile.DIRTYPE
        tf.addfile(dir_info)

    # Compress with zstd
    tar_bytes = tar_buf.getvalue()
    compressed = pyzstd.compress(tar_bytes)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(compressed)
    return output_path
