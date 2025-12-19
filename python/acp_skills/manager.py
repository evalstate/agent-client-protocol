"""
Skills Manager - Core functionality for managing skills.

Handles fetching marketplace, cloning skills, and managing installations.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Callable, Tuple
from urllib.parse import urlparse
import json
import shutil
import subprocess
import tempfile

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .config import SkillsConfig
from .manifest import SkillManifest
from .registry import SkillRegistry


@dataclass
class MarketplaceInfo:
    """Information about a marketplace."""

    name: str
    owner: str
    description: str
    version: str
    plugins: List[SkillManifest]

    @classmethod
    def from_dict(cls, data: dict) -> "MarketplaceInfo":
        """Create from marketplace.json data."""
        metadata = data.get("metadata", {})
        owner_data = data.get("owner", {})

        plugins = [
            SkillManifest.from_marketplace_entry(p)
            for p in data.get("plugins", [])
        ]

        return cls(
            name=data.get("name", ""),
            owner=owner_data.get("name", ""),
            description=metadata.get("description", ""),
            version=metadata.get("version", "1.0.0"),
            plugins=plugins,
        )


class SkillsManager:
    """
    Main skills manager class.

    Handles:
    - Fetching marketplace information
    - Installing skills from repositories
    - Removing installed skills
    - Providing skill content for system prompts
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_skills_changed: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the skills manager.

        Args:
            config: Skills configuration. If None, uses defaults.
            on_skills_changed: Callback invoked when skills are added/removed.
                               Use this to trigger system prompt regeneration.
        """
        self.config = config or SkillsConfig()
        self.registry = SkillRegistry(self.config)
        self._on_skills_changed = on_skills_changed
        self._marketplace_cache: Optional[MarketplaceInfo] = None

    def _fetch_json(self, url: str) -> dict:
        """Fetch JSON from a URL using available HTTP library."""
        if HTTPX_AVAILABLE:
            with httpx.Client(timeout=self.config.request_timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                return response.json()
        elif REQUESTS_AVAILABLE:
            import requests

            response = requests.get(url, timeout=self.config.request_timeout)
            response.raise_for_status()
            return response.json()
        else:
            # Fallback to curl
            import subprocess

            result = subprocess.run(
                ["curl", "-sL", "--max-time", str(self.config.request_timeout), url],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)

    def fetch_marketplace(self, force_refresh: bool = False) -> MarketplaceInfo:
        """
        Fetch marketplace information.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data.

        Returns:
            MarketplaceInfo with available plugins.
        """
        if self._marketplace_cache and not force_refresh:
            return self._marketplace_cache

        data = self._fetch_json(self.config.marketplace_url)
        self._marketplace_cache = MarketplaceInfo.from_dict(data)

        return self._marketplace_cache

    def list_available_skills(self, force_refresh: bool = False) -> List[SkillManifest]:
        """List skills available in the marketplace."""
        marketplace = self.fetch_marketplace(force_refresh)
        return marketplace.plugins

    def list_installed_skills(self) -> List[SkillManifest]:
        """List locally installed skills."""
        return [s.manifest for s in self.registry.list_skills()]

    def _get_repo_info_from_marketplace_url(self) -> Tuple[str, str, str]:
        """
        Extract repo info from marketplace URL.

        Returns:
            Tuple of (owner, repo, branch)
        """
        # Parse URL like:
        # https://raw.githubusercontent.com/huggingface/skills/main/.claude-plugin/marketplace.json
        url = self.config.marketplace_url

        if "raw.githubusercontent.com" in url:
            # raw.githubusercontent.com/owner/repo/branch/path
            parts = urlparse(url).path.strip("/").split("/")
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]

        if "github.com" in url and "/blob/" in url:
            # github.com/owner/repo/blob/branch/path
            parts = urlparse(url).path.strip("/").split("/")
            if len(parts) >= 4 and parts[2] == "blob":
                return parts[0], parts[1], parts[3]

        raise ValueError(f"Cannot parse repository info from URL: {url}")

    def _clone_skill_sparse(
        self,
        owner: str,
        repo: str,
        branch: str,
        source_path: str,
        skill_name: str,
    ) -> Path:
        """
        Clone only the skill directory using sparse checkout.

        Args:
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            source_path: Source path from marketplace (e.g., "./hf-llm-trainer")
            skill_name: Name of the skill

        Returns:
            Path to the installed skill directory
        """
        self.config.ensure_dirs()

        # Clean source path
        source_dir = source_path.lstrip("./")

        # The skill is located at: source_dir/skills/skill_name/
        skill_subpath = f"{source_dir}/skills/{skill_name}"

        # Target directory
        target_dir = self.config.skills_dir / skill_name

        # If already exists, remove it first
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Use sparse checkout to clone only the needed directory
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            repo_url = f"https://github.com/{owner}/{repo}.git"

            # Initialize sparse checkout
            subprocess.run(
                ["git", "clone", "--filter=blob:none", "--sparse", "--depth=1",
                 "--branch", branch, repo_url, str(tmp_path)],
                capture_output=True,
                check=True,
            )

            # Set sparse checkout path
            subprocess.run(
                ["git", "-C", str(tmp_path), "sparse-checkout", "set", skill_subpath],
                capture_output=True,
                check=True,
            )

            # Copy the skill directory to target
            source = tmp_path / skill_subpath

            if not source.exists():
                raise FileNotFoundError(
                    f"Skill path not found in repository: {skill_subpath}"
                )

            shutil.copytree(source, target_dir)

        return target_dir

    def install_skill(self, skill_name: str) -> SkillManifest:
        """
        Install a skill from the marketplace.

        Args:
            skill_name: Name of the skill to install (from marketplace)

        Returns:
            The installed skill's manifest

        Raises:
            ValueError: If skill not found in marketplace
            FileNotFoundError: If skill files not found in repository
        """
        # Find the skill in marketplace
        marketplace = self.fetch_marketplace()
        skill_entry = None

        for plugin in marketplace.plugins:
            if plugin.name == skill_name:
                skill_entry = plugin
                break

        if not skill_entry:
            available = [p.name for p in marketplace.plugins]
            raise ValueError(
                f"Skill '{skill_name}' not found in marketplace. "
                f"Available: {', '.join(available)}"
            )

        # Get repo info
        owner, repo, branch = self._get_repo_info_from_marketplace_url()

        # Clone the skill
        skill_dir = self._clone_skill_sparse(
            owner=owner,
            repo=repo,
            branch=branch,
            source_path=skill_entry.source,
            skill_name=skill_name,
        )

        # Load manifest from installed files
        manifest = SkillManifest.from_local_dir(skill_dir)
        if not manifest:
            raise FileNotFoundError(f"No SKILL.md found in {skill_dir}")

        # Preserve source info
        manifest.source = skill_entry.source

        # Register the skill
        self.registry.register(
            manifest=manifest,
            source_url=self.config.marketplace_url,
            version=marketplace.version,
        )

        # Trigger callback for system prompt regeneration
        if self._on_skills_changed:
            self._on_skills_changed()

        return manifest

    def install_skill_by_index(self, index: int) -> SkillManifest:
        """
        Install a skill by its marketplace index (1-based).

        Args:
            index: 1-based index from marketplace listing

        Returns:
            The installed skill's manifest
        """
        marketplace = self.fetch_marketplace()
        plugins = marketplace.plugins

        if not (1 <= index <= len(plugins)):
            raise ValueError(
                f"Invalid index {index}. Valid range: 1-{len(plugins)}"
            )

        return self.install_skill(plugins[index - 1].name)

    def remove_skill(self, skill_name: str) -> bool:
        """
        Remove an installed skill.

        Args:
            skill_name: Name of the skill to remove

        Returns:
            True if skill was removed, False if not found
        """
        skill = self.registry.get_skill(skill_name)
        if not skill:
            return False

        # Remove files
        skill_dir = self.config.skills_dir / skill_name
        if skill_dir.exists():
            shutil.rmtree(skill_dir)

        # Unregister
        self.registry.unregister(skill_name)

        # Trigger callback for system prompt regeneration
        if self._on_skills_changed:
            self._on_skills_changed()

        return True

    def remove_skill_by_index(self, index: int) -> bool:
        """
        Remove a skill by its installed index (1-based).

        Args:
            index: 1-based index from installed skills listing

        Returns:
            True if skill was removed, False if not found
        """
        skill = self.registry.get_skill_by_index(index)
        if not skill:
            return False

        return self.remove_skill(skill.manifest.name)

    def get_system_prompt_content(self) -> str:
        """
        Get skill content for inclusion in system prompt.

        Returns:
            Combined content of all installed skills, formatted for system prompt.
        """
        content = self.registry.get_all_skill_content()

        if not content:
            return ""

        return f"""
<available_skills>
The following skills are available to assist with specialized tasks:

{content}
</available_skills>
"""

    def refresh(self) -> None:
        """Refresh registry and clear marketplace cache."""
        self.registry.refresh()
        self._marketplace_cache = None
