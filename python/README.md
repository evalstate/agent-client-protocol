# ACP Skills Manager

A skills management system for Agent Client Protocol (ACP) implementations like fast-agent and hf-inference-acp.

## Overview

The Skills Manager provides a slash command interface for managing skills from marketplace repositories:

- `/skills` - List installed skills
- `/skills add` - Browse and install skills from marketplace
- `/skills remove` - Remove installed skills

## Installation

```bash
pip install acp-skills

# With HTTP client support
pip install acp-skills[httpx]
```

## Quick Start

### Basic Usage

```python
from acp_skills import SkillsCommandHandler

# Create handler with default configuration
handler = SkillsCommandHandler()

# Handle slash commands
response = handler.handle_command("/skills")
print(response.message)

# Add a skill
response = handler.handle_command("/skills add", "model-trainer")
print(response.message)

# Get content for system prompt
system_prompt_content = handler.get_system_prompt_content()
```

### With System Prompt Regeneration

```python
from acp_skills import SkillsCommandHandler, SkillsConfig

def regenerate_system_prompt():
    """Called when skills are added or removed."""
    # Your system prompt regeneration logic here
    print("Regenerating system prompt...")

handler = SkillsCommandHandler(
    on_skills_changed=regenerate_system_prompt
)

# When a skill is installed/removed, regenerate_system_prompt() is called
handler.handle_command("/skills add", "model-trainer")
```

### Custom Configuration

```python
from acp_skills import SkillsConfig, SkillsCommandHandler
from pathlib import Path

config = SkillsConfig(
    # Custom marketplace URL
    marketplace_url="https://raw.githubusercontent.com/your-org/skills/main/.claude-plugin/marketplace.json",

    # Custom skills directory
    skills_dir=Path(".my-agent/skills"),

    # Network timeout
    request_timeout=60,
)

handler = SkillsCommandHandler(config=config)
```

### Environment Variables

Configuration can also be set via environment variables:

- `ACP_SKILLS_MARKETPLACE_URL` - Marketplace JSON URL
- `ACP_SKILLS_DIR` - Skills installation directory
- `ACP_SKILLS_CACHE_DIR` - Cache directory for cloned repos
- `ACP_SKILLS_TIMEOUT` - Network request timeout (seconds)
- `ACP_SKILLS_VERBOSE` - Enable verbose output (true/1/yes)

## Integration with ACP

### Advertising Commands

```python
# Get commands for ACP advertisement
commands = handler.available_commands

# Send via session/update notification
session_update = {
    "sessionUpdate": "available_commands_update",
    "availableCommands": commands
}
```

### Handling Interactive Input

```python
from acp_skills import CommandResult

# Initial command
response = handler.handle_command("/skills add")

if response.result == CommandResult.AWAITING_INPUT:
    # Show options to user
    print(response.message)

    # Get user selection
    user_input = input("> ")

    # Complete the action
    response = handler.handle_input(user_input)
    print(response.message)
```

### System Prompt Content

```python
# Get skill content for system prompt
content = handler.get_system_prompt_content()

# Append to your system prompt
system_prompt = f"""
Your base system prompt here...

{content}
"""
```

## Architecture

```
acp_skills/
├── __init__.py      # Package exports
├── config.py        # Configuration management
├── manifest.py      # Skill manifest parsing (SKILL.md)
├── registry.py      # Installed skills tracking
├── manager.py       # Core installation/removal logic
└── commands.py      # Slash command handlers
```

## How Skills Work

1. **Marketplace**: Skills are discovered from a `marketplace.json` file hosted in a GitHub repository
2. **Installation**: Skills are cloned using sparse checkout (only the needed files)
3. **Registry**: Installed skills are tracked in `.fast-agent/skills/.registry.json`
4. **System Prompt**: Skill content (SKILL.md + references) is included in the agent's system prompt

### Directory Structure

```
.fast-agent/
└── skills/
    ├── .registry.json          # Installed skills metadata
    ├── model-trainer/
    │   ├── SKILL.md            # Main skill documentation
    │   ├── references/         # Additional reference docs
    │   └── scripts/            # Helper scripts
    └── dataset-creator/
        └── SKILL.md
```

## API Reference

### SkillsConfig

Configuration dataclass with the following fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `marketplace_url` | `str` | HuggingFace skills | URL to marketplace.json |
| `skills_dir` | `Path` | `.fast-agent/skills` | Installation directory |
| `cache_dir` | `Path` | `.fast-agent/.cache/skills` | Cache for cloning |
| `request_timeout` | `int` | 30 | HTTP timeout (seconds) |
| `verbose` | `bool` | False | Verbose output |

### SkillsCommandHandler

Main class for handling slash commands.

**Methods:**
- `handle_command(command, args)` - Process a slash command
- `handle_input(user_input)` - Handle user input for pending actions
- `get_system_prompt_content()` - Get skill content for system prompt
- `available_commands` - List of commands for ACP advertisement

### CommandResponse

Response from command execution.

| Field | Type | Description |
|-------|------|-------------|
| `result` | `CommandResult` | SUCCESS, ERROR, CANCELLED, AWAITING_INPUT |
| `message` | `str` | Human-readable response |
| `data` | `Any` | Optional data (skills list, manifest, etc.) |

## License

MIT License - see LICENSE file for details.
