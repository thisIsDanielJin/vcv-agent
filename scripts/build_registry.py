"""Extract module registry from Fundamental plugin.json and existing catalog data.

Run once to bootstrap registry/modules.json. Extend manually as needed
by inspecting saved .vcv patch files for port/param IDs.
"""

import json
from pathlib import Path

# Base catalog from patchsmith reverse-engineering (port/param IDs verified against real patches).
# Modules not yet fully mapped get placeholder entries with just slug info,
# to be filled in by inspecting saved patches.

REGISTRY: dict[str, dict] = {}


def mod(plugin: str, model: str, **kwargs: object) -> None:
    key = f"{plugin}/{model}"
    entry: dict = {"plugin": plugin, "model": model, "hp": kwargs.get("hp", 0)}
    entry["params"] = kwargs.get("params", [])
    entry["inputs"] = kwargs.get("inputs", [])
    entry["outputs"] = kwargs.get("outputs", [])
    entry["data"] = kwargs.get("data")
    REGISTRY[key] = entry


# ─── Core ────────────────────────────────────────────────────────────

mod("Core", "MIDIToCVInterface",
    outputs=[
        {"id": 0, "name": "V/OCT"},
        {"id": 1, "name": "GATE"},
        {"id": 2, "name": "VEL"},
        {"id": 3, "name": "AFT"},
        {"id": 4, "name": "PW"},
        {"id": 5, "name": "MOD"},
        {"id": 6, "name": "RETRIG"},
        {"id": 7, "name": "CLK"},
        {"id": 8, "name": "VOL"},
    ],
    data={
        "channels": 1,
        "monoMode": 0,
        "polyMode": 0,
        "smooth": True,
        "clockDivision": 24,
        "midi": {"driver": -11, "deviceName": "QWERTY keyboard (US)", "channel": -1},
    },
)

mod("Core", "AudioInterface2",
    inputs=[
        {"id": 0, "name": "IN L"},
        {"id": 1, "name": "IN R"},
    ],
    outputs=[
        {"id": 0, "name": "OUT L"},
        {"id": 1, "name": "OUT R"},
    ],
    params=[
        {"id": 0, "name": "level", "min": 0.0, "max": 2.0, "default": 1.0},
    ],
    data={
        "audio": {
            "driver": 5,
            "deviceName": "",
            "sampleRate": 48000.0,
            "blockSize": 256,
        },
        "dcFilter": True,
    },
)

mod("Core", "Notes",
    data={"text": ""},
)

# ─── Fundamental: Oscillators ────────────────────────────────────────

