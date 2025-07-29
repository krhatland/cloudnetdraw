"""
Unit tests for Azure API functions with proper mocking to improve coverage
"""
import pytest
import os
import sys
from unittest.mock import patch, MagicMock, Mock
from azure.core.exceptions import ResourceNotFoundError

from cloudnetdraw.azure_client import (
    find_hub_vnet_using_resource_graph, find_peered_vnets,
    get_vnet_topology_for_selected_subscriptions,
    get_subscriptions_non_interactive, resolve_subscription_names_to_ids,
    read_subscriptions_from_file, get_sp_credentials, initialize_credentials,
    get_credentials
)
from cloudnetdraw.topology import get_filtered_vnet_topology


class TestFindHubVnetUsingResourceGraph:
    """Test find_hub_vnet_using_resource_graph function with proper mocking"""
    
    def test_find_hub_vnet_missing_resource_group(self):
        """Test error when resource group is missing"""
        with patch('cloudnetdraw.azure_client.get_credentials'), \
             pytest.raises(SystemExit) as exc_info:
            find_hub_vnet_using_resource_graph("simple-vnet-name")
        
        assert exc_info.value.code == 1
    
    def test_find_hub_vnet_exception_handling(self):
        """Test exception handling in find_hub_vnet_using_resource_graph"""
        mock_credentials = MagicMock()
        mock_resource_graph_client = MagicMock()
        mock_resource_graph_client.resources.side_effect = Exception("API Error")
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.ResourceGraphClient', return_value=mock_resource_graph_client):
            
            result = find_hub_vnet_using_resource_graph("rg-1/test-vnet")
            assert result is None


class TestFindPeeredVnets:
    """Test find_peered_vnets function with proper mocking"""
    
    def test_find_peered_vnets_empty_list(self):
        """Test find_peered_vnets with empty resource ID list"""
        peered_vnets, accessible_resource_ids = find_peered_vnets([])
        assert peered_vnets == []
        assert accessible_resource_ids == []
    
    def test_find_peered_vnets_invalid_resource_id(self):
        """Test find_peered_vnets with invalid resource ID format"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client):
            
            peered_vnets, accessible_resource_ids = find_peered_vnets(['/invalid/resource/id'])
            assert peered_vnets == []
            assert accessible_resource_ids == []
    
    def test_find_peered_vnets_duplicate_handling(self):
        """Test find_peered_vnets with duplicate resource IDs"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription
        
        mock_network_client = MagicMock()
        mock_vnet = MagicMock()
        mock_vnet.name = 'test-vnet'
        mock_vnet.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
        mock_vnet.address_space.address_prefixes = ['10.0.0.0/16']
        mock_vnet.subnets = []
        mock_network_client.virtual_networks.get.return_value = mock_vnet
        mock_network_client.virtual_network_peerings.list.return_value = []
        
        # Same resource ID twice - should only process once
        resource_ids = [
            '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet',
            '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
        ]
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            peered_vnets, accessible_resource_ids = find_peered_vnets(resource_ids)
            assert len(peered_vnets) == 1  # Should only have one VNet despite two identical IDs
            assert len(accessible_resource_ids) == 1  # Should have one accessible resource ID
    
    def test_find_peered_vnets_resource_not_found(self):
        """Test find_peered_vnets with ResourceNotFoundError"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription
        
        mock_network_client = MagicMock()
        mock_network_client.virtual_networks.get.side_effect = ResourceNotFoundError("VNet not found")
        
        resource_ids = [
            '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/deleted-vnet'
        ]
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            peered_vnets, accessible_resource_ids = find_peered_vnets(resource_ids)
            assert peered_vnets == []  # Should return empty list when VNet not found
            assert accessible_resource_ids == []  # Should return empty list for accessible resource IDs
    
    def test_find_peered_vnets_general_exception(self):
        """Test find_peered_vnets with general exception"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription_client.subscriptions.get.side_effect = Exception("General error")
        
        resource_ids = [
            '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
        ]
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client):
            
            peered_vnets, accessible_resource_ids = find_peered_vnets(resource_ids)
            assert peered_vnets == []  # Should return empty list on exception
            assert accessible_resource_ids == []  # Should return empty list for accessible resource IDs


