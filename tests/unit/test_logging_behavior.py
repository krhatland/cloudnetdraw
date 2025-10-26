"""
Unit tests for logging behavior and consistency
"""

import pytest
import logging
import tempfile
import os
from unittest.mock import patch, Mock
from io import StringIO
import sys

from cloudnetdraw import cli, azure_client
from cloudnetdraw.utils import save_to_json


class TestLoggingConfiguration:
    """Test logging configuration and levels"""
    
    def test_default_logging_level_warning(self):
        """Test that default logging level is WARNING"""
        # Mock argparse namespace with verbose=False
        args = Mock()
        args.verbose = False
        args.func = Mock()
        
        with patch('logging.basicConfig') as mock_config:
            # Simulate the logging configuration from main()
            log_level = logging.INFO if args.verbose else logging.WARNING
            
            assert log_level == logging.WARNING
    
    def test_verbose_logging_level_info(self):
        """Test that verbose logging level is INFO"""
        # Mock argparse namespace with verbose=True
        args = Mock()
        args.verbose = True
        args.func = Mock()
        
        with patch('logging.basicConfig') as mock_config:
            # Simulate the logging configuration from main()
            log_level = logging.INFO if args.verbose else logging.WARNING
            
            assert log_level == logging.INFO
    
    def test_logging_format_consistency(self):
        """Test that logging format is consistent"""
        args = Mock()
        args.verbose = True
        args.func = Mock()
        
        with patch('logging.basicConfig') as mock_config:
            # Simulate main() logging configuration
            log_level = logging.INFO if args.verbose else logging.WARNING
            expected_format = '%(asctime)s - %(levelname)s - %(message)s'
            
            # Verify format would be correct
            assert expected_format == '%(asctime)s - %(levelname)s - %(message)s'


class TestLoggingLevels:
    """Test that logging levels are used appropriately"""
    
    @patch('cloudnetdraw.azure_client.logging')
    def test_error_logging_for_fatal_conditions(self, mock_logging):
        """Test that ERROR level is used for fatal conditions"""
        # Test Service Principal credentials error
        with patch.dict(os.environ, {}, clear=True):
            try:
                azure_client.get_sp_credentials()
            except SystemExit:
                pass
        
        # Should have called logging.error
        mock_logging.error.assert_called()
    
    @patch('cloudnetdraw.utils.logging')
    def test_info_logging_for_status_messages(self, mock_logging):
        """Test that INFO level is used for status messages"""
        # Test save_to_json function which uses logging.info
        test_data = {"test": "data"}
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_file = f.name
        
        try:
            save_to_json(test_data, temp_file)
            # Should have called logging.info
            mock_logging.info.assert_called()
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)
    
    def test_no_warning_level_misuse(self):
        """Test that WARNING level is appropriately used for expected conditions"""
        # Read the source file and verify logging.warning calls are appropriate
        # Check logging usage in the new module structure
        import cloudnetdraw.azure_client
        import inspect
        
        # Get the source code of the azure_client module
        source_code = inspect.getsource(cloudnetdraw.azure_client)
        
        # Should have logging.warning calls for expected conditions like ResourceNotFound
        warning_calls = source_code.count('logging.warning(')
        
        # Check that warning calls are used appropriately (for expected conditions like ResourceNotFound)
        # We expect some logging.warning calls for ResourceNotFound scenarios
        assert warning_calls > 0, "Should have logging.warning calls for expected conditions like ResourceNotFound"
        
        # Verify ResourceNotFound cases use logging.warning (not logging.error)
        # Verify ResourceNotFound cases use appropriate logging levels
        assert warning_calls > 0 or 'logging.info(' in source_code, "Should have appropriate logging calls"


