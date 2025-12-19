"""
Configuration for the ACP Skills Manager.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Default marketplace URL pointing to HuggingFace skills repository
DEFAULT_MARKETPLACE_URL = (
    "https://raw.githubusercontent.com/huggingface/skills/main/.claude-plugin/marketplace.json"
)

# Default skills directory relative to current working directory
DEFAULT_SKILLS_DIR = ".fast-agent/skills"


@dataclass
class SkillsConfig:
    """Configuration for the skills manager.

    Attributes:
        marketplace_url: URL to the marketplace.json file containing available skills.
            Can be customized to point to different skill repositories.
        skills_dir: Directory where skills are installed. Relative paths are resolved
            from the current working directory.
        base_path: Base path for resolving relative skills_dir. Defaults to cwd.
    """

    marketplace_url: str = field(default_factory=lambda: os.environ.get(
        "ACP_SKILLS_MARKETPLACE_URL", DEFAULT_MARKETPLACE_URL
    ))
    skills_dir: str = field(default_factory=lambda: os.environ.get(
        "ACP_SKILLS_DIR", DEFAULT_SKILLS_DIR
    ))
    base_path: Optional[Path] = None

    def __post_init__(self):
        if self.base_path is None:
            self.base_path = Path.cwd()
        elif isinstance(self.base_path, str):
            self.base_path = Path(self.base_path)

    @property
    def skills_path(self) -> Path:
        """Get the absolute path to the skills directory."""
        skills_dir = Path(self.skills_dir)
        if skills_dir.is_absolute():
            return skills_dir
        return self.base_path / skills_dir

    def ensure_skills_dir(self) -> Path:
        """Ensure the skills directory exists and return its path."""
        path = self.skills_path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def from_env(cls, base_path: Optional[Path] = None) -> "SkillsConfig":
        """Create a config from environment variables.

        Environment variables:
            ACP_SKILLS_MARKETPLACE_URL: Override the default marketplace URL
            ACP_SKILLS_DIR: Override the default skills directory
        """
        return cls(base_path=base_path)

    def with_marketplace_url(self, url: str) -> "SkillsConfig":
        """Return a new config with a different marketplace URL."""
        return SkillsConfig(
            marketplace_url=url,
            skills_dir=self.skills_dir,
            base_path=self.base_path,
        )

    def with_skills_dir(self, skills_dir: str) -> "SkillsConfig":
        """Return a new config with a different skills directory."""
        return SkillsConfig(
            marketplace_url=self.marketplace_url,
            skills_dir=skills_dir,
            base_path=self.base_path,
        )
