"""
Unit tests to improve code coverage for uncovered branches and error handling paths
"""
import pytest
import json
import tempfile
import os
from unittest.mock import patch, MagicMock, Mock
from azure.core.exceptions import ResourceNotFoundError

from azure_query import (
    extract_resource_group, parse_vnet_identifier, determine_hub_for_spoke,
    extract_vnet_name_from_resource_id, create_vnet_id_mapping,
    main, query_command, hld_command, mld_command
)


class TestErrorHandling:
    """Test error handling paths and edge cases"""
    
    def test_parse_vnet_identifier_invalid_resource_id_parts(self):
        """Test parse_vnet_identifier with invalid resource ID parts"""
        # Test insufficient parts
        with pytest.raises(ValueError, match="Invalid VNet resource ID format"):
            parse_vnet_identifier("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network")
        
        # Test wrong provider
        with pytest.raises(ValueError, match="Invalid VNet resource ID format"):
            parse_vnet_identifier("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm")
        
        # Test wrong resource type
        with pytest.raises(ValueError, match="Invalid VNet resource ID format"):
            parse_vnet_identifier("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/ip")
    
    def test_parse_vnet_identifier_invalid_slash_format(self):
        """Test parse_vnet_identifier with invalid slash format"""
        with pytest.raises(ValueError, match="Invalid VNet identifier format"):
            parse_vnet_identifier("rg/vnet/extra/parts")
    
    def test_extract_vnet_name_from_resource_id_invalid_format(self):
        """Test extract_vnet_name_from_resource_id with invalid formats"""
        # Test insufficient parts
        with pytest.raises(ValueError, match="Invalid VNet resource ID"):
            extract_vnet_name_from_resource_id("/subscriptions/sub/resourceGroups")
        
        # Test wrong resource type
        with pytest.raises(ValueError, match="Invalid VNet resource ID"):
            extract_vnet_name_from_resource_id("/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/publicIPAddresses/ip")
    
    def test_determine_hub_for_spoke_no_hubs(self):
        """Test determine_hub_for_spoke with no hub VNets"""
        spoke_vnet = {"peerings": ["spoke_to_hub"]}
        result = determine_hub_for_spoke(spoke_vnet, [])
        assert result is None
    
    def test_determine_hub_for_spoke_no_peerings(self):
        """Test determine_hub_for_spoke with spoke that has no peerings"""
        spoke_vnet = {}
        hub_vnets = [{"peerings": ["hub_to_spoke"]}]
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == "hub_0"  # Falls back to first hub
    
    def test_determine_hub_for_spoke_missing_peerings_key(self):
        """Test determine_hub_for_spoke with missing peerings key"""
        spoke_vnet = {"peerings": ["spoke_to_hub"]}
        hub_vnets = [{}]  # Hub without peerings key
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == "hub_0"  # Falls back to first hub
    
    def test_create_vnet_id_mapping_missing_name_keys(self):
        """Test create_vnet_id_mapping with VNets missing name keys"""
        vnets = [{"address_space": "10.0.0.0/16"}]  # Missing name key
        zones = [{
            'hub': {'address_space': '10.1.0.0/16'},  # Missing name key
            'hub_index': 0,
            'spokes': [{'address_space': '10.2.0.0/16'}]  # Missing name key
        }]
        all_non_peered = [{'address_space': '10.3.0.0/16'}]  # Missing name key
        
        mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
        assert mapping == {}  # Should be empty since no names exist


class TestCLIErrorHandling:
    """Test CLI error handling scenarios"""
    
    def test_main_file_not_found_error(self):
        """Test main function handling FileNotFoundError"""
        with patch('sys.argv', ['azure-query.py', 'query', '--subscriptions', 'test-sub']), \
             patch('azure_query.query_command', side_effect=FileNotFoundError("File not found")), \
             patch('azure_query.initialize_credentials'), \
             pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1
    
    def test_main_general_exception(self):
        """Test main function handling general exceptions"""
        with patch('sys.argv', ['azure-query.py', 'query', '--subscriptions', 'test-sub']), \
             patch('azure_query.query_command', side_effect=Exception("General error")), \
             patch('azure_query.initialize_credentials'), \
             pytest.raises(SystemExit) as exc_info:
            main()
        
        assert exc_info.value.code == 1


