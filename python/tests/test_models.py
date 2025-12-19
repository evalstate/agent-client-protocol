"""Tests for data models."""

import json
import tempfile
from pathlib import Path
import pytest

from acp_skills.models import (
    MarketplaceOwner,
    MarketplaceMetadata,
    MarketplacePlugin,
    Marketplace,
    Manifest,
    Skill,
)


class TestMarketplacePlugin:
    """Tests for MarketplacePlugin."""

    def test_from_dict(self):
        """Test creating plugin from dictionary."""
        data = {
            "name": "test-plugin",
            "source": "./test_source",
            "description": "A test plugin",
        }
        plugin = MarketplacePlugin.from_dict(data)

        assert plugin.name == "test-plugin"
        assert plugin.source == "./test_source"
        assert plugin.description == "A test plugin"

    def test_get_skill_folder_name(self):
        """Test skill folder name extraction."""
        plugin = MarketplacePlugin(
            name="my-skill",
            source="./my_skill_source",
            description="Test",
        )
        assert plugin.get_skill_folder_name() == "my-skill"


class TestMarketplace:
    """Tests for Marketplace."""

    @pytest.fixture
    def sample_marketplace_data(self):
        """Sample marketplace data for testing."""
        return {
            "name": "test-marketplace",
            "owner": {"name": "Test Owner"},
            "metadata": {
                "description": "Test marketplace",
                "version": "1.0.0",
            },
            "plugins": [
                {
                    "name": "plugin-one",
                    "source": "./plugin_one",
                    "description": "First plugin",
                },
                {
                    "name": "plugin-two",
                    "source": "./plugin_two",
                    "description": "Second plugin",
                },
            ],
        }

    def test_from_dict(self, sample_marketplace_data):
        """Test creating marketplace from dictionary."""
        marketplace = Marketplace.from_dict(sample_marketplace_data)

        assert marketplace.name == "test-marketplace"
        assert marketplace.owner.name == "Test Owner"
        assert marketplace.metadata.description == "Test marketplace"
        assert marketplace.metadata.version == "1.0.0"
        assert len(marketplace.plugins) == 2

    def test_from_json(self, sample_marketplace_data):
        """Test creating marketplace from JSON string."""
        json_str = json.dumps(sample_marketplace_data)
        marketplace = Marketplace.from_json(json_str, raw_url="https://example.com")

        assert marketplace.name == "test-marketplace"
        assert marketplace.raw_url == "https://example.com"

    def test_get_plugin_by_name(self, sample_marketplace_data):
        """Test finding plugin by name."""
        marketplace = Marketplace.from_dict(sample_marketplace_data)

        plugin = marketplace.get_plugin_by_name("plugin-one")
        assert plugin is not None
        assert plugin.name == "plugin-one"

        # Case insensitive
        plugin = marketplace.get_plugin_by_name("PLUGIN-ONE")
        assert plugin is not None
        assert plugin.name == "plugin-one"

        # Not found
        plugin = marketplace.get_plugin_by_name("nonexistent")
        assert plugin is None

    def test_get_plugin_by_index(self, sample_marketplace_data):
        """Test finding plugin by index."""
        marketplace = Marketplace.from_dict(sample_marketplace_data)

        # 1-based index
        plugin = marketplace.get_plugin_by_index(1)
        assert plugin is not None
        assert plugin.name == "plugin-one"

        plugin = marketplace.get_plugin_by_index(2)
        assert plugin is not None
        assert plugin.name == "plugin-two"

        # Out of range
        plugin = marketplace.get_plugin_by_index(0)
        assert plugin is None
        plugin = marketplace.get_plugin_by_index(3)
        assert plugin is None


class TestManifest:
    """Tests for Manifest."""

    def test_from_skill_md(self):
        """Test parsing SKILL.md file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            skill_md = skill_dir / "SKILL.md"
            skill_md.write_text(
                "# My Test Skill\n\n"
                "This is the description of my test skill.\n\n"
                "## Usage\n\n"
                "Some usage instructions."
            )

            manifest = Manifest.from_skill_md(skill_md)

            assert manifest.name == "My Test Skill"
            assert "description of my test skill" in manifest.description
            assert "My Test Skill" in manifest.raw_content

    def test_from_json_file(self):
        """Test parsing manifest.json file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            manifest_json = skill_dir / "manifest.json"
            manifest_json.write_text(
                json.dumps({
                    "name": "JSON Skill",
                    "description": "A skill from JSON",
                    "version": "2.0.0",
                    "author": "Test Author",
                })
            )

            manifest = Manifest.from_json_file(manifest_json)

            assert manifest.name == "JSON Skill"
            assert manifest.description == "A skill from JSON"
            assert manifest.version == "2.0.0"
            assert manifest.author == "Test Author"

    def test_from_path_prefers_skill_md(self):
        """Test that SKILL.md is preferred over manifest.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()

            # Create both files
            (skill_dir / "SKILL.md").write_text("# MD Skill\n\nFrom markdown")
            (skill_dir / "manifest.json").write_text(
                json.dumps({"name": "JSON Skill", "description": "From JSON"})
            )

            manifest = Manifest.from_path(skill_dir)
            assert manifest.name == "MD Skill"

    def test_from_path_fallback_to_dir_name(self):
        """Test fallback to directory name when no manifest."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill-dir"
            skill_dir.mkdir()

            manifest = Manifest.from_path(skill_dir)
            assert manifest.name == "my-skill-dir"
            assert manifest.description == "No manifest found"


class TestSkill:
    """Tests for Skill."""

    def test_from_path(self):
        """Test creating skill from path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Test\n\nDescription here")

            skill = Skill.from_path(skill_dir, index=1)

            assert skill.name == "Test"
            assert skill.path == skill_dir
            assert skill.index == 1

    def test_get_system_prompt_content(self):
        """Test getting system prompt content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            content = "# Test Skill\n\nThis is the skill content."
            (skill_dir / "SKILL.md").write_text(content)

            skill = Skill.from_path(skill_dir)
            prompt_content = skill.get_system_prompt_content()

            assert content in prompt_content

    def test_to_dict(self):
        """Test converting skill to dictionary."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "test-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("# Test\n\nDescription")

            skill = Skill.from_path(skill_dir)
            data = skill.to_dict()

            assert data["name"] == "Test"
            assert str(skill_dir) in data["path"]
