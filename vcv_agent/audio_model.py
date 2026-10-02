"""Local audio model: Qwen2-Audio-7B-Instruct (4-bit MLX) for Apple Silicon.

Provides a natural-language "second opinion" on rendered audio without
any API calls. The spectrogram + numeric features do the heavy lifting
for convergence decisions. This model adds subjective descriptions:
"bright", "percussive", "metallic", etc.

The model is loaded lazily on first call and reused across iterations.
First load downloads ~4.2 GB to ~/.cache/huggingface/ (one-time).
Inference takes ~20-30s per audio clip on M3 Pro.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

# Lazy-loaded globals so import is instant
_model: Any = None
_model_id = "mlx-community/Qwen2-Audio-7B-Instruct-4bit"


def _get_model() -> Any:
    """Load the model on first call, reuse after."""
    global _model
    if _model is not None:
        return _model

    from mlx_audio.stt.utils import load_model

    print(f"  Loading {_model_id} (first call only)...")
    t0 = time.time()
    _model = load_model(_model_id)
    print(f"  Model loaded in {time.time() - t0:.1f}s")
    return _model


def describe_audio(wav_path: Path, target_description: str) -> str:
    """Analyze a WAV file and return a natural-language description.

    Args:
        wav_path: path to the rendered WAV
        target_description: what the sound should be (for comparison)

    Returns:
        Text description of the sound + comparison to target.
    """
    model = _get_model()

    prompt = (
        "Describe this synthesizer sound in detail. "
        "Cover: pitch (high/low/specific note), timbre (harsh/warm/metallic/smooth), "
        "brightness (bright/dark), envelope (percussive/sustained/plucky), "
        "and character (noisy/tonal/resonant/distorted). "
        f"Then compare it to this target: {target_description}. "
        "What matches? What differs?"
    )

    t0 = time.time()
    result = model.generate(str(wav_path), prompt=prompt)
    elapsed = time.time() - t0

    description = result.text if hasattr(result, "text") else str(result)
    return f"{description}\n[Qwen2-Audio inference: {elapsed:.1f}s]"


def is_available() -> bool:
    """Check if MLX audio model can run on this machine."""
    try:
        import mlx  # noqa: F401
        import mlx_audio  # noqa: F401

        return True
    except ImportError:
        return False