class TestDiagramGenerationEdgeCases:
    """Test edge cases in diagram generation functions"""
    
    def test_hld_command_file_not_found(self):
        """Test HLD command with missing topology file"""
        args = MagicMock()
        args.topology = "nonexistent.json"
        args.output = "test.drawio"
        args.config_file = "config.yaml"
        args.verbose = False
        
        with pytest.raises(FileNotFoundError):
            hld_command(args)
    
    def test_mld_command_file_not_found(self):
        """Test MLD command with missing topology file"""
        args = MagicMock()
        args.topology = "nonexistent.json"
        args.output = "test.drawio"
        args.config_file = "config.yaml"
        args.verbose = False
        
        with pytest.raises(FileNotFoundError):
            mld_command(args)
    
    def test_hld_generation_with_virtual_hub(self):
        """Test HLD generation with virtual hub VNets"""
        # Create test topology with virtual hub
        test_topology = {
            "vnets": [
                {
                    "name": "virtual-hub-001",
                    "address_space": "10.0.0.0/16",
                    "type": "virtual_hub",
                    "subnets": [],
                    "peerings": [],
                    "peerings_count": 0,
                    "subscription_name": "Test Subscription",
                    "resource_id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Network/virtualHubs/virtual-hub-001",
                    "expressroute": "Yes",
                    "vpn_gateway": "Yes",
                    "firewall": "Yes",
                    "peering_resource_ids": []
                }
            ]
        }
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as topology_file:
            json.dump(test_topology, topology_file)
            topology_path = topology_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            with patch('config.Config') as mock_config:
                # Mock config with required attributes
                mock_config_instance = MagicMock()
                mock_config_instance.hub_threshold = 2
                mock_config_instance.vnet_width = 400
                mock_config_instance.group_height_extra = 50
                mock_config_instance.canvas_padding = 20
                mock_config_instance.zone_spacing = 50
                mock_config_instance.vnet_spacing_x = 450
                mock_config_instance.get_canvas_attributes.return_value = {
                    'dx': '1422', 'dy': '794', 'grid': '1', 'gridSize': '10'
                }
                mock_config_instance.get_icon_size.return_value = (20, 20)
                mock_config_instance.get_icon_path.return_value = "test_icon.svg"
                mock_config_instance.get_vnet_style_string.return_value = "test_style"
                mock_config_instance.get_edge_style_string.return_value = "test_edge_style"
                mock_config_instance.icon_positioning = {
                    'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5}
                }
                mock_config.return_value = mock_config_instance
                
                args = MagicMock()
                args.topology = topology_path
                args.output = output_path
                args.config_file = "config.yaml"
                args.verbose = False
                
                # Should not raise an exception
                hld_command(args)
                
                # Verify output file was created
                assert os.path.exists(output_path)
                
        finally:
            # Clean up temporary files
            for file_path in [topology_path, output_path]:
                if os.path.exists(file_path):
                    os.unlink(file_path)
    
    def test_mld_generation_with_virtual_hub(self):
        """Test MLD generation with virtual hub VNets"""
        # Create test topology with virtual hub
        test_topology = {
            "vnets": [
                {
                    "name": "virtual-hub-001",
                    "address_space": "10.0.0.0/16",
                    "type": "virtual_hub",
                    "subnets": [],
                    "peerings": [],
                    "peerings_count": 0,
                    "subscription_name": "Test Subscription",
                    "resource_id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Network/virtualHubs/virtual-hub-001",
                    "expressroute": "Yes",
                    "vpn_gateway": "Yes",
                    "firewall": "Yes",
                    "peering_resource_ids": []
                }
            ]
        }
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as topology_file:
            json.dump(test_topology, topology_file)
            topology_path = topology_file.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as output_file:
            output_path = output_file.name
        
        try:
            with patch('config.Config') as mock_config:
                # Mock config with required attributes
                mock_config_instance = MagicMock()
                mock_config_instance.hub_threshold = 2
                mock_config_instance.vnet_width = 400
                mock_config_instance.canvas_padding = 20
                mock_config_instance.zone_spacing = 50
                mock_config_instance.vnet_spacing_x = 450
                mock_config_instance.get_canvas_attributes.return_value = {
                    'dx': '1422', 'dy': '794', 'grid': '1', 'gridSize': '10'
                }
                mock_config_instance.get_icon_size.return_value = (20, 20)
                mock_config_instance.get_icon_path.return_value = "test_icon.svg"
                mock_config_instance.get_vnet_style_string.return_value = "test_style"
                mock_config_instance.get_subnet_style_string.return_value = "test_subnet_style"
                mock_config_instance.get_edge_style_string.return_value = "test_edge_style"
                mock_config_instance.layout = {
                    'hub': {'width': 400, 'height': 50},
                    'subnet': {'padding_y': 10, 'spacing_y': 30, 'padding_x': 25, 'width': 350, 'height': 25}
                }
                mock_config_instance.drawio = {
                    'group': {'extra_height': 50, 'connectable': '0'}
                }
                mock_config_instance.icon_positioning = {
                    'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                    'vnet_icons': {'y_offset': 5, 'right_margin': 10, 'icon_gap': 5},
                    'subnet_icons': {'icon_gap': 5, 'subnet_icon_y_offset': 2, 'icon_y_offset': 2}
                }
                mock_config.return_value = mock_config_instance
                
                args = MagicMock()
                args.topology = topology_path
                args.output = output_path
                args.config_file = "config.yaml"
                args.verbose = False
                
                # Should not raise an exception
                mld_command(args)
                
                # Verify output file was created
                assert os.path.exists(output_path)
                
        finally:
            # Clean up temporary files
            for file_path in [topology_path, output_path]:
                if os.path.exists(file_path):
                    os.unlink(file_path)


