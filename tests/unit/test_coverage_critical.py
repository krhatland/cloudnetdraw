"""
Critical coverage tests to reach 80% threshold
These tests target specific uncovered lines in azure-query.py
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from azure.core.exceptions import ResourceNotFoundError

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import cloudnetdraw.azure_client as azure_query

class TestCredentialErrorHandling:
    """Test error handling in credential functions"""

    def test_get_sp_credentials_missing_env_vars(self):
        """Test get_sp_credentials when environment variables are missing - covers lines 25-26"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                azure_query.get_sp_credentials()
            assert exc_info.value.code == 1

    def test_get_credentials_not_initialized(self):
        """Test get_credentials when credentials not initialized - covers lines 41-42"""
        # Reset global credentials
        azure_query._credentials = None
        with pytest.raises(RuntimeError) as exc_info:
            azure_query.get_credentials()
        assert "Credentials not initialized" in str(exc_info.value)

class TestSubscriptionHandling:
    """Test subscription-related functions for error cases"""

    def test_read_subscriptions_from_file_not_found(self):
        """Test read_subscriptions_from_file with non-existent file - covers lines 58-59"""
        with pytest.raises(SystemExit) as exc_info:
            azure_query.read_subscriptions_from_file("nonexistent_file.txt")
        assert exc_info.value.code == 1

    def test_read_subscriptions_from_file_general_error(self):
        """Test read_subscriptions_from_file with general error - covers lines 61-62"""
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(SystemExit) as exc_info:
                azure_query.read_subscriptions_from_file("test_file.txt")
            assert exc_info.value.code == 1

    @patch('cloudnetdraw.azure_client.get_credentials')
    def test_resolve_subscription_names_to_ids_not_found(self, mock_get_credentials):
        """Test resolve_subscription_names_to_ids when subscription not found - covers lines 77-79"""
        # Mock credentials
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock subscription client
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = "existing-subscription"
        mock_subscription.subscription_id = "existing-id"
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]
        
        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client):
            with pytest.raises(SystemExit) as exc_info:
                azure_query.resolve_subscription_names_to_ids(["non-existent-subscription"])
            assert exc_info.value.code == 1

    @patch('cloudnetdraw.azure_client.get_credentials')
    def test_get_all_subscription_ids_logging(self, mock_get_credentials):
        """Test get_all_subscription_ids logging - covers lines 88-89"""
        # Mock credentials
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock subscription client
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.subscription_id = "test-subscription-id"
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]
        
        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client):
            with patch('cloudnetdraw.azure_client.logging') as mock_logging:
                result = azure_query.get_all_subscription_ids()
                assert result == ["test-subscription-id"]
                mock_logging.info.assert_called_with("Found 1 subscriptions")

class TestVnetIdentifierParsing:
    """Test VNet identifier parsing edge cases"""

    def test_parse_vnet_identifier_invalid_resource_id(self):
        """Test parse_vnet_identifier with invalid resource ID format - covers line 106"""
        invalid_resource_id = "/invalid/resource/id/format"
        with pytest.raises(ValueError) as exc_info:
            from cloudnetdraw.utils import parse_vnet_identifier
            parse_vnet_identifier(invalid_resource_id)
        assert "Invalid VNet resource ID format" in str(exc_info.value)

    def test_parse_vnet_identifier_invalid_format(self):
        """Test parse_vnet_identifier with invalid format - covers line 121"""
        invalid_identifier = "too/many/parts/in/identifier"
        with pytest.raises(ValueError) as exc_info:
            from cloudnetdraw.utils import parse_vnet_identifier
            parse_vnet_identifier(invalid_identifier)
        assert "Invalid VNet identifier format" in str(exc_info.value)

