"""Tests for slash command handlers."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch
import pytest

from acp_skills.config import SkillsConfig
from acp_skills.manager import SkillsManager
from acp_skills.commands import (
    SkillsCommandHandler,
    CommandState,
    CommandResult,
)


class TestSkillsCommandHandler:
    """Tests for SkillsCommandHandler."""

    @pytest.fixture
    def temp_skills_dir(self):
        """Create a temporary skills directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def config(self, temp_skills_dir):
        """Create a config with the temp directory."""
        return SkillsConfig(
            skills_dir=str(temp_skills_dir),
            base_path=temp_skills_dir.parent,
        )

    @pytest.fixture
    def manager(self, config):
        """Create a manager instance."""
        return SkillsManager(config)

    @pytest.fixture
    def handler(self, manager):
        """Create a command handler."""
        return SkillsCommandHandler(manager)

    def _create_skill(self, skills_dir: Path, name: str) -> Path:
        """Helper to create a skill directory."""
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(f"# {name}\n\nDescription for {name}")
        return skill_dir

    def test_handle_skills_list_empty(self, handler):
        """Test /skills with no installed skills."""
        result = handler.handle("/skills")

        assert result.success is True
        assert "No skills installed" in result.message
        assert result.awaiting_input is False

    def test_handle_skills_list_with_skills(self, handler, temp_skills_dir):
        """Test /skills with installed skills."""
        self._create_skill(temp_skills_dir, "test-skill")
        handler.manager.registry.refresh()

        result = handler.handle("/skills")

        assert result.success is True
        assert "test-skill" in result.message or "Installed skills" in result.message

    def test_handle_unknown_command(self, handler):
        """Test handling unknown command."""
        result = handler.handle("/unknown")

        assert result.success is False
        assert "Unknown command" in result.message

    def test_handle_unknown_subcommand(self, handler):
        """Test handling unknown subcommand."""
        result = handler.handle("/skills unknown")

        assert result.success is False
        assert "Unknown subcommand" in result.message

    def test_handle_skills_add_shows_marketplace(self, handler):
        """Test /skills add shows available plugins."""
        with patch.object(handler.manager.marketplace, "fetch") as mock_fetch:
            from acp_skills.models import Marketplace

            mock_fetch.return_value = Marketplace.from_dict({
                "name": "test",
                "owner": {"name": "Test"},
                "metadata": {"description": "Test", "version": "1.0.0"},
                "plugins": [
                    {"name": "plugin-one", "source": "./p1", "description": "First"},
                ],
            })

            result = handler.handle("/skills add")

            assert result.success is True
            assert result.awaiting_input is True
            assert result.state == CommandState.AWAITING_ADD_SELECTION
            assert "plugin-one" in result.message

    def test_handle_skills_add_direct(self, handler):
        """Test /skills add <name> installs directly."""
        with patch.object(handler.manager, "install") as mock_install:
            from acp_skills.models import Skill, Manifest

            mock_skill = Mock()
            mock_skill.name = "installed-skill"
            mock_skill.manifest = Mock()
            mock_skill.manifest.description = "Test description"
            mock_install.return_value = mock_skill

            result = handler.handle("/skills add installed-skill")

            mock_install.assert_called_once_with("installed-skill")
            assert result.success is True
            assert "Successfully installed" in result.message

    def test_handle_skills_remove_empty(self, handler):
        """Test /skills remove with no skills."""
        result = handler.handle("/skills remove")

        assert result.success is True
        assert "No skills installed" in result.message

    def test_handle_skills_remove_shows_list(self, handler, temp_skills_dir):
        """Test /skills remove shows installed skills."""
        self._create_skill(temp_skills_dir, "test-skill")
        handler.manager.registry.refresh()

        result = handler.handle("/skills remove")

        assert result.success is True
        assert result.awaiting_input is True
        assert result.state == CommandState.AWAITING_REMOVE_SELECTION

    def test_handle_skills_remove_direct(self, handler, temp_skills_dir):
        """Test /skills remove <name> removes directly."""
        self._create_skill(temp_skills_dir, "to-remove")
        handler.manager.registry.refresh()

        result = handler.handle("/skills remove to-remove")

        assert result.success is True
        assert "Successfully removed" in result.message

    def test_handle_input_quit(self, handler):
        """Test quitting from interactive mode."""
        with patch.object(handler.manager.marketplace, "fetch"):
            from acp_skills.models import Marketplace

            handler.manager.marketplace._marketplace_cache = Marketplace.from_dict({
                "name": "test",
                "owner": {"name": "Test"},
                "metadata": {"description": "Test", "version": "1.0.0"},
                "plugins": [],
            })

            handler.handle("/skills add")  # Enter interactive mode

        result = handler.handle_input("q")

        assert result.success is True
        assert "Cancelled" in result.message
        assert handler.state == CommandState.IDLE

    def test_handle_input_no_pending(self, handler):
        """Test handling input when no pending operation."""
        result = handler.handle_input("1")

        assert result.success is False
        assert "No pending operation" in result.message

    def test_handle_input_add_selection(self, handler):
        """Test completing add with input."""
        with patch.object(handler.manager, "install") as mock_install:
            mock_skill = Mock()
            mock_skill.name = "selected-skill"
            mock_skill.manifest = Mock()
            mock_skill.manifest.description = "Test"
            mock_install.return_value = mock_skill

            handler._state = CommandState.AWAITING_ADD_SELECTION

            result = handler.handle_input("1")

            mock_install.assert_called_once_with("1")
            assert result.success is True

    def test_handle_input_remove_selection(self, handler, temp_skills_dir):
        """Test completing remove with input."""
        self._create_skill(temp_skills_dir, "to-remove")
        handler.manager.registry.refresh()
        handler._state = CommandState.AWAITING_REMOVE_SELECTION

        result = handler.handle_input("1")

        assert result.success is True
        assert "Successfully removed" in result.message

    def test_reset_state(self, handler):
        """Test resetting state."""
        handler._state = CommandState.AWAITING_ADD_SELECTION

        handler.reset_state()

        assert handler.state == CommandState.IDLE

    def test_without_leading_slash(self, handler):
        """Test handling command without leading slash."""
        result = handler.handle("skills")

        assert result.success is True
        # Should still work

    def test_empty_command(self, handler):
        """Test handling empty command."""
        result = handler.handle("")

        assert result.success is False
        assert "Usage" in result.message
