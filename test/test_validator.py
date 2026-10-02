"""Test the patch validator against the module registry."""

from pathlib import Path

from vcv_agent.validator import load_registry, validate_patch

REGISTRY_PATH = Path(__file__).parent.parent / "registry" / "modules.json"


def test_valid_minimal_patch() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "version": "2.6.4",
        "modules": [
            {
                "id": 1,
                "plugin": "Fundamental",
                "model": "VCO",
                "params": [
                    {"id": 2, "value": 0.0},  # freq
                    {"id": 5, "value": 0.5},  # pw
                ],
            },
            {
                "id": 2,
                "plugin": "Fundamental",
                "model": "VCA-1",
                "params": [{"id": 0, "value": 1.0}],
            },
            {
                "id": 3,
                "plugin": "Core",
                "model": "AudioInterface2",
                "params": [{"id": 0, "value": 1.0}],
            },
        ],
        "cables": [
            {
                "id": 100,
                "outputModuleId": 1,
                "outputId": 2,  # VCO SAW
                "inputModuleId": 2,
                "inputId": 1,  # VCA-1 IN
            },
            {
                "id": 101,
                "outputModuleId": 2,
                "outputId": 0,  # VCA-1 OUT
                "inputModuleId": 3,
                "inputId": 0,  # Audio IN L
            },
        ],
    }
    result = validate_patch(patch, registry)
    assert result.valid, f"Expected valid, got errors: {[e.message for e in result.errors]}"


def test_unknown_module() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "modules": [
            {"id": 1, "plugin": "Fundamental", "model": "NOPE", "params": []},
            {"id": 2, "plugin": "Core", "model": "AudioInterface2", "params": []},
        ],
        "cables": [],
    }
    result = validate_patch(patch, registry)
    assert not result.valid
    assert any(e.type == "unknown_module" for e in result.errors)


def test_param_out_of_range() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "modules": [
            {
                "id": 1,
                "plugin": "Fundamental",
                "model": "VCO",
                "params": [{"id": 2, "value": 99.0}],  # freq max is 4.0
            },
            {"id": 2, "plugin": "Core", "model": "AudioInterface2", "params": []},
        ],
        "cables": [],
    }
    result = validate_patch(patch, registry)
    assert not result.valid
    assert any(e.type == "param_out_of_range" for e in result.errors)


def test_no_audio_output() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "modules": [
            {"id": 1, "plugin": "Fundamental", "model": "VCO", "params": []},
        ],
        "cables": [],
    }
    result = validate_patch(patch, registry)
    assert not result.valid
    assert any(e.type == "no_audio_output" for e in result.errors)


def test_invalid_cable_port() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "modules": [
            {"id": 1, "plugin": "Fundamental", "model": "VCO", "params": []},
            {"id": 2, "plugin": "Core", "model": "AudioInterface2", "params": []},
        ],
        "cables": [
            {
                "id": 100,
                "outputModuleId": 1,
                "outputId": 99,  # VCO only has outputs 0-3
                "inputModuleId": 2,
                "inputId": 0,
            }
        ],
    }
    result = validate_patch(patch, registry)
    assert not result.valid
    assert any(e.type == "port_out_of_range" for e in result.errors)


def test_duplicate_module_id() -> None:
    registry = load_registry(REGISTRY_PATH)
    patch = {
        "modules": [
            {"id": 1, "plugin": "Fundamental", "model": "VCO", "params": []},
            {"id": 1, "plugin": "Fundamental", "model": "VCA-1", "params": []},
            {"id": 2, "plugin": "Core", "model": "AudioInterface2", "params": []},
        ],
        "cables": [],
    }
    result = validate_patch(patch, registry)
    assert not result.valid
    assert any(e.type == "duplicate_module_id" for e in result.errors)
