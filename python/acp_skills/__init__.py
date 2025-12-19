"""
ACP Skills Manager

A skills management system for Agent Client Protocol (ACP) implementations.
Provides slash command interface for managing skills from marketplace repositories.
"""

from .config import SkillsConfig
from .manifest import SkillManifest
from .registry import SkillRegistry
from .manager import SkillsManager
from .commands import SkillsCommandHandler

__version__ = "0.1.0"

__all__ = [
    "SkillsConfig",
    "SkillManifest",
    "SkillRegistry",
    "SkillsManager",
    "SkillsCommandHandler",
]
