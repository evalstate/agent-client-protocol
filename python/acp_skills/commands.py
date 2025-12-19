"""
Slash command handlers for the skills manager.

Provides handlers for:
- /skills - List installed skills
- /skills add - Add a skill from the marketplace
- /skills remove - Remove an installed skill
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable, Any, Awaitable, Union

from .config import SkillsConfig
from .manager import SkillsManager
from .marketplace import MarketplaceError


class CommandState(Enum):
    """State of the command handler."""

    IDLE = "idle"
    AWAITING_ADD_SELECTION = "awaiting_add_selection"
    AWAITING_REMOVE_SELECTION = "awaiting_remove_selection"


@dataclass
class CommandResult:
    """Result of a command execution."""

    message: str
    success: bool = True
    awaiting_input: bool = False
    state: CommandState = CommandState.IDLE


# Type alias for input request callback
# For ACP mode, this returns a coroutine; for CLI mode, it might be sync
InputCallback = Callable[[str], Union[str, Awaitable[str]]]


class SkillsCommandHandler:
    """Handler for skills-related slash commands.

    This class manages the state machine for interactive commands like
    /skills add which require user input to select a skill.

    Usage:
        handler = SkillsCommandHandler(manager)

        # Handle a command
        result = handler.handle("/skills")
        print(result.message)

        # For interactive commands
        result = handler.handle("/skills add")
        print(result.message)  # Shows available skills
        if result.awaiting_input:
            user_input = input("> ")
            result = handler.handle_input(user_input)
            print(result.message)
    """

    def __init__(
        self,
        manager: Optional[SkillsManager] = None,
        config: Optional[SkillsConfig] = None,
    ):
        """Initialize the command handler.

        Args:
            manager: The skills manager to use. If None, creates a new one.
            config: Configuration for creating a new manager if manager is None.
        """
        if manager is not None:
            self.manager = manager
        else:
            self.manager = SkillsManager(config)

        self._state = CommandState.IDLE

    @property
    def state(self) -> CommandState:
        """Get the current command state."""
        return self._state

    def reset_state(self) -> None:
        """Reset the command state to idle."""
        self._state = CommandState.IDLE

    def handle(self, command: str) -> CommandResult:
        """Handle a skills command.

        Args:
            command: The full command string (e.g., "/skills", "/skills add").

        Returns:
            A CommandResult with the response message and state.
        """
        # Parse the command
        parts = command.strip().split()

        if not parts:
            return CommandResult(
                message="Usage: /skills [add|remove]",
                success=False,
            )

        # Remove leading slash if present
        base_cmd = parts[0].lstrip("/")
        if base_cmd != "skills":
            return CommandResult(
                message=f"Unknown command: {parts[0]}",
                success=False,
            )

        # Determine subcommand
        if len(parts) == 1:
            # /skills - list installed
            return self._handle_list()

        subcommand = parts[1].lower()
        args = parts[2:] if len(parts) > 2 else []

        if subcommand == "add":
            return self._handle_add(args)
        elif subcommand == "remove":
            return self._handle_remove(args)
        else:
            return CommandResult(
                message=f"Unknown subcommand: {subcommand}\nUsage: /skills [add|remove]",
                success=False,
            )

    def handle_input(self, user_input: str) -> CommandResult:
        """Handle user input for interactive commands.

        Args:
            user_input: The user's input (e.g., skill number or name, or 'q').

        Returns:
            A CommandResult with the response message and state.
        """
        user_input = user_input.strip()

        # Handle quit
        if user_input.lower() == "q":
            self._state = CommandState.IDLE
            return CommandResult(message="Cancelled.", success=True)

        if self._state == CommandState.AWAITING_ADD_SELECTION:
            return self._complete_add(user_input)
        elif self._state == CommandState.AWAITING_REMOVE_SELECTION:
            return self._complete_remove(user_input)
        else:
            return CommandResult(
                message="No pending operation. Use /skills add or /skills remove.",
                success=False,
            )

    def _handle_list(self) -> CommandResult:
        """Handle /skills command to list installed skills."""
        message = self.manager.format_installed_list()
        return CommandResult(message=message, success=True)

    def _handle_add(self, args: list) -> CommandResult:
        """Handle /skills add command.

        If args provided, install directly. Otherwise, show available and wait.
        """
        if args:
            # Direct install: /skills add <name_or_number>
            identifier = args[0]
            return self._complete_add(identifier)

        # Show available skills and wait for selection
        try:
            message = self.manager.format_available_list()
            self._state = CommandState.AWAITING_ADD_SELECTION
            return CommandResult(
                message=message,
                success=True,
                awaiting_input=True,
                state=CommandState.AWAITING_ADD_SELECTION,
            )
        except MarketplaceError as e:
            return CommandResult(
                message=f"Error fetching marketplace: {e}",
                success=False,
            )

    def _complete_add(self, identifier: str) -> CommandResult:
        """Complete the add operation with the given identifier."""
        self._state = CommandState.IDLE

        try:
            skill = self.manager.install(identifier)
            return CommandResult(
                message=f"Successfully installed skill: {skill.name}\n"
                f"Description: {skill.manifest.description}\n"
                f"System prompt will be updated.",
                success=True,
            )
        except MarketplaceError as e:
            return CommandResult(
                message=f"Error installing skill: {e}",
                success=False,
            )

    def _handle_remove(self, args: list) -> CommandResult:
        """Handle /skills remove command.

        If args provided, remove directly. Otherwise, show installed and wait.
        """
        if args:
            # Direct remove: /skills remove <name_or_number>
            identifier = args[0]
            return self._complete_remove(identifier)

        # Show installed skills and wait for selection
        skills = self.manager.list_installed()
        if not skills:
            return CommandResult(
                message="No skills installed.",
                success=True,
            )

        message = self.manager.format_installed_list()
        message += "\n\nEnter a number or name to remove, or 'q' to cancel:"

        self._state = CommandState.AWAITING_REMOVE_SELECTION
        return CommandResult(
            message=message,
            success=True,
            awaiting_input=True,
            state=CommandState.AWAITING_REMOVE_SELECTION,
        )

    def _complete_remove(self, identifier: str) -> CommandResult:
        """Complete the remove operation with the given identifier."""
        self._state = CommandState.IDLE

        skill = self.manager.remove(identifier)
        if skill:
            return CommandResult(
                message=f"Successfully removed skill: {skill.name}\n"
                f"System prompt will be updated.",
                success=True,
            )
        else:
            return CommandResult(
                message=f"Skill not found: {identifier}",
                success=False,
            )


class AsyncSkillsCommandHandler:
    """Async version of the command handler for ACP integration.

    This handler is designed to work with the ACP session model where
    user input is requested asynchronously through the protocol.
    """

    def __init__(
        self,
        manager: Optional[SkillsManager] = None,
        config: Optional[SkillsConfig] = None,
        request_input: Optional[Callable[[str], Awaitable[str]]] = None,
    ):
        """Initialize the async command handler.

        Args:
            manager: The skills manager to use.
            config: Configuration for creating a new manager.
            request_input: Async callback to request user input.
                Signature: async (prompt: str) -> str
        """
        self._sync_handler = SkillsCommandHandler(manager, config)
        self._request_input = request_input

    @property
    def manager(self) -> SkillsManager:
        return self._sync_handler.manager

    def set_request_input(self, callback: Callable[[str], Awaitable[str]]) -> None:
        """Set the input request callback."""
        self._request_input = callback

    async def handle(self, command: str) -> CommandResult:
        """Handle a skills command asynchronously.

        For interactive commands, this will request user input through
        the configured callback.

        Args:
            command: The full command string.

        Returns:
            The final CommandResult after all interactions complete.
        """
        result = self._sync_handler.handle(command)

        # If awaiting input and we have a callback, request it
        while result.awaiting_input and self._request_input:
            user_input = await self._request_input(result.message)
            result = self._sync_handler.handle_input(user_input)

        return result
