"""Orchestrator: the main agent loop that ties generate-validate-render-analyze-revise."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vcv_agent.analyzer import (
    AudioFeatures,
    compare_features,
    extract_features,
    generate_spectrogram,
)
from vcv_agent.compiler import compile_vcv
from vcv_agent.config import settings
from vcv_agent.llm import build_system_prompt, generate_patch, get_audio_description
from vcv_agent.validator import ValidationResult, load_registry, validate_patch


@dataclass
class IterationResult:
    iteration: int
    patch: dict[str, Any]
    validation: ValidationResult
    features: AudioFeatures | None = None
    audio_description: str = ""
    explanation: str = ""
    wav_path: Path | None = None
    spectrogram_path: Path | None = None


@dataclass
class RunResult:
    run_dir: Path
    iterations: list[IterationResult] = field(default_factory=list)
    converged: bool = False
    best_iteration: int = 0


def run_agent(
    prompt: str,
    reference_wav: Path | None = None,
    max_iterations: int | None = None,
    use_audio_model: bool = True,
    render_fn: Any = None,  # injectable for testing
) -> RunResult:
    """Main agent loop.

    Args:
        prompt: text description of desired sound
        reference_wav: optional WAV file to match
        max_iterations: override from settings
        use_audio_model: whether to use GPT-4o audio for feedback
        render_fn: optional render function override (for testing without Rack)
    """
    if max_iterations is None:
        max_iterations = settings.max_iterations

    # Setup run directory
    ts = time.strftime("%Y%m%d_%H%M%S")
    run_dir = settings.runs_dir / f"run_{ts}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save target
    (run_dir / "target.txt").write_text(prompt)

    # Load registry
    registry = load_registry(settings.registry_path)
    system_prompt = build_system_prompt(settings.registry_path)

    # Extract reference features if provided
    target_features: AudioFeatures | None = None
    if reference_wav:
        target_features = extract_features(reference_wav)
        ref_spec = run_dir / "target_spectrogram.png"
        generate_spectrogram(reference_wav, ref_spec)
        (run_dir / "target_features.json").write_text(
            json.dumps(target_features.to_dict(), indent=2)
        )

    # Conversation history for the LLM
    history: list[dict[str, Any]] = []
    result = RunResult(run_dir=run_dir)

    for i in range(max_iterations):
        iter_dir = run_dir / f"iter_{i:03d}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"Iteration {i}")
        print(f"{'='*60}")

        # 1. Build the prompt for this iteration
        if i == 0:
            iter_prompt = f"Create a VCV Rack patch for: {prompt}"
            if target_features:
                features_json = json.dumps(target_features.to_dict(), indent=2)
                iter_prompt += f"\n\nTarget audio features:\n{features_json}"
        else:
            prev = result.iterations[-1]
            iter_prompt = _build_revision_prompt(prev, target_features)

        # 2. Generate patch via LLM
        print("  Generating patch...")
        spectrogram = result.iterations[-1].spectrogram_path if i > 0 else None
        try:
            patch, explanation = generate_patch(
                iter_prompt,
                system_prompt=system_prompt,
                history=history,
                spectrogram_path=spectrogram,
            )
        except Exception as e:
            print(f"  LLM error: {e}")
            break

        # Save LLM output
        (iter_dir / "patch.json").write_text(json.dumps(patch, indent=2))
        (iter_dir / "llm_response.json").write_text(json.dumps({
            "prompt": iter_prompt,
            "explanation": explanation,
        }, indent=2))

        # 3. Validate
        print("  Validating...")
        validation = validate_patch(patch, registry)
        (iter_dir / "validation.json").write_text(json.dumps(validation.to_dict(), indent=2))

        if not validation.valid:
            print(f"  Validation failed: {len(validation.errors)} errors")
            for err in validation.errors[:5]:
                print(f"    - {err.type}: {err.message}")

            # Feed errors back to LLM
            error_text = json.dumps(validation.to_dict(), indent=2)
            history.append({"role": "assistant", "content": json.dumps(patch)})
            history.append({
                "role": "user",
                "content": (
                    f"Validation failed:\n{error_text}\n"
                    "Fix these errors and output the corrected patch JSON."
                ),
            })

            iter_result = IterationResult(
                iteration=i, patch=patch, validation=validation, explanation=explanation
            )
            result.iterations.append(iter_result)
            continue

        print("  Validation passed!")

        # 4. Compile to .vcv
        vcv_path = iter_dir / "patch.vcv"
        compile_vcv(patch, vcv_path)
        print(f"  Compiled: {vcv_path}")

        # 5. Render
        wav_path = iter_dir / "audio.wav"
        features: AudioFeatures | None = None
        audio_desc = ""

        if render_fn:
            # Use injected render function (testing)
            render_fn(vcv_path, wav_path)
        else:
            try:
                from vcv_agent.renderer import render_patch

                print(f"  Rendering ({settings.render_duration}s)...")
                render_patch(vcv_path, wav_path)
            except Exception as e:
                print(f"  Render failed: {e}")
                print("  Skipping audio analysis for this iteration.")
                iter_result = IterationResult(
                    iteration=i,
                    patch=patch,
                    validation=validation,
                    explanation=explanation,
                    wav_path=None,
                )
                result.iterations.append(iter_result)
                history.append({"role": "assistant", "content": json.dumps(patch)})
                continue

        # 6. Analyze
        if wav_path.exists():
            print("  Analyzing audio...")
            spec_path = iter_dir / "spectrogram.png"
            generate_spectrogram(wav_path, spec_path)
            features = extract_features(wav_path)
            (iter_dir / "features.json").write_text(
                json.dumps(features.to_dict(), indent=2)
            )
            print(f"  Features: centroid={features.spectral_centroid_hz}Hz, "
                  f"pitch={features.estimated_pitch_hz}Hz, "
                  f"rms={features.rms_energy}")

            # Optional audio-native model
            if use_audio_model and settings.openai_api_key:
                try:
                    print("  Getting audio description from GPT-4o...")
                    audio_desc = get_audio_description(wav_path, prompt)
                    (iter_dir / "audio_description.txt").write_text(audio_desc)
                    print(f"  Audio desc: {audio_desc[:100]}...")
                except Exception as e:
                    print(f"  Audio model failed (non-fatal): {e}")

        # 7. Build history for next iteration
        iter_result = IterationResult(
            iteration=i,
            patch=patch,
            validation=validation,
            features=features,
            audio_description=audio_desc,
            explanation=explanation,
            wav_path=wav_path if wav_path.exists() else None,
            spectrogram_path=spec_path if spec_path.exists() else None,
        )
        result.iterations.append(iter_result)

        # Add to conversation history
        history.append({"role": "assistant", "content": json.dumps(patch) + "\n" + explanation})

        # 8. Check convergence
        if target_features and features:
            deltas = compare_features(features, target_features)
            (iter_dir / "deltas.json").write_text(json.dumps(deltas, indent=2))

            if _is_converged(features, target_features):
                print("  CONVERGED! Features match target within threshold.")
                result.converged = True
                result.best_iteration = i
                break

    # Save summary
    summary = {
        "prompt": prompt,
        "total_iterations": len(result.iterations),
        "converged": result.converged,
        "best_iteration": result.best_iteration,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\nRun complete: {run_dir}")
    print(f"  Iterations: {len(result.iterations)}")
    print(f"  Converged: {result.converged}")

    return result


def _build_revision_prompt(prev: IterationResult, target: AudioFeatures | None) -> str:
    """Build the revision prompt from the previous iteration's results."""
    parts = ["Revise the patch based on this feedback:\n"]

    if prev.features:
        parts.append(f"Current features:\n{json.dumps(prev.features.to_dict(), indent=2)}")

    if target and prev.features:
        deltas = compare_features(prev.features, target)
        parts.append(f"\nFeature deltas vs target:\n{json.dumps(deltas, indent=2)}")

    if prev.audio_description:
        parts.append(f"\nAudio description: {prev.audio_description}")

    parts.append(
        "\nChange at most 2-3 parameters. Explain what you're changing and why. "
        "Output the full revised patch JSON."
    )

    return "\n".join(parts)


def _is_converged(current: AudioFeatures, target: AudioFeatures, threshold: float = 0.15) -> bool:
    """Check if features are within threshold (15% relative error) of target."""
    for field_name in ["spectral_centroid_hz", "estimated_pitch_hz", "rms_energy"]:
        curr = getattr(current, field_name)
        tgt = getattr(target, field_name)
        if tgt == 0:
            continue
        rel_err = abs(curr - tgt) / abs(tgt)
        if rel_err > threshold:
            return False
    return True
