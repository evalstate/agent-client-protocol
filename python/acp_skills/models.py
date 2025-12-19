"""
Data models for the ACP Skills Manager.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Any
import json


@dataclass
class MarketplaceOwner:
    """Owner information from marketplace.json."""

    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "MarketplaceOwner":
        return cls(name=data.get("name", "Unknown"))


@dataclass
class MarketplaceMetadata:
    """Metadata from marketplace.json."""

    description: str
    version: str

    @classmethod
    def from_dict(cls, data: dict) -> "MarketplaceMetadata":
        return cls(
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
        )


@dataclass
class MarketplacePlugin:
    """A plugin/skill entry from marketplace.json."""

    name: str
    source: str
    description: str

    @classmethod
    def from_dict(cls, data: dict) -> "MarketplacePlugin":
        return cls(
            name=data.get("name", ""),
            source=data.get("source", ""),
            description=data.get("description", ""),
        )

    def get_skill_folder_name(self) -> str:
        """Extract the final folder name for the skill.

        The source path like './hf_dataset_creator' should result in
        a skill folder name based on the skill's name, not the source path.
        """
        return self.name


@dataclass
class Marketplace:
    """Parsed marketplace.json data."""

    name: str
    owner: MarketplaceOwner
    metadata: MarketplaceMetadata
    plugins: List[MarketplacePlugin]
    raw_url: str = ""  # The URL this marketplace was fetched from

    @classmethod
    def from_dict(cls, data: dict, raw_url: str = "") -> "Marketplace":
        return cls(
            name=data.get("name", ""),
            owner=MarketplaceOwner.from_dict(data.get("owner", {})),
            metadata=MarketplaceMetadata.from_dict(data.get("metadata", {})),
            plugins=[
                MarketplacePlugin.from_dict(p) for p in data.get("plugins", [])
            ],
            raw_url=raw_url,
        )

    @classmethod
    def from_json(cls, json_str: str, raw_url: str = "") -> "Marketplace":
        data = json.loads(json_str)
        return cls.from_dict(data, raw_url)

    def get_plugin_by_name(self, name: str) -> Optional[MarketplacePlugin]:
        """Find a plugin by name (case-insensitive)."""
        name_lower = name.lower()
        for plugin in self.plugins:
            if plugin.name.lower() == name_lower:
                return plugin
        return None

    def get_plugin_by_index(self, index: int) -> Optional[MarketplacePlugin]:
        """Get a plugin by its 1-based index."""
        if 1 <= index <= len(self.plugins):
            return self.plugins[index - 1]
        return None


@dataclass
class Manifest:
    """Manifest for an installed skill (SKILL.md or manifest.json)."""

    name: str
    description: str
    version: str = "0.0.0"
    author: str = ""
    source_url: str = ""
    raw_content: str = ""  # Full content of SKILL.md if applicable

    @classmethod
    def from_skill_md(cls, path: Path) -> "Manifest":
        """Parse a SKILL.md file to extract manifest information."""
        content = path.read_text(encoding="utf-8")
        name = path.parent.name
        description = ""

        # Try to extract description from the first paragraph after the title
        lines = content.strip().split("\n")
        in_description = False
        desc_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                # Extract name from title if present
                name = stripped[2:].strip()
                in_description = True
                continue
            if in_description:
                if stripped.startswith("#"):
                    break  # Hit next section
                if stripped:
                    desc_lines.append(stripped)
                elif desc_lines:
                    break  # Empty line after description

        description = " ".join(desc_lines)

        return cls(
            name=name,
            description=description,
            raw_content=content,
        )

    @classmethod
    def from_json_file(cls, path: Path) -> "Manifest":
        """Parse a manifest.json file."""
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(
            name=data.get("name", path.parent.name),
            description=data.get("description", ""),
            version=data.get("version", "0.0.0"),
            author=data.get("author", ""),
            source_url=data.get("source_url", ""),
        )

    @classmethod
    def from_path(cls, skill_dir: Path) -> "Manifest":
        """Load manifest from a skill directory, trying different formats."""
        # Try SKILL.md first (Claude Code style)
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            return cls.from_skill_md(skill_md)

        # Try manifest.json
        manifest_json = skill_dir / "manifest.json"
        if manifest_json.exists():
            return cls.from_json_file(manifest_json)

        # Fallback to directory name
        return cls(
            name=skill_dir.name,
            description="No manifest found",
        )


@dataclass
class Skill:
    """A locally installed skill."""

    name: str
    path: Path
    manifest: Manifest
    index: int = 0  # 1-based index for display purposes

    @classmethod
    def from_path(cls, path: Path, index: int = 0) -> "Skill":
        """Create a Skill from its installation path."""
        manifest = Manifest.from_path(path)
        return cls(
            name=manifest.name,
            path=path,
            manifest=manifest,
            index=index,
        )

    def get_system_prompt_content(self) -> str:
        """Get the content to include in the system prompt."""
        if self.manifest.raw_content:
            return self.manifest.raw_content
        # Generate a basic prompt from manifest data
        return f"# {self.manifest.name}\n\n{self.manifest.description}"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.manifest.description,
            "version": self.manifest.version,
        }
