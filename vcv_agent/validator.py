"""Validate a VCV Rack patch JSON against the module registry."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ValidationError:
    type: str
    message: str
    fix: str = ""


@dataclass
class ValidationResult:
    valid: bool
    errors: list[ValidationError] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "valid": self.valid,
            "errors": [{"type": e.type, "message": e.message, "fix": e.fix} for e in self.errors],
        }
        return d


def load_registry(path: Path | str = "registry/modules.json") -> dict[str, Any]:
    with open(path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def validate_patch(patch: dict[str, Any], registry: dict[str, Any]) -> ValidationResult:
    """Validate a patch dict against the module registry. Returns structured errors."""
    errors: list[ValidationError] = []
    module_ids: dict[int, str] = {}  # id -> plugin/model

    modules = patch.get("modules", [])
    cables = patch.get("cables", [])

    if not modules:
        errors.append(ValidationError("empty_patch", "Patch has no modules"))
        return ValidationResult(valid=False, errors=errors)

    # 1. Validate modules
    for mod in modules:
        mod_id = mod.get("id")
        plugin = mod.get("plugin", "")
        model = mod.get("model", "")
        key = f"{plugin}/{model}"

        if key not in registry:
            available = ", ".join(sorted(registry.keys()))
            errors.append(ValidationError(
                "unknown_module",
                f"Unknown module: {key}",
                f"Available: {available}",
            ))
            continue

        spec = registry[key]
        module_ids[mod_id] = key

        # Validate params
        spec_params = {p["id"]: p for p in spec.get("params", [])}
        for param in mod.get("params", []):
            pid = param.get("id")
            val = param.get("value")
            if pid not in spec_params:
                valid_ids = sorted(spec_params.keys())
                errors.append(ValidationError(
                    "unknown_param",
                    f"Module {key} (id={mod_id}): unknown param id={pid}",
                    f"Valid param IDs: {valid_ids}",
                ))
                continue
            sp = spec_params[pid]
            if "min" in sp and "max" in sp and val is not None:
                if val < sp["min"] or val > sp["max"]:
                    errors.append(ValidationError(
                        "param_out_of_range",
                        f"Module {key} (id={mod_id}): param '{sp['name']}' value={val} "
                        f"outside [{sp['min']}, {sp['max']}]",
                        f"Set to within [{sp['min']}, {sp['max']}]",
                    ))

    # 2. Check audio output exists
    has_audio = any(
        m.get("plugin") == "Core" and m.get("model") == "AudioInterface2"
        for m in modules
    )
    if not has_audio:
        errors.append(ValidationError(
            "no_audio_output",
            "Patch has no Core/AudioInterface2. Audio will not be captured.",
            "Add a Core/AudioInterface2 module with cables to its IN L/R ports.",
        ))

    # 3. Validate cables
    for cable in cables:
        out_mod = cable.get("outputModuleId")
        in_mod = cable.get("inputModuleId")
        out_port = cable.get("outputId")
        in_port = cable.get("inputId")

        if out_mod not in module_ids:
            errors.append(ValidationError(
                "cable_unknown_module",
                f"Cable references unknown output module id={out_mod}",
                "outputModuleId must match an existing module's id",
            ))
            continue
        if in_mod not in module_ids:
            errors.append(ValidationError(
                "cable_unknown_module",
                f"Cable references unknown input module id={in_mod}",
                "inputModuleId must match an existing module's id",
            ))
            continue

        # Validate port IDs against registry
        out_key = module_ids[out_mod]
        in_key = module_ids[in_mod]
        out_spec = registry[out_key]
        in_spec = registry[in_key]

        out_ports = out_spec.get("outputs", [])
        in_ports = in_spec.get("inputs", [])

        max_out = max((p["id"] for p in out_ports), default=-1)
        max_in = max((p["id"] for p in in_ports), default=-1)

        if out_port is not None and out_ports and out_port > max_out:
            port_names = [f"{p['id']}={p['name']}" for p in out_ports]
            errors.append(ValidationError(
                "port_out_of_range",
                f"Cable: output port {out_port} on {out_key} exceeds max {max_out}",
                f"Available outputs: {port_names}",
            ))

        if in_port is not None and in_ports and in_port > max_in:
            port_names = [f"{p['id']}={p['name']}" for p in in_ports]
            errors.append(ValidationError(
                "port_out_of_range",
                f"Cable: input port {in_port} on {in_key} exceeds max {max_in}",
                f"Available inputs: {port_names}",
            ))

    # 4. Check for duplicate module IDs
    seen_ids: set[int] = set()
    for mod in modules:
        mid = mod.get("id")
        if mid in seen_ids:
            errors.append(ValidationError(
                "duplicate_module_id",
                f"Duplicate module id={mid}",
                "Each module must have a unique id",
            ))
        seen_ids.add(mid)

    return ValidationResult(valid=len(errors) == 0, errors=errors)
