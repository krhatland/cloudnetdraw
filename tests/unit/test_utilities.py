"""
Unit tests for utility functions
"""
import pytest
import re
import os
import tempfile
import json
from unittest.mock import patch, mock_open, Mock
from pathlib import Path

# Import functions under test
from azure_query import (
    is_subscription_id,
    extract_resource_group,
    read_subscriptions_from_file,
    resolve_subscription_names_to_ids,
    save_to_json,
    extract_vnet_name_from_resource_id,
    get_sp_credentials,
    get_credentials
)


class TestSubscriptionIdValidation:
    """Test subscription ID validation"""

    @pytest.mark.parametrize("subscription_id,expected", [
        ("550e8400-e29b-41d4-a716-446655440000", True),  # Valid UUID
        ("12345678-1234-1234-1234-123456789012", True),  # Valid UUID
        ("abcdef00-1234-5678-9abc-def012345678", True),  # Valid UUID with letters
        ("subscription-name", False),  # Name format
        ("not-a-uuid", False),  # Invalid format
        ("12345678-1234-1234-1234-12345678901", False),  # Too short
        ("12345678-1234-1234-1234-1234567890123", False),  # Too long
        ("12345678-1234-1234-1234-12345678901g", False),  # Invalid character
        ("", False),  # Empty string
        ("12345678-1234-1234-1234", False),  # Missing segment
        ("12345678-1234-1234-1234-123456789012-extra", False),  # Extra segment
    ])
    def test_is_subscription_id(self, subscription_id, expected):
        """Test subscription ID validation with various formats"""
        assert is_subscription_id(subscription_id) == expected

    def test_is_subscription_id_regex_pattern(self):
        """Test that the regex pattern matches Azure subscription ID format"""
        # Azure subscription ID pattern: 8-4-4-4-12 hexadecimal digits
        valid_id = "550e8400-e29b-41d4-a716-446655440000"
        pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
        assert re.match(pattern, valid_id) is not None
        assert is_subscription_id(valid_id) is True


class TestResourceGroupExtraction:
    """Test resource group extraction from resource IDs"""

    def test_extract_resource_group_vnet(self):
        """Test extracting resource group from VNet resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/my-vnet"
        result = extract_resource_group(resource_id)
        assert result == "my-rg"

    def test_extract_resource_group_hub(self):
        """Test extracting resource group from virtual hub resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualHubs/my-hub"
        result = extract_resource_group(resource_id)
        assert result == "hub-rg"

    def test_extract_resource_group_complex_name(self):
        """Test extracting resource group with complex name"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-complex-rg-name-123/providers/Microsoft.Network/virtualNetworks/test-vnet"
        result = extract_resource_group(resource_id)
        assert result == "my-complex-rg-name-123"

    def test_extract_resource_group_different_provider(self):
        """Test extracting resource group from different provider resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/storage-rg/providers/Microsoft.Storage/storageAccounts/myaccount"
        result = extract_resource_group(resource_id)
        assert result == "storage-rg"

    def test_extract_resource_group_index_error(self):
        """Test handling of malformed resource ID"""
        malformed_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups"
        with pytest.raises(IndexError):
            extract_resource_group(malformed_id)


