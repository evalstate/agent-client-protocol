"""
Skills Marketplace - Fetch and parse remote skill marketplaces.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .config import SkillsConfig
from .models import Marketplace, MarketplacePlugin


class MarketplaceError(Exception):
    """Error fetching or parsing marketplace data."""

    pass


class SkillsMarketplace:
    """Fetches and manages remote skill marketplaces.

    The marketplace fetches skill listings from a configurable URL and provides
    methods to browse and download skills.
    """

    def __init__(self, config: SkillsConfig):
        self.config = config
        self._marketplace_cache: Optional[Marketplace] = None

    def _extract_repo_info(self, url: str) -> Tuple[str, str, str, str]:
        """Extract owner, repo, branch, and path from a GitHub URL.

        Handles URLs like:
        - https://raw.githubusercontent.com/owner/repo/branch/path/to/file
        - https://github.com/owner/repo/blob/branch/path/to/file

        Returns:
            Tuple of (owner, repo, branch, base_path)
        """
        parsed = urlparse(url)

        if "raw.githubusercontent.com" in parsed.netloc:
            # Format: /owner/repo/branch/path/to/file
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 3:
                owner = parts[0]
                repo = parts[1]
                branch = parts[2]
                base_path = "/".join(parts[3:-1])  # Exclude filename
                return owner, repo, branch, base_path

        elif "github.com" in parsed.netloc:
            # Format: /owner/repo/blob/branch/path/to/file
            parts = parsed.path.strip("/").split("/")
            if len(parts) >= 4 and parts[2] == "blob":
                owner = parts[0]
                repo = parts[1]
                branch = parts[3]
                base_path = "/".join(parts[4:-1])  # Exclude filename
                return owner, repo, branch, base_path

        raise MarketplaceError(f"Unable to parse GitHub URL: {url}")

    def _get_raw_url(self, owner: str, repo: str, branch: str, path: str) -> str:
        """Construct a raw GitHub URL for a file."""
        return f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"

    def fetch(self, force_refresh: bool = False) -> Marketplace:
        """Fetch the marketplace data.

        Args:
            force_refresh: If True, bypass the cache and fetch fresh data.

        Returns:
            The parsed Marketplace object.

        Raises:
            MarketplaceError: If the fetch or parse fails.
        """
        if self._marketplace_cache is not None and not force_refresh:
            return self._marketplace_cache

        url = self.config.marketplace_url
        try:
            request = Request(url, headers={"User-Agent": "ACP-Skills-Manager/0.1"})
            with urlopen(request, timeout=30) as response:
                data = response.read().decode("utf-8")
                self._marketplace_cache = Marketplace.from_json(data, raw_url=url)
                return self._marketplace_cache

        except HTTPError as e:
            raise MarketplaceError(f"HTTP error fetching marketplace: {e.code} {e.reason}")
        except URLError as e:
            raise MarketplaceError(f"URL error fetching marketplace: {e.reason}")
        except json.JSONDecodeError as e:
            raise MarketplaceError(f"Invalid JSON in marketplace: {e}")
        except Exception as e:
            raise MarketplaceError(f"Error fetching marketplace: {e}")

    def refresh(self) -> Marketplace:
        """Force a refresh of the marketplace data."""
        return self.fetch(force_refresh=True)

    def list_plugins(self) -> list[MarketplacePlugin]:
        """List all available plugins from the marketplace."""
        marketplace = self.fetch()
        return marketplace.plugins

    def get_plugin(self, identifier: str) -> Optional[MarketplacePlugin]:
        """Get a plugin by name or index.

        Args:
            identifier: Plugin name or 1-based index as string.

        Returns:
            The plugin if found, None otherwise.
        """
        marketplace = self.fetch()

        if identifier.isdigit():
            return marketplace.get_plugin_by_index(int(identifier))

        return marketplace.get_plugin_by_name(identifier)

    def download_skill(self, plugin: MarketplacePlugin, target_dir: Path) -> Path:
        """Download a skill from the marketplace to the target directory.

        This uses sparse checkout to only download the specific skill folder
        from the repository, avoiding downloading the entire repo.

        Args:
            plugin: The plugin to download.
            target_dir: The directory where the skill should be installed.

        Returns:
            The path to the installed skill.

        Raises:
            MarketplaceError: If the download fails.
        """
        marketplace = self.fetch()
        url = marketplace.raw_url

        try:
            owner, repo, branch, base_path = self._extract_repo_info(url)
        except MarketplaceError:
            raise

        # Construct the source path within the repo
        # plugin.source is like "./hf_dataset_creator"
        source_path = plugin.source.lstrip("./")
        if base_path:
            full_source_path = f"{base_path.rsplit('/', 1)[0]}/{source_path}" if "/" in base_path else source_path
        else:
            full_source_path = source_path

        # The skill folder name (flattened structure)
        skill_folder_name = plugin.name
        skill_target_path = target_dir / skill_folder_name

        # Check if already installed
        if skill_target_path.exists():
            raise MarketplaceError(f"Skill '{plugin.name}' is already installed")

        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Use sparse checkout to download only the specific folder
        try:
            self._sparse_checkout(owner, repo, branch, full_source_path, skill_target_path)
        except subprocess.CalledProcessError as e:
            raise MarketplaceError(f"Failed to download skill: {e}")

        # Look for the actual skill content (may be nested further)
        # e.g., hf_dataset_creator/skills/hugging-face-dataset-creator/SKILL.md
        self._find_and_move_skill_content(skill_target_path, plugin.name)

        return skill_target_path

    def _sparse_checkout(
        self, owner: str, repo: str, branch: str, source_path: str, target_path: Path
    ) -> None:
        """Perform a sparse checkout of a specific folder from a git repo.

        Uses git sparse-checkout to efficiently download only the needed files.
        """
        repo_url = f"https://github.com/{owner}/{repo}.git"

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            clone_path = tmp_path / "repo"

            # Initialize a new git repo
            subprocess.run(
                ["git", "init", str(clone_path)],
                check=True,
                capture_output=True,
            )

            # Add the remote
            subprocess.run(
                ["git", "-C", str(clone_path), "remote", "add", "origin", repo_url],
                check=True,
                capture_output=True,
            )

            # Enable sparse checkout
            subprocess.run(
                ["git", "-C", str(clone_path), "sparse-checkout", "init", "--cone"],
                check=True,
                capture_output=True,
            )

            # Set the sparse checkout path
            subprocess.run(
                ["git", "-C", str(clone_path), "sparse-checkout", "set", source_path],
                check=True,
                capture_output=True,
            )

            # Fetch and checkout
            subprocess.run(
                ["git", "-C", str(clone_path), "fetch", "--depth=1", "origin", branch],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(clone_path), "checkout", branch],
                check=True,
                capture_output=True,
            )

            # Find the downloaded folder and copy to target
            source_full_path = clone_path / source_path
            if source_full_path.exists():
                # Copy the contents to target
                import shutil

                if target_path.exists():
                    shutil.rmtree(target_path)
                shutil.copytree(source_full_path, target_path)
            else:
                raise MarketplaceError(
                    f"Source path not found after checkout: {source_path}"
                )

    def _find_and_move_skill_content(self, skill_path: Path, skill_name: str) -> None:
        """Find the actual skill content and flatten if needed.

        Skills may be nested like: hf_dataset_creator/skills/skill-name/SKILL.md
        We want to flatten this to just the skill-name folder content.
        """
        # Look for SKILL.md anywhere in the tree
        skill_files = list(skill_path.rglob("SKILL.md"))

        if not skill_files:
            # No SKILL.md found, try manifest.json
            skill_files = list(skill_path.rglob("manifest.json"))

        if not skill_files:
            # No manifest found, keep the directory as-is
            return

        # Use the first match
        skill_content_dir = skill_files[0].parent

        # If the skill content is in a subdirectory, move it up
        if skill_content_dir != skill_path:
            import shutil

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_content = Path(tmpdir) / "content"
                shutil.copytree(skill_content_dir, tmp_content)
                shutil.rmtree(skill_path)
                shutil.copytree(tmp_content, skill_path)

    def format_plugins_list(self) -> str:
        """Format the available plugins for display."""
        try:
            marketplace = self.fetch()
        except MarketplaceError as e:
            return f"Error fetching marketplace: {e}"

        plugins = marketplace.plugins
        if not plugins:
            return "No skills available in the marketplace."

        lines = [
            f"Available skills from {marketplace.name}:",
            f"({marketplace.metadata.description})",
            "",
        ]

        for i, plugin in enumerate(plugins, 1):
            desc = plugin.description
            if len(desc) > 60:
                desc = desc[:57] + "..."
            lines.append(f"  {i}. {plugin.name}")
            lines.append(f"     {desc}")

        lines.append("")
        lines.append("Enter a number or name to install, or 'q' to cancel:")

        return "\n".join(lines)
