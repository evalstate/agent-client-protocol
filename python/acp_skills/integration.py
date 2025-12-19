"""
Integration helpers for ACP and fast-agent.

This module provides integration points for:
- ACP (Agent Client Protocol) - hf-inference-acp
- fast-agent frontend

The integration handles:
- Registering skills slash commands
- System prompt regeneration after skill changes
- ACP available commands updates
"""

from dataclasses import dataclass
from typing import Optional, Callable, List, Any, Protocol

from .config import SkillsConfig
from .manager import SkillsManager
from .commands import SkillsCommandHandler, AsyncSkillsCommandHandler, CommandResult


class SystemPromptProvider(Protocol):
    """Protocol for objects that can regenerate system prompts."""

    def regenerate_system_prompt(self) -> None:
        """Regenerate the system prompt with updated skill content."""
        ...


class AvailableCommandsNotifier(Protocol):
    """Protocol for objects that can notify about available commands updates."""

    def notify_available_commands_update(self, commands: List[dict]) -> None:
        """Notify that available commands have been updated."""
        ...


@dataclass
class SkillsCommand:
    """ACP-compatible command definition for skills."""

    name: str = "skills"
    description: str = "Manage installed skills"

    def to_acp_command(self) -> dict:
        """Convert to ACP AvailableCommand format."""
        return {
            "name": self.name,
            "description": self.description,
            "input": {
                "type": "unstructured",
                "hint": "[add|remove] [skill_name_or_number]",
            },
        }


class SkillsIntegration:
    """Integration layer for skills management in ACP/fast-agent.

    This class provides the glue between the skills manager and the
    agent's session management, including:
    - Slash command handling
    - System prompt regeneration
    - ACP available commands updates

    Usage:
        # Create the integration
        integration = SkillsIntegration(
            config=SkillsConfig(),
            on_system_prompt_changed=my_regenerate_fn,
        )

        # Register commands (returns ACP-compatible command defs)
        commands = integration.get_available_commands()

        # Handle incoming slash command
        result = integration.handle_command("/skills add")

        # For interactive flow
        if result.awaiting_input:
            user_input = get_user_input(result.message)
            result = integration.handle_input(user_input)
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_system_prompt_changed: Optional[Callable[[], None]] = None,
    ):
        """Initialize the skills integration.

        Args:
            config: Skills configuration. If None, uses defaults.
            on_system_prompt_changed: Callback invoked when skills change and
                the system prompt should be regenerated.
        """
        self.config = config or SkillsConfig()

        # Create manager with the callback
        self.manager = SkillsManager(
            config=self.config,
            on_skills_changed=on_system_prompt_changed,
        )

        # Create command handler
        self.command_handler = SkillsCommandHandler(manager=self.manager)

        # Store callback for later updates
        self._on_system_prompt_changed = on_system_prompt_changed

    def set_on_system_prompt_changed(self, callback: Callable[[], None]) -> None:
        """Set or update the system prompt changed callback."""
        self._on_system_prompt_changed = callback
        self.manager.set_on_skills_changed(callback)

    def get_available_commands(self) -> List[dict]:
        """Get the list of available commands in ACP format.

        Returns:
            List of ACP AvailableCommand dictionaries.
        """
        return [SkillsCommand().to_acp_command()]

    def handle_command(self, command: str) -> CommandResult:
        """Handle a skills slash command.

        Args:
            command: The full command (e.g., "/skills", "/skills add").

        Returns:
            CommandResult with response message and state.
        """
        return self.command_handler.handle(command)

    def handle_input(self, user_input: str) -> CommandResult:
        """Handle user input for interactive commands.

        Args:
            user_input: User's selection (number, name, or 'q').

        Returns:
            CommandResult with response message and state.
        """
        return self.command_handler.handle_input(user_input)

    def get_system_prompt_additions(self) -> str:
        """Get skill content to add to the system prompt.

        Returns:
            Combined content from all installed skills.
        """
        return self.manager.get_system_prompt_additions()

    def is_skills_command(self, command: str) -> bool:
        """Check if a command is a skills command.

        Args:
            command: The command to check.

        Returns:
            True if this is a skills command.
        """
        cmd = command.strip().lstrip("/").lower()
        return cmd == "skills" or cmd.startswith("skills ")


class AsyncSkillsIntegration:
    """Async version of SkillsIntegration for ACP sessions.

    This version handles the async nature of ACP communication,
    where user input requests go through the protocol.
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_system_prompt_changed: Optional[Callable[[], None]] = None,
        request_input: Optional[Callable[[str], Any]] = None,
    ):
        """Initialize the async skills integration.

        Args:
            config: Skills configuration.
            on_system_prompt_changed: Callback when skills change.
            request_input: Async function to request user input.
                Signature: async (prompt: str) -> str
        """
        self._sync = SkillsIntegration(config, on_system_prompt_changed)
        self._request_input = request_input
        self._async_handler = AsyncSkillsCommandHandler(
            manager=self._sync.manager,
            request_input=request_input,
        )

    @property
    def manager(self) -> SkillsManager:
        return self._sync.manager

    @property
    def config(self) -> SkillsConfig:
        return self._sync.config

    def set_request_input(self, callback: Callable[[str], Any]) -> None:
        """Set the input request callback."""
        self._request_input = callback
        self._async_handler.set_request_input(callback)

    def set_on_system_prompt_changed(self, callback: Callable[[], None]) -> None:
        """Set the system prompt changed callback."""
        self._sync.set_on_system_prompt_changed(callback)

    def get_available_commands(self) -> List[dict]:
        """Get available commands in ACP format."""
        return self._sync.get_available_commands()

    async def handle_command(self, command: str) -> CommandResult:
        """Handle a skills command asynchronously."""
        return await self._async_handler.handle(command)

    def get_system_prompt_additions(self) -> str:
        """Get skill content for the system prompt."""
        return self._sync.get_system_prompt_additions()

    def is_skills_command(self, command: str) -> bool:
        """Check if this is a skills command."""
        return self._sync.is_skills_command(command)


def create_skills_integration(
    base_path: Optional[str] = None,
    marketplace_url: Optional[str] = None,
    skills_dir: Optional[str] = None,
    on_system_prompt_changed: Optional[Callable[[], None]] = None,
) -> SkillsIntegration:
    """Factory function to create a skills integration.

    Args:
        base_path: Base path for resolving relative paths.
        marketplace_url: Override the default marketplace URL.
        skills_dir: Override the default skills directory.
        on_system_prompt_changed: Callback when skills change.

    Returns:
        Configured SkillsIntegration instance.
    """
    from pathlib import Path

    config = SkillsConfig(base_path=Path(base_path) if base_path else None)

    if marketplace_url:
        config = config.with_marketplace_url(marketplace_url)
    if skills_dir:
        config = config.with_skills_dir(skills_dir)

    return SkillsIntegration(
        config=config,
        on_system_prompt_changed=on_system_prompt_changed,
    )
