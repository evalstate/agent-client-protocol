"""
Skills Manager - High-level orchestration of skill operations.
"""

from pathlib import Path
from typing import Optional, Callable, List, Any

from .config import SkillsConfig
from .models import Skill, MarketplacePlugin
from .registry import SkillsRegistry
from .marketplace import SkillsMarketplace, MarketplaceError


# Type alias for the system prompt regeneration callback
SystemPromptCallback = Callable[[], None]


class SkillsManager:
    """High-level manager for skill operations.

    Orchestrates the registry and marketplace to provide a unified interface
    for skill management operations.
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_skills_changed: Optional[SystemPromptCallback] = None,
    ):
        """Initialize the skills manager.

        Args:
            config: Configuration for the skills manager. If None, uses defaults.
            on_skills_changed: Callback to invoke after skills are added or removed.
                This is typically used to regenerate the system prompt.
        """
        self.config = config or SkillsConfig()
        self.registry = SkillsRegistry(self.config)
        self.marketplace = SkillsMarketplace(self.config)
        self._on_skills_changed = on_skills_changed

    def _notify_skills_changed(self) -> None:
        """Invoke the skills changed callback if registered."""
        if self._on_skills_changed:
            self._on_skills_changed()

    def set_on_skills_changed(self, callback: Optional[SystemPromptCallback]) -> None:
        """Set or update the skills changed callback.

        Args:
            callback: The callback to invoke when skills change, or None to remove.
        """
        self._on_skills_changed = callback

    # --- List operations ---

    def list_installed(self) -> List[Skill]:
        """List all installed skills."""
        return self.registry.list_skills()

    def list_available(self) -> List[MarketplacePlugin]:
        """List all available skills from the marketplace."""
        return self.marketplace.list_plugins()

    def get_installed_skill(self, identifier: str) -> Optional[Skill]:
        """Get an installed skill by name or index."""
        return self.registry.get_by_name_or_index(identifier)

    def get_available_plugin(self, identifier: str) -> Optional[MarketplacePlugin]:
        """Get an available plugin by name or index."""
        return self.marketplace.get_plugin(identifier)

    # --- Install operations ---

    def install(self, identifier: str) -> Skill:
        """Install a skill from the marketplace.

        Args:
            identifier: Plugin name or 1-based index as string.

        Returns:
            The installed Skill object.

        Raises:
            MarketplaceError: If the plugin is not found or installation fails.
        """
        plugin = self.marketplace.get_plugin(identifier)
        if not plugin:
            raise MarketplaceError(f"Plugin not found: {identifier}")

        return self.install_plugin(plugin)

    def install_plugin(self, plugin: MarketplacePlugin) -> Skill:
        """Install a specific plugin.

        Args:
            plugin: The marketplace plugin to install.

        Returns:
            The installed Skill object.

        Raises:
            MarketplaceError: If installation fails.
        """
        # Check if already installed
        if self.registry.exists(plugin.name):
            raise MarketplaceError(f"Skill '{plugin.name}' is already installed")

        # Ensure skills directory exists
        self.config.ensure_skills_dir()

        # Download and install
        skill_path = self.marketplace.download_skill(plugin, self.config.skills_path)

        # Refresh the registry
        self.registry.refresh()

        # Get the installed skill
        skill = self.registry.get_by_name(plugin.name)
        if not skill:
            # Fallback: create a skill from the path
            skill = Skill.from_path(skill_path)

        # Notify that skills have changed
        self._notify_skills_changed()

        return skill

    # --- Remove operations ---

    def remove(self, identifier: str) -> Optional[Skill]:
        """Remove an installed skill by name or index.

        Args:
            identifier: Skill name or 1-based index as string.

        Returns:
            The removed Skill object, or None if not found.
        """
        skill = self.registry.get_by_name_or_index(identifier)
        if not skill:
            return None

        return self.remove_skill(skill)

    def remove_skill(self, skill: Skill) -> Optional[Skill]:
        """Remove a specific skill.

        Args:
            skill: The skill to remove.

        Returns:
            The removed Skill object, or None if removal failed.
        """
        if self.registry.remove(skill):
            # Notify that skills have changed
            self._notify_skills_changed()
            return skill
        return None

    # --- System prompt operations ---

    def get_system_prompt_additions(self) -> str:
        """Get content from all installed skills to add to the system prompt."""
        return self.registry.get_system_prompt_additions()

    # --- Display formatting ---

    def format_installed_list(self) -> str:
        """Format the installed skills list for display."""
        return self.registry.format_skills_list()

    def format_available_list(self) -> str:
        """Format the available plugins list for display."""
        return self.marketplace.format_plugins_list()

    def format_skill_details(self, skill: Skill) -> str:
        """Format detailed information about a skill."""
        lines = [
            f"Skill: {skill.name}",
            f"Path: {skill.path}",
            f"Description: {skill.manifest.description}",
        ]
        if skill.manifest.version:
            lines.append(f"Version: {skill.manifest.version}")
        if skill.manifest.author:
            lines.append(f"Author: {skill.manifest.author}")
        return "\n".join(lines)

    def format_plugin_details(self, plugin: MarketplacePlugin) -> str:
        """Format detailed information about a marketplace plugin."""
        return f"Plugin: {plugin.name}\nSource: {plugin.source}\nDescription: {plugin.description}"

    # --- Marketplace operations ---

    def refresh_marketplace(self) -> None:
        """Force a refresh of the marketplace data."""
        self.marketplace.refresh()

    def is_installed(self, name: str) -> bool:
        """Check if a skill with the given name is installed."""
        return self.registry.exists(name)
