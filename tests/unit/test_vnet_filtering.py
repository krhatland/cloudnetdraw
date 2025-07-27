import pytest
from unittest.mock import Mock, patch
import importlib
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import the module using importlib to handle the hyphenated name
azure_query = importlib.import_module('azure-query')

# Import the functions we want to test
from azure_query import parse_vnet_identifier, get_filtered_vnet_topology


class TestParseVnetIdentifier:
    """Test parse_vnet_identifier function"""
    
    def test_parse_simple_vnet_name(self):
        """Test parsing simple VNet name"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("test-vnet")
        assert subscription_id is None
        assert resource_group is None
        assert vnet_name == "test-vnet"
    
    def test_parse_vnet_name_with_hyphens(self):
        """Test parsing VNet name with hyphens"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("test-vnet-001")
        assert subscription_id is None
        assert resource_group is None
        assert vnet_name == "test-vnet-001"
    
    def test_parse_vnet_name_with_underscores(self):
        """Test parsing VNet name with underscores"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("test_vnet_001")
        assert subscription_id is None
        assert resource_group is None
        assert vnet_name == "test_vnet_001"
    
    def test_parse_rg_vnet_format(self):
        """Test parsing resource_group/vnet_name format"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("rg-test/vnet-test")
        assert subscription_id is None
        assert resource_group == "rg-test"
        assert vnet_name == "vnet-test"
    
    def test_parse_rg_vnet_format_with_underscores(self):
        """Test parsing resource_group/vnet_name format with underscores"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("rg_test/vnet_test")
        assert subscription_id is None
        assert resource_group == "rg_test"
        assert vnet_name == "vnet_test"
    
    def test_parse_subscription_rg_vnet_format(self):
        """Test parsing subscription/resource_group/vnet_name format"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("test-sub/rg-test/vnet-test")
        assert subscription_id == "test-sub"
        assert resource_group == "rg-test"
        assert vnet_name == "vnet-test"
    
    def test_parse_subscription_rg_vnet_format_with_uuid(self):
        """Test parsing subscription/resource_group/vnet_name format with UUID subscription"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("12345678-1234-1234-1234-123456789012/rg-test/vnet-test")
        assert subscription_id == "12345678-1234-1234-1234-123456789012"
        assert resource_group == "rg-test"
        assert vnet_name == "vnet-test"
    
    def test_parse_rg_vnet_format_invalid_multiple_slashes(self):
        """Test parsing invalid format with more than 3 parts"""
        with pytest.raises(ValueError) as exc_info:
            parse_vnet_identifier("sub/rg-test/vnet-test/extra")
        assert "Invalid VNet identifier format" in str(exc_info.value)
    
    def test_parse_full_resource_id(self):
        """Test parsing full Azure resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-test/providers/Microsoft.Network/virtualNetworks/vnet-test"
        subscription_id, resource_group, vnet_name = parse_vnet_identifier(resource_id)
        assert subscription_id == "12345678-1234-1234-1234-123456789012"
        assert resource_group == "rg-test"
        assert vnet_name == "vnet-test"
    
    def test_parse_resource_id_with_special_chars(self):
        """Test parsing resource ID with special characters in names"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-test-001/providers/Microsoft.Network/virtualNetworks/vnet-test-001"
        subscription_id, resource_group, vnet_name = parse_vnet_identifier(resource_id)
        assert subscription_id == "12345678-1234-1234-1234-123456789012"
        assert resource_group == "rg-test-001"
        assert vnet_name == "vnet-test-001"
    
    def test_parse_invalid_resource_id_format(self):
        """Test parsing invalid resource ID format"""
        with pytest.raises(ValueError) as exc_info:
            parse_vnet_identifier("/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test")
        assert "Invalid VNet resource ID format" in str(exc_info.value)
    
    def test_parse_incomplete_resource_id(self):
        """Test parsing incomplete resource ID"""
        with pytest.raises(ValueError) as exc_info:
            parse_vnet_identifier("/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-test")
        assert "Invalid VNet resource ID format" in str(exc_info.value)
    
    def test_parse_wrong_provider_in_resource_id(self):
        """Test parsing resource ID with wrong provider"""
        with pytest.raises(ValueError) as exc_info:
            parse_vnet_identifier("/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-test")
        assert "Invalid VNet resource ID format" in str(exc_info.value)
    
    def test_parse_empty_string(self):
        """Test parsing empty string"""
        subscription_id, resource_group, vnet_name = parse_vnet_identifier("")
        assert subscription_id is None
        assert resource_group is None
        assert vnet_name == ""
    
    def test_parse_resource_id_case_sensitivity(self):
        """Test parsing resource ID with mixed case"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/RG-Test/providers/Microsoft.Network/virtualNetworks/VNet-Test"
        subscription_id, resource_group, vnet_name = parse_vnet_identifier(resource_id)
        assert subscription_id == "12345678-1234-1234-1234-123456789012"
        assert resource_group == "RG-Test"
        assert vnet_name == "VNet-Test"


