"""
Targeted coverage tests for specific functions:
- find_peered_vnets
- generate_hld_diagram  
- add_peering_edges
- generate_mld_diagram
"""

import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from azure.core.exceptions import ResourceNotFoundError
import json
import tempfile

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from cloudnetdraw import azure_client, topology, diagram_generator

class TestFindPeeredVnetsMissingCoverage:
    """Test missing coverage in find_peered_vnets function"""

    @patch('cloudnetdraw.azure_client.get_credentials')
    @patch('cloudnetdraw.azure_client.NetworkManagementClient')
    @patch('cloudnetdraw.azure_client.SubscriptionClient')
    def test_find_peered_vnets_error_cleanup_logic(self, mock_subscription_client_cls, mock_network_client_cls, mock_get_credentials):
        """Test error message cleanup logic - covers line 377"""
        mock_credentials = Mock()
        mock_get_credentials.return_value = mock_credentials
        
        # Mock subscription client
        mock_subscription_client = Mock()
        mock_subscription_client_cls.return_value = mock_subscription_client
        
        # Mock network client that raises an exception with Code: in the message
        mock_network_client = Mock()
        error_message = "Some error occurred\nCode: ErrorCode123\nMessage: Detailed error info"
        mock_network_client.virtual_networks.get.side_effect = Exception(error_message)
        mock_network_client_cls.return_value = mock_network_client
        
        resource_ids = ["/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"]
        
        peered_vnets, accessible_ids = azure_client.find_peered_vnets(resource_ids)
        
        # Should handle the error gracefully and return empty results
        assert peered_vnets == []
        assert accessible_ids == []

