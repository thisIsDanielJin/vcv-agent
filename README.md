# vcv-agent

LLM-in-the-loop sound design agent for VCV Rack Pro.

Describe a sound (or provide a reference WAV), and the agent iteratively generates,
renders, analyzes, and refines VCV Rack patches until the output converges on the target.

## How it works

```mermaid
flowchart TD
    A["Prompt / Reference WAV"] --> B["LLM generates patch JSON"]
    B --> C{"Validate\n(registry check)"}
    C -- "errors" --> D["Feed errors back to LLM"]
    D --> B
    C -- "valid" --> E["Compile to .vcv"]
    E --> F["Render headless\n(Rack Pro -h)"]
    F --> G["Analyze WAV"]
    G --> H["Spectrogram\n(mel, PNG)"]
    G --> I["Audio features\n(centroid, pitch, rms...)"]
    G --> J["Audio-native model\n(GPT-4o listens)"]
    H & I & J --> K{"Converged?"}
    K -- "no" --> L["Build revision prompt\nwith feedback"]
    L --> B
    K -- "yes / max iters" --> M["Output: .vcv + .wav + run log"]

    style A fill:#1a1a2e,stroke:#e94560,color:#eee
    style M fill:#1a1a2e,stroke:#0f3460,color:#eee
    style K fill:#16213e,stroke:#e94560,color:#eee
    style C fill:#16213e,stroke:#e94560,color:#eee
```

## Architecture

```mermaid
graph LR
    subgraph Orchestrator
        CLI["CLI\n(click)"]
        ORCH["Agent Loop"]
    end

    subgraph Generation
        LLM["LLM Interface\n(OpenAI / Anthropic)"]
        REG["Module Registry\n(42 modules JSON)"]
    end

    subgraph Verification
        VAL["Validator"]
        COMP["Compiler\n(JSON → .vcv)"]
    end

    subgraph Audio
        REND["Renderer\n(Rack Pro headless)"]
        SPEC["Spectrogram\n(librosa)"]
        FEAT["Feature Extraction"]
        AUD["Audio-Native Model\n(GPT-4o audio)"]
    end

    CLI --> ORCH
    ORCH --> LLM
    REG --> LLM
    REG --> VAL
    ORCH --> VAL
    VAL --> COMP
    COMP --> REND
    REND --> SPEC
    REND --> FEAT
    REND --> AUD
    SPEC & FEAT & AUD --> ORCH

    style CLI fill:#0f3460,stroke:#e94560,color:#eee
    style ORCH fill:#0f3460,stroke:#e94560,color:#eee
    style LLM fill:#16213e,stroke:#0f3460,color:#eee
    style REG fill:#16213e,stroke:#0f3460,color:#eee
    style VAL fill:#1a1a2e,stroke:#0f3460,color:#eee
    style COMP fill:#1a1a2e,stroke:#0f3460,color:#eee
    style REND fill:#1a1a2e,stroke:#e94560,color:#eee
    style SPEC fill:#1a1a2e,stroke:#e94560,color:#eee
    style FEAT fill:#1a1a2e,stroke:#e94560,color:#eee
    style AUD fill:#1a1a2e,stroke:#e94560,color:#eee
```

## Feedback channels

The agent "hears" through three complementary channels:

```mermaid
flowchart LR
    WAV["rendered .wav"]

    WAV --> S["Spectrogram\n(visual)"]
    WAV --> F["Feature Extraction\n(numeric)"]
    WAV --> A["GPT-4o Audio\n(listens to WAV)"]

    S --> |"mel PNG\nsent as image"| LLM["LLM"]
    F --> |"centroid, pitch,\nrms, flatness..."| LLM
    A --> |"natural language\nsonic description"| LLM

    style WAV fill:#16213e,stroke:#e94560,color:#eee
    style S fill:#1a1a2e,stroke:#0f3460,color:#eee
    style F fill:#1a1a2e,stroke:#0f3460,color:#eee
    style A fill:#1a1a2e,stroke:#0f3460,color:#eee
    style LLM fill:#0f3460,stroke:#e94560,color:#eee
```

## Iteration strategy

```mermaid
stateDiagram-v2
    [*] --> Generate: initial prompt
    Generate --> Validate
    Validate --> FixErrors: invalid
    FixErrors --> Generate
    Validate --> Render: valid
    Render --> Analyze
    Analyze --> Compare
    Compare --> Tweak: delta > threshold\n(change 1-3 params)
    Compare --> StructuralChange: plateau 3 rounds\n(swap waveform, add module)
    Tweak --> Generate
    StructuralChange --> Generate
    Compare --> Done: converged or max iters
    Done --> [*]
```

## Requirements

- Python 3.11+
- VCV Rack 2 Pro (headless mode)
- OpenAI API key (GPT-4o for generation + audio feedback)
- librosa, matplotlib, pyzstd (installed via pip)

## Quick start

```bash
git clone https://github.com/thisIsDanielJin/vcv-agent.git
cd vcv-agent
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # add your OPENAI_API_KEY

# text prompt mode
vcv-agent "short percussive acid bleep, A3, resonant filter sweep, 50ms decay"

# reference audio mode
vcv-agent --reference path/to/target.wav

# validate a patch without rendering
vcv-agent --validate-only --patch-json path/to/patch.json
```

## Project structure

```
vcv-agent/
  vcv_agent/
    cli.py             # entry point
    orchestrator.py    # agent loop (generate-validate-render-analyze-revise)
    llm.py             # LLM interface (OpenAI, GPT-4o audio)
    validator.py       # structural patch validation against registry
    compiler.py        # patch JSON -> .vcv file (tar+zstd)
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

## Module scope (v1)

38 Fundamental modules + 3 Core modules. No third-party plugins.
The full registry with every parameter ID, port ID, and valid range
lives in `registry/modules.json`.

## Status

Pre-alpha. Core pipeline built, not yet battle-tested end-to-end.

## License

MIT
