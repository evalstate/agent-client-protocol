# ACP Skills Manager

A skills manager for Agent Client Protocol (ACP) agents. This module provides a way to manage "skills" - reusable AI agent capabilities that can be installed from a marketplace and included in system prompts.

## Features

- **`/skills`** - List installed skills
- **`/skills add`** - Install skills from a configurable marketplace
- **`/skills remove`** - Remove installed skills
- Automatic system prompt regeneration after skill changes
- Support for both sync and async operation modes

## Installation

```bash
pip install acp-skills
```

Or for development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```python
from acp_skills import SkillsConfig, SkillsManager, SkillsCommandHandler

# Create a manager with default configuration
manager = SkillsManager()

# Or with custom configuration
config = SkillsConfig(
    marketplace_url="https://example.com/marketplace.json",
    skills_dir=".my-agent/skills",
)
manager = SkillsManager(config)

# Use the command handler for slash commands
handler = SkillsCommandHandler(manager)
result = handler.handle("/skills")
print(result.message)
```

## Integration with ACP Agents

```python
from acp_skills import SkillsIntegration

# Create integration with system prompt callback
integration = SkillsIntegration(
    on_system_prompt_changed=my_regenerate_system_prompt_fn,
)

# Get available commands for ACP AvailableCommandsUpdate
commands = integration.get_available_commands()

# Handle incoming slash commands
if integration.is_skills_command(user_message):
    result = integration.handle_command(user_message)

    # For interactive commands
    if result.awaiting_input:
        user_input = await get_user_input(result.message)
        result = integration.handle_input(user_input)

# Get skill content for system prompt
skill_content = integration.get_system_prompt_additions()
```

## Configuration

Configuration can be set via environment variables:

- `ACP_SKILLS_MARKETPLACE_URL` - URL to the marketplace.json file
- `ACP_SKILLS_DIR` - Directory for installed skills (default: `.fast-agent/skills`)

## Marketplace Format

The marketplace.json should follow this format:

```json
{
  "name": "my-skills",
  "owner": {"name": "My Organization"},
  "metadata": {
    "description": "Skills for AI agents",
    "version": "1.0.0"
  },
  "plugins": [
    {
      "name": "my-skill",
      "source": "./path/to/skill",
      "description": "Description of the skill"
    }
  ]
}
```

## Skill Format

Skills should contain either:

1. **SKILL.md** - Markdown file with skill content (Claude Code style)
2. **manifest.json** - JSON manifest with metadata

The content of SKILL.md is included directly in the system prompt.

## Running Tests

```bash
pytest
```

## License

Apache-2.0
