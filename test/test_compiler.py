"""Test the patch compiler."""

import io
import json
import tarfile
from pathlib import Path

import pyzstd

from vcv_agent.compiler import compile_vcv


def test_compile_produces_valid_vcv(tmp_path: Path) -> None:
    patch = {
        "version": "2.6.4",
        "modules": [
            {"id": 1, "plugin": "Fundamental", "model": "VCO", "params": []},
            {"id": 2, "plugin": "Core", "model": "AudioInterface2", "params": []},
        ],
        "cables": [
            {"id": 100, "outputModuleId": 1, "outputId": 2, "inputModuleId": 2, "inputId": 0}
        ],
    }

    out = tmp_path / "test.vcv"
    result = compile_vcv(patch, out)

    assert result.exists()
    assert result.stat().st_size > 0

    # Decompress and verify structure
    compressed = result.read_bytes()
    tar_bytes = pyzstd.decompress(compressed)
    tf = tarfile.open(fileobj=io.BytesIO(tar_bytes))

    names = tf.getnames()
    assert "./patch.json" in names
    assert "./modules/" in names or "./modules" in names

    # Verify patch.json is valid JSON
    patch_json = json.loads(tf.extractfile("./patch.json").read())  # type: ignore[union-attr]
    assert "modules" in patch_json
    assert "cables" in patch_json
    assert patch_json["version"] == "2.6.4"