class TestSubscriptionFileReading:
    """Test subscription list file reading"""

    def test_read_subscriptions_from_file_valid(self, temp_directory):
        """Test reading valid subscriptions file"""
        subscriptions_content = "subscription-1\nsubscription-2\nsubscription-3\n"
        subscriptions_file = Path(temp_directory) / "subscriptions.txt"
        subscriptions_file.write_text(subscriptions_content)
        
        result = read_subscriptions_from_file(str(subscriptions_file))
        assert result == ["subscription-1", "subscription-2", "subscription-3"]

    def test_read_subscriptions_from_file_with_empty_lines(self, temp_directory):
        """Test reading subscriptions file with empty lines"""
        subscriptions_content = "subscription-1\n\nsubscription-2\n\n\nsubscription-3\n\n"
        subscriptions_file = Path(temp_directory) / "subscriptions.txt"
        subscriptions_file.write_text(subscriptions_content)
        
        result = read_subscriptions_from_file(str(subscriptions_file))
        assert result == ["subscription-1", "subscription-2", "subscription-3"]

    def test_read_subscriptions_from_file_with_whitespace(self, temp_directory):
        """Test reading subscriptions file with whitespace"""
        subscriptions_content = "  subscription-1  \n\t subscription-2 \t\n subscription-3\n"
        subscriptions_file = Path(temp_directory) / "subscriptions.txt"
        subscriptions_file.write_text(subscriptions_content)
        
        result = read_subscriptions_from_file(str(subscriptions_file))
        assert result == ["subscription-1", "subscription-2", "subscription-3"]

    def test_read_subscriptions_from_file_not_found(self):
        """Test handling of missing subscriptions file"""
        with pytest.raises(SystemExit):
            read_subscriptions_from_file("nonexistent.txt")

    def test_read_subscriptions_from_file_permission_error(self):
        """Test handling of permission error when reading file"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(SystemExit):
                read_subscriptions_from_file("subscriptions.txt")

    def test_read_subscriptions_from_file_empty_file(self, temp_directory):
        """Test reading empty subscriptions file"""
        subscriptions_file = Path(temp_directory) / "empty.txt"
        subscriptions_file.write_text("")
        
        result = read_subscriptions_from_file(str(subscriptions_file))
        assert result == []


class TestSubscriptionNameResolution:
    """Test subscription name to ID resolution"""

    def test_resolve_subscription_names_to_ids_success(self, mock_azure_credentials):
        """Test successful subscription name resolution"""
        from azure_query import initialize_credentials, resolve_subscription_names_to_ids
        
        # Initialize credentials
        initialize_credentials()
        
        mock_subscription_client = Mock()
        mock_subscriptions = [
            Mock(display_name="Test Subscription 1", subscription_id="sub-1"),
            Mock(display_name="Test Subscription 2", subscription_id="sub-2"),
            Mock(display_name="Test Subscription 3", subscription_id="sub-3")
        ]
        mock_subscription_client.subscriptions.list.return_value = mock_subscriptions
        
        with patch('azure_query.SubscriptionClient', return_value=mock_subscription_client):
            result = resolve_subscription_names_to_ids(
                ["Test Subscription 1", "Test Subscription 3"]
            )
            assert result == ["sub-1", "sub-3"]

    def test_resolve_subscription_names_to_ids_not_found(self, mock_azure_credentials):
        """Test handling of subscription name not found"""
        from azure_query import initialize_credentials, resolve_subscription_names_to_ids
        
        # Initialize credentials
        initialize_credentials()
        
        mock_subscription_client = Mock()
        mock_subscriptions = [
            Mock(display_name="Test Subscription 1", subscription_id="sub-1"),
            Mock(display_name="Test Subscription 2", subscription_id="sub-2")
        ]
        mock_subscription_client.subscriptions.list.return_value = mock_subscriptions
        
        with patch('azure_query.SubscriptionClient', return_value=mock_subscription_client):
            with pytest.raises(SystemExit):
                resolve_subscription_names_to_ids(
                    ["Test Subscription 1", "Nonexistent Subscription"]
                )

    def test_resolve_subscription_names_to_ids_empty_list(self, mock_azure_credentials):
        """Test resolution with empty subscription list"""
        from azure_query import initialize_credentials, resolve_subscription_names_to_ids
        
        # Initialize credentials
        initialize_credentials()
        
        mock_subscription_client = Mock()
        mock_subscription_client.subscriptions.list.return_value = []
        
        with patch('azure_query.SubscriptionClient', return_value=mock_subscription_client):
            result = resolve_subscription_names_to_ids([])
            assert result == []


class TestJsonSaving:
    """Test JSON file saving functionality"""

    def test_save_to_json_default_filename(self, temp_directory, sample_topology):
        """Test saving JSON with default filename"""
        with patch('builtins.open', mock_open()) as mock_file:
            save_to_json(sample_topology)
            mock_file.assert_called_once_with("network_topology.json", "w")

    def test_save_to_json_custom_filename(self, temp_directory, sample_topology):
        """Test saving JSON with custom filename"""
        with patch('builtins.open', mock_open()) as mock_file:
            save_to_json(sample_topology, "custom_topology.json")
            mock_file.assert_called_once_with("custom_topology.json", "w")

    def test_save_to_json_data_structure(self, temp_directory, sample_topology):
        """Test that JSON data is properly structured"""
        output_file = Path(temp_directory) / "test_topology.json"
        save_to_json(sample_topology, str(output_file))
        
        # Read back the saved file
        with open(output_file, 'r') as f:
            saved_data = json.load(f)
        
        assert 'vnets' in saved_data
        assert len(saved_data['vnets']) == len(sample_topology['vnets'])
        assert saved_data['vnets'][0]['name'] == sample_topology['vnets'][0]['name']

    def test_save_to_json_pretty_formatting(self, temp_directory, sample_topology):
        """Test that JSON is saved with pretty formatting"""
        output_file = Path(temp_directory) / "test_topology.json"
        save_to_json(sample_topology, str(output_file))
        
        # Read the raw file content
        with open(output_file, 'r') as f:
            content = f.read()
        
        # Check for indentation (pretty printing)
        assert '    ' in content  # Should have 4-space indentation
        assert '\n' in content    # Should have newlines


class TestVnetNameExtractionFromResourceId:
    """Test VNet name extraction from resource ID functionality"""

    def test_extract_vnet_name_from_resource_id_valid(self):
        """Test extracting VNet name from valid resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001"
        result = extract_vnet_name_from_resource_id(resource_id)
        assert result == "hub-vnet-001"

    def test_extract_vnet_name_complex_names(self):
        """Test extracting complex VNet names"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/my-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet-prod-central"
        result = extract_vnet_name_from_resource_id(resource_id)
        assert result == "hub-vnet-prod-central"

    def test_extract_vnet_name_with_numbers(self):
        """Test extracting VNet names with numbers"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/vnet1-prod-001"
        result = extract_vnet_name_from_resource_id(resource_id)
        assert result == "vnet1-prod-001"

    def test_extract_vnet_name_with_underscores(self):
        """Test extracting VNet names with underscores"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/my_vnet_name"
        result = extract_vnet_name_from_resource_id(resource_id)
        assert result == "my_vnet_name"

    def test_extract_vnet_name_invalid_format(self):
        """Test handling of invalid resource ID format"""
        with pytest.raises(ValueError, match="Invalid VNet resource ID"):
            extract_vnet_name_from_resource_id("/invalid/resource/id")

    def test_extract_vnet_name_wrong_provider(self):
        """Test handling of wrong provider in resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm-001"
        with pytest.raises(ValueError, match="Invalid VNet resource ID"):
            extract_vnet_name_from_resource_id(resource_id)

    def test_extract_vnet_name_incomplete_resource_id(self):
        """Test handling of incomplete resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1"
        with pytest.raises(ValueError, match="Invalid VNet resource ID"):
            extract_vnet_name_from_resource_id(resource_id)


class TestCredentialHandling:
    """Test credential acquisition functions"""

    def test_get_sp_credentials_success(self, mock_azure_env):
        """Test successful service principal credential acquisition"""
        with patch('azure_query.ClientSecretCredential') as mock_cred:
            mock_instance = Mock()
            mock_cred.return_value = mock_instance
            
            result = get_sp_credentials()
            
            mock_cred.assert_called_once_with(
                'test-tenant-id',
                'test-client-id', 
                'test-client-secret'
            )
            assert result == mock_instance

    def test_get_sp_credentials_missing_client_id(self):
        """Test service principal credentials with missing client ID"""
        env_vars = {
            'AZURE_CLIENT_SECRET': 'test-secret',
            'AZURE_TENANT_ID': 'test-tenant-id'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(SystemExit):
                get_sp_credentials()

    def test_get_sp_credentials_missing_client_secret(self):
        """Test service principal credentials with missing client secret"""
        env_vars = {
            'AZURE_CLIENT_ID': 'test-client-id',
            'AZURE_TENANT_ID': 'test-tenant-id'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(SystemExit):
                get_sp_credentials()

    def test_get_sp_credentials_missing_tenant_id(self):
        """Test service principal credentials with missing tenant ID"""
        env_vars = {
            'AZURE_CLIENT_ID': 'test-client-id',
            'AZURE_CLIENT_SECRET': 'test-secret'
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(SystemExit):
                get_sp_credentials()

    def test_initialize_credentials_service_principal(self, mock_azure_env):
        """Test global credential initialization using service principal"""
        from azure_query import initialize_credentials, get_credentials
        with patch('azure_query.get_sp_credentials') as mock_sp_creds:
            mock_instance = Mock()
            mock_sp_creds.return_value = mock_instance
            
            initialize_credentials(use_service_principal=True)
            result = get_credentials()
            
            mock_sp_creds.assert_called_once()
            assert result == mock_instance

    def test_initialize_credentials_azure_cli(self):
        """Test global credential initialization using Azure CLI"""
        from azure_query import initialize_credentials, get_credentials
        with patch('azure_query.AzureCliCredential') as mock_cli_creds:
            mock_instance = Mock()
            mock_cli_creds.return_value = mock_instance
            
            initialize_credentials(use_service_principal=False)
            result = get_credentials()
            
            mock_cli_creds.assert_called_once()
            assert result == mock_instance

    def test_initialize_credentials_default_to_cli(self):
        """Test global credential initialization defaults to Azure CLI"""
        from azure_query import initialize_credentials, get_credentials
        with patch('azure_query.AzureCliCredential') as mock_cli_creds:
            mock_instance = Mock()
            mock_cli_creds.return_value = mock_instance
            
            initialize_credentials()
            result = get_credentials()
            
            mock_cli_creds.assert_called_once()
            assert result == mock_instance

    def test_get_credentials_not_initialized(self):
        """Test getting credentials when not initialized"""
        from azure_query import _credentials
        import azure_query
        
        # Clear global credentials
        azure_query._credentials = None
        
        with pytest.raises(RuntimeError, match="Credentials not initialized"):
            get_credentials()