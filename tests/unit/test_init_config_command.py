"""
Tests for the init-config command functionality
"""
import pytest
import os
import tempfile
import shutil
from unittest.mock import patch, Mock, ANY
from argparse import Namespace

from cloudnetdraw.cli import init_config_command


class TestInitConfigCommand:
    """Test the init-config command"""
    
    def test_init_config_command_success(self):
        """Test successful configuration file creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output="test_config.yaml", force=False)
            
            # Mock the bundled config path method directly
            with patch('cloudnetdraw.cli.shutil.copy2') as mock_copy, \
                 patch('cloudnetdraw.cli.logging.info') as mock_log_info, \
                 patch('cloudnetdraw.cli.os.path.exists', return_value=False), \
                 patch('os.getcwd', return_value=tmpdir):
                
                # Execute command
                init_config_command(args)
                
                # Verify copy was called with some path and output file
                mock_copy.assert_called_once()
                call_args = mock_copy.call_args[0]
                assert call_args[1] == "test_config.yaml"
                assert "config.yaml" in call_args[0]  # Source path should contain config.yaml
                
                # Verify success messages
                assert mock_log_info.call_count == 3
                mock_log_info.assert_any_call("Configuration file created: test_config.yaml")
                mock_log_info.assert_any_call("You can now customize the configuration settings.")
                mock_log_info.assert_any_call("Use --config-file to specify this file in other commands.")
    
    def test_init_config_command_default_output(self):
        """Test init-config command with default output file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output=None, force=False)
            
            with patch('cloudnetdraw.cli.shutil.copy2') as mock_copy, \
                 patch('cloudnetdraw.cli.logging.info'), \
                 patch('cloudnetdraw.cli.os.path.exists', return_value=False), \
                 patch('os.getcwd', return_value=tmpdir):
                
                init_config_command(args)
                
                # Should use default "config.yaml"
                mock_copy.assert_called_once()
                call_args = mock_copy.call_args[0]
                assert call_args[1] == "config.yaml"
                assert "config.yaml" in call_args[0]  # Source path should contain config.yaml
    
    def test_init_config_command_file_exists_no_force(self):
        """Test init-config command when file exists without force flag"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output="config.yaml", force=False)
            
            with patch('cloudnetdraw.cli.os.path.exists', return_value=True), \
                 patch('cloudnetdraw.cli.logging.error') as mock_log_error, \
                 patch('cloudnetdraw.cli.sys.exit') as mock_exit, \
                 patch('os.getcwd', return_value=tmpdir):
                
                init_config_command(args)
                
                # Should log error and exit
                mock_log_error.assert_any_call("Configuration file 'config.yaml' already exists.")
                mock_log_error.assert_any_call("Use --force to overwrite existing file.")
                mock_exit.assert_called_once_with(1)
    
    def test_init_config_command_file_exists_with_force(self):
        """Test init-config command when file exists with force flag"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output="config.yaml", force=True)
            
            with patch('cloudnetdraw.cli.shutil.copy2') as mock_copy, \
                 patch('cloudnetdraw.cli.logging.info'), \
                 patch('cloudnetdraw.cli.os.path.exists', return_value=True), \
                 patch('os.getcwd', return_value=tmpdir):
                
                init_config_command(args)
                
                # Should proceed with copy despite file existing
                mock_copy.assert_called_once()
                call_args = mock_copy.call_args[0]
                assert call_args[1] == "config.yaml"
                assert "config.yaml" in call_args[0]  # Source path should contain config.yaml
    
    def test_init_config_command_copy_error(self):
        """Test init-config command when copy fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output="config.yaml", force=False)
            
            with patch('cloudnetdraw.cli.shutil.copy2', side_effect=PermissionError("Permission denied")), \
                 patch('cloudnetdraw.cli.logging.error') as mock_log_error, \
                 patch('cloudnetdraw.cli.sys.exit') as mock_exit, \
                 patch('cloudnetdraw.cli.os.path.exists', return_value=False), \
                 patch('os.getcwd', return_value=tmpdir):
                
                init_config_command(args)
                
                # Should log error and exit
                mock_log_error.assert_called_once_with("Failed to create configuration file: Permission denied")
                mock_exit.assert_called_once_with(1)
    
    def test_init_config_command_bundled_config_error(self):
        """Test init-config command when getting bundled config fails"""
        with tempfile.TemporaryDirectory() as tmpdir:
            args = Namespace(output="config.yaml", force=False)
            
            # Mock the _get_bundled_config_path method to raise an error
            with patch('cloudnetdraw.config.Config._get_bundled_config_path', side_effect=FileNotFoundError("Bundled config not found")), \
                 patch('cloudnetdraw.cli.logging.error') as mock_log_error, \
                 patch('cloudnetdraw.cli.sys.exit') as mock_exit, \
                 patch('cloudnetdraw.cli.os.path.exists', return_value=False), \
                 patch('os.getcwd', return_value=tmpdir):
                
                init_config_command(args)
                
                # Should log error and exit
                mock_log_error.assert_called_once_with("Failed to create configuration file: Bundled config not found")
                mock_exit.assert_called_once_with(1)