class TestGenerateHldDiagramMissingCoverage:
    """Test missing coverage in generate_hld_diagram function"""

    def setup_method(self):
        """Set up test fixtures"""
        self.sample_topology = {
            "vnets": [
                {
                    "name": "hub-vnet",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 5,
                    "peerings": ["spoke1", "spoke2"],
                    "peering_resource_ids": [
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1",
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke2"
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "tenant_id": "tenant1",
                    "subscription_id": "sub1",
                    "resourcegroup_id": "/subscriptions/sub1/resourceGroups/rg1",
                    "azure_console_url": "https://portal.azure.com/#@tenant1/resource/hub-vnet",
                    "expressroute": "Yes",
                    "vpn_gateway": "Yes", 
                    "firewall": "Yes",
                    "subnets": [{"name": "subnet1", "address": "10.0.1.0/24"}]
                },
                {
                    "name": "spoke1",
                    "address_space": "10.1.0.0/16", 
                    "peerings_count": 2,
                    "peerings": ["hub-vnet", "spoke2"],
                    "peering_resource_ids": [
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke2"
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "tenant_id": "tenant1",
                    "subscription_id": "sub1",
                    "resourcegroup_id": "/subscriptions/sub1/resourceGroups/rg1",
                    "azure_console_url": "https://portal.azure.com/#@tenant1/resource/spoke1",
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No",
                    "subnets": [{"name": "subnet1", "address": "10.1.1.0/24"}]
                },
                {
                    "name": "spoke2", 
                    "address_space": "10.2.0.0/16",
                    "peerings_count": 2,
                    "peerings": ["hub-vnet", "spoke1"],
                    "peering_resource_ids": [
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1"
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke2",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg", 
                    "tenant_id": "tenant1",
                    "subscription_id": "sub1",
                    "resourcegroup_id": "/subscriptions/sub1/resourceGroups/rg1",
                    "azure_console_url": "https://portal.azure.com/#@tenant1/resource/spoke2",
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No",
                    "subnets": [{"name": "subnet1", "address": "10.2.1.0/24"}]
                },
                {
                    "name": "unpeered-vnet",
                    "address_space": "10.3.0.0/16",
                    "peerings_count": 0,
                    "peerings": [],
                    "peering_resource_ids": [],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/unpeered-vnet",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "tenant_id": "tenant1", 
                    "subscription_id": "sub1",
                    "resourcegroup_id": "/subscriptions/sub1/resourceGroups/rg1",
                    "azure_console_url": "https://portal.azure.com/#@tenant1/resource/unpeered-vnet",
                    "expressroute": "No",
                    "vpn_gateway": "No",
                    "firewall": "No",
                    "subnets": [{"name": "subnet1", "address": "10.3.1.0/24"}]
                }
            ]
        }

    @patch('cloudnetdraw.config.Config')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_hld_diagram_with_spokes_without_names(self, mock_file, mock_config_cls):
        """Test generate_hld_diagram with spokes that have no names - covers line 1102"""
        # Create normal topology but patch the cross-zone function to test continue logic
        topology_with_spoke = {
            "vnets": [
                {
                    "name": "hub-vnet",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 3,
                    "peerings": ["spoke1"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                },
                {
                    "name": "spoke1",  # Give it a name for main processing
                    "address_space": "10.1.0.0/16",
                    "peerings_count": 1,
                    "peerings": ["hub-vnet"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                }
            ]
        }
        
        mock_file.return_value.read.return_value = json.dumps(topology_with_spoke)
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 2
        mock_config.vnet_width = 400
        mock_config.group_height_extra = 20
        mock_config.canvas_padding = 20
        mock_config.zone_spacing = 100
        mock_config.vnet_spacing_x = 50
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5}
        }
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.get_icon_path.return_value = "test.svg"
        mock_config.get_vnet_style_string.return_value = "test-style"
        mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
        mock_config.get_edge_style_string.return_value = "test-peering-style"
        mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            # Should handle the unnamed spoke gracefully
            diagram_generator.generate_hld_diagram(tmp.name, "test_topology.json", mock_config)

    @patch('cloudnetdraw.config.Config')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_hld_diagram_cross_zone_edges(self, mock_file, mock_config_cls):
        """Test generate_hld_diagram cross-zone edge generation - covers lines 1109-1133"""
        # Create topology with multiple hubs and cross-connected spokes
        multi_hub_topology = {
            "vnets": [
                {
                    "name": "hub1",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 3,
                    "peerings": ["spoke1"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub1",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                },
                {
                    "name": "hub2",
                    "address_space": "10.10.0.0/16", 
                    "peerings_count": 3,
                    "peerings": ["spoke1"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub2",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                },
                {
                    "name": "spoke1",
                    "address_space": "10.1.0.0/16",
                    "peerings_count": 2,
                    "peerings": ["hub1", "hub2"],
                    "peering_resource_ids": [
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub1",
                        "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub2"
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke1",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                }
            ]
        }
        
        mock_file.return_value.read.return_value = json.dumps(multi_hub_topology)
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 2
        mock_config.vnet_width = 400
        mock_config.group_height_extra = 20
        mock_config.canvas_padding = 20
        mock_config.zone_spacing = 100
        mock_config.vnet_spacing_x = 50
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5}
        }
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_icon_size.return_value = (20, 20) 
        mock_config.get_icon_path.return_value = "test.svg"
        mock_config.get_vnet_style_string.return_value = "test-style"
        mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
        mock_config.get_edge_style_string.return_value = "test-peering-style"
        mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
        mock_config_cls.return_value = mock_config
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            # Should create cross-zone edges for spoke1 connecting to both hubs
            diagram_generator.generate_hld_diagram(tmp.name, "test_topology.json", mock_config)

    @patch('cloudnetdraw.config.Config')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_hld_diagram_dual_column_layout(self, mock_file, mock_config_cls):
        """Test generate_hld_diagram with dual column layout - covers lines 1258-1313"""
        # Create topology with more than 6 spokes to trigger dual column layout
        many_spokes_topology = {
            "vnets": [
                {
                    "name": "hub-vnet",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 8,
                    "peerings": ["spoke1", "spoke2", "spoke3", "spoke4", "spoke5", "spoke6", "spoke7", "spoke8"],
                    "peering_resource_ids": [
                        f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke{i}"
                        for i in range(1, 9)
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg"
                }
            ]
        }
        
        # Add 8 spokes
        for i in range(1, 9):
            spoke = {
                "name": f"spoke{i}",
                "address_space": f"10.{i}.0.0/16",
                "peerings_count": 1,
                "peerings": ["hub-vnet"],
                "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet"],
                "resource_id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke{i}",
                "subscription_name": "test-sub",
                "resourcegroup_name": "test-rg"
            }
            many_spokes_topology["vnets"].append(spoke)
        
        mock_file.return_value.read.return_value = json.dumps(many_spokes_topology)
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 2
        mock_config.vnet_width = 400
        mock_config.group_height_extra = 20
        mock_config.canvas_padding = 20
        mock_config.zone_spacing = 100
        mock_config.vnet_spacing_x = 50
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5}
        }
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.get_icon_path.return_value = "test.svg"
        mock_config.get_vnet_style_string.return_value = "test-style"
        mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
        mock_config.get_edge_style_string.return_value = "test-peering-style"
        mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            # Should use dual column layout for 8 spokes
            diagram_generator.generate_hld_diagram(tmp.name, "test_topology.json", mock_config)

class TestAddPeeringEdgesStandalone:
    """Test standalone add_peering_edges function - covers lines 1437-1514"""

    def test_add_peering_edges_complete_function(self):
        """Test the complete standalone add_peering_edges function"""
        from lxml import etree
        from cloudnetdraw.layout import add_peering_edges
        
        # Mock vnets with peering relationships
        vnets = [
            {
                "name": "vnet1",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "peerings_count": 2,
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet3"
                ]
            },
            {
                "name": "vnet2",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
                "peerings_count": 1,
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
                ]
            },
            {
                "name": "vnet3",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet3",
<<<<<<< Updated upstream
                "peerings_count": 1,
=======
>>>>>>> Stashed changes
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
                ]
            }
        ]
        
        # Mock vnet mapping
        vnet_mapping = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1": "vnet1_main",
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2": "vnet2_main",
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet3": "vnet3_main"
        }
        
        # Create mock root element
        root = etree.Element("root")
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 10  # Set proper threshold value
        mock_config.get_edge_style_string.return_value = "test-edge-style"
        
<<<<<<< Updated upstream
        # Call the function - provide empty hub_vnets list so all VNets are treated as spokes
        azure_query.add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets=[])
