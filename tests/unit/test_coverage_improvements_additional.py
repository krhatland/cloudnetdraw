"""
Additional tests to improve code coverage for azure-query.py
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import os
import logging
import sys
import tempfile
from azure.core.exceptions import ResourceNotFoundError

# Import the functions we want to test
from azure_query import (
    find_hub_vnet_using_resource_graph,
    find_peered_vnets,
    determine_hub_for_spoke,
    parse_vnet_identifier,
    query_command,
    get_subscriptions_non_interactive,
    main
)


class TestAdditionalCoverageImprovements:
    """Test additional code paths to improve coverage"""

    def test_find_hub_vnet_with_subscription_id_in_identifier(self):
        """Test find_hub_vnet_using_resource_graph with subscription ID in identifier"""
        # Mock the credential and clients
        mock_credentials = Mock()
        mock_resource_graph_client = Mock()
        mock_network_client = Mock()
        mock_subscription_client = Mock()
        
        # Mock the VNet response
        mock_vnet = Mock()
        mock_vnet.name = "test-vnet"
        mock_vnet.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"
        mock_vnet.address_space.address_prefixes = ["10.0.0.0/16"]
        mock_vnet.subnets = []
        
        # Mock the subscription response
        mock_subscription = Mock()
        mock_subscription.display_name = "Test Subscription"
        mock_subscription.tenant_id = "test-tenant"
        
        # Mock the resource graph response
        mock_response = Mock()
        mock_response.data = [{
            'subscriptionId': 'test-sub',
            'resourceGroup': 'test-rg',
            'name': 'test-vnet',
            'id': '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet'
        }]
        
        mock_debug_response = Mock()
        mock_debug_response.data = []
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.ResourceGraphClient', return_value=mock_resource_graph_client), \
             patch('azure_query.NetworkManagementClient', return_value=mock_network_client), \
             patch('azure_query.SubscriptionClient', return_value=mock_subscription_client):
            
            # Configure mocks
            mock_resource_graph_client.resources.side_effect = [mock_response, mock_debug_response]
            mock_network_client.virtual_networks.get.return_value = mock_vnet
            mock_subscription_client.subscriptions.get.return_value = mock_subscription
            mock_network_client.virtual_network_peerings.list.return_value = []
            
            # Test with subscription ID in identifier (triggers line 133)
            result = find_hub_vnet_using_resource_graph("test-sub/test-rg/test-vnet")
            
            # Verify the query was called with subscription ID filter
            assert mock_resource_graph_client.resources.call_count == 2
            query_request = mock_resource_graph_client.resources.call_args_list[0][0][0]
            assert "subscriptionId =~ 'test-sub'" in query_request.query
            assert result is not None
            assert result["name"] == "test-vnet"

    def test_find_peered_vnets_with_code_cleanup(self):
        """Test find_peered_vnets with Code: message cleanup"""
        mock_credentials = Mock()
        mock_subscription_client = Mock()
        mock_network_client = Mock()
        
        # Mock a VNet that will cause an exception with Code: in message
        resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"]
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.SubscriptionClient', return_value=mock_subscription_client), \
             patch('azure_query.NetworkManagementClient', return_value=mock_network_client):
            
            # Configure mock to raise exception with Code: in message
            error_msg = "Some error occurred\nCode: ErrorCode\nMessage: Error details"
            mock_network_client.virtual_networks.get.side_effect = Exception(error_msg)
            
            # This should trigger the code cleanup path (line 393)
            result_vnets, result_ids = find_peered_vnets(resource_ids)
            
            # Should return empty results due to exception
            assert result_vnets == []
            assert result_ids == []

    def test_find_peered_vnets_with_resource_not_found(self):
        """Test find_peered_vnets with ResourceNotFound exception"""
        mock_credentials = Mock()
        mock_subscription_client = Mock()
        mock_network_client = Mock()
        
        resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/deleted-vnet"]
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.SubscriptionClient', return_value=mock_subscription_client), \
             patch('azure_query.NetworkManagementClient', return_value=mock_network_client):
            
            # Configure mock to raise ResourceNotFound-like exception
            mock_network_client.virtual_networks.get.side_effect = Exception("ResourceNotFound: The resource was not found")
            
            # This should trigger the ResourceNotFound handling path (lines 385-386)
            result_vnets, result_ids = find_peered_vnets(resource_ids)
            
            # Should return empty results due to ResourceNotFound
            assert result_vnets == []
            assert result_ids == []

    def test_determine_hub_for_spoke_fallback(self):
        """Test determine_hub_for_spoke fallback return"""
        # Empty hub list should trigger fallback (line 710)
        spoke_vnet = {"peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/some-peering"]}
        hub_vnets = []
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result is None

    def test_determine_hub_for_spoke_with_hubs_no_match(self):
        """Test determine_hub_for_spoke with hubs but no match"""
        spoke_vnet = {"peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke-peering"]}
        hub_vnets = [{"peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/different-peering"]}]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        # Should return hub_0 as fallback
        assert result == "hub_0"

    def test_query_command_with_invalid_vnet_identifier(self):
        """Test query_command with invalid VNet identifier"""
        mock_credentials = Mock()
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.initialize_credentials'):
            
            # Create mock args with invalid VNet identifier
            args = Mock()
            args.service_principal = False
            args.subscriptions = None
            args.subscriptions_file = None
            args.vnets = "invalid/format/with/too/many/parts"
            args.output = None
            args.verbose = False
            
            # This should trigger ValueError handling (lines 655-657)
            with pytest.raises(SystemExit):
                query_command(args)

    def test_get_subscriptions_non_interactive_with_subscription_ids(self):
        """Test get_subscriptions_non_interactive with subscription IDs"""
        args = Mock()
        args.subscriptions = "12345678-1234-1234-1234-123456789012,87654321-4321-4321-4321-210987654321"
        args.subscriptions_file = None
        
        # Mock is_subscription_id to return True for first subscription
        with patch('azure_query.is_subscription_id', return_value=True):
            result = get_subscriptions_non_interactive(args)
            
            # Should return the IDs as-is (lines 691-694)
            expected = ["12345678-1234-1234-1234-123456789012", "87654321-4321-4321-4321-210987654321"]
            assert result == expected

    def test_main_with_file_not_found_error(self):
        """Test main function with FileNotFoundError"""
        test_args = ["azure-query.py", "query", "--topology", "nonexistent.json"]
        
        with patch('sys.argv', test_args), \
             patch('azure_query.query_command', side_effect=FileNotFoundError("File not found")):
            
            # This should trigger FileNotFoundError handling (lines 916-918)
            with pytest.raises(SystemExit):
                main()

    def test_main_with_general_exception(self):
        """Test main function with general exception"""
        test_args = ["azure-query.py", "query"]
        
        with patch('sys.argv', test_args), \
             patch('azure_query.query_command', side_effect=Exception("General error")):
            
            # This should trigger general exception handling (lines 919-921)
            with pytest.raises(SystemExit):
                main()

    def test_parse_vnet_identifier_simple_name(self):
        """Test parse_vnet_identifier with simple VNet name"""
        # Test the simple name path (line 116)
        result = parse_vnet_identifier("simple-vnet-name")
        assert result == (None, None, "simple-vnet-name")

    def test_find_hub_vnet_no_resource_group(self):
        """Test find_hub_vnet_using_resource_graph with no resource group"""
        # This should trigger the error on lines 123-125
        with pytest.raises(SystemExit):
            find_hub_vnet_using_resource_graph("simple-vnet-name")

    def test_find_peered_vnets_with_invalid_resource_id(self):
        """Test find_peered_vnets with invalid resource ID format"""
        mock_credentials = Mock()
        mock_subscription_client = Mock()
        
        # Invalid resource ID format
        resource_ids = ["invalid-resource-id-format"]
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.SubscriptionClient', return_value=mock_subscription_client):
            
            # Should handle invalid format and return empty results
            result_vnets, result_ids = find_peered_vnets(resource_ids)
            
            assert result_vnets == []
            assert result_ids == []

    def test_find_peered_vnets_with_peering_info(self):
        """Test find_peered_vnets with peering information"""
        mock_credentials = Mock()
        mock_subscription_client = Mock()
        mock_network_client = Mock()
        
        # Mock a proper VNet with peering
        mock_vnet = Mock()
        mock_vnet.name = "test-vnet"
        mock_vnet.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"
        mock_vnet.address_space.address_prefixes = ["10.0.0.0/16"]
        mock_vnet.subnets = []
        
        # Mock peering
        mock_peering = Mock()
        mock_peering.name = "test-peering"
        mock_peering.remote_virtual_network.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/remote-vnet"
        
        # Mock subscription
        mock_subscription = Mock()
        mock_subscription.display_name = "Test Subscription"
        mock_subscription.tenant_id = "test-tenant"
        
        resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"]
        
        with patch('azure_query.get_credentials', return_value=mock_credentials), \
             patch('azure_query.SubscriptionClient', return_value=mock_subscription_client), \
             patch('azure_query.NetworkManagementClient', return_value=mock_network_client):
            
            # Configure mocks
            mock_network_client.virtual_networks.get.return_value = mock_vnet
            mock_subscription_client.subscriptions.get.return_value = mock_subscription
            mock_network_client.virtual_network_peerings.list.return_value = [mock_peering]
            
            # This should trigger the peering info paths (lines 371-373)
            result_vnets, result_ids = find_peered_vnets(resource_ids)
            
            assert len(result_vnets) == 1
            assert len(result_ids) == 1
            assert result_vnets[0]["name"] == "test-vnet"
            assert result_vnets[0]["peering_resource_ids"] == ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/remote-vnet"]
            assert result_vnets[0]["peerings_count"] == 1