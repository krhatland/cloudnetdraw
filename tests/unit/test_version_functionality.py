"""
Tests for CLI version functionality
"""
import subprocess
import sys
import pytest
from unittest.mock import patch, Mock
import argparse

from cloudnetdraw.cli import create_parser
from cloudnetdraw import __version__

try:
    from importlib.metadata import version
except ImportError:
    # Python < 3.8
    from importlib_metadata import version


class TestVersionFunctionality:
    """Test the --version command line option"""
    
    def test_version_argument_in_parser(self):
        """Test that --version argument is properly configured in parser"""
        parser = create_parser()
        
        # Test that --version action is configured
        version_action = None
        for action in parser._actions:
            if hasattr(action, 'option_strings') and '--version' in action.option_strings:
                version_action = action
                break
        
        assert version_action is not None, "--version option should be configured in parser"
        assert version_action.__class__.__name__ == '_VersionAction', "--version should use _VersionAction"
        assert version_action.version == f'CloudNet Draw {__version__}', "Version string should match expected format"
    
    def test_version_displays_correct_version(self):
        """Test that --version displays the correct version string"""
        parser = create_parser()
        
        # Test that parsing --version raises SystemExit (normal behavior for version action)
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['--version'])
        
        # SystemExit with code 0 indicates successful version display
        assert exc_info.value.code == 0, "--version should exit with code 0"
    
    def test_version_subprocess_call(self):
        """Test --version functionality via subprocess call"""
        # Test the actual CLI command
        result = subprocess.run([
            sys.executable, '-m', 'cloudnetdraw.cli', '--version'
        ], capture_output=True, text=True, cwd='.')
        
        assert result.returncode == 0, "CLI --version should exit successfully"
        assert f'CloudNet Draw {__version__}' in result.stdout, "Version output should contain correct version string"
    
    def test_version_import_consistency(self):
        """Test that the version imported matches the expected version"""
        from cloudnetdraw import __version__ as imported_version
        
        # Get version from package metadata for comparison
        expected_version = version("cloudnetdraw")
        
        # Version should be a string in semantic versioning format
        assert isinstance(imported_version, str), "Version should be a string"
        assert len(imported_version.split('.')) >= 2, "Version should be in semantic versioning format"
        assert imported_version == expected_version, "Version should match package metadata version"
    
    def test_help_includes_version_option(self):
        """Test that --version appears in help text"""
        parser = create_parser()
        help_text = parser.format_help()
        
        assert '--version' in help_text, "--version should appear in help text"
        assert 'show program\'s version number and exit' in help_text, "Version help text should be descriptive"
    
    def test_version_and_subcommand_mutually_exclusive(self):
        """Test that --version works without requiring subcommands"""
        parser = create_parser()
        
        # Version should work without subcommands
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(['--version'])
        
        assert exc_info.value.code == 0, "--version should work without subcommands"
        
        # But normal usage should still require subcommands
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        
        assert exc_info.value.code == 2, "Missing subcommand should cause error exit"