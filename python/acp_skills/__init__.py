"""
ACP Skills Manager - Manage skills for Agent Client Protocol agents.

This module provides a skills manager that can:
- List available skills in a local folder
- Add skills from a configurable marketplace
- Remove installed skills
- Regenerate system prompts after skill changes
"""

from .config import SkillsConfig
from .models import Skill, Manifest, MarketplacePlugin
from .registry import SkillsRegistry
from .marketplace import SkillsMarketplace
from .manager import SkillsManager
from .commands import SkillsCommandHandler

__version__ = "0.1.0"

__all__ = [
    "SkillsConfig",
    "Skill",
    "Manifest",
    "MarketplacePlugin",
    "SkillsRegistry",
    "SkillsMarketplace",
    "SkillsManager",
    "SkillsCommandHandler",
]
