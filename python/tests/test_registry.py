"""Tests for SkillsRegistry."""

import tempfile
from pathlib import Path
import pytest

from acp_skills.config import SkillsConfig
from acp_skills.registry import SkillsRegistry


class TestSkillsRegistry:
    """Tests for SkillsRegistry."""

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
    def registry(self, config):
        """Create a registry instance."""
        return SkillsRegistry(config)

    def _create_skill(self, skills_dir: Path, name: str, content: str = None) -> Path:
        """Helper to create a skill directory."""
        skill_dir = skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)
        if content is None:
            content = f"# {name}\n\nDescription for {name}"
        (skill_dir / "SKILL.md").write_text(content)
        return skill_dir

    def test_list_empty(self, registry):
        """Test listing when no skills installed."""
        skills = registry.list_skills()
        assert skills == []
        assert len(registry) == 0

    def test_list_skills(self, registry, temp_skills_dir):
        """Test listing installed skills."""
        self._create_skill(temp_skills_dir, "skill-one")
        self._create_skill(temp_skills_dir, "skill-two")

        skills = registry.list_skills()
        assert len(skills) == 2
        names = [s.name for s in skills]
        assert "skill-one" in names
        assert "skill-two" in names

    def test_get_by_name(self, registry, temp_skills_dir):
        """Test getting skill by name."""
        self._create_skill(temp_skills_dir, "my-skill")

        skill = registry.get_by_name("my-skill")
        assert skill is not None
        assert skill.name == "my-skill"

        # Case insensitive
        skill = registry.get_by_name("MY-SKILL")
        assert skill is not None

        # Not found
        skill = registry.get_by_name("nonexistent")
        assert skill is None

    def test_get_by_index(self, registry, temp_skills_dir):
        """Test getting skill by index."""
        self._create_skill(temp_skills_dir, "aaa-skill")
        self._create_skill(temp_skills_dir, "bbb-skill")

        # Skills are sorted, so indices are predictable
        skill = registry.get_by_index(1)
        assert skill is not None
        assert skill.name == "aaa-skill"

        skill = registry.get_by_index(2)
        assert skill is not None
        assert skill.name == "bbb-skill"

        # Out of range
        skill = registry.get_by_index(0)
        assert skill is None
        skill = registry.get_by_index(3)
        assert skill is None

    def test_get_by_name_or_index(self, registry, temp_skills_dir):
        """Test getting skill by name or index."""
        self._create_skill(temp_skills_dir, "test-skill")

        # By name
        skill = registry.get_by_name_or_index("test-skill")
        assert skill is not None

        # By index
        skill = registry.get_by_name_or_index("1")
        assert skill is not None

    def test_exists(self, registry, temp_skills_dir):
        """Test checking if skill exists."""
        self._create_skill(temp_skills_dir, "existing-skill")

        assert registry.exists("existing-skill")
        assert not registry.exists("nonexistent")

    def test_remove(self, registry, temp_skills_dir):
        """Test removing a skill."""
        skill_path = self._create_skill(temp_skills_dir, "to-remove")
        assert skill_path.exists()

        skill = registry.get_by_name("to-remove")
        assert skill is not None

        result = registry.remove(skill)
        assert result is True
        assert not skill_path.exists()
        assert not registry.exists("to-remove")

    def test_remove_by_name(self, registry, temp_skills_dir):
        """Test removing by name."""
        self._create_skill(temp_skills_dir, "remove-by-name")

        result = registry.remove_by_name("remove-by-name")
        assert result is True
        assert not registry.exists("remove-by-name")

    def test_remove_by_index(self, registry, temp_skills_dir):
        """Test removing by index."""
        self._create_skill(temp_skills_dir, "remove-by-index")

        result = registry.remove_by_index(1)
        assert result is True

    def test_remove_by_name_or_index(self, registry, temp_skills_dir):
        """Test remove_by_name_or_index returns the removed skill."""
        self._create_skill(temp_skills_dir, "test-skill")

        skill = registry.remove_by_name_or_index("test-skill")
        assert skill is not None
        assert skill.name == "test-skill"

    def test_refresh(self, registry, temp_skills_dir):
        """Test refreshing the cache."""
        # Initial empty
        assert len(registry.list_skills()) == 0

        # Add a skill
        self._create_skill(temp_skills_dir, "new-skill")

        # Still empty (cached)
        assert len(registry._skills_cache) == 0

        # Refresh
        registry.refresh()

        # Now should see it
        assert len(registry.list_skills()) == 1

    def test_get_system_prompt_additions(self, registry, temp_skills_dir):
        """Test getting system prompt content."""
        self._create_skill(
            temp_skills_dir,
            "skill-one",
            "# Skill One\n\nContent for skill one",
        )
        self._create_skill(
            temp_skills_dir,
            "skill-two",
            "# Skill Two\n\nContent for skill two",
        )

        content = registry.get_system_prompt_additions()
        assert "Skill One" in content
        assert "Skill Two" in content

    def test_format_skills_list_empty(self, registry):
        """Test formatting empty skills list."""
        output = registry.format_skills_list()
        assert "No skills installed" in output

    def test_format_skills_list(self, registry, temp_skills_dir):
        """Test formatting skills list."""
        self._create_skill(temp_skills_dir, "test-skill", "# Test\n\nA description")
        registry.refresh()

        output = registry.format_skills_list()
        assert "Installed skills" in output
        assert "1. test-skill" in output or "1. Test" in output

    def test_iteration(self, registry, temp_skills_dir):
        """Test iterating over skills."""
        self._create_skill(temp_skills_dir, "skill-one")
        self._create_skill(temp_skills_dir, "skill-two")

        names = [s.name for s in registry]
        assert len(names) == 2

    def test_ignores_hidden_directories(self, registry, temp_skills_dir):
        """Test that hidden directories are ignored."""
        self._create_skill(temp_skills_dir, "visible-skill")
        (temp_skills_dir / ".hidden-skill").mkdir()

        skills = registry.list_skills()
        assert len(skills) == 1
        assert skills[0].name == "visible-skill"
