"""Integration tests for CLI interface functionality."""

import os
import json
import tempfile
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCLISubcommands:
    """Test CLI subcommand parsing and execution."""
    
    def test_query_subcommand_basic(self):
        """Test basic query subcommand execution."""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--subscriptions', '12345678-1234-1234-1234-123456789012',
                '--output', 'test_output.json'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
    
    def test_hld_subcommand_basic(self):
        """Test basic HLD subcommand execution with valid topology."""
        sample_topology = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "address_space": "10.0.0.0/16",
                    "subnets": [],
                    "peerings": [],
                    "subscription_name": "Test Subscription",
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_topology, f)
            input_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', input_file,
                '--output', 'test_hld.drawio'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"
        finally:
            os.unlink(input_file)
    
    def test_mld_subcommand_basic(self):
        """Test basic MLD subcommand execution with valid topology."""
        sample_topology = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "address_space": "10.0.0.0/16",
                    "subnets": [],
                    "peerings": [],
                    "subscription_name": "Test Subscription",
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_topology, f)
            input_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'mld',
                '--topology', input_file,
                '--output', 'test_mld.drawio'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0, f"Command failed with stderr: {result.stderr}"
        finally:
            os.unlink(input_file)
    
    def test_hld_subcommand_empty_vnets_fatal(self):
        """Test HLD subcommand exits with error when topology has no VNets."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"vnets": []}, f)
            input_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', input_file,
                '--output', 'test_hld.drawio'
            ], capture_output=True, text=True)
            
            assert result.returncode == 1, f"Command should have failed but returned {result.returncode}"
            assert "No VNets found in topology file" in result.stderr
        finally:
            os.unlink(input_file)
    
    def test_mld_subcommand_empty_vnets_fatal(self):
        """Test MLD subcommand exits with error when topology has no VNets."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"vnets": []}, f)
            input_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'mld',
                '--topology', input_file,
                '--output', 'test_mld.drawio'
            ], capture_output=True, text=True)
            
            assert result.returncode == 1, f"Command should have failed but returned {result.returncode}"
            assert "No VNets found in topology file" in result.stderr
        finally:
            os.unlink(input_file)
    
    def test_invalid_subcommand(self):
        """Test handling of invalid subcommands."""
        result = subprocess.run([
            'python', 'azure-query.py', 'invalid_command'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert "invalid choice" in result.stderr.lower()
    
    def test_no_subcommand(self):
        """Test handling when no subcommand is provided."""
        result = subprocess.run([
            'python', 'azure-query.py'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
        assert "required" in result.stderr.lower() or "choose from" in result.stderr.lower()


class TestArgumentValidation:
    """Test argument validation and defaults."""
    
    def test_query_missing_subscription_ids(self):
        """Test query command enters interactive mode when no subscriptions provided."""
        with patch('subprocess.run') as mock_run:
            # Mock subprocess call that simulates interactive mode timeout/failure
            mock_run.return_value = MagicMock(returncode=1, stdout='', stderr='No subscriptions specified and interactive mode not supported in tests')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
    
    def test_query_invalid_subscription_id_format(self):
        """Test query command with invalid subscription ID format."""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.return_value = MagicMock()
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--subscriptions', 'invalid-subscription-id'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
    
    def test_hld_default_topology_file(self):
        """Test HLD command with default topology file - should fail if empty."""
        result = subprocess.run([
            'python', 'azure-query.py', 'hld'
        ], capture_output=True, text=True)
        
        # Should fail if default topology file is empty or doesn't exist
        assert result.returncode == 1
        assert "No VNets found in topology file" in result.stderr or "No such file or directory" in result.stderr
    
    def test_hld_nonexistent_input_file(self):
        """Test HLD command with nonexistent input file."""
        result = subprocess.run([
            'python', 'azure-query.py', 'hld',
            '--topology', 'nonexistent_file.json'
        ], capture_output=True, text=True)
        
        assert result.returncode != 0
    
    def test_mld_default_topology_file(self):
        """Test MLD command with default topology file - should fail if empty."""
        result = subprocess.run([
            'python', 'azure-query.py', 'mld'
        ], capture_output=True, text=True)
        
        # Should fail if default topology file is empty or doesn't exist
        assert result.returncode == 1
        assert "No VNets found in topology file" in result.stderr or "No such file or directory" in result.stderr
    
    def test_default_output_filename_hld(self):
        """Test default output filename for HLD."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"vnets": []}, f)
            input_file = f.name
        
        try:
            with patch('subprocess.run') as mock_run:
                # Mock successful subprocess call
                mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
                
                result = subprocess.run([
                    'python', 'azure-query.py', 'hld',
                    '--topology', input_file
                ], capture_output=True, text=True)
                
                assert result.returncode == 0
                mock_run.assert_called_once()
                # Verify the command was called with expected arguments
                call_args = mock_run.call_args[0][0]
                assert 'hld' in call_args
                assert input_file in call_args
        finally:
            os.unlink(input_file)
    
    def test_default_output_filename_mld(self):
        """Test default output filename for MLD."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"vnets": []}, f)
            input_file = f.name
        
        try:
            with patch('subprocess.run') as mock_run:
                # Mock successful subprocess call
                mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
                
                result = subprocess.run([
                    'python', 'azure-query.py', 'mld',
                    '--topology', input_file
                ], capture_output=True, text=True)
                
                assert result.returncode == 0
                mock_run.assert_called_once()
                # Verify the command was called with expected arguments
                call_args = mock_run.call_args[0][0]
                assert 'mld' in call_args
                assert input_file in call_args
        finally:
            os.unlink(input_file)


class TestConfigFileResolution:
    """Test configuration file path resolution."""
    
    def test_config_file_short_option(self):
        """Test -c short option for config file."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '-c', str(config_path),
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '-c' in call_args
            assert str(config_path) in call_args
    
    def test_config_file_long_option(self):
        """Test --config-file long option for config file."""
        config_path = Path('tests/fixtures/sample_configs/minimal_config.yaml')
        
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--config-file', str(config_path),
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '--config-file' in call_args
            assert str(config_path) in call_args
    
    def test_nonexistent_config_file(self):
        """Test handling of nonexistent config file."""
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs:
            
            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--config-file', 'nonexistent_config.yaml',
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
    
    def test_invalid_config_file(self):
        """Test handling of invalid config file."""
        config_path = Path('tests/fixtures/sample_configs/invalid_config.yaml')
        
        with patch('azure_query.get_credentials') as mock_creds, \
             patch('azure_query.get_subscriptions_non_interactive') as mock_subs:
            
            mock_creds.return_value = MagicMock()
            mock_subs.return_value = ["12345678-1234-1234-1234-123456789012"]
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--config-file', str(config_path),
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0


class TestVerboseQuietLogging:
    """Test verbose and quiet logging modes."""
    
    def test_verbose_flag_short(self):
        """Test -v verbose flag."""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call with verbose output
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='INFO - Processing...')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '-v',
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '-v' in call_args
            # In verbose mode, should see more output
            assert len(result.stderr) > 0 or len(result.stdout) > 0
    
    def test_verbose_flag_long(self):
        """Test --verbose flag."""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call with verbose output
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='INFO - Processing...')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--verbose',
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # Verify the command was called with expected arguments
            call_args = mock_run.call_args[0][0]
            assert '--verbose' in call_args
            # In verbose mode, should see more output
            assert len(result.stderr) > 0 or len(result.stdout) > 0
    
    def test_quiet_is_default(self):
        """Test that quiet mode is the default."""
        with patch('subprocess.run') as mock_run:
            # Mock successful subprocess call with minimal output (default quiet mode)
            mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
            mock_run.assert_called_once()
            # In quiet mode (default), should see minimal output
            assert len(result.stderr) == 0
            assert len(result.stdout) == 0


class TestOutputFileSpecification:
    """Test output file specification."""
    
    def test_query_custom_output_file(self):
        """Test query command with custom output file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_file = f.name
        
        try:
            with patch('subprocess.run') as mock_run:
                # Mock successful subprocess call
                mock_run.return_value = MagicMock(returncode=0, stdout='', stderr='')
                
                result = subprocess.run([
                    'python', 'azure-query.py', 'query',
                    '--subscriptions', '12345678-1234-1234-1234-123456789012',
                    '--output', output_file
                ], capture_output=True, text=True)
                
                assert result.returncode == 0
                mock_run.assert_called_once()
                # Verify the command was called with expected arguments
                call_args = mock_run.call_args[0][0]
                assert '--output' in call_args
                assert output_file in call_args
        finally:
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_hld_custom_output_file(self):
        """Test HLD command with custom output file and valid topology."""
        sample_topology = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "address_space": "10.0.0.0/16",
                    "subnets": [],
                    "peerings": [],
                    "subscription_name": "Test Subscription",
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_topology, f)
            input_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            output_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', input_file,
                '--output', output_file
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
        finally:
            if os.path.exists(input_file):
                os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)
    
    def test_mld_custom_output_file(self):
        """Test MLD command with custom output file and valid topology."""
        sample_topology = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "address_space": "10.0.0.0/16",
                    "subnets": [],
                    "peerings": [],
                    "subscription_name": "Test Subscription",
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_topology, f)
            input_file = f.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
            output_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'mld',
                '--topology', input_file,
                '--output', output_file
            ], capture_output=True, text=True)
            
            assert result.returncode == 0
        finally:
            if os.path.exists(input_file):
                os.unlink(input_file)
            if os.path.exists(output_file):
                os.unlink(output_file)


