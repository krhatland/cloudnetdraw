"""
Unit tests for Azure client functions and API interactions
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from azure.core.exceptions import ResourceNotFoundError
from pathlib import Path

# Import functions under test
from cloudnetdraw.azure_client import (
    get_vnet_topology_for_selected_subscriptions,
    list_and_select_subscriptions,
    get_subscriptions_non_interactive,
    initialize_credentials
)


class TestVNetTopologyCollection:
    """Test VNet topology collection from Azure"""

    def test_get_vnet_topology_single_subscription(self, mock_azure_credentials, mock_network_client):
        """Test topology collection from single subscription"""
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription

        # Mock VNet data
        mock_vnet = Mock()
        mock_vnet.name = 'test-vnet'
        mock_vnet.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
        mock_vnet.address_space.address_prefixes = ['10.0.0.0/16']
        
        # Mock subnet
        mock_subnet = Mock()
        mock_subnet.name = 'default'
        mock_subnet.address_prefix = '10.0.0.0/24'
        mock_subnet.address_prefixes = ['10.0.0.0/24']
        mock_subnet.network_security_group = None
        mock_subnet.route_table = None
        mock_vnet.subnets = [mock_subnet]
        
        mock_network_client.virtual_networks.list_all.return_value = [mock_vnet]
        mock_network_client.virtual_network_peerings.list.return_value = []
        mock_network_client.virtual_wans.list.return_value = []

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            # Initialize credentials for global usage
            initialize_credentials()
            result = get_vnet_topology_for_selected_subscriptions(['sub-1'])
            
            assert 'vnets' in result
            assert len(result['vnets']) == 1
            assert result['vnets'][0]['name'] == 'test-vnet'
            assert result['vnets'][0]['address_space'] == '10.0.0.0/16'
            assert result['vnets'][0]['subscription_name'] == 'Test Subscription'

    def test_get_vnet_topology_with_peerings(self, mock_azure_credentials):
        """Test topology collection with VNet peerings"""
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription

        mock_network_client = Mock()
        
        # Mock VNet with peerings
        mock_vnet = Mock()
        mock_vnet.name = 'hub-vnet'
        mock_vnet.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet'
        mock_vnet.address_space.address_prefixes = ['10.0.0.0/16']
        
        # Mock subnets including GatewaySubnet
        mock_gateway_subnet = Mock()
        mock_gateway_subnet.name = 'GatewaySubnet'
        mock_gateway_subnet.address_prefix = '10.0.1.0/24'
        mock_gateway_subnet.address_prefixes = ['10.0.1.0/24']
        mock_gateway_subnet.network_security_group = None
        mock_gateway_subnet.route_table = None
        
        mock_default_subnet = Mock()
        mock_default_subnet.name = 'default'
        mock_default_subnet.address_prefix = '10.0.0.0/24'
        mock_default_subnet.address_prefixes = ['10.0.0.0/24']
        mock_default_subnet.network_security_group = Mock()  # Has NSG
        mock_default_subnet.route_table = Mock()  # Has UDR
        
        mock_vnet.subnets = [mock_gateway_subnet, mock_default_subnet]
        
        # Mock peerings
        mock_peering1 = Mock()
        mock_peering1.name = 'hub-vnet_to_spoke1'
        mock_peering2 = Mock()
        mock_peering2.name = 'hub-vnet_to_spoke2'
        
        mock_network_client.virtual_networks.list_all.return_value = [mock_vnet]
        mock_network_client.virtual_network_peerings.list.return_value = [mock_peering1, mock_peering2]
        mock_network_client.virtual_wans.list.return_value = []

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            # Initialize credentials for global usage
            initialize_credentials()
            result = get_vnet_topology_for_selected_subscriptions(['sub-1'])
            
            vnet = result['vnets'][0]
            assert vnet['name'] == 'hub-vnet'
            assert vnet['peerings_count'] == 2
            assert vnet['expressroute'] == 'Yes'  # Due to GatewaySubnet
            assert vnet['vpn_gateway'] == 'Yes'   # Due to GatewaySubnet
            assert vnet['firewall'] == 'No'       # No AzureFirewallSubnet
            
            # Check subnets
            assert len(vnet['subnets']) == 2
            gateway_subnet = next(s for s in vnet['subnets'] if s['name'] == 'GatewaySubnet')
            assert gateway_subnet['nsg'] == 'No'
            assert gateway_subnet['udr'] == 'No'
            
            default_subnet = next(s for s in vnet['subnets'] if s['name'] == 'default')
            assert default_subnet['nsg'] == 'Yes'
            assert default_subnet['udr'] == 'Yes'

    def test_get_vnet_topology_with_virtual_hub(self, mock_azure_credentials):
        """Test topology collection with Virtual WAN hub"""
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription.tenant_id = 'tenant-123'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription

        mock_network_client = Mock()
        
        # Mock Virtual WAN
        mock_vwan = Mock()
        mock_vwan.name = 'test-vwan'
        mock_vwan.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualWans/test-vwan'
        
        # Mock Virtual Hub
        mock_hub = Mock()
        mock_hub.name = 'test-hub'
        mock_hub.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualHubs/test-hub'
        mock_hub.address_prefix = '10.0.0.0/16'
        mock_hub.express_route_gateway = Mock()  # Has ExpressRoute
        mock_hub.vpn_gateway = Mock()           # Has VPN
        mock_hub.azure_firewall = None          # No firewall
        
        mock_network_client.virtual_wans.list.return_value = [mock_vwan]
        mock_network_client.virtual_hubs.list_by_resource_group.return_value = [mock_hub]
        mock_network_client.virtual_networks.list_all.return_value = []

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            # Initialize credentials for global usage
            initialize_credentials()
            result = get_vnet_topology_for_selected_subscriptions(['sub-1'])
            
            assert len(result['vnets']) == 1
            hub = result['vnets'][0]
            assert hub['name'] == 'test-hub'
            assert hub['type'] == 'virtual_hub'
            assert hub['address_space'] == '10.0.0.0/16'
            assert hub['expressroute'] == 'Yes'
            assert hub['vpn_gateway'] == 'Yes'
            assert hub['firewall'] == 'No'
            assert hub['subnets'] == []  # Virtual hubs don't have traditional subnets
            assert hub['peerings_count'] == 0

    def test_get_vnet_topology_multiple_subscriptions(self, mock_azure_credentials):
        """Test topology collection from multiple subscriptions"""
        mock_subscription_client = Mock()
        
        # Mock subscriptions
        mock_sub1 = Mock()
        mock_sub1.display_name = 'Subscription 1'
        mock_sub2 = Mock()
        mock_sub2.display_name = 'Subscription 2'
        
        def mock_get_subscription(sub_id):
            if sub_id == 'sub-1':
                return mock_sub1
            elif sub_id == 'sub-2':
                return mock_sub2
        
        mock_subscription_client.subscriptions.get.side_effect = mock_get_subscription

        # Mock network clients for each subscription
        def mock_network_client(credentials, subscription_id):
            mock_client = Mock()
            
            if subscription_id == 'sub-1':
                # VNet in subscription 1
                mock_vnet = Mock()
                mock_vnet.name = 'vnet1'
                mock_vnet.id = f'/subscriptions/{subscription_id}/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1'
                mock_vnet.address_space.address_prefixes = ['10.1.0.0/16']
                mock_vnet.subnets = []
            elif subscription_id == 'sub-2':
                # VNet in subscription 2
                mock_vnet = Mock()
                mock_vnet.name = 'vnet2'
                mock_vnet.id = f'/subscriptions/{subscription_id}/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2'
                mock_vnet.address_space.address_prefixes = ['10.2.0.0/16']
                mock_vnet.subnets = []
            
            mock_client.virtual_networks.list_all.return_value = [mock_vnet]
            mock_client.virtual_network_peerings.list.return_value = []
            mock_client.virtual_wans.list.return_value = []
            return mock_client

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', side_effect=mock_network_client):
            
            # Initialize credentials for global usage
            initialize_credentials()
            result = get_vnet_topology_for_selected_subscriptions(['sub-1', 'sub-2'])
            
            assert len(result['vnets']) == 2
            
            vnet1 = next(v for v in result['vnets'] if v['name'] == 'vnet1')
            assert vnet1['subscription_name'] == 'Subscription 1'
            assert vnet1['address_space'] == '10.1.0.0/16'
            
            vnet2 = next(v for v in result['vnets'] if v['name'] == 'vnet2')
            assert vnet2['subscription_name'] == 'Subscription 2'
            assert vnet2['address_space'] == '10.2.0.0/16'

    def test_get_vnet_topology_api_error_handling(self, mock_azure_credentials):
        """Test handling of Azure API errors"""
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription

        mock_network_client = Mock()
        mock_network_client.virtual_networks.list_all.side_effect = ResourceNotFoundError("Resource not found")
        mock_network_client.virtual_wans.list.return_value = []

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            # Should exit with error code 1 when Azure API error occurs
            # Initialize credentials for global usage
            initialize_credentials()
            
            with pytest.raises(SystemExit) as exc_info:
                get_vnet_topology_for_selected_subscriptions(['sub-1'])
            assert exc_info.value.code == 1

    def test_get_vnet_topology_virtual_wan_error_handling(self, mock_azure_credentials):
        """Test handling of Virtual WAN API errors"""
        mock_subscription_client = Mock()
        mock_subscription = Mock()
        mock_subscription.display_name = 'Test Subscription'
        mock_subscription_client.subscriptions.get.return_value = mock_subscription

        mock_network_client = Mock()
        mock_network_client.virtual_networks.list_all.return_value = []
        mock_network_client.virtual_wans.list.side_effect = Exception("Virtual WAN error")

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('cloudnetdraw.azure_client.NetworkManagementClient', return_value=mock_network_client):
            
            # Should exit with error code 1 when Azure API error occurs
            # Initialize credentials for global usage
            initialize_credentials()
            
            with pytest.raises(SystemExit) as exc_info:
                get_vnet_topology_for_selected_subscriptions(['sub-1'])
            assert exc_info.value.code == 1


class TestSubscriptionListing:
    """Test subscription listing and selection"""

    def test_list_and_select_subscriptions(self, mock_azure_credentials, mock_subscription_list):
        """Test interactive subscription selection"""
        mock_subscription_client = Mock()
        mock_subscription_client.subscriptions.list.return_value = mock_subscription_list

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('builtins.input', return_value='0,2'):
            
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = list_and_select_subscriptions()
            
            assert len(result) == 2
            assert result[0] == 'sub-1'
            assert result[1] == 'sub-3'

    def test_list_and_select_subscriptions_sorting(self, mock_azure_credentials):
        """Test that subscriptions are sorted alphabetically"""
        # Create unsorted mock subscriptions
        mock_subscriptions = [
            Mock(subscription_id='sub-3', display_name='Z Subscription'),
            Mock(subscription_id='sub-1', display_name='A Subscription'),
            Mock(subscription_id='sub-2', display_name='B Subscription'),
        ]
        
        mock_subscription_client = Mock()
        mock_subscription_client.subscriptions.list.return_value = mock_subscriptions

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('builtins.input', return_value='0,1,2'):
            
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = list_and_select_subscriptions()
            
            # Should return IDs in order of sorted display names
            assert result == ['sub-1', 'sub-2', 'sub-3']

    def test_list_and_select_subscriptions_single_selection(self, mock_azure_credentials, mock_subscription_list):
        """Test selecting single subscription"""
        mock_subscription_client = Mock()
        mock_subscription_client.subscriptions.list.return_value = mock_subscription_list

        with patch('cloudnetdraw.azure_client.SubscriptionClient', return_value=mock_subscription_client), \
             patch('builtins.input', return_value='1'):
            
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = list_and_select_subscriptions()
            
            assert len(result) == 1
            assert result[0] == 'sub-2'


class TestNonInteractiveSubscriptionHandling:
    """Test non-interactive subscription handling"""

    def test_get_subscriptions_non_interactive_from_args(self, mock_azure_credentials):
        """Test getting subscriptions from command line arguments"""
        mock_args = Mock()
        mock_args.subscriptions = 'sub-1,sub-2,sub-3'
        mock_args.subscriptions_file = None
        
        with patch('cloudnetdraw.azure_client.is_subscription_id', return_value=True):
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = get_subscriptions_non_interactive(mock_args)
            assert result == ['sub-1', 'sub-2', 'sub-3']

    def test_get_subscriptions_non_interactive_from_file(self, mock_azure_credentials, temp_directory):
        """Test getting subscriptions from file"""
        # Create subscriptions file
        subscriptions_file = Path(temp_directory) / "subscriptions.txt"
        subscriptions_file.write_text("sub-1\nsub-2\nsub-3\n")
        
        mock_args = Mock()
        mock_args.subscriptions = None
        mock_args.subscriptions_file = str(subscriptions_file)
        
        with patch('cloudnetdraw.azure_client.is_subscription_id', return_value=True):
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = get_subscriptions_non_interactive(mock_args)
            assert result == ['sub-1', 'sub-2', 'sub-3']

    def test_get_subscriptions_non_interactive_both_specified_error(self, mock_azure_credentials):
        """Test error when both subscriptions and file are specified"""
        mock_args = Mock()
        mock_args.subscriptions = 'sub-1,sub-2'
        mock_args.subscriptions_file = 'subscriptions.txt'
        
        with pytest.raises(SystemExit):
            # Initialize credentials for global usage
            initialize_credentials()
            
            get_subscriptions_non_interactive(mock_args)

    def test_get_subscriptions_non_interactive_name_resolution(self, mock_azure_credentials):
        """Test subscription name to ID resolution"""
        mock_args = Mock()
        mock_args.subscriptions = 'Test Subscription 1,Test Subscription 2'
        mock_args.subscriptions_file = None
        
        with patch('cloudnetdraw.azure_client.is_subscription_id', return_value=False), \
             patch('cloudnetdraw.azure_client.resolve_subscription_names_to_ids', return_value=['sub-1', 'sub-2']) as mock_resolve:
            
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = get_subscriptions_non_interactive(mock_args)
            
            mock_resolve.assert_called_once_with(['Test Subscription 1', 'Test Subscription 2'])
            assert result == ['sub-1', 'sub-2']

    def test_get_subscriptions_non_interactive_whitespace_handling(self, mock_azure_credentials):
        """Test proper whitespace handling in subscription lists"""
        mock_args = Mock()
        mock_args.subscriptions = ' sub-1 , sub-2 , sub-3 '
        mock_args.subscriptions_file = None
        
        with patch('cloudnetdraw.azure_client.is_subscription_id', return_value=True):
            # Initialize credentials for global usage
            initialize_credentials()
            
            result = get_subscriptions_non_interactive(mock_args)
            assert result == ['sub-1', 'sub-2', 'sub-3']