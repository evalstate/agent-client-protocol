#!/usr/bin/env python3
"""
Example integration of Skills Manager with fast-agent.

This shows a more complete integration pattern including:
- Command routing
- Interactive input handling
- Session management
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

from acp_skills import (
    SkillsCommandHandler,
    SkillsConfig,
    CommandResult,
    CommandResponse,
)


@dataclass
class SessionState:
    """Session state for tracking pending actions."""
    pending_command: Optional[str] = None
    skills_handler: Optional[SkillsCommandHandler] = None


class FastAgentSkillsIntegration:
    """
    Integration layer for fast-agent.

    This class can be used as a mixin or component in fast-agent
    to add skills management capabilities.
    """

    def __init__(
        self,
        config: Optional[SkillsConfig] = None,
        on_system_prompt_change: Optional[callable] = None,
    ):
        self.config = config or SkillsConfig.from_env()
        self._on_system_prompt_change = on_system_prompt_change

        self.handler = SkillsCommandHandler(
            config=self.config,
            on_skills_changed=self._handle_skills_changed,
        )

    def _handle_skills_changed(self) -> None:
        """Called when skills are added or removed."""
        if self._on_system_prompt_change:
            self._on_system_prompt_change()

    def is_skills_command(self, message: str) -> bool:
        """Check if a message is a skills command."""
        message = message.strip().lower()
        return message.startswith("/skills")

    def route_command(self, message: str) -> CommandResponse:
        """
        Route a user message to the appropriate handler.

        Args:
            message: The user's message

        Returns:
            CommandResponse with result
        """
        message = message.strip()

        # Parse command and args
        parts = message.split(maxsplit=2)
        command = parts[0] if parts else ""

        # Handle /skills subcommands
        if command == "/skills":
            if len(parts) == 1:
                return self.handler.handle_command("/skills")
            elif parts[1] == "add":
                args = parts[2] if len(parts) > 2 else ""
                return self.handler.handle_command("/skills add", args)
            elif parts[1] == "remove":
                args = parts[2] if len(parts) > 2 else ""
                return self.handler.handle_command("/skills remove", args)
            else:
                return CommandResponse(
                    result=CommandResult.ERROR,
                    message=f"Unknown subcommand: {parts[1]}"
                )

        return CommandResponse(
            result=CommandResult.ERROR,
            message=f"Not a skills command: {message}"
        )

    def handle_pending_input(self, user_input: str) -> CommandResponse:
        """Handle input for pending actions."""
        return self.handler.handle_input(user_input)

    def has_pending_action(self) -> bool:
        """Check if there's a pending action."""
        return self.handler.has_pending_action

    def get_skills_system_prompt(self) -> str:
        """Get skills content for system prompt."""
        return self.handler.get_system_prompt_content()

    def advertise_commands(self) -> list:
        """Get commands for ACP advertisement."""
        return self.handler.available_commands


def interactive_demo():
    """Interactive demo of the skills integration."""
    print("\n" + "=" * 60)
    print("Fast-Agent Skills Manager - Interactive Demo")
    print("=" * 60)
    print("\nCommands:")
    print("  /skills        - List installed skills")
    print("  /skills add    - Browse and install from marketplace")
    print("  /skills remove - Remove an installed skill")
    print("  quit           - Exit demo")
    print("=" * 60 + "\n")

    def on_prompt_change():
        print("\n[System] System prompt regenerated")

    integration = FastAgentSkillsIntegration(
        on_system_prompt_change=on_prompt_change
    )

    while True:
        try:
            if integration.has_pending_action():
                user_input = input("Selection> ").strip()
                if user_input.lower() == "quit":
                    break
                response = integration.handle_pending_input(user_input)
            else:
                user_input = input("\nCommand> ").strip()
                if user_input.lower() == "quit":
                    break

                if not user_input:
                    continue

                if integration.is_skills_command(user_input):
                    response = integration.route_command(user_input)
                else:
                    print(f"Unknown command. Try /skills")
                    continue

            # Print response
            print(f"\n{response.message}")

            if response.result == CommandResult.ERROR:
                print("\n[Error occurred]")

        except KeyboardInterrupt:
            print("\n\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")

    print("\nGoodbye!")


if __name__ == "__main__":
    interactive_demo()