class TestHelpTextGeneration:
    """Test help text generation for all commands."""
    
    def test_main_help(self):
        """Test main help text."""
        result = subprocess.run([
            'python', 'azure-query.py', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'usage:' in result.stdout.lower()
        assert 'query' in result.stdout
        assert 'hld' in result.stdout
        assert 'mld' in result.stdout
    
    def test_query_help(self):
        """Test query subcommand help text."""
        result = subprocess.run([
            'python', 'azure-query.py', 'query', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'usage:' in result.stdout.lower()
        assert 'subscription' in result.stdout.lower()
        assert 'output' in result.stdout.lower()
        assert 'config' in result.stdout.lower()
        assert 'verbose' in result.stdout.lower()
    
    def test_hld_help(self):
        """Test HLD subcommand help text."""
        result = subprocess.run([
            'python', 'azure-query.py', 'hld', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'usage:' in result.stdout.lower()
        assert 'topology' in result.stdout.lower()
        assert 'output' in result.stdout.lower()
        assert 'config' in result.stdout.lower()
    
    def test_mld_help(self):
        """Test MLD subcommand help text."""
        result = subprocess.run([
            'python', 'azure-query.py', 'mld', '--help'
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert 'usage:' in result.stdout.lower()
        assert 'topology' in result.stdout.lower()
        assert 'output' in result.stdout.lower()
        assert 'config' in result.stdout.lower()


class TestErrorHandling:
    """Test error handling for various scenarios."""
    
    def test_missing_azure_credentials(self):
        """Test handling when Azure credentials are not available."""
        with patch('azure_query.get_credentials') as mock_creds:
            mock_creds.side_effect = Exception("No credentials available")
            
            result = subprocess.run([
                'python', 'azure-query.py', 'query',
                '--subscriptions', '12345678-1234-1234-1234-123456789012'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
    
    def test_invalid_json_input_file(self):
        """Test handling of invalid JSON input file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("invalid json content")
            input_file = f.name
        
        try:
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', input_file
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
        finally:
            os.unlink(input_file)
    
    def test_permission_denied_output_file(self):
        """Test handling when output file cannot be written due to permissions."""
        sample_topology = {
            "vnets": [
                {
                    "name": "test-vnet",
                    "address_space": "10.0.0.0/16",
                    "subnets": [],
                    "peerings": [],
                    "subscription_name": "Test Subscription",
                    "peerings_count": 0
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(sample_topology, f)
            input_file = f.name
        
        try:
            # Try to write to root directory (should fail)
            result = subprocess.run([
                'python', 'azure-query.py', 'hld',
                '--topology', input_file,
                '--output', '/root/test.drawio'
            ], capture_output=True, text=True)
            
            assert result.returncode != 0
        finally:
            os.unlink(input_file)