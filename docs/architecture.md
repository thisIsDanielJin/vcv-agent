# vcv-agent -- Architecture

## Problem

LLMs can generate VCV Rack patch JSON, but the results are bad because:
1. Structural errors (wrong slugs, invalid port IDs, out-of-range params)
2. No sonic feedback -- the LLM cannot hear what it produced

This project closes the loop: generate, render, hear, compare, revise.

## System overview

```
 USER
  |  "make a bleepy acid line in A minor"
  |  (or: --reference target.wav)
  v
┌─────────────────────────────────────────────────┐
│              ORCHESTRATOR (Python)               │
│                                                  │
│  1. Prompt LLM with task + context               │
│  2. LLM returns patch JSON                       │
│  3. Validate patch (module registry)             │
│  4. Fix structural errors (re-prompt if needed)  │
│  5. Write .vcv file                              │
│  6. Render headless (Rack Pro -h) -> WAV         │
│  7. Analyze WAV:                                 │
│     a. spectrogram (mel, PNG)                    │
│     b. audio features (centroid, pitch, rms...)  │
│     c. audio-native model (GPT-4o audio input)   │
│  8. Compare analysis to target                   │
│  9. Feed comparison back to LLM                  │
│  10. LLM revises patch -> goto 3                 │
│  11. Stop when converged or max iterations hit   │
│                                                  │
│  Output: final .vcv + .wav + run log             │
└─────────────────────────────────────────────────┘
```

## Components

### 1. Module registry (`registry/`)

Machine-readable JSON catalog of every Fundamental + Core module:
- slug, plugin name
- every parameter: id, name, min, max, default
- every input port: id, name
- every output port: id, name
- default data blocks (for modules with stateful settings)

Source: extracted from real .vcv patch files + Rack SDK docs.
Scope: Fundamental (38 modules) + Core (MIDI-to-CV, Audio, Notes) only.
No third-party modules in v1.