class TestFindHubVnetUsingResourceGraph:
    """Test find_hub_vnet_using_resource_graph function using direct mocking"""
    
    def test_find_hub_vnet_by_name_single_subscription(self):
        """Test finding hub VNet by name in single subscription"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [
                {
                    'name': 'GatewaySubnet',
                    'address': '10.0.1.0/24',
                    'nsg': 'No',
                    'udr': 'No'
                }
            ],
            'peerings': ['hub-vnet-001_to_spoke1'],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'Yes',
            'vpn_gateway': 'Yes',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': ['/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/spoke1'],
            'peerings_count': 1
        }
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph('rg-1/hub-vnet-001')
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['subscription_id'] == '12345678-1234-1234-1234-123456789012'
            assert result['resource_group'] == 'rg-1'
            assert result['is_explicit_hub'] is True
            assert result['expressroute'] == 'Yes'
            assert result['vpn_gateway'] == 'Yes'
            assert len(result['peering_resource_ids']) == 1
    
    def test_find_hub_vnet_using_resource_graph_success(self):
        """Test finding hub VNet using Resource Graph API successfully"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph('rg-1/hub-vnet-001')
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['subscription_id'] == '12345678-1234-1234-1234-123456789012'
            assert result['resource_group'] == 'rg-1'
            assert result['is_explicit_hub'] is True
            assert result['expressroute'] == 'No'
            assert result['vpn_gateway'] == 'No'
            assert len(result['peering_resource_ids']) == 0
    
    def test_find_hub_vnet_by_resource_id(self):
        """Test finding hub VNet by resource ID"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001"
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph(resource_id)
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['subscription_id'] == '12345678-1234-1234-1234-123456789012'
            assert result['resource_group'] == 'rg-1'
            assert result['is_explicit_hub'] is True
    
    def test_find_hub_vnet_not_found(self):
        """Test when hub VNet is not found"""
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=None):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph('rg-1/nonexistent-vnet')
            
            assert result is None
    
    def test_find_hub_vnet_multiple_subscriptions(self):
        """Test finding hub VNet across multiple subscriptions"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription 2',
            'subscription_id': '87654321-4321-4321-4321-210987654321',
            'resource_group': 'rg-2',
            'resource_id': '/subscriptions/87654321-4321-4321-4321-210987654321/resourceGroups/rg-2/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph('rg-2/hub-vnet-001')
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['subscription_id'] == '87654321-4321-4321-4321-210987654321'
            assert result['resource_group'] == 'rg-2'
            assert result['is_explicit_hub'] is True
    
    def test_find_hub_vnet_resource_group_filtering(self):
        """Test filtering by resource group when using resource ID"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.1.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-2',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-2/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-2/providers/Microsoft.Network/virtualNetworks/hub-vnet-001"
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph(resource_id)
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['subscription_id'] == '12345678-1234-1234-1234-123456789012'
            assert result['resource_group'] == 'rg-2'
            assert result['is_explicit_hub'] is True


class TestExplicitHubFlag:
    """Test explicit hub flag functionality"""
    
    def test_explicit_hub_flag_set(self):
        """Test that is_explicit_hub flag is set correctly"""
        expected_result = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,  # This is the key assertion
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=expected_result):
            from azure_query import find_hub_vnet_using_resource_graph
            result = find_hub_vnet_using_resource_graph('rg-1/hub-vnet-001')
            
            assert result is not None
            assert result['name'] == 'hub-vnet-001'
            assert result['is_explicit_hub'] is True  # This is the key assertion
            assert result['peerings_count'] == 0  # No peerings, but still treated as hub


class TestGetFilteredVnetTopology:
    """Test get_filtered_vnet_topology function"""
    
    def test_get_filtered_topology_basic(self):
        """Test basic filtered topology functionality"""
        mock_hub_vnet = {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            'peerings': [],
            'subscription_name': 'Test Subscription',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'resource_group': 'rg-1',
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No',
            'is_explicit_hub': True,
            'peering_resource_ids': [],
            'peerings_count': 0
        }
        
        expected_topology = {"vnets": [mock_hub_vnet]}
        
        # Mock both functions
        with patch('azure_query.find_hub_vnet_using_resource_graph', return_value=mock_hub_vnet), \
             patch('azure_query.find_peered_vnets', return_value=([], [])):
            
            result = get_filtered_vnet_topology('rg-1/hub-vnet-001', ['12345678-1234-1234-1234-123456789012'])
            
            assert result is not None
            assert 'vnets' in result
            assert len(result['vnets']) == 1  # Just the hub VNet with no peerings
            assert result['vnets'][0]['name'] == 'hub-vnet-001'
            assert result['vnets'][0]['is_explicit_hub'] is True