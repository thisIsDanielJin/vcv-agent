"""Application config loaded from environment / .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config lives here. Override via .env or environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    # VCV Rack Pro binary path. Auto-detected on macOS if unset.
    rack_path: str = ""

    # LLM
    openai_api_key: str = ""
    model: str = "gpt-4o"

    # Rendering
    render_duration: int = 8
    sample_rate: int = 48000

    # Agent loop
    max_iterations: int = 10

    # Paths
    runs_dir: Path = Path("runs")
    registry_path: Path = Path("registry/modules.json")

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
            Path("/Applications/VCV Rack 2 Pro.app/Contents/MacOS/Rack"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        raise FileNotFoundError(
            "Could not find VCV Rack Pro binary. Set RACK_PATH in .env"
        )


settings = Settings()
