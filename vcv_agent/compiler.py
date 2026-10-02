"""Compile a patch dict into a .vcv file (tar + zstd archive)."""

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


def compile_vcv(patch: dict[str, Any], output_path: Path) -> Path:
    """Take a patch dict, compile to a .vcv file. Returns the output path."""
    patch = ensure_patch_defaults(patch)
    patch = assign_module_ids(patch)
    patch = layout_modules(patch)

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
