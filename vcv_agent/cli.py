"""CLI entry point."""

from __future__ import annotations

from pathlib import Path

import click


@click.command()
@click.argument("prompt", required=False)
@click.option("--reference", "-r", type=click.Path(exists=True), help="Reference WAV to match")
@click.option("--max-iters", "-n", type=int, default=None, help="Max iterations (default: 10)")
@click.option("--model", "-m", type=str, default=None, help="LLM model (default: gpt-4o)")
@click.option("--no-audio-feedback", is_flag=True, help="Skip GPT-4o audio analysis")
@click.option("--validate-only", is_flag=True, help="Just validate a patch JSON, no rendering")
@click.option("--patch-json", type=click.Path(exists=True), help="Validate an existing patch JSON")
def main(
    prompt: str | None,
    reference: str | None,
    max_iters: int | None,
    model: str | None,
    no_audio_feedback: bool,
    validate_only: bool,
    patch_json: str | None,
) -> None:
    """VCV Rack sound design agent. Iteratively creates patches via LLM + audio feedback.

    PROMPT: describe the sound you want, e.g. "short acid bleep, A3, resonant filter sweep"
    """
    if validate_only and patch_json:
        _run_validation(Path(patch_json))
        return

    if not prompt and not reference:
        click.echo("Provide a text prompt or --reference WAV file.")
        raise SystemExit(1)

    if model:
        from vcv_agent.config import settings

        settings.model = model

    from vcv_agent.orchestrator import run_agent

    result = run_agent(
        prompt=prompt or "Match the reference audio as closely as possible.",
        reference_wav=Path(reference) if reference else None,
        max_iterations=max_iters,
        use_audio_model=not no_audio_feedback,
    )

    if result.converged:
        click.echo(f"\nConverged at iteration {result.best_iteration}!")
    else:
        click.echo(f"\nDid not converge after {len(result.iterations)} iterations.")
    click.echo(f"Results in: {result.run_dir}")


def _run_validation(patch_path: Path) -> None:
    """Validate a single patch JSON file against the registry."""
    import json

    from vcv_agent.validator import load_registry, validate_patch

    patch = json.loads(patch_path.read_text())
    registry = load_registry()
    result = validate_patch(patch, registry)

    if result.valid:
        click.echo("VALID")
    else:
        click.echo(f"INVALID: {len(result.errors)} errors")
        for err in result.errors:
            click.echo(f"  [{err.type}] {err.message}")
            if err.fix:
                click.echo(f"    fix: {err.fix}")


if __name__ == "__main__":
    main()