class TestGetFilteredVnetTopology:
    """Test get_filtered_vnet_topology function"""
    
    def test_get_filtered_vnet_topology_hub_not_found(self):
        """Test get_filtered_vnet_topology when hub VNet is not found"""
        with patch('cloudnetdraw.azure_client.find_hub_vnet_using_resource_graph', return_value=None), \
             pytest.raises(SystemExit) as exc_info:
            get_filtered_vnet_topology("rg-1/nonexistent-vnet", ["sub-1"])
        
        assert exc_info.value.code == 1
    
    def test_get_filtered_vnet_topology_success(self):
        """Test successful get_filtered_vnet_topology"""
        mock_hub_vnet = {
            'name': 'hub-vnet',
            'subscription_name': 'Test Subscription',
            'peering_resource_ids': [
                '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke-vnet'
            ]
        }
        
        mock_spoke_vnets = [{
            'name': 'spoke-vnet',
            'subscription_name': 'Test Subscription'
        }]
        
        with patch('cloudnetdraw.topology.find_hub_vnet_using_resource_graph', return_value=mock_hub_vnet), \
             patch('cloudnetdraw.topology.find_peered_vnets', return_value=(mock_spoke_vnets, ['/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke-vnet'])):
            
            result = get_filtered_vnet_topology("rg-1/hub-vnet", ["sub-1"])
            
            assert 'vnets' in result
            assert len(result['vnets']) == 2  # Hub + 1 spoke
            assert result['vnets'][0]['name'] == 'hub-vnet'
            assert result['vnets'][1]['name'] == 'spoke-vnet'


class TestGetVnetTopologyForSelectedSubscriptions:
    """Test get_vnet_topology_for_selected_subscriptions function"""
    
    def test_get_vnet_topology_subscription_access_error(self):
        """Test get_vnet_topology when subscription access fails"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription_client.subscriptions.get.side_effect = Exception("Access denied")
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             pytest.raises(SystemExit) as exc_info:
            get_vnet_topology_for_selected_subscriptions(["invalid-sub"])
        
        assert exc_info.value.code == 1
    
    def test_get_vnet_topology_virtual_wan_error(self):
        """Test get_vnet_topology when virtual WAN listing fails"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription
        
        mock_network_client = MagicMock()
        mock_network_client.virtual_wans.list.side_effect = Exception("Virtual WAN error")
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client), \
             pytest.raises(SystemExit) as exc_info:
            get_vnet_topology_for_selected_subscriptions(["sub-1"])
        
        assert exc_info.value.code == 1
    
    def test_get_vnet_topology_vnet_processing_error(self):
        """Test get_vnet_topology when VNet processing fails"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription
        
        mock_network_client = MagicMock()
        mock_network_client.virtual_wans.list.return_value = []
        
        # Mock VNet that will cause processing error
        mock_vnet = MagicMock()
        mock_vnet.name = 'test-vnet'
        mock_vnet.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
        mock_vnet.address_space.address_prefixes = ['10.0.0.0/16']
        mock_vnet.subnets = []
        mock_network_client.virtual_networks.list_all.return_value = [mock_vnet]
        
        # Mock peering list to raise exception
        mock_network_client.virtual_network_peerings.list.side_effect = Exception("Peering error")
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client), \
             patch('cloudnetdraw.utils.extract_resource_group', return_value='rg-1'), \
             pytest.raises(SystemExit) as exc_info:
            get_vnet_topology_for_selected_subscriptions(["sub-1"])
        
        assert exc_info.value.code == 1
    
    def test_get_vnet_topology_no_vnets_found(self):
        """Test get_vnet_topology when no VNets are found"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription
        
        mock_network_client = MagicMock()
        mock_network_client.virtual_wans.list.return_value = []
        mock_network_client.virtual_networks.list_all.return_value = []
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client), \
             pytest.raises(SystemExit) as exc_info:
            get_vnet_topology_for_selected_subscriptions(["sub-1"])
        
        assert exc_info.value.code == 1