mod("Fundamental", "VCO",
    inputs=[
        {"id": 0, "name": "V/OCT"},
        {"id": 1, "name": "FM"},
        {"id": 2, "name": "SYNC"},
        {"id": 3, "name": "PW"},
    ],
    outputs=[
        {"id": 0, "name": "SIN"},
        {"id": 1, "name": "TRI"},
        {"id": 2, "name": "SAW"},
        {"id": 3, "name": "SQR"},
    ],
    params=[
        {"id": 0, "name": "mode", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "sync", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 2, "name": "freq", "min": -4.0, "max": 4.0, "default": 0.0},
        {"id": 3, "name": "fine", "min": -0.083, "max": 0.083, "default": 0.0},
        {"id": 4, "name": "fm", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 5, "name": "pw", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 6, "name": "pwm", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 7, "name": "lin_fm", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "VCO2",
    inputs=[
        {"id": 0, "name": "V/OCT"},
        {"id": 1, "name": "FM"},
        {"id": 2, "name": "SYNC"},
    ],
    outputs=[
        {"id": 0, "name": "OUT"},
    ],
    params=[
        {"id": 0, "name": "offset", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "invert", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "freq", "min": -4.0, "max": 4.0, "default": 0.0},
        {"id": 3, "name": "fine", "min": -0.083, "max": 0.083, "default": 0.0},
        {"id": 4, "name": "fm", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 5, "name": "wave", "min": 0.0, "max": 3.0, "default": 1.5},
    ],
)

# ─── Fundamental: Filters ────────────────────────────────────────────

mod("Fundamental", "VCF",
    inputs=[
        {"id": 0, "name": "CUTOFF CV"},
        {"id": 1, "name": "RES CV"},
        {"id": 2, "name": "DRIVE CV"},
        {"id": 3, "name": "IN"},
    ],
    outputs=[
        {"id": 0, "name": "LPF"},
        {"id": 1, "name": "HPF"},
    ],
    params=[
        {"id": 0, "name": "cutoff", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 1, "name": "res", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "drive", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 3, "name": "cutoff_cv", "min": -1.0, "max": 1.0, "default": 0.5},
    ],
)

# ─── Fundamental: Amplifiers & Mixers ────────────────────────────────

mod("Fundamental", "VCA-1",
    inputs=[
        {"id": 0, "name": "CV"},
        {"id": 1, "name": "IN"},
    ],
    outputs=[
        {"id": 0, "name": "OUT"},
    ],
    params=[
        {"id": 0, "name": "level", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 1, "name": "exp", "min": 0.0, "max": 1.0, "default": 1.0},
    ],
)

mod("Fundamental", "VCA",
    inputs=[
        {"id": 0, "name": "IN 1"},
        {"id": 1, "name": "CV 1"},
        {"id": 2, "name": "IN 2"},
        {"id": 3, "name": "CV 2"},
    ],
    outputs=[
        {"id": 0, "name": "OUT 1"},
        {"id": 1, "name": "OUT 2"},
    ],
    params=[
        {"id": 0, "name": "level_1", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 1, "name": "level_2", "min": 0.0, "max": 1.0, "default": 0.5},
    ],
)

mod("Fundamental", "Mixer",
    inputs=[
        {"id": i, "name": f"IN {i+1}"} for i in range(6)
    ],
    outputs=[
        {"id": 0, "name": "MIX"},
    ],
    params=[
        {"id": 0, "name": "level", "min": 0.0, "max": 2.0, "default": 1.0},
    ],
)

mod("Fundamental", "VCMixer",
    inputs=[
        {"id": 0, "name": "IN 1"},
        {"id": 1, "name": "CV 1"},
        {"id": 2, "name": "IN 2"},
        {"id": 3, "name": "CV 2"},
        {"id": 4, "name": "IN 3"},
        {"id": 5, "name": "CV 3"},
        {"id": 6, "name": "IN 4"},
        {"id": 7, "name": "CV 4"},
    ],
    outputs=[
        {"id": 0, "name": "MIX"},
        {"id": 1, "name": "OUT 1"},
        {"id": 2, "name": "OUT 2"},
        {"id": 3, "name": "OUT 3"},
        {"id": 4, "name": "OUT 4"},
    ],
    params=[
        {"id": 0, "name": "mix_level", "min": 0.0, "max": 2.0, "default": 1.0},
        {"id": 1, "name": "ch_1", "min": 0.0, "max": 2.0, "default": 1.0},
        {"id": 2, "name": "ch_2", "min": 0.0, "max": 2.0, "default": 1.0},
        {"id": 3, "name": "ch_3", "min": 0.0, "max": 2.0, "default": 1.0},
        {"id": 4, "name": "ch_4", "min": 0.0, "max": 2.0, "default": 1.0},
    ],
)

# ─── Fundamental: Modulation ─────────────────────────────────────────

mod("Fundamental", "LFO",
    inputs=[
        {"id": 0, "name": "FM"},
        {"id": 1, "name": "RESET"},
        {"id": 2, "name": "PW"},
        {"id": 3, "name": "CLK"},
    ],
    outputs=[
        {"id": 0, "name": "SIN"},
        {"id": 1, "name": "TRI"},
        {"id": 2, "name": "SAW"},
        {"id": 3, "name": "SQR"},
    ],
    params=[
        {"id": 0, "name": "offset", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "invert", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "freq", "min": -8.0, "max": 10.0, "default": 0.0},
        {"id": 3, "name": "pw", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 4, "name": "fm", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 5, "name": "pwm", "min": -1.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "LFO2",
    inputs=[
        {"id": 0, "name": "FM"},
        {"id": 1, "name": "RESET"},
    ],
    outputs=[
        {"id": 0, "name": "OUT"},
    ],
    params=[
        {"id": 0, "name": "offset", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "invert", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "freq", "min": -8.0, "max": 10.0, "default": 0.0},
        {"id": 3, "name": "wave", "min": 0.0, "max": 3.0, "default": 1.5},
        {"id": 4, "name": "fm", "min": -1.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "ADSR",
    inputs=[
        {"id": 0, "name": "ATT CV"},
        {"id": 1, "name": "DEC CV"},
        {"id": 2, "name": "SUS CV"},
        {"id": 3, "name": "REL CV"},
        {"id": 4, "name": "GATE"},
        {"id": 5, "name": "RETRIG"},
    ],
    outputs=[
        {"id": 0, "name": "ENV"},
    ],
    params=[
        {"id": 0, "name": "att", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 1, "name": "dec", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 2, "name": "sus", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 3, "name": "rel", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 4, "name": "att_cv", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 5, "name": "dec_cv", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 6, "name": "sus_cv", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 7, "name": "rel_cv", "min": -1.0, "max": 1.0, "default": 0.0},
        {"id": 8, "name": "mode", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "Random",
    inputs=[
        {"id": 0, "name": "RATE CV"},
        {"id": 1, "name": "TRIG"},
        {"id": 2, "name": "SHAPE CV"},
        {"id": 3, "name": "IN"},
    ],
    outputs=[
        {"id": 0, "name": "STEP"},
        {"id": 1, "name": "LIN"},
        {"id": 2, "name": "SMTH"},
        {"id": 3, "name": "EXP"},
        {"id": 4, "name": "TRIG"},
    ],
    params=[
        {"id": 0, "name": "rate", "min": -8.0, "max": 10.0, "default": 0.0},
        {"id": 1, "name": "shape", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 2, "name": "offset", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 3, "name": "prob", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 4, "name": "rnd", "min": 0.0, "max": 1.0, "default": 1.0},
    ],
)

# ─── Fundamental: Effects ────────────────────────────────────────────

mod("Fundamental", "Delay",
    inputs=[
        {"id": 0, "name": "TIME CV"},
        {"id": 1, "name": "FDBK CV"},
        {"id": 2, "name": "MIX CV"},
        {"id": 3, "name": "IN"},
        {"id": 4, "name": "CLK"},
        {"id": 5, "name": "TONE CV"},
    ],
    outputs=[
        {"id": 0, "name": "WET"},
        {"id": 1, "name": "MIX"},
    ],
    params=[
        {"id": 0, "name": "time", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 1, "name": "feedback", "min": 0.0, "max": 1.0, "default": 0.4},
        {"id": 2, "name": "mix", "min": 0.0, "max": 1.0, "default": 0.5},
        {"id": 3, "name": "tone", "min": 0.0, "max": 1.0, "default": 0.5},
    ],
)

# ─── Fundamental: Noise ──────────────────────────────────────────────

mod("Fundamental", "Noise",
    outputs=[
        {"id": 0, "name": "WHITE"},
        {"id": 1, "name": "PINK"},
        {"id": 2, "name": "RED"},
        {"id": 3, "name": "VIOLET"},
        {"id": 4, "name": "BLUE"},
        {"id": 5, "name": "GRAY"},
        {"id": 6, "name": "BLACK"},
    ],
)

# ─── Fundamental: Sequencing ─────────────────────────────────────────

mod("Fundamental", "SEQ3",
    inputs=[
        {"id": 0, "name": "CLOCK"},
        {"id": 1, "name": "RESET"},
        {"id": 2, "name": "RUN"},
    ],
    outputs=[
        {"id": 0, "name": "CLK"},
        {"id": 1, "name": "CV 1"},
        {"id": 2, "name": "CV 2"},
        {"id": 3, "name": "CV 3"},
        {"id": 4, "name": "STEP 1"},
        {"id": 5, "name": "STEP 2"},
        {"id": 6, "name": "STEP 3"},
        {"id": 7, "name": "STEP 4"},
        {"id": 8, "name": "STEP 5"},
        {"id": 9, "name": "STEP 6"},
        {"id": 10, "name": "STEP 7"},
        {"id": 11, "name": "STEP 8"},
        {"id": 12, "name": "GATE"},
    ],
    params=[
        {"id": 0, "name": "run", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "reset", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "clock", "min": -2.0, "max": 6.0, "default": 1.0},
        {"id": 3, "name": "steps", "min": 1.0, "max": 8.0, "default": 8.0},
        *[{"id": 4 + i, "name": f"row1_{i+1}", "min": -10.0, "max": 10.0, "default": 0.0} for i in range(8)],
        *[{"id": 12 + i, "name": f"row2_{i+1}", "min": -10.0, "max": 10.0, "default": 0.0} for i in range(8)],
        *[{"id": 20 + i, "name": f"row3_{i+1}", "min": -10.0, "max": 10.0, "default": 0.0} for i in range(8)],
        *[{"id": 28 + i, "name": f"gate_{i+1}", "min": 0.0, "max": 1.0, "default": 1.0} for i in range(8)],
        {"id": 36, "name": "clock_pass", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 37, "name": "gate_mode", "min": 0.0, "max": 1.0, "default": 1.0},
        {"id": 38, "name": "mode_3", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
    data={"running": True, "gates": [1, 1, 1, 1, 1, 1, 1, 1], "clockPassthrough": False},
)

# ─── Fundamental: Utilities ──────────────────────────────────────────

mod("Fundamental", "8vert",
    inputs=[{"id": i, "name": f"IN {i+1}"} for i in range(8)],
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(8)],
    params=[
        {"id": i, "name": f"gain_{i+1}", "min": -1.0, "max": 1.0, "default": 0.0}
        for i in range(8)
    ],
)

mod("Fundamental", "Unity",
    inputs=[
        *[{"id": i, "name": f"IN {i+1}"} for i in range(6)],
    ],
    outputs=[
        {"id": 0, "name": "MIX"},
        {"id": 1, "name": "INV"},
    ],
)

mod("Fundamental", "Mutes",
    inputs=[{"id": i, "name": f"IN {i+1}"} for i in range(10)],
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(10)],
    params=[
        {"id": i, "name": f"mute_{i+1}", "min": 0.0, "max": 1.0, "default": 0.0}
        for i in range(10)
    ],
)

mod("Fundamental", "Pulses",
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(10)],
    params=[
        {"id": i, "name": f"pulse_{i+1}", "min": 0.0, "max": 1.0, "default": 0.0}
        for i in range(10)
    ],
)

mod("Fundamental", "Push",
    outputs=[
        {"id": 0, "name": "TRIG"},
        {"id": 1, "name": "GATE"},
    ],
)

mod("Fundamental", "Mult",
    inputs=[
        {"id": 0, "name": "IN"},
    ],
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(8)],
)

mod("Fundamental", "CVMix",
    inputs=[
        {"id": 0, "name": "IN 1"},
        {"id": 1, "name": "IN 2"},
        {"id": 2, "name": "IN 3"},
    ],
    outputs=[
        {"id": 0, "name": "MIX"},
    ],
    params=[
        {"id": 0, "name": "level_1", "min": -2.0, "max": 2.0, "default": 0.0},
        {"id": 1, "name": "level_2", "min": -2.0, "max": 2.0, "default": 0.0},
        {"id": 2, "name": "level_3", "min": -2.0, "max": 2.0, "default": 0.0},
    ],
)

mod("Fundamental", "Fade",
    inputs=[
        {"id": 0, "name": "IN 1"},
        {"id": 1, "name": "IN 2"},
        {"id": 2, "name": "CV"},
    ],
    outputs=[
        {"id": 0, "name": "OUT 1"},
        {"id": 1, "name": "OUT 2"},
    ],
    params=[
        {"id": 0, "name": "fade", "min": 0.0, "max": 1.0, "default": 0.5},
    ],
)

mod("Fundamental", "Octave",
    inputs=[{"id": 0, "name": "IN"}],
    outputs=[{"id": 0, "name": "OUT"}],
    params=[
        {"id": 0, "name": "octave", "min": -4.0, "max": 4.0, "default": 0.0},
    ],
)

mod("Fundamental", "Quantizer",
    inputs=[
        {"id": 0, "name": "IN"},
        {"id": 1, "name": "OFFSET CV"},
    ],
    outputs=[
        {"id": 0, "name": "OUT"},
    ],
    params=[
        {"id": 0, "name": "offset", "min": -1.0, "max": 1.0, "default": 0.0},
    ],
    data={"enabledNotes": [True] * 12},
)

mod("Fundamental", "Rescale",
    inputs=[{"id": 0, "name": "IN"}],
    outputs=[{"id": 0, "name": "OUT"}],
    params=[
        {"id": 0, "name": "gain", "min": -10.0, "max": 10.0, "default": 1.0},
        {"id": 1, "name": "offset", "min": -10.0, "max": 10.0, "default": 0.0},
        {"id": 2, "name": "min", "min": -10.0, "max": 10.0, "default": -10.0},
        {"id": 3, "name": "max", "min": -10.0, "max": 10.0, "default": 10.0},
    ],
)

# ─── Fundamental: Signal Processing ──────────────────────────────────

mod("Fundamental", "Process",
    inputs=[
        {"id": 0, "name": "IN"},
        {"id": 1, "name": "GATE"},
    ],
    outputs=[
        {"id": 0, "name": "S&H 1"},
        {"id": 1, "name": "S&H 2"},
        {"id": 2, "name": "T&H"},
        {"id": 3, "name": "H&T"},
        {"id": 4, "name": "SLEW"},
        {"id": 5, "name": "GLIDE"},
    ],
    params=[
        {"id": 0, "name": "slew", "min": 0.0, "max": 1.0, "default": 0.5},
    ],
)

mod("Fundamental", "SHASR",
    inputs=[
        *[{"id": i, "name": f"TRIG {i+1}"} for i in range(8)],
        *[{"id": 8 + i, "name": f"IN {i+1}"} for i in range(8)],
    ],
    outputs=[
        {"id": i, "name": f"S&H {i+1}"} for i in range(8)
    ],
    params=[
        {"id": 0, "name": "push", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 1, "name": "clear", "min": 0.0, "max": 1.0, "default": 0.0},
        {"id": 2, "name": "rnd", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "Gates",
    inputs=[
        {"id": 0, "name": "IN"},
    ],
    outputs=[
        {"id": 0, "name": "RISE"},
        {"id": 1, "name": "FALL"},
        {"id": 2, "name": "FLIP"},
        {"id": 3, "name": "FLOP"},
        {"id": 4, "name": "GATE"},
        {"id": 5, "name": "DLY"},
    ],
    params=[
        {"id": 0, "name": "length", "min": 0.0, "max": 1.0, "default": 0.5},
    ],
)

mod("Fundamental", "Logic",
    inputs=[
        {"id": 0, "name": "A"},
        {"id": 1, "name": "B"},
    ],
    outputs=[
        {"id": 0, "name": "OR"},
        {"id": 1, "name": "AND"},
        {"id": 2, "name": "XOR"},
        {"id": 3, "name": "NOR"},
        {"id": 4, "name": "NAND"},
        {"id": 5, "name": "XNOR"},
        {"id": 6, "name": "NOT A"},
        {"id": 7, "name": "NOT B"},
    ],
)

mod("Fundamental", "Compare",
    inputs=[
        {"id": 0, "name": "A"},
        {"id": 1, "name": "B"},
    ],
    outputs=[
        {"id": 0, "name": "MAX"},
        {"id": 1, "name": "MIN"},
        {"id": 2, "name": "CLIP"},
        {"id": 3, "name": "LIM"},
        {"id": 4, "name": "A>B"},
        {"id": 5, "name": "A<B"},
    ],
)

mod("Fundamental", "RandomValues",
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(7)],
    params=[
        {"id": 0, "name": "rnd", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
)

# ─── Fundamental: Routing ────────────────────────────────────────────

mod("Fundamental", "SequentialSwitch1",
    inputs=[
        {"id": 0, "name": "CLK"},
        {"id": 1, "name": "RESET"},
        {"id": 2, "name": "IN"},
    ],
    outputs=[{"id": i, "name": f"OUT {i+1}"} for i in range(4)],
    params=[
        {"id": 0, "name": "steps", "min": 1.0, "max": 4.0, "default": 4.0},
    ],
)

mod("Fundamental", "SequentialSwitch2",
    inputs=[
        {"id": 0, "name": "CLK"},
        {"id": 1, "name": "RESET"},
        *[{"id": 2 + i, "name": f"IN {i+1}"} for i in range(4)],
    ],
    outputs=[
        {"id": 0, "name": "OUT"},
    ],
    params=[
        {"id": 0, "name": "steps", "min": 1.0, "max": 4.0, "default": 4.0},
    ],
)

mod("Fundamental", "Split",
    inputs=[{"id": 0, "name": "POLY"}],
    outputs=[{"id": i, "name": f"CH {i+1}"} for i in range(16)],
)

mod("Fundamental", "Merge",
    inputs=[{"id": i, "name": f"CH {i+1}"} for i in range(16)],
    outputs=[{"id": 0, "name": "POLY"}],
    params=[
        {"id": 0, "name": "channels", "min": 1.0, "max": 16.0, "default": 16.0},
    ],
)

mod("Fundamental", "Sum",
    inputs=[{"id": 0, "name": "POLY"}],
    outputs=[{"id": 0, "name": "MONO"}],
    params=[
        {"id": 0, "name": "level", "min": 0.0, "max": 2.0, "default": 1.0},
    ],
)

mod("Fundamental", "MidSide",
    inputs=[
        {"id": 0, "name": "L"},
        {"id": 1, "name": "R"},
        {"id": 2, "name": "WIDTH CV"},
    ],
    outputs=[
        {"id": 0, "name": "L"},
        {"id": 1, "name": "R"},
    ],
    params=[
        {"id": 0, "name": "width", "min": 0.0, "max": 2.0, "default": 1.0},
    ],
)

# ─── Fundamental: Visualization ──────────────────────────────────────

mod("Fundamental", "Scope",
    inputs=[
        {"id": 0, "name": "X"},
        {"id": 1, "name": "Y"},
        {"id": 2, "name": "TRIG"},
    ],
    params=[
        {"id": 0, "name": "time", "min": -6.0, "max": -16.0, "default": -14.0},
        {"id": 1, "name": "x_scale", "min": -2.0, "max": 8.0, "default": 0.0},
        {"id": 2, "name": "x_pos", "min": -10.0, "max": 10.0, "default": 0.0},
        {"id": 3, "name": "y_scale", "min": -2.0, "max": 8.0, "default": 0.0},
        {"id": 4, "name": "y_pos", "min": -10.0, "max": 10.0, "default": 0.0},
        {"id": 5, "name": "trig_level", "min": -10.0, "max": 10.0, "default": 0.0},
        {"id": 6, "name": "external", "min": 0.0, "max": 1.0, "default": 0.0},
    ],
)

mod("Fundamental", "Viz",
    inputs=[{"id": 0, "name": "POLY"}],
)


# ─── Generate ────────────────────────────────────────────────────────

def main() -> None:
    out = Path(__file__).parent.parent / "registry" / "modules.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(REGISTRY, indent=2) + "\n")
    print(f"Wrote {len(REGISTRY)} modules to {out}")


if __name__ == "__main__":
    main()