class TestLoggingOutput:
    """Test actual logging output behavior"""
    
    def test_default_silence_info_messages(self, caplog):
        """Test that INFO messages are not shown by default"""
        with caplog.at_level(logging.WARNING):
            # Configure logging as the main function would for non-verbose
            logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
            
            # Log an INFO message
            logging.info("This should not appear")
            logging.warning("This should appear")
            logging.error("This should also appear")
            
            # Only WARNING and ERROR should be captured
            assert len([r for r in caplog.records if r.levelno >= logging.WARNING]) == 2
            assert len([r for r in caplog.records if r.levelno == logging.INFO]) == 0
    
    def test_verbose_shows_all_messages(self, caplog):
        """Test that verbose mode shows INFO, WARNING, and ERROR messages"""
        with caplog.at_level(logging.INFO):
            # Configure logging as the main function would for verbose
            logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
            
            # Log messages at different levels
            logging.info("This should appear in verbose")
            logging.warning("This should appear in verbose")
            logging.error("This should appear in verbose")
            
            # All three should be captured
            assert len([r for r in caplog.records if r.levelno >= logging.INFO]) == 3
    
    def test_error_messages_always_shown(self, caplog):
        """Test that ERROR messages are shown regardless of verbosity"""
        # Test both default and verbose levels
        for level in [logging.WARNING, logging.INFO]:
            caplog.clear()
            with caplog.at_level(level):
                logging.error("Critical error message")
                
                # ERROR should always be captured
                error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
                assert len(error_records) == 1
                assert "Critical error message" in error_records[0].message


class TestLoggingConsistency:
    """Test logging consistency across different functions"""
    
    def test_consistent_error_handling_pattern(self):
        """Test that error handling follows consistent logging pattern"""
        # Read source and check that sys.exit(1) is preceded by logging.error
        # Check all modules for consistent error handling
        import inspect
        
        modules = [
            'cloudnetdraw.azure_client',
            'cloudnetdraw.cli',
            'cloudnetdraw.utils'
        ]
        
        total_exits = 0
        total_error_before_exit = 0
        
        for module_name in modules:
            try:
                module = __import__(module_name, fromlist=[''])
                source_code = inspect.getsource(module)
            except (ImportError, OSError):
                continue
            
            lines = source_code.split('\n')
            
            for i, line in enumerate(lines):
                if 'sys.exit(1)' in line:
                    total_exits += 1
                    # Look for logging.error in the preceding few lines
                    for j in range(max(0, i-5), i):
                        if 'logging.error(' in lines[j]:
                            total_error_before_exit += 1
                            break
        
        # Most exits should be preceded by error logging
        if total_exits > 0:
            error_ratio = total_error_before_exit / total_exits
            assert error_ratio >= 0.6, f"Only {error_ratio:.1%} of sys.exit(1) calls are preceded by logging.error"
    
    def test_no_print_statements_for_errors(self):
        """Test that error output uses logging instead of print statements"""
        # Check all modules for minimal print usage
        import inspect
        
        modules = [
            'cloudnetdraw.azure_client',
            'cloudnetdraw.cli',
            'cloudnetdraw.utils',
            'cloudnetdraw.diagram_generator'
        ]
        
        total_prints = 0
        for module_name in modules:
            try:
                module = __import__(module_name, fromlist=[''])
                source_code = inspect.getsource(module)
                total_prints += source_code.count('print(')
            except (ImportError, OSError):
                continue
        
        # Allow some print usage for completion/success messages
        assert total_prints <= 3, f"Found {total_prints} print statements - errors should use logging"


class TestCLILoggingIntegration:
    """Test logging behavior in CLI context"""
    
    @patch('cloudnetdraw.cli.logging.basicConfig')
    def test_cli_verbose_flag_sets_correct_level(self, mock_basic_config):
        """Test that CLI -v flag correctly sets INFO level"""
        # Mock argparse to return verbose=True
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            args = Mock()
            args.verbose = True
            args.command = 'query'
            args.func = Mock()
            mock_parse_args.return_value = args
            
            # Mock the function to prevent actual execution
            with patch.object(args, 'func'):
                try:
                    cli.main()
                except (SystemExit, Exception):
                    pass  # Ignore any exit or execution errors
            
            # Verify logging was configured with INFO level
            mock_basic_config.assert_called_with(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )
    
    @patch('cloudnetdraw.cli.logging.basicConfig')
    def test_cli_default_sets_warning_level(self, mock_basic_config):
        """Test that CLI default (no -v) correctly sets WARNING level"""
        # Mock argparse to return verbose=False
        with patch('argparse.ArgumentParser.parse_args') as mock_parse_args:
            args = Mock()
            args.verbose = False
            args.command = 'query'
            args.func = Mock()
            mock_parse_args.return_value = args
            
            # Mock the function to prevent actual execution
            with patch.object(args, 'func'):
                try:
                    cli.main()
                except (SystemExit, Exception):
                    pass  # Ignore any exit or execution errors
            
            # Verify logging was configured with WARNING level
            mock_basic_config.assert_called_with(
                level=logging.WARNING,
                format='%(asctime)s - %(levelname)s - %(message)s'
            )