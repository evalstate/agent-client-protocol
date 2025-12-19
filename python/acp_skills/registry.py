"""
Skill registry for tracking installed skills.

Provides functionality to list, query, and manage installed skills.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import json
from datetime import datetime

from .manifest import SkillManifest
from .config import SkillsConfig


@dataclass
class InstalledSkill:
    """Represents an installed skill with metadata."""

    manifest: SkillManifest
    installed_at: datetime
    source_url: str  # The marketplace URL it was installed from
    version: str = "1.0.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "manifest": self.manifest.to_dict(),
            "installed_at": self.installed_at.isoformat(),
            "source_url": self.source_url,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict, skill_dir: Path) -> Optional["InstalledSkill"]:
        """Create from dictionary."""
        manifest = SkillManifest.from_local_dir(skill_dir)
        if not manifest:
            return None

        # Override with stored metadata
        manifest.source = data.get("manifest", {}).get("source", "")

        return cls(
            manifest=manifest,
            installed_at=datetime.fromisoformat(data.get("installed_at", datetime.now().isoformat())),
            source_url=data.get("source_url", ""),
            version=data.get("version", "1.0.0"),
        )


class SkillRegistry:
    """Registry for tracking installed skills."""

    def __init__(self, config: SkillsConfig):
        self.config = config
        self._skills: Dict[str, InstalledSkill] = {}
        self._registry_file = config.skills_dir / ".registry.json"
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        self._skills.clear()

        # Load from registry file if it exists
        registry_data = {}
        if self._registry_file.exists():
            try:
                registry_data = json.loads(self._registry_file.read_text())
            except (json.JSONDecodeError, IOError):
                registry_data = {}

        # Scan skills directory for installed skills
        if self.config.skills_dir.exists():
            for skill_dir in self.config.skills_dir.iterdir():
                if skill_dir.is_dir() and not skill_dir.name.startswith("."):
                    skill_data = registry_data.get(skill_dir.name, {})
                    installed = InstalledSkill.from_dict(skill_data, skill_dir)
                    if installed:
                        self._skills[skill_dir.name] = installed

    def _save(self) -> None:
        """Save registry to disk."""
        self.config.ensure_dirs()

        data = {
            name: skill.to_dict()
            for name, skill in self._skills.items()
        }

        self._registry_file.write_text(json.dumps(data, indent=2))

    def refresh(self) -> None:
        """Refresh the registry from disk."""
        self._load()

    def list_skills(self) -> List[InstalledSkill]:
        """List all installed skills."""
        return list(self._skills.values())

    def get_skill(self, name: str) -> Optional[InstalledSkill]:
        """Get a specific skill by name."""
        return self._skills.get(name)

    def get_skill_by_index(self, index: int) -> Optional[InstalledSkill]:
        """Get a skill by its ordinal index (1-based)."""
        skills = self.list_skills()
        if 1 <= index <= len(skills):
            return skills[index - 1]
        return None

    def register(
        self,
        manifest: SkillManifest,
        source_url: str,
        version: str = "1.0.0"
    ) -> InstalledSkill:
        """Register a newly installed skill."""
        installed = InstalledSkill(
            manifest=manifest,
            installed_at=datetime.now(),
            source_url=source_url,
            version=version,
        )

        self._skills[manifest.name] = installed
        self._save()

        return installed

    def unregister(self, name: str) -> bool:
        """Unregister a skill (does not delete files)."""
        if name in self._skills:
            del self._skills[name]
            self._save()
            return True
        return False

    def is_installed(self, name: str) -> bool:
        """Check if a skill is installed."""
        return name in self._skills

    def get_all_skill_content(self) -> str:
        """Get combined content of all skills for system prompt."""
        parts = []

        for skill in self._skills.values():
            content = skill.manifest.get_full_context()
            if content:
                parts.append(f"## Skill: {skill.manifest.name}\n\n{content}")

        return "\n\n---\n\n".join(parts)

    def skill_count(self) -> int:
        """Get the number of installed skills."""
        return len(self._skills)