class TestResourceGraphErrorHandling:
    """Test error handling in resource graph functions"""

    @patch('cloudnetdraw.azure_client.get_credentials')
    def test_find_hub_vnet_no_resource_group(self, mock_get_credentials):
        """Test find_hub_vnet_using_resource_graph with missing resource group - covers lines 132-133"""
        with pytest.raises(SystemExit) as exc_info:
            azure_query.find_hub_vnet_using_resource_graph("simple-vnet-name")
        assert exc_info.value.code == 1

    @patch('cloudnetdraw.azure_client.get_credentials')
    @patch('cloudnetdraw.azure_client.ResourceGraphClient')
    @patch('cloudnetdraw.azure_client.SubscriptionClient')
    def test_find_hub_vnet_no_results(self, mock_subscription_client_cls, mock_resource_graph_client_cls, mock_get_credentials):
        """Test find_hub_vnet_using_resource_graph with no results - covers lines 184-191"""
        # Mock credentials
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock resource graph client - no results
        mock_resource_graph_client = Mock()
        mock_response = Mock()
        mock_response.data = []
        mock_resource_graph_client.resources.return_value = mock_response
        mock_resource_graph_client_cls.return_value = mock_resource_graph_client
        
        # Mock debug response - also no results
        mock_debug_response = Mock()
        mock_debug_response.data = []
        
        # Configure the mock to return different responses for different calls
        mock_resource_graph_client.resources.side_effect = [mock_response, mock_debug_response]
        
        with pytest.raises(SystemExit) as exc_info:
            azure_query.find_hub_vnet_using_resource_graph("rg-test/vnet-test")
        assert exc_info.value.code == 1

    @patch('cloudnetdraw.azure_client.get_credentials')
    @patch('cloudnetdraw.azure_client.ResourceGraphClient')
    @patch('cloudnetdraw.azure_client.SubscriptionClient')
    def test_find_hub_vnet_multiple_results(self, mock_subscription_client_cls, mock_resource_graph_client_cls, mock_get_credentials):
        """Test find_hub_vnet_using_resource_graph with multiple results - covers lines 194-196"""
        # Mock credentials
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock resource graph client - multiple results
        mock_resource_graph_client = Mock()
        mock_response = Mock()
        mock_response.data = [
            {'resourceGroup': 'rg1', 'name': 'vnet1', 'subscriptionId': 'sub1'},
            {'resourceGroup': 'rg2', 'name': 'vnet1', 'subscriptionId': 'sub2'}
        ]
        # Need to mock both calls to resources (main query and debug query)
        mock_debug_response = Mock()
        mock_debug_response.data = []
        mock_resource_graph_client.resources.side_effect = [mock_response, mock_debug_response]
        mock_resource_graph_client_cls.return_value = mock_resource_graph_client
        
        # Mock subscription client - needs to properly mock subscriptions.list()
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.subscription_id = "test-sub-id"
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]
        mock_subscription_client_cls.return_value = mock_subscription_client
        
        with pytest.raises(SystemExit) as exc_info:
            azure_query.find_hub_vnet_using_resource_graph("rg-test/vnet-test")
        assert exc_info.value.code == 1

class TestQueryCommandValidation:
    """Test query command argument validation"""

    def test_query_command_mutually_exclusive_args(self):
        """Test query command with mutually exclusive arguments - covers lines 594-598"""
        # Mock argparse namespace with conflicting arguments
        mock_args = Mock()
        mock_args.service_principal = False
        mock_args.subscriptions = "subscription1,subscription2"
        mock_args.subscriptions_file = "subscriptions.txt"
        mock_args.vnets = None
        
        with pytest.raises(SystemExit) as exc_info:
            from cloudnetdraw.cli import query_command
            query_command(mock_args)
        assert exc_info.value.code == 1

    @patch('cloudnetdraw.utils.parse_vnet_identifier')
    def test_query_command_vnet_legacy_format_no_subscriptions(self, mock_parse_vnet_identifier):
        """Test query command with VNet in legacy format but no subscriptions - covers lines 619-624"""
        # Mock parse_vnet_identifier to return legacy format (no subscription_id)
        mock_parse_vnet_identifier.return_value = (None, "rg-test", "vnet-test")
        
        mock_args = Mock()
        mock_args.service_principal = False
        mock_args.subscriptions = None
        mock_args.subscriptions_file = None
        mock_args.vnets = "rg-test/vnet-test"
        
        with pytest.raises(SystemExit) as exc_info:
            from cloudnetdraw.cli import query_command
            query_command(mock_args)
        assert exc_info.value.code == 1

