"""Application config loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config lives here. Override via .env or environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # Claude via hyperspace proxy (default, free via SAP)
    claude_proxy_url: str = "http://localhost:6655/anthropic"
    claude_proxy_key: str = "7ae5cde3-7528-4fca-8121-185d05bd7eee"
    model: str = "anthropic--claude-4.6-sonnet"

    # VCV Rack Pro binary path. Auto-detected on macOS if unset.
    rack_path: str = ""

    # Rendering
    render_duration: int = 8
    sample_rate: int = 48000

    # Agent loop
    max_iterations: int = 10

    # Paths
    runs_dir: Path = Path(__file__).parent.parent / "runs"
    registry_path: Path = Path(__file__).parent.parent / "registry" / "modules.json"

    def resolve_rack_path(self) -> str:
        """Find the Rack binary, auto-detecting on macOS if not configured."""
        if self.rack_path:
            return self.rack_path
        # macOS default location
        candidates = [
            Path.home()
            / "Documents"
            / "Apps"
            / "VCV Rack 2 Pro.app"
            / "Contents"
            / "MacOS"
            / "Rack",
            Path(
                "/Applications/VCV Rack 2 Pro.app/Contents/MacOS/Rack"
            ),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            "Could not find VCV Rack Pro binary. Set RACK_PATH in .env"
        )


settings = Settings()
