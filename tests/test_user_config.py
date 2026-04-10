"""
Tests for user configuration management (~/.finbaserc).
"""

import pytest
import yaml
from pathlib import Path
import tempfile
import shutil

from finbase.config.user_config import (
    UserConfig,
    initialize_user_space,
    get_configured_db_path,
    DEFAULT_USER_SPACE,
    DEFAULT_DB_PATH
)


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    yield config_dir
    # Cleanup
    if config_dir.exists():
        shutil.rmtree(config_dir)


@pytest.fixture
def temp_config_file(temp_config_dir):
    """Create temporary config file path."""
    return temp_config_dir / ".finbaserc"


@pytest.fixture
def user_config(temp_config_file):
    """Create UserConfig instance with temporary file."""
    return UserConfig(config_path=temp_config_file)


class TestUserConfigInit:
    """Test UserConfig initialization."""

    def test_init_creates_empty_config_if_not_exists(self, temp_config_file):
        """Test that init works when config file doesn't exist."""
        config = UserConfig(config_path=temp_config_file)
        assert config.config_path == temp_config_file
        assert config._config == {}

    def test_init_loads_existing_config(self, temp_config_file):
        """Test that init loads existing config file."""
        # Create config file
        config_data = {
            'database': {
                'path': '/test/path/db.db'
            }
        }
        with open(temp_config_file, 'w') as f:
            yaml.safe_dump(config_data, f)

        # Load it
        config = UserConfig(config_path=temp_config_file)
        assert config._config == config_data

    def test_init_handles_empty_yaml(self, temp_config_file):
        """Test that init handles empty YAML file."""
        temp_config_file.write_text('')
        config = UserConfig(config_path=temp_config_file)
        assert config._config == {}

    def test_init_handles_invalid_yaml(self, temp_config_file):
        """Test that init handles invalid YAML gracefully."""
        temp_config_file.write_text('invalid: yaml: content: {{{')
        config = UserConfig(config_path=temp_config_file)
        assert config._config == {}


class TestUserConfigDatabasePath:
    """Test database path get/set operations."""

    def test_get_db_path_none_if_not_set(self, user_config):
        """Test get_db_path returns None when not configured."""
        assert user_config.get_db_path() is None

    def test_set_and_get_db_path(self, user_config, temp_config_file):
        """Test setting and getting database path."""
        test_path = Path('/test/database/location.db')
        user_config.set_db_path(test_path)

        # Verify in memory
        assert user_config.get_db_path() == test_path

        # Verify saved to file
        assert temp_config_file.exists()
        with open(temp_config_file, 'r') as f:
            saved_config = yaml.safe_load(f)
        assert saved_config['database']['path'] == str(test_path)

    def test_set_db_path_creates_nested_structure(self, user_config):
        """Test that set_db_path creates nested config structure."""
        test_path = Path('/test/db.db')
        user_config.set_db_path(test_path)

        assert 'database' in user_config._config
        assert 'path' in user_config._config['database']
        assert user_config._config['database']['path'] == str(test_path)

    def test_set_db_path_expands_tilde(self, user_config):
        """Test that get_db_path expands ~ to user home."""
        user_config.set_db_path(Path('~/test/db.db'))
        retrieved_path = user_config.get_db_path()
        assert retrieved_path.is_absolute()
        assert '~' not in str(retrieved_path)


