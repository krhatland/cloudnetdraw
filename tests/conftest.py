"""
Pytest configuration and shared fixtures for CloudNet Draw tests
"""
import pytest
import json
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
from pathlib import Path


@pytest.fixture
def sample_config_dict():
    """Basic configuration dictionary for testing"""
    return {
        'thresholds': {
            'hub_peering_count': 3
        },
        'styles': {
            'hub': {
                'border_color': '#0078D4',
                'fill_color': '#E6F1FB',
                'font_color': '#004578',
                'line_color': '#0078D4',
                'text_align': 'left'
            },
            'spoke': {
                'border_color': '#CC6600',
                'fill_color': '#f2f7fc',
                'font_color': '#CC6600',
                'line_color': '#0078D4',
                'text_align': 'left'
            },
            'non_peered': {
                'border_color': 'gray',
                'fill_color': '#f5f5f5',
                'font_color': 'gray',
                'line_color': 'gray',
                'text_align': 'left'
            }
        },
        'subnet': {
            'border_color': '#C8C6C4',
            'fill_color': '#FAF9F8',
            'font_color': '#323130',
            'text_align': 'left'
        },
        'layout': {
            'canvas': {
                'padding': 20
            },
            'zone': {
                'spacing': 500
            },
            'vnet': {
                'width': 400,
                'spacing_x': 450,
                'spacing_y': 100
            },
            'hub': {
                'spacing_x': 450,
                'spacing_y': 400,
                'width': 400,
                'height': 50
            },
            'spoke': {
                'spacing_y': 100,
                'start_y': 200,
                'width': 400,
                'height': 50,
                'left_x': -100,
                'right_x': 900
            },
            'non_peered': {
                'spacing_y': 100,
                'start_y': 200,
                'x': 1450,
                'width': 400,
                'height': 50
            },
            'subnet': {
                'width': 350,
                'height': 20,
                'padding_x': 25,
                'padding_y': 55,
                'spacing_y': 30
            }
        },
        'edges': {
            'stroke_color': '#0078D4',
            'stroke_width': 2,
            'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;'
        },
        'icons': {
            'vnet': {'path': 'img/lib/azure2/networking/Virtual_Networks.svg', 'width': 20, 'height': 20},
            'firewall': {'path': 'img/lib/azure2/networking/Firewalls.svg', 'width': 20, 'height': 20},
            'vpn_gateway': {'path': 'img/lib/azure2/networking/Virtual_Network_Gateways.svg', 'width': 20, 'height': 20},
            'expressroute': {'path': 'img/lib/azure2/networking/ExpressRoute_Circuits.svg', 'width': 20, 'height': 20},
            'nsg': {'path': 'img/lib/azure2/networking/Network_Security_Groups.svg', 'width': 16, 'height': 16},
            'route_table': {'path': 'img/lib/azure2/networking/Route_Tables.svg', 'width': 16, 'height': 16},
            'subnet': {'path': 'img/lib/azure2/networking/Subnet.svg', 'width': 20, 'height': 12},
            'virtual_hub': {'path': 'img/lib/azure2/networking/Virtual_WANs.svg', 'width': 20, 'height': 20}
        },
        'icon_positioning': {
            'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5},
            'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
            'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
        },
        'drawio': {
            'canvas': {
                'dx': '371', 'dy': '1462', 'grid': '0', 'gridSize': '10',
                'background': '#ffffff', 'pageWidth': '827', 'pageHeight': '1169'
            },
            'group': {'extra_height': 20, 'connectable': '0'}
        }
    }


@pytest.fixture
def mock_config_file(sample_config_dict):
    """Mock config file with sample data"""
    yaml_content = """
thresholds:
  hub_peering_count: 3
styles:
  hub:
    border_color: "#0078D4"
    fill_color: "#E6F1FB"
    font_color: "#004578"
    text_align: "left"
"""
    with patch('builtins.open', mock_open(read_data=yaml_content)), \
         patch('yaml.safe_load', return_value=sample_config_dict):
        yield


@pytest.fixture
def sample_vnets():
    """Sample VNet data for testing"""
    return [
        {
            'name': 'hub-vnet',
            'address_space': '10.0.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.0.0.0/24', 'nsg': 'Yes', 'udr': 'No'},
                {'name': 'GatewaySubnet', 'address': '10.0.1.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'peerings': ['hub-vnet_to_spoke1', 'hub-vnet_to_spoke2', 'hub-vnet_to_spoke3'],
            'peerings_count': 3,
            'subscription_name': 'test-subscription',
            'expressroute': 'Yes',
            'vpn_gateway': 'Yes',
            'firewall': 'No'
        },
        {
            'name': 'spoke1',
            'address_space': '10.1.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.1.0.0/24', 'nsg': 'Yes', 'udr': 'Yes'}
            ],
            'peerings': ['spoke1_to_hub-vnet'],
            'peerings_count': 1,
            'subscription_name': 'test-subscription',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No'
        },
        {
            'name': 'spoke2',
            'address_space': '10.2.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.2.0.0/24', 'nsg': 'No', 'udr': 'Yes'},
                {'name': 'web-tier', 'address': '10.2.1.0/24', 'nsg': 'Yes', 'udr': 'Yes'}
            ],
            'peerings': ['spoke2_to_hub-vnet', 'spoke2_to_spoke3'],
            'peerings_count': 2,
            'subscription_name': 'test-subscription',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'Yes'
        },
        {
            'name': 'spoke3',
            'address_space': '10.3.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.3.0.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'peerings': ['spoke3_to_hub-vnet', 'spoke3_to_spoke2'],
            'peerings_count': 2,
            'subscription_name': 'test-subscription',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No'
        },
        {
            'name': 'isolated-vnet',
            'address_space': '10.4.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.4.0.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'peerings': [],
            'peerings_count': 0,
            'subscription_name': 'test-subscription',
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No'
        }
    ]


