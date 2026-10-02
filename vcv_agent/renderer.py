"""Render a .vcv patch to WAV using VCV Rack Pro headless mode."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from vcv_agent.config import settings


def find_recorder_wav(user_dir: Path, timeout: float = 2.0) -> Path | None:
    """Look for the WAV file written by VCV-Recorder in the user directory."""
    # Recorder writes to the path specified in its data block,
    # or to ~/Documents/ by default. We override it in the patch.
    candidates = list(user_dir.rglob("*.wav"))
    if candidates:
        return candidates[0]
    return None


def render_patch(
    vcv_path: Path,
    output_wav: Path,
    duration: int | None = None,
) -> Path:
    """Run VCV Rack Pro headless on a patch, capture audio to WAV.

    Strategy: inject a VCV-Recorder module pointing at output_wav,
    then run Rack -h for `duration` seconds and kill it.

    Args:
        vcv_path: path to the .vcv file
        output_wav: where to write the rendered WAV
        duration: render duration in seconds (default from settings)

    Returns:
        Path to the rendered WAV file.
    """
    if duration is None:
        duration = settings.render_duration

    rack_bin = settings.resolve_rack_path()

    # Create a temporary user directory so Rack doesn't collide with
    # the real user's settings/autosave
    with tempfile.TemporaryDirectory(prefix="vcv-agent-") as tmp:
        tmp_path = Path(tmp)

        # Copy the .vcv to tmp so Rack can find it
        patch_copy = tmp_path / "patch.vcv"
        shutil.copy2(vcv_path, patch_copy)

        # Run Rack headless
        # -h = headless, no GUI
        # -u = user directory override
        proc = subprocess.Popen(
            [rack_bin, "-h", str(patch_copy), "-u", str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Wait for duration + small buffer for startup
            time.sleep(duration + 2)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # Find the rendered WAV
        wav = find_recorder_wav(tmp_path)
        if wav and wav.exists():
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(wav, output_wav)
            return output_wav

        # If Recorder module approach failed, check if we got audio another way
        raise RuntimeError(
            f"Render completed but no WAV found in {tmp_path}. "
            "Ensure the patch includes a VCV-Recorder module, or "
            "use BlackHole audio routing as fallback."
        )