class TestUserConfigGenericGetSet:
    """Test generic get/set operations."""

    def test_get_nonexistent_key_returns_default(self, user_config):
        """Test get returns default for nonexistent key."""
        assert user_config.get('nonexistent.key', 'default') == 'default'
        assert user_config.get('nonexistent.key') is None

    def test_set_and_get_simple_key(self, user_config):
        """Test setting and getting simple key."""
        user_config.set('test_key', 'test_value')
        assert user_config.get('test_key') == 'test_value'

    def test_set_and_get_nested_key(self, user_config):
        """Test setting and getting nested key with dots."""
        user_config.set('level1.level2.level3', 'deep_value')
        assert user_config.get('level1.level2.level3') == 'deep_value'

    def test_set_overwrites_existing_value(self, user_config):
        """Test that set overwrites existing value."""
        user_config.set('key', 'value1')
        assert user_config.get('key') == 'value1'

        user_config.set('key', 'value2')
        assert user_config.get('key') == 'value2'

    def test_get_all_returns_copy(self, user_config):
        """Test that get_all returns a copy of config."""
        user_config.set('test', 'value')
        config_copy = user_config.get_all()

        # Modify copy
        config_copy['test'] = 'modified'

        # Original should be unchanged
        assert user_config.get('test') == 'value'


class TestUserConfigPersistence:
    """Test config persistence to file."""

    def test_config_saved_to_yaml_format(self, user_config, temp_config_file):
        """Test that config is saved in YAML format."""
        user_config.set('database.path', '/test/db.db')
        user_config.set('logging.level', 'DEBUG')

        assert temp_config_file.exists()

        # Read raw YAML
        with open(temp_config_file, 'r') as f:
            saved_data = yaml.safe_load(f)

        assert saved_data['database']['path'] == '/test/db.db'
        assert saved_data['logging']['level'] == 'DEBUG'

    def test_config_reloaded_correctly(self, temp_config_file):
        """Test that config can be saved and reloaded."""
        # Create and save config
        config1 = UserConfig(config_path=temp_config_file)
        config1.set('database.path', '/test/path.db')
        config1.set('custom.setting', 'value')

        # Load in new instance
        config2 = UserConfig(config_path=temp_config_file)
        assert config2.get('database.path') == '/test/path.db'
        assert config2.get('custom.setting') == 'value'


class TestInitializeUserSpace:
    """Test initialize_user_space function."""

    def test_initialize_default_path(self, tmp_path):
        """Test initializing with default path."""
        # Use explicit path instead of trying to mock Path.home()
        user_space = tmp_path / ".finbase"
        db_path = user_space / "timeseries.db"
        config_path = tmp_path / ".finbaserc"

        # Mock config path
        from finbase.config import user_config as uc_module
        original_config_path = uc_module.DEFAULT_CONFIG_PATH
        uc_module.DEFAULT_CONFIG_PATH = config_path

        try:
            # Initialize with explicit path (None would use real home)
            result = initialize_user_space(db_path)

            # Verify directory created
            assert user_space.exists()
            assert user_space.is_dir()

            # Verify config saved
            assert config_path.exists()
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            assert config['database']['path'] == str(db_path)
            assert result == db_path
        finally:
            uc_module.DEFAULT_CONFIG_PATH = original_config_path

    def test_initialize_custom_path(self, tmp_path, temp_config_file):
        """Test initializing with custom path."""
        custom_db_path = tmp_path / "custom" / "location" / "db.db"

        # Mock config path
        from finbase.config import user_config as uc_module
        original_default = uc_module.DEFAULT_CONFIG_PATH
        uc_module.DEFAULT_CONFIG_PATH = temp_config_file

        try:
            result = initialize_user_space(custom_db_path)

            # Verify directory created
            assert custom_db_path.parent.exists()
            assert result == custom_db_path

            # Verify config saved
            assert temp_config_file.exists()
            with open(temp_config_file, 'r') as f:
                config = yaml.safe_load(f)
            assert config['database']['path'] == str(custom_db_path)
        finally:
            # Restore
            uc_module.DEFAULT_CONFIG_PATH = original_default

    def test_initialize_creates_nested_directories(self, tmp_path, temp_config_file):
        """Test that initialize creates nested directory structure."""
        deep_path = tmp_path / "level1" / "level2" / "level3" / "db.db"

        # Mock config path
        from finbase.config import user_config as uc_module
        original_default = uc_module.DEFAULT_CONFIG_PATH
        uc_module.DEFAULT_CONFIG_PATH = temp_config_file

        try:
            result = initialize_user_space(deep_path)
            assert deep_path.parent.exists()
            assert result == deep_path
        finally:
            uc_module.DEFAULT_CONFIG_PATH = original_default