@pytest.fixture
def sample_topology(sample_vnets):
    """Complete topology data structure"""
    return {
        'vnets': sample_vnets
    }


@pytest.fixture
def mock_azure_credentials():
    """Mock Azure credentials"""
    mock_creds = Mock()
    mock_creds.get_token.return_value = Mock(token='fake-token')
    return mock_creds


@pytest.fixture
def mock_subscription_list():
    """Mock subscription list from Azure"""
    return [
        Mock(subscription_id='sub-1', display_name='Test Subscription 1'),
        Mock(subscription_id='sub-2', display_name='Test Subscription 2'),
        Mock(subscription_id='sub-3', display_name='Test Subscription 3')
    ]


@pytest.fixture
def mock_network_client():
    """Mock Azure NetworkManagementClient"""
    mock_client = Mock()
    
    # Mock VNet data
    mock_vnet = Mock()
    mock_vnet.name = 'test-vnet'
    mock_vnet.id = '/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/test-vnet'
    mock_vnet.address_space.address_prefixes = ['10.0.0.0/16']
    
    # Mock subnet data
    mock_subnet = Mock()
    mock_subnet.name = 'default'
    mock_subnet.address_prefix = '10.0.0.0/24'
    mock_subnet.network_security_group = None
    mock_subnet.route_table = None
    mock_vnet.subnets = [mock_subnet]
    
    mock_client.virtual_networks.list_all.return_value = [mock_vnet]
    mock_client.virtual_network_peerings.list.return_value = []
    mock_client.virtual_wans.list.return_value = []
    
    return mock_client


@pytest.fixture
def temp_directory():
    """Temporary directory for file operations"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def mock_file_operations():
    """Mock file operations"""
    with patch('builtins.open', mock_open()) as mock_file:
        yield mock_file


@pytest.fixture
def sample_azure_env_vars():
    """Sample environment variables for Azure authentication"""
    return {
        'AZURE_CLIENT_ID': 'test-client-id',
        'AZURE_CLIENT_SECRET': 'test-client-secret',
        'AZURE_TENANT_ID': 'test-tenant-id'
    }


@pytest.fixture
def mock_azure_env(sample_azure_env_vars):
    """Mock Azure environment variables"""
    with patch.dict(os.environ, sample_azure_env_vars):
        yield


@pytest.fixture
def virtual_hub_vnet():
    """Sample Virtual Hub VNet for testing"""
    return {
        'name': 'virtual-hub-1',
        'address_space': '10.0.0.0/16',
        'type': 'virtual_hub',
        'subnets': [],
        'peerings': [],
        'peerings_count': 0,
        'subscription_name': 'test-subscription',
        'expressroute': 'Yes',
        'vpn_gateway': 'Yes',
        'firewall': 'Yes'
    }


@pytest.fixture
def large_topology():
    """Large topology for performance testing"""
    vnets = []
    
    # Create 5 hubs
    for i in range(5):
        hub = {
            'name': f'hub-{i}',
            'address_space': f'10.{i}.0.0/16',
            'subnets': [
                {'name': 'default', 'address': f'10.{i}.0.0/24', 'nsg': 'Yes', 'udr': 'Yes'},
                {'name': 'GatewaySubnet', 'address': f'10.{i}.1.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'peerings': [f'hub-{i}_to_spoke{i}-{j}' for j in range(10)],
            'peerings_count': 10,
            'subscription_name': f'test-subscription-{i}',
            'expressroute': 'Yes' if i % 2 == 0 else 'No',
            'vpn_gateway': 'Yes',
            'firewall': 'Yes' if i % 3 == 0 else 'No'
        }
        vnets.append(hub)
        
        # Create 10 spokes per hub
        for j in range(10):
            spoke = {
                'name': f'spoke{i}-{j}',
                'address_space': f'10.{i+10}.{j}.0/24',
                'subnets': [
                    {'name': 'default', 'address': f'10.{i+10}.{j}.0/26', 'nsg': 'Yes', 'udr': 'Yes'}
                ],
                'peerings': [f'spoke{i}-{j}_to_hub-{i}'],
                'peerings_count': 1,
                'subscription_name': f'test-subscription-{i}',
                'expressroute': 'No',
                'vpn_gateway': 'No',
                'firewall': 'No'
            }
            vnets.append(spoke)
    
    return {'vnets': vnets}


# Parameterized test data
@pytest.fixture(params=[
    (0, 'spoke'),
    (1, 'spoke'),
    (2, 'spoke'),
    (3, 'hub'),
    (5, 'hub'),
    (10, 'hub')
])
def hub_classification_data(request):
    """Parameterized data for hub classification tests"""
    return request.param


@pytest.fixture(params=[
    (1, 1), (3, 1), (6, 1),    # single column
    (7, 2), (10, 2), (15, 2)   # dual column
])
def spoke_layout_data(request):
    """Parameterized data for spoke layout tests"""
    return request.param


@pytest.fixture(params=[
    "8-4-4-4-12",  # Valid UUID format
    "subscription-name",  # Name format
    "invalid-format",  # Invalid format
    ""  # Empty string
])
def subscription_id_data(request):
    """Parameterized data for subscription ID validation tests"""
    return request.param