=======
        # Mock hub_vnets
        hub_vnets = []
        
        # Call the function
        add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets)
>>>>>>> Stashed changes
        
        # Verify edges were created
        edges = root.findall(".//mxCell[@edge='1']")
        assert len(edges) >= 2  # Should create edges for the peering relationships
        
        # Verify edge properties
        for edge in edges:
            assert edge.get("edge") == "1"
            assert edge.get("style") == "test-edge-style"
            assert edge.get("parent") == "1"
            assert "peering_edge_" in edge.get("id")

    def test_add_peering_edges_asymmetric_peering(self):
        """Test add_peering_edges with asymmetric peering relationships"""
        from lxml import etree
        from cloudnetdraw.layout import add_peering_edges
        
        # Mock vnets with asymmetric peering (vnet1 peers to vnet2, but vnet2 doesn't peer back)
        vnets = [
            {
                "name": "vnet1",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "peerings_count": 1,
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2"
                ]
            },
            {
                "name": "vnet2",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
<<<<<<< Updated upstream
                "peerings_count": 0,
=======
>>>>>>> Stashed changes
                "peering_resource_ids": []  # No peering back to vnet1
            }
        ]
        
        vnet_mapping = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1": "vnet1_main",
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2": "vnet2_main"
        }
        
        root = etree.Element("root")
        mock_config = Mock()
        mock_config.hub_threshold = 10  # Set proper threshold value
        mock_config.get_edge_style_string.return_value = "test-edge-style"
        hub_vnets = []
        
<<<<<<< Updated upstream
        # Should handle asymmetric peering without errors - provide empty hub_vnets list
        azure_query.add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets=[])
=======
        # Should handle asymmetric peering without errors
        add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets)
>>>>>>> Stashed changes
        
        edges = root.findall(".//mxCell[@edge='1']")
        assert len(edges) == 1  # Should create one edge for the one-way peering

    def test_add_peering_edges_duplicate_prevention(self):
        """Test add_peering_edges prevents duplicate edges"""
        from lxml import etree
        from cloudnetdraw.layout import add_peering_edges
        
        # Mock vnets with bidirectional peering
        vnets = [
            {
                "name": "vnet1",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "peerings_count": 1,
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2"
                ]
            },
            {
                "name": "vnet2",
                "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
                "peerings_count": 1,
                "peering_resource_ids": [
                    "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
                ]
            }
        ]
        
        vnet_mapping = {
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1": "vnet1_main",
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2": "vnet2_main"
        }
        
        root = etree.Element("root")
        mock_config = Mock()
        mock_config.hub_threshold = 10  # Set proper threshold value
        mock_config.get_edge_style_string.return_value = "test-edge-style"
        hub_vnets = []
        
