#!/usr/bin/env python3
"""
Example integration of Skills Manager with hf-inference-acp.

This example shows how to integrate the skills manager into an ACP agent
implementation, handling slash commands and system prompt regeneration.
"""

from typing import Callable, Optional
from acp_skills import (
    SkillsCommandHandler,
    SkillsConfig,
    CommandResult,
)


class ACPAgentWithSkills:
    """
    Example ACP agent with skills management.

    This is a simplified example showing the key integration points.
    """

    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
        self._system_prompt_base = "You are a helpful AI assistant."
        self._system_prompt_skills = ""

        # Initialize skills handler with system prompt regeneration callback
        self.skills_handler = SkillsCommandHandler(
            on_skills_changed=self._regenerate_system_prompt
        )

        # Initial system prompt generation
        self._regenerate_system_prompt()

    def _regenerate_system_prompt(self) -> None:
        """Regenerate system prompt with current skills content."""
        self._system_prompt_skills = self.skills_handler.get_system_prompt_content()
        print("[Agent] System prompt regenerated with skills content")

    @property
    def system_prompt(self) -> str:
        """Get the complete system prompt."""
        return f"{self._system_prompt_base}\n\n{self._system_prompt_skills}"

    def get_available_commands(self) -> list:
        """
        Get available slash commands for ACP advertisement.

        This would be sent via session/update notification.
        """
        return self.skills_handler.available_commands

    def handle_slash_command(self, command: str, args: str = "") -> str:
        """
        Handle a slash command from the user.

        Args:
            command: The slash command (e.g., "/skills", "/skills add")
            args: Command arguments

        Returns:
            Response message to show the user
        """
        if command.startswith("/skills"):
            response = self.skills_handler.handle_command(command, args)

            # If awaiting input, we'd need to handle the interactive flow
            if response.result == CommandResult.AWAITING_INPUT:
                # In a real implementation, this would involve
                # sending the message to the user and waiting for input
                return response.message + "\n\n(Enter selection or 'q' to cancel)"

            return response.message

        return f"Unknown command: {command}"

    def handle_user_input_for_pending_action(self, user_input: str) -> str:
        """
        Handle user input when there's a pending action.

        Args:
            user_input: The user's selection

        Returns:
            Response message
        """
        if self.skills_handler.has_pending_action:
            response = self.skills_handler.handle_input(user_input)
            return response.message

        return "No pending action."


def main():
    """Demo of the skills manager integration."""
    print("=" * 60)
    print("Skills Manager Demo")
    print("=" * 60)

    # Create agent
    agent = ACPAgentWithSkills()

    # Show initial system prompt
    print("\n[Initial System Prompt]")
    print(agent.system_prompt)
    print()

    # Demo: List available commands
    print("\n[Available Commands for ACP]")
    for cmd in agent.get_available_commands():
        print(f"  /{cmd['name']}: {cmd['description']}")
    print()

    # Demo: /skills command (list installed)
    print("\n[Command: /skills]")
    result = agent.handle_slash_command("/skills")
    print(result)

    # Demo: /skills add (show marketplace)
    print("\n[Command: /skills add]")
    result = agent.handle_slash_command("/skills add")
    print(result)

    # Demo: Install a skill
    print("\n[Installing skill 'model-trainer']")
    result = agent.handle_user_input_for_pending_action("1")  # Select first skill
    print(result)

    # Show updated system prompt
    print("\n[Updated System Prompt]")
    print(agent.system_prompt[:500] + "..." if len(agent.system_prompt) > 500 else agent.system_prompt)

    # Demo: /skills (list installed after adding)
    print("\n[Command: /skills (after install)]")
    result = agent.handle_slash_command("/skills")
    print(result)


if __name__ == "__main__":
    main()