Used by the validator and by the LLM prompt (as context for what's available).

### 2. Patch validator (`validator/`)

Deterministic, fast, no audio. Checks:
- Every module slug exists in registry
- Every cable references valid output/input port IDs on existing modules
- Every parameter value is within min/max range
- Audio output module exists (signal chain terminates)
- No duplicate module IDs

Returns structured errors the LLM can act on:
```json
{
  "valid": false,
  "errors": [
    {"type": "unknown_module", "module": "Fundamental/Nope", "fix": "available modules: VCO, VCO2, ..."},
    {"type": "port_out_of_range", "module_id": 3, "port_id": 99, "max_port_id": 3}
  ]
}
```

### 3. Renderer (`renderer/`)

Invokes VCV Rack Pro in headless mode, captures audio output.

Pipeline:
1. Write validated patch JSON, pack as .vcv (tar + zstd)
2. Inject Recorder module into patch (or use audio file output)
3. Run: `/path/to/Rack -h patch.vcv`
4. Wait for render duration (configurable, default 8s)
5. Collect WAV output
6. Kill process

Config:
- `RACK_PATH`: path to Rack binary (default: auto-detect)
- `RENDER_DURATION`: seconds to capture (default: 8)
- `SAMPLE_RATE`: 44100 or 48000

Note: VCV Rack renders in real-time only. An 8s patch takes 8s.

### 4. Analyzer (`analyzer/`)

Three analysis channels, combined into one feedback payload:

**a. Spectrogram (always runs)**
- librosa mel spectrogram -> PNG
- Side-by-side with reference spectrogram (if reference mode)
- Sent to LLM as image attachment

**b. Audio features (always runs)**
- Spectral centroid (brightness, Hz)
- Estimated fundamental pitch (Hz)
- RMS energy (loudness)
- Spectral flatness (0 = tonal, 1 = noisy)
- Onset count + timing (rhythm pattern)
- Duration of non-silence
- Envelope shape (attack/decay estimate)

Returned as structured JSON. LLM uses this for precise parameter reasoning.

**c. Audio-native model (optional, configurable)**
- Send WAV directly to GPT-4o (audio input) or Qwen2-Audio
- Ask: "Describe this sound. How does it compare to: {target description}?"
- Returns natural language sonic description
- Most useful for subjective qualities ("does this sound bleepy?")

Feedback payload sent to LLM per iteration:
```json
{
  "iteration": 3,
  "spectrogram_path": "runs/run_001/iter_003/spectrogram.png",
  "features": {
    "spectral_centroid_hz": 2400,
    "estimated_pitch_hz": 440,
    "rms_energy": 0.3,
    "spectral_flatness": 0.1,
    "onset_count": 8,
    "duration_sec": 8.0
  },
  "audio_description": "A bright, metallic tone with fast attack...",
  "target_features": { ... },
  "feature_deltas": {
    "spectral_centroid_hz": "+1600 (too bright)",
    "estimated_pitch_hz": "+220 (octave too high)"
  }
}
```

### 5. LLM interface (`llm/`)

Manages the conversation loop with the LLM. Supports:
- OpenAI API (GPT-4o, GPT-4.1) for patch generation + audio-native feedback
- Anthropic API (Claude) for patch generation + spectrogram vision
- Extensible to other providers

Prompt structure per iteration:

**System prompt:** Module registry (compressed), patch JSON schema,
iteration rules (change max 2-3 params per round, explain reasoning).

**Iteration prompt:**
- Current patch JSON
- Analysis results (spectrogram image + features + audio description)
- History of previous iterations (what changed, what effect it had)
- Target description or reference analysis
- Instruction: revise the patch or declare done

Convergence rules:
- Feature deltas below threshold for 2 consecutive iterations -> done
- Audio-native model says "close match" -> done
- Max iterations reached (default: 10) -> stop, output best attempt

### 6. Patch compiler (`compiler/`)

Converts the LLM's patch JSON into a loadable .vcv file:
- Assign numeric module IDs
- Set default data blocks from registry
- Compute module positions (simple left-to-right layout)
- Serialize to patch.json
- Pack: tar + zstd -> .vcv

### 7. CLI (`cli.py`)

Entry point. Two modes:

```bash
# Text prompt: describe what you want
vcv-agent "short percussive acid bleep, A3, resonant filter sweep"

# Reference audio: match this sound
vcv-agent --reference target.wav

# Options
vcv-agent --max-iters 8 --model gpt-4o --no-audio-feedback "..."
```

## Iteration strategy

1. LLM generates initial patch from description (or closest guess to reference)
2. Each iteration: change 1-3 parameters max, explain why
3. If features plateau after 3 rounds, try structural change (different waveform, different signal path)
4. Log every iteration: patch JSON, WAV, spectrogram, features, LLM reasoning

## Run directory layout

```
runs/
  run_001/
    target.txt              # or target.wav + target_spectrogram.png
    iter_000/
      patch.json
      patch.vcv
      audio.wav
      spectrogram.png
      features.json
      llm_response.json     # reasoning + patch diff
    iter_001/
      ...
    iter_final/
      ...
    summary.json            # iterations, convergence, best attempt
```

## Module scope (v1)

Only Fundamental + Core modules. 38 Fundamental modules:

VCO, VCO2, VCF, VCA-1, VCA, LFO, LFO2, Delay, ADSR, Mixer, VCMixer,
8vert, Unity, Mutes, Pulses, Scope, SEQ3, SequentialSwitch1,
SequentialSwitch2, Octave, Quantizer, Split, Merge, Sum, Viz, MidSide,
Noise, Random, CVMix, Fade, Logic, Compare, Gates, Process, Mult,
Rescale, RandomValues, Push, SHASR

Core modules: MIDIToCVInterface, AudioInterface2, Notes

## Tech choices

| Concern        | Choice           | Why                                          |
|----------------|------------------|----------------------------------------------|
| Language       | Python 3.11+     | librosa, openai SDK, rapid iteration         |
| Audio analysis | librosa + numpy  | Best DSP library for feature extraction      |
| Spectrogram    | librosa + matplotlib | Standard, LLM-friendly PNG output        |
| LLM SDK        | openai + anthropic | GPT-4o audio-native, Claude vision         |
| Patch packing  | tarfile + pyzstd | Pure Python .vcv creation                    |
| CLI            | click            | Simple, no magic                             |
| Config         | .env + pydantic  | Typed settings, easy to override             |

## Build order (slices)

1. Module registry JSON (extract from real patches)
2. Patch validator
3. Patch compiler (JSON -> .vcv)
4. Renderer (headless Rack Pro -> WAV)
5. Analyzer (spectrogram + features)
6. Single LLM iteration (generate -> validate -> render -> analyze -> prompt)
7. Full loop with convergence detection
8. Audio-native model integration (GPT-4o audio input)
9. Reference audio mode (match a target WAV)
10. CLI polish
