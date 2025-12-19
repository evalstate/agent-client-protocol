"""
Skill manifest parsing and representation.

Handles parsing of SKILL.md files and marketplace.json entries.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List
import re


@dataclass
class SkillManifest:
    """Represents a skill's manifest information."""

    # Unique identifier for the skill
    name: str

    # Human-readable description
    description: str

    # Source path in the repository (e.g., "./hf-llm-trainer")
    source: str = ""

    # Local installation path
    local_path: Optional[Path] = None

    # Content of the SKILL.md file (loaded on demand)
    skill_content: Optional[str] = None

    # Additional reference files
    references: List[Path] = field(default_factory=list)

    # Scripts associated with the skill
    scripts: List[Path] = field(default_factory=list)

    @classmethod
    def from_marketplace_entry(cls, entry: dict) -> "SkillManifest":
        """Create manifest from a marketplace.json plugin entry."""
        return cls(
            name=entry.get("name", ""),
            description=entry.get("description", ""),
            source=entry.get("source", ""),
        )

    @classmethod
    def from_local_dir(cls, skill_dir: Path) -> Optional["SkillManifest"]:
        """Create manifest from a local skill directory."""
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            return None

        # Read the SKILL.md content
        content = skill_md.read_text(encoding="utf-8")

        # Extract description from the first paragraph or heading
        description = cls._extract_description(content)

        # Find reference files
        references = []
        refs_dir = skill_dir / "references"
        if refs_dir.exists():
            references = list(refs_dir.glob("*.md"))

        # Find scripts
        scripts = []
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            scripts = list(scripts_dir.glob("*.py"))

        return cls(
            name=skill_dir.name,
            description=description,
            local_path=skill_dir,
            skill_content=content,
            references=references,
            scripts=scripts,
        )

    @staticmethod
    def _extract_description(content: str) -> str:
        """Extract a description from SKILL.md content."""
        # Try to find a description after the first heading
        lines = content.split("\n")
        description_lines = []
        in_description = False

        for line in lines:
            # Skip empty lines at start
            if not in_description and not line.strip():
                continue

            # Skip the first heading
            if line.startswith("#") and not in_description:
                in_description = True
                continue

            # Stop at next heading or after getting enough content
            if in_description:
                if line.startswith("#"):
                    break
                description_lines.append(line)
                # Get first substantial paragraph
                if len(" ".join(description_lines)) > 100:
                    break

        description = " ".join(description_lines).strip()

        # Clean up and truncate if needed
        description = re.sub(r'\s+', ' ', description)
        if len(description) > 200:
            description = description[:197] + "..."

        return description or "No description available"

    def get_skill_content(self) -> str:
        """Get the full SKILL.md content, loading from file if needed."""
        if self.skill_content is not None:
            return self.skill_content

        if self.local_path:
            skill_md = self.local_path / "SKILL.md"
            if skill_md.exists():
                self.skill_content = skill_md.read_text(encoding="utf-8")
                return self.skill_content

        return ""

    def get_full_context(self) -> str:
        """Get the full skill context including references."""
        parts = [self.get_skill_content()]

        for ref_file in self.references:
            if ref_file.exists():
                parts.append(f"\n\n## Reference: {ref_file.name}\n\n")
                parts.append(ref_file.read_text(encoding="utf-8"))

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Convert manifest to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "source": self.source,
            "local_path": str(self.local_path) if self.local_path else None,
            "references": [str(r) for r in self.references],
            "scripts": [str(s) for s in self.scripts],
        }