class TestGetConfiguredDbPath:
    """Test get_configured_db_path function."""

    def test_returns_configured_path_if_exists(self, temp_config_file):
        """Test that it returns configured path when available."""
        # Set up config
        config = UserConfig(config_path=temp_config_file)
        test_path = Path('/test/configured/db.db')
        config.set_db_path(test_path)

        # Mock DEFAULT_CONFIG_PATH
        from finbase.config import user_config as uc_module
        original_default = uc_module.DEFAULT_CONFIG_PATH
        uc_module.DEFAULT_CONFIG_PATH = temp_config_file

        try:
            result = get_configured_db_path()
            assert result == test_path
        finally:
            uc_module.DEFAULT_CONFIG_PATH = original_default

    def test_returns_default_if_no_config(self, tmp_path, monkeypatch):
        """Test that it returns default path when no config exists."""
        # Use non-existent config file
        nonexistent_config = tmp_path / "nonexistent.yaml"

        # Mock DEFAULT_CONFIG_PATH and DEFAULT_DB_PATH
        from finbase.config import user_config as uc_module
        original_config_path = uc_module.DEFAULT_CONFIG_PATH
        original_db_path = uc_module.DEFAULT_DB_PATH

        temp_home = tmp_path / "home"
        temp_home.mkdir()
        expected_path = temp_home / ".finbase" / "timeseries.db"

        uc_module.DEFAULT_CONFIG_PATH = nonexistent_config
        uc_module.DEFAULT_DB_PATH = expected_path

        try:
            result = get_configured_db_path()
            assert result == expected_path
        finally:
            uc_module.DEFAULT_CONFIG_PATH = original_config_path
            uc_module.DEFAULT_DB_PATH = original_db_path


class TestYAMLFormat:
    """Test YAML format specifics."""

    def test_yaml_is_readable_format(self, user_config, temp_config_file):
        """Test that saved YAML is human-readable."""
        user_config.set('database.path', '/test/db.db')
        user_config.set('logging.level', 'INFO')

        # Read raw content
        content = temp_config_file.read_text()

        # Check YAML structure (not JSON)
        assert 'database:' in content
        assert '  path:' in content
        assert 'logging:' in content
        assert '  level:' in content
        # Should not have JSON format
        assert '{' not in content or '}' not in content

    def test_yaml_preserves_types(self, user_config, temp_config_file):
        """Test that YAML preserves data types."""
        user_config.set('string_val', 'text')
        user_config.set('int_val', 42)
        user_config.set('float_val', 3.14)
        user_config.set('bool_val', True)
        user_config.set('list_val', [1, 2, 3])

        # Reload
        config2 = UserConfig(config_path=temp_config_file)
        assert isinstance(config2.get('string_val'), str)
        assert isinstance(config2.get('int_val'), int)
        assert isinstance(config2.get('float_val'), float)
        assert isinstance(config2.get('bool_val'), bool)
        assert isinstance(config2.get('list_val'), list)


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_handles_permission_errors_gracefully(self, tmp_path):
        """Test handling of permission errors during save."""
        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        config_file = readonly_dir / ".finbaserc"

        config = UserConfig(config_path=config_file)

        # Make directory read-only (Unix-like systems)
        import os
        if os.name != 'nt':  # Skip on Windows
            readonly_dir.chmod(0o444)
            try:
                with pytest.raises(Exception):
                    config.set('test', 'value')
            finally:
                # Restore permissions for cleanup
                readonly_dir.chmod(0o755)

    def test_handles_corrupted_config_file(self, temp_config_file):
        """Test handling of corrupted config file."""
        # Write corrupted YAML
        temp_config_file.write_text('{{{{ invalid yaml content')

        # Should not raise, should return empty config
        config = UserConfig(config_path=temp_config_file)
        assert config._config == {}
        assert config.get_db_path() is None