class TestLayoutCalculationBranches:
    """Test layout calculation branches and edge cases"""
    
    def test_create_vnet_id_mapping_dual_column_layout(self):
        """Test create_vnet_id_mapping with dual column layout (>6 spokes)"""
        vnets = []
        
        # Create 8 spokes to trigger dual column layout
        spokes = []
        for i in range(8):
            spokes.append({'name': f'spoke-{i}'})
        
        zones = [{
            'hub': {'name': 'hub-0'},
            'hub_index': 0,
            'spokes': spokes
        }]
        all_non_peered = []
        
        mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should have hub mapping
        assert mapping['hub-0'] == 'hub_0'
        
        # Should have left and right spoke mappings
        assert 'spoke-0' in mapping  # Should be in left column
        assert 'spoke-4' in mapping  # Should be in right column
        
        # Check that left spokes are mapped correctly
        for i in range(4):  # First 4 spokes go to left
            assert mapping[f'spoke-{i}'] == f'left_spoke0_{i}'
        
        # Check that right spokes are mapped correctly  
        for i in range(4, 8):  # Last 4 spokes go to right
            assert mapping[f'spoke-{i}'] == f'right_spoke0_{i-4}'
    
    def test_create_vnet_id_mapping_single_column_layout(self):
        """Test create_vnet_id_mapping with single column layout (<=6 spokes)"""
        vnets = []
        
        # Create 4 spokes for single column layout
        spokes = []
        for i in range(4):
            spokes.append({'name': f'spoke-{i}'})
        
        zones = [{
            'hub': {'name': 'hub-0'},
            'hub_index': 0,
            'spokes': spokes
        }]
        all_non_peered = []
        
        mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should have hub mapping
        assert mapping['hub-0'] == 'hub_0'
        
        # All spokes should be in right column (single column)
        for i in range(4):
            assert mapping[f'spoke-{i}'] == f'right_spoke0_{i}'
    
    def test_create_vnet_id_mapping_odd_number_spokes(self):
        """Test create_vnet_id_mapping with odd number of spokes in dual column"""
        vnets = []
        
        # Create 7 spokes to test odd number handling
        spokes = []
        for i in range(7):
            spokes.append({'name': f'spoke-{i}'})
        
        zones = [{
            'hub': {'name': 'hub-0'},
            'hub_index': 0,
            'spokes': spokes
        }]
        all_non_peered = []
        
        mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should have hub mapping
        assert mapping['hub-0'] == 'hub_0'
        
        # First 4 spokes should be in left column (ceiling of 7/2 = 4)
        for i in range(4):
            assert mapping[f'spoke-{i}'] == f'left_spoke0_{i}'
        
        # Last 3 spokes should be in right column
        for i in range(4, 7):
            assert mapping[f'spoke-{i}'] == f'right_spoke0_{i-4}'
    
    def test_create_vnet_id_mapping_multiple_zones(self):
        """Test create_vnet_id_mapping with multiple zones"""
        vnets = []
        
        zones = [
            {
                'hub': {'name': 'hub-0'},
                'hub_index': 0,
                'spokes': [{'name': 'spoke-0-0'}, {'name': 'spoke-0-1'}]
            },
            {
                'hub': {'name': 'hub-1'},
                'hub_index': 1,
                'spokes': [{'name': 'spoke-1-0'}, {'name': 'spoke-1-1'}]
            }
        ]
        all_non_peered = [{'name': 'nonpeered-0'}]
        
        mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should have hub mappings for both zones
        assert mapping['hub-0'] == 'hub_0'
        assert mapping['hub-1'] == 'hub_1'
        
        # Zone 0 spokes
        assert mapping['spoke-0-0'] == 'right_spoke0_0'
        assert mapping['spoke-0-1'] == 'right_spoke0_1'
        
        # Zone 1 spokes
        assert mapping['spoke-1-0'] == 'right_spoke1_0'
        assert mapping['spoke-1-1'] == 'right_spoke1_1'
        
        # Non-peered VNet
        assert mapping['nonpeered-0'] == 'nonpeered_spoke0'