class TestHierarchicalIdGeneration:
    """Test hierarchical ID generation fallback logic"""

    def test_generate_hierarchical_id_fallback_missing_metadata(self):
        """Test generate_hierarchical_id fallback when metadata is missing - covers lines 729-750"""
        # VNet data with missing Azure metadata
        vnet_data = {
            'name': 'test-vnet',
            # Missing subscription_name and resourcegroup_name
        }
        
        # Test various element types for fallback logic
        from cloudnetdraw.diagram_generator import generate_hierarchical_id
        result = generate_hierarchical_id(vnet_data, 'group')
        assert result == 'test-vnet'
        
        result = generate_hierarchical_id(vnet_data, 'main')
        assert result == 'test-vnet_main'
        
        result = generate_hierarchical_id(vnet_data, 'subnet', '0')
        assert result == 'test-vnet_subnet_0'
        
        result = generate_hierarchical_id(vnet_data, 'icon', 'vpn')
        assert result == 'test-vnet_icon_vpn'
        
        # Test unknown element type
        result = generate_hierarchical_id(vnet_data, 'unknown_type', 'suffix')
        assert result == 'test-vnet_unknown_type_suffix'

class TestVnetIdMappingFallback:
    """Test VNet ID mapping fallback logic"""

    def test_create_vnet_id_mapping_no_azure_metadata(self):
        """Test create_vnet_id_mapping fallback when no Azure metadata - covers lines 814-854"""
        # Mock zones without Azure metadata
        zones = [{
            'hub': {'name': 'hub-vnet', 'resource_id': 'hub-resource-id'},
            'hub_index': 0,
            'spokes': [
                {'name': 'spoke1', 'resource_id': 'spoke1-resource-id'},
                {'name': 'spoke2', 'resource_id': 'spoke2-resource-id'}
            ]
        }]
        
        all_non_peered = [
            {'name': 'nonpeered1', 'resource_id': 'nonpeered1-resource-id'}
        ]
        
        vnets = []  # Empty VNets list for this test
        
        from cloudnetdraw.topology import create_vnet_id_mapping
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should use fallback synthetic IDs
        assert 'hub-resource-id' in result
        assert result['hub-resource-id'] == 'hub_0'
        assert 'spoke1-resource-id' in result
        assert 'spoke2-resource-id' in result
        assert 'nonpeered1-resource-id' in result

class TestErrorHandlingInPeeredVnets:
    """Test error handling in find_peered_vnets function"""

    @patch('cloudnetdraw.azure_client.get_credentials')
    def test_find_peered_vnets_resource_not_found_error(self, mock_get_credentials):
        """Test find_peered_vnets with ResourceNotFoundError - covers lines 368-370"""
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock network client that raises ResourceNotFoundError
        mock_network_client = Mock()
        mock_network_client.virtual_networks.get.side_effect = ResourceNotFoundError("Resource not found")
        
        with patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            with patch('cloudnetdraw.azure_client.SubscriptionClient'):
                # Test with a resource ID that will trigger the error
                resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/deleted-vnet"]
                
                peered_vnets, accessible_ids = azure_query.find_peered_vnets(resource_ids)
                
                # Should handle the error gracefully and return empty results
                assert peered_vnets == []
                assert accessible_ids == []

    @patch('cloudnetdraw.azure_client.get_credentials')
    def test_find_peered_vnets_general_error(self, mock_get_credentials):
        """Test find_peered_vnets with general error - covers lines 377-378"""
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock network client that raises a general exception
        mock_network_client = Mock()
        mock_network_client.virtual_networks.get.side_effect = Exception("General error")
        
        with patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            with patch('cloudnetdraw.azure_client.SubscriptionClient'):
                resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/error-vnet"]
                
                peered_vnets, accessible_ids = azure_query.find_peered_vnets(resource_ids)
                
                # Should handle the error gracefully and return empty results
                assert peered_vnets == []
                assert accessible_ids == []