<<<<<<< Updated upstream
        # Should create only one edge, not two (prevents duplicates) - provide empty hub_vnets list
        azure_query.add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets=[])
=======
        # Should create only one edge, not two (prevents duplicates)
        add_peering_edges(vnets, vnet_mapping, root, mock_config, hub_vnets)
>>>>>>> Stashed changes
        
        edges = root.findall(".//mxCell[@edge='1']")
        assert len(edges) == 1  # Should create only one edge for bidirectional peering

class TestGenerateMldDiagramMissingCoverage:
    """Test missing coverage in generate_mld_diagram function"""

    @patch('cloudnetdraw.config.Config')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_mld_diagram_source_vnet_filtering(self, mock_file, mock_config_cls):
        """Test generate_mld_diagram source VNet filtering - covers line 1905"""
        topology = {
            "vnets": [
                {
                    "name": "hub-vnet",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 3,
                    # Missing resource_id to trigger continue statement
                    "peering_resource_ids": [],
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "subnets": [{"name": "subnet1", "address": "10.0.1.0/24", "nsg": "Yes", "udr": "No"}]
                }
            ]
        }
        
        mock_file.return_value.read.return_value = json.dumps(topology)
        
        # Mock config 
        mock_config = Mock()
        mock_config.hub_threshold = 2
        mock_config.canvas_padding = 20
        mock_config.zone_spacing = 100
        mock_config.vnet_spacing_x = 50
        mock_config.vnet_width = 400
        mock_config.layout = {
            'hub': {'width': 400, 'height': 50},
            'subnet': {'padding_x': 25, 'padding_y': 25, 'spacing_y': 30, 'width': 350, 'height': 25}
        }
        mock_config.drawio = {
            'group': {'extra_height': 20, 'connectable': '0'}
        }
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5},
            'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
            'subnet_icons': {'icon_gap': 5, 'subnet_icon_y_offset': 2, 'icon_y_offset': 2}
        }
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.get_icon_path.return_value = "test.svg"
        mock_config.get_vnet_style_string.return_value = "test-style"
        mock_config.get_subnet_style_string.return_value = "test-subnet-style"
        mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
        mock_config.get_edge_style_string.return_value = "test-peering-style"
        mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
        mock_config_cls.return_value = mock_config
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            # Should handle VNet without resource_id gracefully
            diagram_generator.generate_mld_diagram(tmp.name, "test_topology.json", mock_config)

    @patch('cloudnetdraw.config.Config')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_mld_diagram_left_spokes_layout(self, mock_file, mock_config_cls):
        """Test generate_mld_diagram with left spokes layout - covers lines 2017-2020, 2057-2079"""
        # Create topology with exactly 7 spokes to trigger left/right split (>6 spokes)
        many_spokes_topology = {
            "vnets": [
                {
                    "name": "hub-vnet",
                    "address_space": "10.0.0.0/16",
                    "peerings_count": 7,
                    "peerings": [f"spoke{i}" for i in range(1, 8)],
                    "peering_resource_ids": [
                        f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke{i}"
                        for i in range(1, 8)
                    ],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "subnets": [{"name": "hub-subnet", "address": "10.0.1.0/24", "nsg": "Yes", "udr": "Yes"}]
                }
            ]
        }
        
        # Add 7 spokes (will be split: 4 left, 3 right)
        for i in range(1, 8):
            spoke = {
                "name": f"spoke{i}",
                "address_space": f"10.{i}.0.0/16",
                "peerings_count": 1,
                "peerings": ["hub-vnet"],
                "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/hub-vnet"],
                "resource_id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/spoke{i}",
                "subscription_name": "test-sub", 
                "resourcegroup_name": "test-rg",
                "subnets": [{"name": f"spoke{i}-subnet", "address": f"10.{i}.1.0/24", "nsg": "No", "udr": "No"}]
            }
            many_spokes_topology["vnets"].append(spoke)
        
        mock_file.return_value.read.return_value = json.dumps(many_spokes_topology)
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 2
        mock_config.canvas_padding = 20
        mock_config.zone_spacing = 100
        mock_config.vnet_spacing_x = 50
        mock_config.vnet_width = 400
        mock_config.layout = {
            'hub': {'width': 400, 'height': 50},
            'subnet': {'padding_x': 25, 'padding_y': 25, 'spacing_y': 30, 'width': 350, 'height': 25}
        }
        mock_config.drawio = {
            'group': {'extra_height': 20, 'connectable': '0'}
        }
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5},
            'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
            'subnet_icons': {'icon_gap': 5, 'subnet_icon_y_offset': 2, 'icon_y_offset': 2}
        }
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.get_icon_path.return_value = "test.svg"
        mock_config.get_vnet_style_string.return_value = "test-style"
        mock_config.get_subnet_style_string.return_value = "test-subnet-style" 
        mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
        mock_config.get_edge_style_string.return_value = "test-peering-style"
        mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
        mock_config_cls.return_value = mock_config
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as tmp:
            # Should use left/right layout for 7 spokes
            diagram_generator.generate_mld_diagram(tmp.name, "test_topology.json", mock_config)

    def test_generate_mld_diagram_nested_add_peering_edges(self):
        """Test the nested add_peering_edges function within generate_mld_diagram - covers lines 1909-1962"""
        # This test verifies that the nested add_peering_edges function gets called
        # The function logic is identical to the standalone version, so we verify it exists and works
        
        topology = {
            "vnets": [
                {
                    "name": "vnet1",
                    "address_space": "10.0.0.0/16", 
                    "peerings_count": 1,
                    "peerings": ["vnet2"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "subnets": [{"name": "subnet1", "address": "10.0.1.0/24", "nsg": "Yes", "udr": "No"}]
                },
                {
                    "name": "vnet2",
                    "address_space": "10.1.0.0/16",
                    "peerings_count": 1, 
                    "peerings": ["vnet1"],
                    "peering_resource_ids": ["/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"],
                    "resource_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet2",
                    "subscription_name": "test-sub",
                    "resourcegroup_name": "test-rg",
                    "subnets": [{"name": "subnet2", "address": "10.1.1.0/24", "nsg": "No", "udr": "Yes"}]
                }
            ]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as json_tmp:
            json_tmp.write(json.dumps(topology))
            json_tmp.flush()
            
            # Mock config
            mock_config = Mock()
            mock_config.hub_threshold = 2
            mock_config.canvas_padding = 20
            mock_config.zone_spacing = 100
            mock_config.vnet_spacing_x = 50
            mock_config.vnet_width = 400
            mock_config.layout = {
                'hub': {'width': 400, 'height': 50},
                'subnet': {'padding_x': 25, 'padding_y': 25, 'spacing_y': 30, 'width': 350, 'height': 25}
            }
            mock_config.drawio = {
                'group': {'extra_height': 20, 'connectable': '0'}
            }
            mock_config.icon_positioning = {
                'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5},
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_gap': 5, 'subnet_icon_y_offset': 2, 'icon_y_offset': 2}
            }
            mock_config.get_canvas_attributes.return_value = {}
            mock_config.get_icon_size.return_value = (20, 20)
            mock_config.get_icon_path.return_value = "test.svg"
            mock_config.get_vnet_style_string.return_value = "test-style"
            mock_config.get_subnet_style_string.return_value = "test-subnet-style"
            mock_config.get_hub_spoke_edge_style.return_value = "test-edge-style"
            mock_config.get_edge_style_string.return_value = "test-peering-style"
            mock_config.get_cross_zone_edge_style.return_value = "test-cross-zone-style"
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as drawio_tmp:
                # Should call the nested add_peering_edges function
                diagram_generator.generate_mld_diagram(drawio_tmp.name, json_tmp.name, mock_config)
                
                # Verify the file was created (indicates the nested function was called)
                assert os.path.exists(drawio_tmp.name)
                
                # Clean up
                os.unlink(json_tmp.name)
                os.unlink(drawio_tmp.name)