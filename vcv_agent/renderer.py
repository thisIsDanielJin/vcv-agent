"""Render a VCV Rack patch to WAV via patchsmith's in-process Go synth.

VCV Rack Pro headless mode exits immediately after loading the patch
(the engine needs an audio callback to stay alive). Patchsmith has a
working pure-Go DSP engine that emulates core Fundamental modules.

We convert the patch JSON to patchsmith's .forge DSL and call
`patchsmith render`.

Supported modules (patchsmith synth):
  Fundamental: VCO, VCA-1, ADSR, SEQ3, LFO, VCF, Noise, Delay
  Core: MIDIToCVInterface, AudioInterface2, Notes
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

PATCHSMITH_BIN = (
    Path.home() / "Documents" / "vcv-patchsmith" / "bin" / "patchsmith"
)

# Map (plugin, model, port_id, direction) -> forge port name.
# Extracted from patchsmith's catalog (builtin.go).
PORT_NAMES: dict[tuple[str, str, int, str], str] = {
    # Core.MIDIToCVInterface outputs
    ("Core", "MIDIToCVInterface", 0, "out"): "VOCT",
    ("Core", "MIDIToCVInterface", 1, "out"): "GATE",
    ("Core", "MIDIToCVInterface", 2, "out"): "VEL",
    # Core.AudioInterface2 inputs
    ("Core", "AudioInterface2", 0, "in"): "IN1",
    ("Core", "AudioInterface2", 1, "in"): "IN2",
    # Fundamental.VCO
    ("Fundamental", "VCO", 0, "in"): "PITCH",
    ("Fundamental", "VCO", 1, "in"): "FM",
    ("Fundamental", "VCO", 2, "in"): "SYNC",
    ("Fundamental", "VCO", 3, "in"): "PW",
    ("Fundamental", "VCO", 0, "out"): "SIN",
    ("Fundamental", "VCO", 1, "out"): "TRI",
    ("Fundamental", "VCO", 2, "out"): "SAW",
    ("Fundamental", "VCO", 3, "out"): "SQR",
    # Fundamental.VCA-1
    ("Fundamental", "VCA-1", 0, "in"): "CV",
    ("Fundamental", "VCA-1", 1, "in"): "IN",
    ("Fundamental", "VCA-1", 0, "out"): "OUT",
    # Fundamental.ADSR
    ("Fundamental", "ADSR", 4, "in"): "GATE",
    ("Fundamental", "ADSR", 5, "in"): "RETR",
    ("Fundamental", "ADSR", 0, "out"): "ENV",
    # Fundamental.VCF
    ("Fundamental", "VCF", 0, "in"): "CUTOFF_CV",
    ("Fundamental", "VCF", 1, "in"): "RES_CV",
    ("Fundamental", "VCF", 2, "in"): "DRIVE_CV",
    ("Fundamental", "VCF", 3, "in"): "IN",
    ("Fundamental", "VCF", 0, "out"): "LPF",
    ("Fundamental", "VCF", 1, "out"): "HPF",
    # Fundamental.LFO
    ("Fundamental", "LFO", 0, "in"): "FM",
    ("Fundamental", "LFO", 1, "in"): "RESET",
    ("Fundamental", "LFO", 2, "in"): "PW",
    ("Fundamental", "LFO", 3, "in"): "CLK",
    ("Fundamental", "LFO", 0, "out"): "SIN",
    ("Fundamental", "LFO", 1, "out"): "TRI",
    ("Fundamental", "LFO", 2, "out"): "SAW",
    ("Fundamental", "LFO", 3, "out"): "SQR",
    # Fundamental.Noise
    ("Fundamental", "Noise", 0, "out"): "WHITE",
    ("Fundamental", "Noise", 1, "out"): "PINK",
    ("Fundamental", "Noise", 2, "out"): "RED",
    # Fundamental.Delay
    ("Fundamental", "Delay", 0, "in"): "TIME_CV",
    ("Fundamental", "Delay", 1, "in"): "FB_CV",
    ("Fundamental", "Delay", 2, "in"): "MIX_CV",
    ("Fundamental", "Delay", 3, "in"): "IN",
    ("Fundamental", "Delay", 4, "in"): "CLK",
    ("Fundamental", "Delay", 0, "out"): "WET",
    ("Fundamental", "Delay", 1, "out"): "MIX",
    # Fundamental.SEQ3
    ("Fundamental", "SEQ3", 0, "in"): "CLOCK",
    ("Fundamental", "SEQ3", 1, "in"): "RESET",
    ("Fundamental", "SEQ3", 0, "out"): "CLK",
    ("Fundamental", "SEQ3", 1, "out"): "CV1",
    ("Fundamental", "SEQ3", 2, "out"): "CV2",
    ("Fundamental", "SEQ3", 3, "out"): "CV3",
    ("Fundamental", "SEQ3", 12, "out"): "TRIG",
}

# Param name map for .forge DSL
PARAM_NAMES: dict[tuple[str, str, int], str] = {
    ("Fundamental", "VCO", 2): "freq",
    ("Fundamental", "VCO", 3): "fine",
    ("Fundamental", "VCO", 4): "fm",
    ("Fundamental", "VCO", 5): "pw",
    ("Fundamental", "ADSR", 0): "att",
    ("Fundamental", "ADSR", 1): "dec",
    ("Fundamental", "ADSR", 2): "sus",
    ("Fundamental", "ADSR", 3): "rel",
    ("Fundamental", "VCA-1", 0): "level",
    ("Fundamental", "VCF", 0): "cutoff",
    ("Fundamental", "VCF", 1): "res",
    ("Fundamental", "VCF", 2): "drive",
    ("Fundamental", "VCF", 3): "cutoff_cv_scale",
    ("Fundamental", "LFO", 0): "offset",
    ("Fundamental", "LFO", 1): "invert",
    ("Fundamental", "LFO", 2): "rate",
    ("Fundamental", "Delay", 0): "time",
    ("Fundamental", "Delay", 1): "feedback",
    ("Fundamental", "Delay", 2): "mix",
    ("Fundamental", "SEQ3", 2): "clock",
    ("Fundamental", "SEQ3", 3): "steps",
}
# SEQ3 row1 params (4-11)
for _i in range(8):
    PARAM_NAMES[("Fundamental", "SEQ3", 4 + _i)] = f"row1_{_i + 1}"
    PARAM_NAMES[("Fundamental", "SEQ3", 12 + _i)] = f"row2_{_i + 1}"
    PARAM_NAMES[("Fundamental", "SEQ3", 20 + _i)] = f"row3_{_i + 1}"
for _i in range(8):
    PARAM_NAMES[("Fundamental", "SEQ3", 28 + _i)] = f"gate_{_i + 1}"

SUPPORTED = {
    "Fundamental/VCO", "Fundamental/VCA-1", "Fundamental/ADSR",
    "Fundamental/SEQ3", "Fundamental/LFO", "Fundamental/VCF",
    "Fundamental/Noise", "Fundamental/Delay",
    "Core/MIDIToCVInterface", "Core/AudioInterface2", "Core/Notes",
}


def _patch_json_to_forge(patch: dict[str, Any]) -> str:
    """Convert patch JSON to patchsmith .forge DSL."""
    lines = ["# auto-generated by vcv-agent"]
    modules = patch.get("modules", [])
    cables = patch.get("cables", [])

    id_to_name: dict[int, str] = {}
    id_to_key: dict[int, tuple[str, str]] = {}

    for i, mod in enumerate(modules):
        key = f"{mod['plugin']}/{mod['model']}"
        pk = (mod["plugin"], mod["model"])
        id_to_key[mod["id"]] = pk

        if key not in SUPPORTED:
            continue

        name = f"m{i}"
        id_to_name[mod["id"]] = name

        # Build param block
        params: dict[str, float] = {}
        for p in mod.get("params", []):
            pname = PARAM_NAMES.get((*pk, p["id"]))
            if pname:
                params[pname] = p["value"]

        slug = f"{mod['plugin']}.{mod['model']}"
        if params:
            param_str = ", ".join(
                f"{k} = {v}" for k, v in params.items()
            )
            lines.append(f"{name}: {slug} {{ {param_str} }}")
        else:
            lines.append(f"{name}: {slug}")

    # Wires
    for cable in cables:
        out_mod = cable.get("outputModuleId")
        in_mod = cable.get("inputModuleId")
        if out_mod not in id_to_name or in_mod not in id_to_name:
            continue

        out_pk = id_to_key[out_mod]
        in_pk = id_to_key[in_mod]
        out_port = PORT_NAMES.get(
            (*out_pk, cable["outputId"], "out")
        )
        in_port = PORT_NAMES.get((*in_pk, cable["inputId"], "in"))

        if out_port and in_port:
            lines.append(
                f"{id_to_name[out_mod]}.{out_port} -> "
                f"{id_to_name[in_mod]}.{in_port}"
            )

    return "\n".join(lines)


def render_patch(
    vcv_path: Path,
    output_wav: Path,
    duration: int | None = None,
) -> Path:
    """Render a patch to WAV via patchsmith's Go synth.

    Args:
        vcv_path: path to the .vcv file
        output_wav: where to write the rendered WAV
        duration: render duration in seconds (default: 8)
    """
    if duration is None:
        from vcv_agent.config import settings

        duration = settings.render_duration

    if not PATCHSMITH_BIN.exists():
        raise FileNotFoundError(
            f"patchsmith not found at {PATCHSMITH_BIN}. "
            "Run: cd ~/Documents/vcv-patchsmith && make build"
        )

    # Extract patch JSON
    import io
    import tarfile

    import pyzstd

    compressed = vcv_path.read_bytes()
    tar_bytes = pyzstd.decompress(compressed)
    tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))
    raw = tf.extractfile("./patch.json")
    if raw is None:
        raise RuntimeError(f"No patch.json in {vcv_path}")
    patch: dict[str, Any] = json.loads(raw.read())

    # Convert to .forge
    forge = _patch_json_to_forge(patch)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".forge", delete=False
    ) as f:
        f.write(forge)
        forge_path = Path(f.name)

    try:
        out_dir = output_wav.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [
                str(PATCHSMITH_BIN), "render",
                str(forge_path),
                "-d", f"{duration}s",
                "-o", str(out_dir.resolve()),
            ],
            capture_output=True,
            text=True,
            timeout=duration + 30,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"patchsmith render failed:\n"
                f"forge:\n{forge}\n"
                f"stderr: {result.stderr[:500]}"
            )

        # patchsmith writes audio.wav in the output dir
        rendered = out_dir / "audio.wav"
        if rendered.exists() and str(rendered) != str(output_wav):
            rendered.rename(output_wav)

        if not output_wav.exists():
            wavs = list(out_dir.glob("*.wav"))
            if wavs:
                wavs[0].rename(output_wav)
            else:
                raise RuntimeError(
                    f"No WAV after render.\n"
                    f"stdout: {result.stdout[:300]}\n"
                    f"stderr: {result.stderr[:300]}"
                )

        return output_wav
    finally:
        forge_path.unlink(missing_ok=True)


def _extract_notes(patch: dict[str, Any]) -> str:
    """Extract note sequence from SEQ3 row1 as MIDI note numbers."""
    for mod in patch.get("modules", []):
        if mod.get("model") != "SEQ3":
            continue
        params = {p["id"]: p["value"] for p in mod.get("params", [])}
        steps = int(params.get(3, 8))
        notes = []
        for s in range(steps):
            v_oct = params.get(4 + s, 0.0)
            midi = int(round(60 + v_oct * 12))
            midi = max(0, min(127, midi))
            notes.append(str(midi))
        return ",".join(notes)
    return "C4,E4,G4"


def is_available() -> bool:
    """Check if patchsmith binary exists."""
    return PATCHSMITH_BIN.exists()
