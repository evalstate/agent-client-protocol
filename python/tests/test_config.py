"""Tests for SkillsConfig."""

import os
import tempfile
from pathlib import Path
import pytest

from acp_skills.config import SkillsConfig, DEFAULT_MARKETPLACE_URL, DEFAULT_SKILLS_DIR


class TestSkillsConfig:
    """Tests for SkillsConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = SkillsConfig()
        assert config.marketplace_url == DEFAULT_MARKETPLACE_URL
        assert config.skills_dir == DEFAULT_SKILLS_DIR
        assert config.base_path == Path.cwd()

    def test_custom_values(self):
        """Test custom configuration values."""
        config = SkillsConfig(
            marketplace_url="https://example.com/marketplace.json",
            skills_dir="/custom/skills",
            base_path=Path("/custom/base"),
        )
        assert config.marketplace_url == "https://example.com/marketplace.json"
        assert config.skills_dir == "/custom/skills"
        assert config.base_path == Path("/custom/base")

    def test_skills_path_absolute(self):
        """Test skills_path with absolute skills_dir."""
        config = SkillsConfig(
            skills_dir="/absolute/path/skills",
            base_path=Path("/base"),
        )
        assert config.skills_path == Path("/absolute/path/skills")

    def test_skills_path_relative(self):
        """Test skills_path with relative skills_dir."""
        config = SkillsConfig(
            skills_dir="relative/skills",
            base_path=Path("/base"),
        )
        assert config.skills_path == Path("/base/relative/skills")

    def test_ensure_skills_dir(self):
        """Test that ensure_skills_dir creates the directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SkillsConfig(
                skills_dir="test_skills",
                base_path=Path(tmpdir),
            )
            path = config.ensure_skills_dir()
            assert path.exists()
            assert path.is_dir()
            assert path == Path(tmpdir) / "test_skills"

    def test_from_env(self, monkeypatch):
        """Test loading config from environment variables."""
        monkeypatch.setenv("ACP_SKILLS_MARKETPLACE_URL", "https://env.example.com/market.json")
        monkeypatch.setenv("ACP_SKILLS_DIR", "/env/skills")

        config = SkillsConfig.from_env()
        assert config.marketplace_url == "https://env.example.com/market.json"
        assert config.skills_dir == "/env/skills"

    def test_with_marketplace_url(self):
        """Test creating config with different marketplace URL."""
        original = SkillsConfig()
        modified = original.with_marketplace_url("https://new.example.com/market.json")

        assert modified.marketplace_url == "https://new.example.com/market.json"
        assert modified.skills_dir == original.skills_dir
        assert modified.base_path == original.base_path

    def test_with_skills_dir(self):
        """Test creating config with different skills directory."""
        original = SkillsConfig()
        modified = original.with_skills_dir("/new/skills")

        assert modified.skills_dir == "/new/skills"
        assert modified.marketplace_url == original.marketplace_url
        assert modified.base_path == original.base_path
