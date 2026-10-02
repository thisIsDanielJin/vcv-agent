"""Render a .vcv patch to WAV using VCV Rack Pro headless mode.

Pipeline:
1. Recompile the patch with a VCV-Recorder module injected (writes to a known path)
2. Copy plugins needed (VCV-Recorder) to the temp user directory
3. Launch `Rack -h patch.vcv -u tmpdir`
4. Wait for render duration + buffer
5. Kill process, collect the WAV
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import pyzstd

from vcv_agent.compiler import compile_vcv
from vcv_agent.config import settings


def _extract_patch_json(vcv_path: Path) -> dict[str, Any]:
    """Extract patch.json from a .vcv file."""
    compressed = vcv_path.read_bytes()
    import io

    tar_bytes = pyzstd.decompress(compressed)
    tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))
    raw = tf.extractfile("./patch.json")
    if raw is None:
        raise RuntimeError(f"No patch.json found in {vcv_path}")
    result: dict[str, Any] = json.loads(raw.read())
    return result


def _ensure_recorder_plugin(user_dir: Path) -> None:
    """Copy the VCV-Recorder plugin to the temp user directory.

    VCV-Recorder ships with Rack Pro but needs to be in the user's
    plugin directory for headless mode to find it.
    """
    system_plugins = (
        Path.home() / "Library" / "Application Support" / "Rack2" / "plugins-mac-arm64"
    )
    recorder_src = system_plugins / "VCV-Recorder"

    if not recorder_src.exists():
        # Try other common locations
        for alt in [
            system_plugins.parent / "plugins" / "VCV-Recorder",
            Path("/Applications/VCV Rack 2 Pro.app/Contents/Resources/plugins/VCV-Recorder"),
        ]:
            if alt.exists():
                recorder_src = alt
                break

    if not recorder_src.exists():
        raise FileNotFoundError(
            f"VCV-Recorder plugin not found at {recorder_src}. "
            "Install it from the VCV Rack library."
        )

    dest_plugins = user_dir / "plugins-mac-arm64"
    dest_plugins.mkdir(parents=True, exist_ok=True)
    dest = dest_plugins / "VCV-Recorder"
    if not dest.exists():
        shutil.copytree(recorder_src, dest)


def _copy_fundamental_plugin(user_dir: Path) -> None:
    """Copy the Fundamental plugin to the temp user directory."""
    system_plugins = (
        Path.home() / "Library" / "Application Support" / "Rack2" / "plugins-mac-arm64"
    )
    fund_src = system_plugins / "Fundamental"
    if not fund_src.exists():
        return  # Fundamental is built-in to Rack, may not need separate copy

    dest_plugins = user_dir / "plugins-mac-arm64"
    dest_plugins.mkdir(parents=True, exist_ok=True)
    dest = dest_plugins / "Fundamental"
    if not dest.exists():
        shutil.copytree(fund_src, dest)


def render_patch(
    vcv_path: Path,
    output_wav: Path,
    duration: int | None = None,
) -> Path:
    """Run VCV Rack Pro headless on a patch, capture audio to WAV.

    Recompiles the patch with an injected VCV-Recorder module that
    writes directly to a known WAV path. Then launches Rack in
    headless mode for the specified duration.

    Args:
        vcv_path: path to the .vcv file (LLM-generated, no Recorder)
        output_wav: where the final WAV should end up
        duration: render duration in seconds (default from settings)

    Returns:
        Path to the rendered WAV file.
    """
    if duration is None:
        duration = settings.render_duration

    rack_bin = settings.resolve_rack_path()

    with tempfile.TemporaryDirectory(prefix="vcv-agent-") as tmp:
        tmp_path = Path(tmp)

        # The WAV path the Recorder will write to
        recorder_wav = tmp_path / "recording.wav"

        # Extract the original patch, recompile with Recorder injected
        patch_json = _extract_patch_json(vcv_path)
        recompiled_vcv = tmp_path / "patch.vcv"
        compile_vcv(patch_json, recompiled_vcv, wav_path=str(recorder_wav))

        # Set up plugin directory
        _ensure_recorder_plugin(tmp_path)
        _copy_fundamental_plugin(tmp_path)

        # Write minimal settings.json so Rack doesn't prompt
        settings_json = tmp_path / "settings.json"
        settings_json.write_text(json.dumps({
            "token": "",
            "windowSize": [1, 1],
            "windowPos": [0, 0],
        }))

        # Run Rack headless
        proc = subprocess.Popen(
            [rack_bin, "-h", str(recompiled_vcv), "-u", str(tmp_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            time.sleep(duration + 3)  # duration + startup buffer
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()

        # Collect stderr for debugging
        _, stderr = proc.communicate(timeout=2) if proc.poll() is None else (b"", b"")
        if not recorder_wav.exists():
            # Check if Recorder wrote somewhere else
            wavs = list(tmp_path.rglob("*.wav"))
            if wavs:
                recorder_wav = wavs[0]

        if not recorder_wav.exists():
            stderr_text = stderr.decode("utf-8", errors="replace") if stderr else ""
            raise RuntimeError(
                f"Render completed but no WAV found.\n"
                f"Rack stderr: {stderr_text[:500]}\n"
                f"Tmp dir contents: {list(tmp_path.rglob('*'))}"
            )

        output_wav.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(recorder_wav, output_wav)
        return output_wav
