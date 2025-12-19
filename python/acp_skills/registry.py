"""
Skills Registry - Manages locally installed skills.
"""

from pathlib import Path
from typing import List, Optional, Iterator
import shutil

from .config import SkillsConfig
from .models import Skill, Manifest


class SkillsRegistry:
    """Registry for managing locally installed skills.

    The registry scans the skills directory for installed skills and provides
    methods to list, get, and remove them.
    """

    def __init__(self, config: SkillsConfig):
        self.config = config
        self._skills_cache: Optional[List[Skill]] = None

    @property
    def skills_path(self) -> Path:
        """Get the path to the skills directory."""
        return self.config.skills_path

    def refresh(self) -> None:
        """Clear the skills cache to force a rescan on next access."""
        self._skills_cache = None

    def _scan_skills(self) -> List[Skill]:
        """Scan the skills directory for installed skills."""
        skills = []
        skills_dir = self.skills_path

        if not skills_dir.exists():
            return skills

        # Each subdirectory is a potential skill
        index = 1
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                try:
                    skill = Skill.from_path(entry, index=index)
                    skills.append(skill)
                    index += 1
                except Exception:
                    # Skip directories that can't be parsed as skills
                    pass

        return skills

    def list_skills(self) -> List[Skill]:
        """List all installed skills."""
        if self._skills_cache is None:
            self._skills_cache = self._scan_skills()
        return self._skills_cache

    def __iter__(self) -> Iterator[Skill]:
        """Iterate over installed skills."""
        return iter(self.list_skills())

    def __len__(self) -> int:
        """Return the number of installed skills."""
        return len(self.list_skills())

    def get_by_name(self, name: str) -> Optional[Skill]:
        """Get a skill by name (case-insensitive)."""
        name_lower = name.lower()
        for skill in self.list_skills():
            if skill.name.lower() == name_lower:
                return skill
        return None

    def get_by_index(self, index: int) -> Optional[Skill]:
        """Get a skill by its 1-based display index."""
        skills = self.list_skills()
        if 1 <= index <= len(skills):
            return skills[index - 1]
        return None

    def get_by_name_or_index(self, identifier: str) -> Optional[Skill]:
        """Get a skill by name or index (if identifier is numeric)."""
        # Try as index first if it looks like a number
        if identifier.isdigit():
            skill = self.get_by_index(int(identifier))
            if skill:
                return skill

        # Fall back to name lookup
        return self.get_by_name(identifier)

    def exists(self, name: str) -> bool:
        """Check if a skill with the given name is installed."""
        return self.get_by_name(name) is not None

    def get_skill_path(self, name: str) -> Path:
        """Get the path where a skill with the given name would be installed."""
        return self.skills_path / name

    def remove(self, skill: Skill) -> bool:
        """Remove an installed skill.

        Args:
            skill: The skill to remove.

        Returns:
            True if the skill was removed, False if it didn't exist.
        """
        if not skill.path.exists():
            return False

        try:
            shutil.rmtree(skill.path)
            self.refresh()
            return True
        except Exception:
            return False

    def remove_by_name(self, name: str) -> bool:
        """Remove a skill by name."""
        skill = self.get_by_name(name)
        if skill:
            return self.remove(skill)
        return False

    def remove_by_index(self, index: int) -> bool:
        """Remove a skill by its 1-based display index."""
        skill = self.get_by_index(index)
        if skill:
            return self.remove(skill)
        return False

    def remove_by_name_or_index(self, identifier: str) -> Optional[Skill]:
        """Remove a skill by name or index.

        Returns the removed skill if successful, None otherwise.
        """
        skill = self.get_by_name_or_index(identifier)
        if skill and self.remove(skill):
            return skill
        return None

    def get_system_prompt_additions(self) -> str:
        """Get all skill content to add to the system prompt."""
        parts = []
        for skill in self.list_skills():
            content = skill.get_system_prompt_content()
            if content:
                parts.append(content)

        if not parts:
            return ""

        return "\n\n---\n\n".join(parts)

    def format_skills_list(self) -> str:
        """Format the skills list for display."""
        skills = self.list_skills()
        if not skills:
            return "No skills installed."

        lines = ["Installed skills:", ""]
        for skill in skills:
            desc = skill.manifest.description
            if len(desc) > 60:
                desc = desc[:57] + "..."
            lines.append(f"  {skill.index}. {skill.name}")
            if desc:
                lines.append(f"     {desc}")

        return "\n".join(lines)
