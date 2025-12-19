"""
Slash command handlers for skills management.

Provides the `/skills`, `/skills add`, and `/skills remove` command implementations.
"""

from dataclasses import dataclass
from typing import Optional, List, Callable, Any
from enum import Enum, auto

from .config import SkillsConfig
from .manager import SkillsManager


class CommandResult(Enum):
    """Result of command execution."""
    SUCCESS = auto()
    ERROR = auto()
    CANCELLED = auto()
    AWAITING_INPUT = auto()


@dataclass
class CommandResponse:
    """Response from a command execution."""
    result: CommandResult
    message: str
    data: Optional[Any] = None


class SkillsCommandHandler:
    """
    Handler for skills-related slash commands.

    Supports:
    - /skills - List installed skills
    - /skills add - Show marketplace and install skills
    - /skills remove - Remove installed skills
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_skills_changed: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the command handler.

        Args:
            config: Skills configuration
            on_skills_changed: Callback when skills change (for system prompt regen)
        """
        self.manager = SkillsManager(
            config=config,
            on_skills_changed=on_skills_changed,
        )
        self._pending_action: Optional[str] = None  # "add" or "remove"

    @property
    def available_commands(self) -> List[dict]:
        """Get the list of available commands for ACP advertisement."""
        return [
            {
                "name": "skills",
                "description": "List installed skills",
            },
            {
                "name": "skills add",
                "description": "Browse and install skills from marketplace",
                "input": {"hint": "skill name or number (optional)"},
            },
            {
                "name": "skills remove",
                "description": "Remove an installed skill",
                "input": {"hint": "skill name or number"},
            },
        ]

    def handle_command(self, command: str, args: str = "") -> CommandResponse:
        """
        Handle a skills command.

        Args:
            command: The command (e.g., "skills", "skills add", "skills remove")
            args: Additional arguments

        Returns:
            CommandResponse with result and message
        """
        command = command.lower().strip()
        args = args.strip()

        if command == "skills" or command == "/skills":
            if not args:
                return self._list_installed()
            elif args.startswith("add"):
                return self._handle_add(args[3:].strip())
            elif args.startswith("remove"):
                return self._handle_remove(args[6:].strip())
            else:
                return CommandResponse(
                    result=CommandResult.ERROR,
                    message=f"Unknown skills subcommand: {args}\n"
                            f"Available: /skills, /skills add, /skills remove"
                )

        elif command == "skills add" or command == "/skills add":
            return self._handle_add(args)

        elif command == "skills remove" or command == "/skills remove":
            return self._handle_remove(args)

        return CommandResponse(
            result=CommandResult.ERROR,
            message=f"Unknown command: {command}"
        )

    def handle_input(self, user_input: str) -> CommandResponse:
        """
        Handle user input when awaiting a response.

        Args:
            user_input: The user's input

        Returns:
            CommandResponse with result
        """
        user_input = user_input.strip().lower()

        if user_input == "q":
            self._pending_action = None
            return CommandResponse(
                result=CommandResult.CANCELLED,
                message="Cancelled."
            )

        if self._pending_action == "add":
            return self._complete_add(user_input)
        elif self._pending_action == "remove":
            return self._complete_remove(user_input)

        return CommandResponse(
            result=CommandResult.ERROR,
            message="No pending action."
        )

    def _list_installed(self) -> CommandResponse:
        """List installed skills."""
        skills = self.manager.list_installed_skills()

        if not skills:
            return CommandResponse(
                result=CommandResult.SUCCESS,
                message="No skills installed.\n\n"
                        "Use `/skills add` to browse and install skills from the marketplace."
            )

        lines = ["**Installed Skills:**\n"]
        for i, skill in enumerate(skills, 1):
            lines.append(f"  {i}. **{skill.name}**")
            lines.append(f"     {skill.description}\n")

        lines.append("\nUse `/skills remove <name|number>` to remove a skill.")

        return CommandResponse(
            result=CommandResult.SUCCESS,
            message="\n".join(lines),
            data=skills,
        )

    def _handle_add(self, args: str) -> CommandResponse:
        """Handle /skills add command."""
        try:
            marketplace = self.manager.fetch_marketplace()
        except Exception as e:
            return CommandResponse(
                result=CommandResult.ERROR,
                message=f"Failed to fetch marketplace: {e}"
            )

        plugins = marketplace.plugins

        if not plugins:
            return CommandResponse(
                result=CommandResult.SUCCESS,
                message="No skills available in the marketplace."
            )

        # If argument provided, try to install directly
        if args:
            return self._complete_add(args)

        # Show available skills
        lines = [f"**Available Skills from {marketplace.owner}:**\n"]

        for i, plugin in enumerate(plugins, 1):
            installed = self.manager.registry.is_installed(plugin.name)
            status = " (installed)" if installed else ""
            lines.append(f"  {i}. **{plugin.name}**{status}")
            # Truncate description for display
            desc = plugin.description[:100] + "..." if len(plugin.description) > 100 else plugin.description
            lines.append(f"     {desc}\n")

        lines.append("\nEnter skill name or number to install (or 'q' to cancel):")

        self._pending_action = "add"

        return CommandResponse(
            result=CommandResult.AWAITING_INPUT,
            message="\n".join(lines),
            data=plugins,
        )

    def _complete_add(self, user_input: str) -> CommandResponse:
        """Complete the add action with user input."""
        self._pending_action = None

        if user_input.lower() == "q":
            return CommandResponse(
                result=CommandResult.CANCELLED,
                message="Installation cancelled."
            )

        try:
            # Try as number first
            if user_input.isdigit():
                index = int(user_input)
                manifest = self.manager.install_skill_by_index(index)
            else:
                manifest = self.manager.install_skill(user_input)

            return CommandResponse(
                result=CommandResult.SUCCESS,
                message=f"Successfully installed skill: **{manifest.name}**\n\n"
                        f"The skill is now available and the system prompt has been updated.",
                data=manifest,
            )

        except ValueError as e:
            return CommandResponse(
                result=CommandResult.ERROR,
                message=f"Error: {e}"
            )
        except FileNotFoundError as e:
            return CommandResponse(
                result=CommandResult.ERROR,
                message=f"Skill files not found: {e}"
            )
        except Exception as e:
            return CommandResponse(
                result=CommandResult.ERROR,
                message=f"Failed to install skill: {e}"
            )

    def _handle_remove(self, args: str) -> CommandResponse:
        """Handle /skills remove command."""
        skills = self.manager.list_installed_skills()

        if not skills:
            return CommandResponse(
                result=CommandResult.SUCCESS,
                message="No skills installed."
            )

        # If argument provided, try to remove directly
        if args:
            return self._complete_remove(args)

        # Show installed skills
        lines = ["**Installed Skills:**\n"]

        for i, skill in enumerate(skills, 1):
            lines.append(f"  {i}. **{skill.name}**")
            lines.append(f"     {skill.description}\n")

        lines.append("\nEnter skill name or number to remove (or 'q' to cancel):")

        self._pending_action = "remove"

        return CommandResponse(
            result=CommandResult.AWAITING_INPUT,
            message="\n".join(lines),
            data=skills,
        )

    def _complete_remove(self, user_input: str) -> CommandResponse:
        """Complete the remove action with user input."""
        self._pending_action = None

        if user_input.lower() == "q":
            return CommandResponse(
                result=CommandResult.CANCELLED,
                message="Removal cancelled."
            )

        try:
            # Try as number first
            if user_input.isdigit():
                index = int(user_input)
                skill = self.manager.registry.get_skill_by_index(index)
                if not skill:
                    return CommandResponse(
                        result=CommandResult.ERROR,
                        message=f"Invalid skill number: {index}"
                    )
                skill_name = skill.manifest.name
            else:
                skill_name = user_input

            success = self.manager.remove_skill(skill_name)

            if success:
                return CommandResponse(
                    result=CommandResult.SUCCESS,
                    message=f"Successfully removed skill: **{skill_name}**\n\n"
                            f"The system prompt has been updated.",
                )
            else:
                return CommandResponse(
                    result=CommandResult.ERROR,
                    message=f"Skill not found: {skill_name}"
                )

        except Exception as e:
            return CommandResponse(
                result=CommandResult.ERROR,
                message=f"Failed to remove skill: {e}"
            )

    def get_system_prompt_content(self) -> str:
        """Get skill content for system prompt."""
        return self.manager.get_system_prompt_content()

    @property
    def has_pending_action(self) -> bool:
        """Check if there's a pending action awaiting input."""
        return self._pending_action is not None


# Convenience function for simple integration
def create_skills_handler(
    marketplace_url: Optional[str] = None,
    skills_dir: Optional[str] = None,
    on_skills_changed: Optional[Callable[[], None]] = None,
) -> SkillsCommandHandler:
    """
    Create a skills command handler with custom configuration.

    Args:
        marketplace_url: URL to marketplace.json (optional)
        skills_dir: Directory for installed skills (optional)
        on_skills_changed: Callback when skills change

    Returns:
        Configured SkillsCommandHandler
    """
    from pathlib import Path

    config = SkillsConfig()

    if marketplace_url:
        config.marketplace_url = marketplace_url

    if skills_dir:
        config.skills_dir = Path(skills_dir)

    return SkillsCommandHandler(
        config=config,
        on_skills_changed=on_skills_changed,
    )
