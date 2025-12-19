"""
Skills configuration management.

Handles configuration for marketplace URLs, skills directory, and other settings.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import json
import os


# Default marketplace URL (can be overridden via config)
DEFAULT_MARKETPLACE_URL = (
    "https://raw.githubusercontent.com/huggingface/skills/main/.claude-plugin/marketplace.json"
)

# Default skills installation directory
DEFAULT_SKILLS_DIR = ".fast-agent/skills"


@dataclass
class SkillsConfig:
    """Configuration for the skills manager."""

    # URL to the marketplace.json file
    marketplace_url: str = DEFAULT_MARKETPLACE_URL

    # Local directory where skills are installed
    skills_dir: Path = field(default_factory=lambda: Path(DEFAULT_SKILLS_DIR))

    # Cache directory for cloned repos
    cache_dir: Path = field(default_factory=lambda: Path(".fast-agent/.cache/skills"))

    # Timeout for network requests (seconds)
    request_timeout: int = 30

    # Whether to show verbose output
    verbose: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "SkillsConfig":
        """Create config from dictionary."""
        return cls(
            marketplace_url=data.get("marketplace_url", DEFAULT_MARKETPLACE_URL),
            skills_dir=Path(data.get("skills_dir", DEFAULT_SKILLS_DIR)),
            cache_dir=Path(data.get("cache_dir", ".fast-agent/.cache/skills")),
            request_timeout=data.get("request_timeout", 30),
            verbose=data.get("verbose", False),
        )

    @classmethod
    def from_file(cls, path: Path) -> "SkillsConfig":
        """Load config from a JSON file."""
        if not path.exists():
            return cls()

        with open(path, "r") as f:
            data = json.load(f)

        return cls.from_dict(data.get("skills", {}))

    @classmethod
    def from_env(cls) -> "SkillsConfig":
        """Create config from environment variables."""
        return cls(
            marketplace_url=os.environ.get("ACP_SKILLS_MARKETPLACE_URL", DEFAULT_MARKETPLACE_URL),
            skills_dir=Path(os.environ.get("ACP_SKILLS_DIR", DEFAULT_SKILLS_DIR)),
            cache_dir=Path(os.environ.get("ACP_SKILLS_CACHE_DIR", ".fast-agent/.cache/skills")),
            request_timeout=int(os.environ.get("ACP_SKILLS_TIMEOUT", "30")),
            verbose=os.environ.get("ACP_SKILLS_VERBOSE", "").lower() in ("true", "1", "yes"),
        )

    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "marketplace_url": self.marketplace_url,
            "skills_dir": str(self.skills_dir),
            "cache_dir": str(self.cache_dir),
            "request_timeout": self.request_timeout,
            "verbose": self.verbose,
        }

    def ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
