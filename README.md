# vcv-agent

LLM-in-the-loop sound design agent for VCV Rack Pro.

Describe a sound (or provide a reference WAV), and the agent iteratively generates,
renders, analyzes, and refines VCV Rack patches until the output converges on the target.

## How it works

```mermaid
flowchart TD
    A["Prompt or Reference WAV"] --> B

    subgraph LOOP ["Agent loop (max N iterations)"]
        B["LLM generates/revises\npatch JSON"] --> C{"Validate\nagainst module registry"}
        C -- "invalid" --> D["Append errors\nto conversation"]
        D --> B
        C -- "valid" --> E["Compile JSON to .vcv\n+ inject Recorder module"]
        E --> F["Render via Rack Pro\nheadless mode, WAV"]
        F --> G["Spectrogram\n(mel, PNG)"]
        F --> H["Audio features\n(centroid, pitch, rms,\nflatness, onsets)"]
        F --> I["Qwen2-Audio 7B\nlocal, describes sound"]
        G & H & I --> J["Build revision prompt:\nspectrogram as image +\nfeature deltas + audio description"]
        J --> K{"Features within\n15% of target?"}
        K -- "no, delta > threshold" --> B
    end

    K -- "yes, or max iters" --> M["Output:\nfinal .vcv + .wav +\nrun log per iteration"]

    style A fill:#1a1a2e,stroke:#e94560,color:#eee
    style M fill:#1a1a2e,stroke:#0f3460,color:#eee
    style K fill:#16213e,stroke:#e94560,color:#eee
    style C fill:#16213e,stroke:#e94560,color:#eee
```

## Architecture

```mermaid
graph TD
    subgraph cli ["CLI  (cli.py)"]
        CMD["vcv-agent 'prompt'\nvcv-agent --reference target.wav"]
    end

    subgraph orch ["Orchestrator  (orchestrator.py)"]
        LOOP["Agent loop\nmanages iteration state,\nconversation history,\nconvergence check"]
    end

    subgraph gen ["Generation"]
        REG["Module Registry\nregistry/modules.json\n42 modules: params, ports, ranges"]
        LLM["LLM Interface  (llm.py)\nClaude Sonnet via hyperspace proxy\nSystem prompt includes\nfull registry + patch schema"]
    end

    subgraph verify ["Verification"]
        VAL["Validator  (validator.py)\nModule slugs, param ranges,\nport IDs, cable refs,\naudio output check"]
        COMP["Compiler  (compiler.py)\nAssign module IDs, layout,\ninject Recorder,\nJSON, tar+zstd, .vcv"]
    end

    subgraph audio ["Audio Pipeline"]
        REND["Renderer  (renderer.py)\nRack Pro headless: -h flag\nTemp user dir, kill after N sec\nWAV via injected Recorder"]
        ANLZ["Analyzer  (analyzer.py)\nMel spectrogram, PNG\nFeature extraction, JSON\n(librosa + matplotlib)"]
        QWEN["Qwen2-Audio 7B  (audio_model.py)\nLocal MLX, 4-bit quantized\n~4.2 GB, no API calls\nDescribes sound character"]
    end

    CMD --> LOOP
    LOOP -- "prompt + history" --> LLM
    REG -- "system prompt context" --> LLM
    LLM -- "patch JSON" --> LOOP
    LOOP -- "patch JSON" --> VAL
    REG -- "validation rules" --> VAL
    VAL -- "errors or OK" --> LOOP
    LOOP -- "valid patch" --> COMP
    COMP -- ".vcv file" --> REND
    REND -- ".wav file" --> ANLZ
    REND -- ".wav file" --> QWEN
    ANLZ -- "spectrogram PNG +\nfeatures JSON" --> LOOP
    QWEN -- "sonic description" --> LOOP

    style CMD fill:#0f3460,stroke:#e94560,color:#eee
    style LOOP fill:#0f3460,stroke:#e94560,color:#eee
    style LLM fill:#16213e,stroke:#0f3460,color:#eee
    style REG fill:#16213e,stroke:#0f3460,color:#eee
    style VAL fill:#1a1a2e,stroke:#0f3460,color:#eee
    style COMP fill:#1a1a2e,stroke:#0f3460,color:#eee
    style REND fill:#1a1a2e,stroke:#e94560,color:#eee
    style ANLZ fill:#1a1a2e,stroke:#e94560,color:#eee
    style QWEN fill:#1a1a2e,stroke:#e94560,color:#eee
```

## Requirements

- macOS with Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- VCV Rack 2 Pro (headless mode)
- SAP Hyperspace proxy running (`localhost:6655`) for Claude Sonnet

## Quick start

```bash
git clone https://github.com/thisIsDanielJin/vcv-agent.git
cd vcv-agent
python -m venv .venv && source .venv/bin/activate
pip install -e ".[audio-model]"   # includes Qwen2-Audio via MLX
# no API keys needed -- Claude runs via hyperspace proxy, audio model is local

# text prompt mode
vcv-agent "short percussive acid bleep, A3, resonant filter sweep, 50ms decay"

# reference audio mode
vcv-agent --reference path/to/target.wav

# skip local audio model (faster iterations, spectrogram + features only)
vcv-agent --no-audio-feedback "bright FM bleep, metallic, fast decay"

# validate a patch without rendering
vcv-agent --validate-only --patch-json path/to/patch.json
```

## Project structure

```
vcv-agent/
  vcv_agent/
    cli.py             # entry point
    orchestrator.py    # agent loop (generate-validate-render-analyze-revise)
    llm.py             # LLM interface (OpenAI GPT-4o for patch generation)
    audio_model.py     # local Qwen2-Audio 7B (4-bit MLX, no API)
    validator.py       # structural patch validation against registry
    compiler.py        # patch JSON -> .vcv file + Recorder injection
    renderer.py        # VCV Rack Pro headless rendering
    analyzer.py        # spectrogram + audio feature extraction
    config.py          # settings from .env
  registry/
    modules.json       # 42 modules: params, ports, ranges
  docs/
    architecture.md    # full design doc
  test/                # pytest suite
  scripts/
    build_registry.py  # regenerate registry from source data
```

## Audio feedback

The agent "hears" through three complementary channels:

| Channel | What it provides | Speed | Role |
|---|---|---|---|
| **Spectrogram** (librosa) | Mel spectrogram PNG, sent to LLM as image | Instant | Visual frequency/time overview |
| **Audio features** (librosa) | Centroid, pitch, RMS, flatness, onsets as numbers | Instant | Drives convergence decisions (15% threshold) |
| **Qwen2-Audio** (local MLX) | Natural language description of the sound | ~30s | Subjective second opinion ("bright", "metallic", "percussive") |

## Module scope (v1)

38 Fundamental modules + 3 Core modules + Viz. No third-party plugins.
The full registry with every parameter ID, port ID, and valid range
lives in `registry/modules.json`.

## Status

Pre-alpha. Core pipeline built, not yet battle-tested end-to-end.

## License

MIT