class TestCredentialsAndSubscriptionHandling:
    """Test credential and subscription handling functions"""
    
    def test_get_sp_credentials_missing_client_id(self):
        """Test get_sp_credentials when client ID is missing"""
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(SystemExit) as exc_info:
            get_sp_credentials()
        
        assert exc_info.value.code == 1
    
    def test_get_sp_credentials_missing_client_secret(self):
        """Test get_sp_credentials when client secret is missing"""
        with patch.dict(os.environ, {'AZURE_CLIENT_ID': 'test-id'}, clear=True), \
             pytest.raises(SystemExit) as exc_info:
            get_sp_credentials()
        
        assert exc_info.value.code == 1
    
    def test_get_sp_credentials_missing_tenant_id(self):
        """Test get_sp_credentials when tenant ID is missing"""
        with patch.dict(os.environ, {
            'AZURE_CLIENT_ID': 'test-id',
            'AZURE_CLIENT_SECRET': 'test-secret'
        }, clear=True), \
             pytest.raises(SystemExit) as exc_info:
            get_sp_credentials()
        
        assert exc_info.value.code == 1
    
    def test_get_credentials_not_initialized(self):
        """Test get_credentials when not initialized"""
        # Reset global credentials
        import cloudnetdraw.azure_client
        cloudnetdraw.azure_client._credentials = None
        
        with pytest.raises(RuntimeError, match="Credentials not initialized"):
            get_credentials()
    
    def test_initialize_credentials_service_principal(self):
        """Test initialize_credentials with service principal"""
        with patch.dict(os.environ, {
            'AZURE_CLIENT_ID': 'test-id',
            'AZURE_CLIENT_SECRET': 'test-secret',
            'AZURE_TENANT_ID': 'test-tenant'
        }), \
             patch('cloudnetdraw.azure_client.ClientSecretCredential') as mock_cred:
            
            initialize_credentials(use_service_principal=True)
            mock_cred.assert_called_once_with('test-tenant', 'test-id', 'test-secret')
    
    def test_initialize_credentials_azure_cli(self):
        """Test initialize_credentials with Azure CLI"""
        with patch('cloudnetdraw.azure_client.AzureCliCredential') as mock_cred:
            initialize_credentials(use_service_principal=False)
            mock_cred.assert_called_once()
    
    def test_read_subscriptions_from_file_not_found(self):
        """Test read_subscriptions_from_file with non-existent file"""
        with pytest.raises(SystemExit) as exc_info:
            read_subscriptions_from_file("nonexistent.txt")
        
        assert exc_info.value.code == 1
    
    def test_read_subscriptions_from_file_permission_error(self):
        """Test read_subscriptions_from_file with permission error"""
        with patch('builtins.open', side_effect=PermissionError("Permission denied")), \
             pytest.raises(SystemExit) as exc_info:
            read_subscriptions_from_file("test.txt")
        
        assert exc_info.value.code == 1
    
    def test_resolve_subscription_names_to_ids_not_found(self):
        """Test resolve_subscription_names_to_ids with non-existent subscription"""
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Existing Subscription'
        mock_subscription.subscription_id = 'sub-1'
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             pytest.raises(SystemExit) as exc_info:
            resolve_subscription_names_to_ids(['Non-existent Subscription'])
        
        assert exc_info.value.code == 1
    
    def test_get_subscriptions_non_interactive_both_specified(self):
        """Test get_subscriptions_non_interactive when both subscriptions and file are specified"""
        args = MagicMock()
        args.subscriptions = 'sub-1'
        args.subscriptions_file = 'file.txt'
        
        with pytest.raises(SystemExit) as exc_info:
            get_subscriptions_non_interactive(args)
        
        assert exc_info.value.code == 1
    
    def test_get_subscriptions_non_interactive_subscription_names(self):
        """Test get_subscriptions_non_interactive with subscription names"""
        args = MagicMock()
        args.subscriptions = 'Test Subscription'
        args.subscriptions_file = None
        
        mock_credentials = MagicMock()
        mock_subscription_client = MagicMock()
        mock_subscription = MagicMock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription.subscription_id = 'sub-1'
        mock_subscription_client.subscriptions.list.return_value = [mock_subscription]
        
        with patch('cloudnetdraw.azure_client.get_credentials', return_value=mock_credentials), \
             patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.is_subscription_id', return_value=False):
            
            result = get_subscriptions_non_interactive(args)
            assert result == ['sub-1']