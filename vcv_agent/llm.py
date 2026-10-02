"""LLM interface for patch generation and revision."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from vcv_agent.config import settings


def _load_registry_summary(registry_path: Path | str = "registry/modules.json") -> str:
    """Load registry and format as a compact summary for the system prompt."""
    with open(registry_path) as f:
        registry = json.load(f)

    lines = ["Available VCV Rack modules (Fundamental + Core):"]
    for key, spec in sorted(registry.items()):
        inputs = [f"{p['id']}:{p['name']}" for p in spec.get("inputs", [])]
        outputs = [f"{p['id']}:{p['name']}" for p in spec.get("outputs", [])]
        params = [
            f"{p['id']}:{p['name']}"
            f"[{p.get('min', '?')},{p.get('max', '?')}]={p.get('default', '?')}"
            for p in spec.get("params", [])
        ]
        lines.append(f"\n{key}:")
        if inputs:
            lines.append(f"  inputs: {', '.join(inputs)}")
        if outputs:
            lines.append(f"  outputs: {', '.join(outputs)}")
        if params:
            lines.append(f"  params: {', '.join(params)}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a VCV Rack patch designer. You create patches by outputting valid JSON
that can be loaded into VCV Rack 2 Pro.

{registry}

PATCH JSON FORMAT:
{{
  "version": "2.6.4",
  "modules": [
    {{
      "id": <unique int>,
      "plugin": "Fundamental",
      "model": "<model slug>",
      "params": [{{"id": <param_id>, "value": <float>}}, ...],
      "pos": [<x_hp>, 0]
    }}
  ],
  "cables": [
    {{
      "id": <unique int>,
      "outputModuleId": <module id>,
      "outputId": <output port id>,
      "inputModuleId": <module id>,
      "inputId": <input port id>
    }}
  ]
}}

RULES:
- Every patch MUST include Core/AudioInterface2 as the audio output
- Signal must reach AudioInterface2 inputs (id 0 = left, id 1 = right)
- Do NOT include VCV-Recorder. It is injected automatically for rendering.
- Use only Fundamental and Core modules from the registry above
- Parameter values must be within the documented [min, max] range
- Module IDs must be unique integers
- Cable IDs must be unique integers
- Self-playing patches: use SEQ3 with "data": {{"running": true, "gates": [1,1,1,1,1,1,1,1]}}
- For Core/AudioInterface2, include "data" with audio driver config
- Always include an ADSR envelope for amplitude shaping (gate from SEQ3 output 12)
- Make sure the signal path is complete: source -> processing -> VCA -> AudioInterface2

ITERATION RULES:
- When revising, change at most 2-3 parameters per iteration
- Explain what you changed and why
- If features plateau after 3 rounds, try a structural change (different waveform, new module)

Output ONLY the patch JSON. No markdown fences, no explanation before the JSON.
After the JSON, add a brief explanation of your changes."""


def build_system_prompt(registry_path: Path | str = "registry/modules.json") -> str:
    registry_summary = _load_registry_summary(registry_path)
    return SYSTEM_PROMPT.format(registry=registry_summary)


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def generate_patch(
    prompt: str,
    system_prompt: str | None = None,
    history: list[dict[str, Any]] | None = None,
    spectrogram_path: Path | None = None,
    model: str | None = None,
) -> tuple[dict[str, Any], str]:
    """Call the LLM to generate or revise a patch.

    Returns: (patch_dict, explanation_text)
    """
    if model is None:
        model = settings.model
    if system_prompt is None:
        system_prompt = build_system_prompt()

    client = OpenAI(api_key=settings.openai_api_key)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]

    if history:
        messages.extend(history)

    # Build user message with optional spectrogram image
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    if spectrogram_path and spectrogram_path.exists():
        b64 = _encode_image(spectrogram_path)
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
        })

    messages.append({"role": "user", "content": content})

    response = client.chat.completions.create(
        model=model,
        messages=messages,  # type: ignore[arg-type]
        max_tokens=8192,
        temperature=0.3,
    )

    text = response.choices[0].message.content or ""

    # Parse: extract JSON from response (may have explanation after it)
    patch_dict, explanation = _parse_response(text)
    return patch_dict, explanation


def get_audio_description(
    wav_path: Path,
    target_description: str,
    model: str = "gpt-4o-audio-preview",
) -> str:
    """Send audio to GPT-4o for natural language description and comparison.

    Uses the audio input capability of GPT-4o.
    """
    client = OpenAI(api_key=settings.openai_api_key)

    audio_b64 = base64.b64encode(wav_path.read_bytes()).decode("utf-8")

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an audio analysis expert for synthesizer sounds. "
                    "Describe the sound precisely: pitch, timbre, envelope shape, "
                    "brightness, rhythmic pattern, and overall character. "
                    "Then compare it to the target description."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {"data": audio_b64, "format": "wav"},
                    },
                    {
                        "type": "text",
                        "text": f"Describe this synthesizer sound. Target: {target_description}. "
                        "How close is it? What specifically differs?",
                    },
                ],
            },
        ],
        max_tokens=500,
    )

    return response.choices[0].message.content or ""


def _parse_response(text: str) -> tuple[dict[str, Any], str]:
    """Extract JSON patch and explanation from LLM response text."""
    # Try to find JSON object in the response
    # Look for the outermost { ... } pair
    depth = 0
    json_start = -1
    json_end = -1

    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                json_start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                json_end = i + 1
                break

    if json_start >= 0 and json_end > json_start:
        json_str = text[json_start:json_end]
        explanation = text[json_end:].strip()
        try:
            patch = json.loads(json_str)
            return patch, explanation
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {json_str[:200]}") from e

    raise ValueError(f"No JSON object found in LLM response:\n{text[:500]}")
