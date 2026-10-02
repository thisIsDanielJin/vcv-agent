# vcv-agent

LLM-in-the-loop sound design agent for VCV Rack Pro.

Generate a target sound description (or provide a reference audio file), and the agent iteratively
creates, renders, analyzes, and refines VCV Rack patches until the output converges on the target.

## How it works

```
Prompt / Reference audio
        |
        v
   LLM generates patch JSON
        |
        v
   Validate (module registry, ports, params)
        |
        v
   Render (VCV Rack Pro headless -> WAV)
        |
        v
   Analyze (spectrogram + audio features + audio-native model)
        |
        v
   Compare to target, decide: done or revise
        |
        v
   Loop (max N iterations)
```

## Requirements

- Python 3.11+
- VCV Rack 2 Pro (headless mode)
- API keys: OpenAI (GPT-4o for audio-native feedback) or compatible
- ffmpeg, sox (audio utilities)
- librosa (audio analysis)

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env  # add API keys

# text prompt mode
vcv-agent "short percussive acid bleep, A3, resonant filter sweep, 50ms decay"

# reference audio mode
vcv-agent --reference path/to/target.wav
```

## Status

Pre-alpha. Building slice by slice.

## License

MIT
