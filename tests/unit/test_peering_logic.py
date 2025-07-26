"""
Unit tests for peering logic and VNet relationship handling
"""
import pytest
from unittest.mock import Mock, patch

# Import functions under test
from azure_query import (
    determine_hub_for_spoke,
    parse_peering_name,
    create_vnet_id_mapping
)


class TestHubDetermination:
    """Test hub determination logic for spokes"""

    def test_determine_hub_for_spoke_single_hub(self):
        """Test spoke connection to single hub"""
        spoke_vnet = {
            'name': 'spoke1',
            'peerings': ['spoke1_to_hub1']
        }
        hub_vnets = [
            {
                'name': 'hub1',
                'peerings': ['hub1_to_spoke1', 'hub1_to_spoke2']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'

    def test_determine_hub_for_spoke_multiple_hubs(self):
        """Test spoke connection identification with multiple hubs"""
        spoke_vnet = {
            'name': 'spoke2',
            'peerings': ['spoke2_to_hub2']
        }
        hub_vnets = [
            {
                'name': 'hub1',
                'peerings': ['hub1_to_spoke1']
            },
            {
                'name': 'hub2', 
                'peerings': ['hub2_to_spoke2', 'hub2_to_spoke3']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'

    def test_determine_hub_for_spoke_no_match(self):
        """Test spoke with no hub connections"""
        spoke_vnet = {
            'name': 'orphan-spoke',
            'peerings': ['orphan-spoke_to_other-spoke']
        }
        hub_vnets = [
            {
                'name': 'hub1',
                'peerings': ['hub1_to_spoke1', 'hub1_to_spoke2']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'  # Fallback to first hub

    def test_determine_hub_for_spoke_empty_hubs(self):
        """Test spoke with no hubs available"""
        spoke_vnet = {
            'name': 'spoke1',
            'peerings': ['spoke1_to_hub1']
        }
        hub_vnets = []
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result is None

    def test_determine_hub_for_spoke_no_peerings(self):
        """Test spoke with no peerings"""
        spoke_vnet = {
            'name': 'isolated-spoke',
            'peerings': []
        }
        hub_vnets = [
            {
                'name': 'hub1',
                'peerings': ['hub1_to_spoke1']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'  # Fallback to first hub

    def test_determine_hub_for_spoke_missing_peerings_key(self):
        """Test spoke with missing peerings key"""
        spoke_vnet = {
            'name': 'spoke1'
            # No peerings key
        }
        hub_vnets = [
            {
                'name': 'hub1',
                'peerings': ['hub1_to_spoke1']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'  # Fallback to first hub

    def test_determine_hub_for_spoke_complex_peering_names(self):
        """Test spoke with complex peering names"""
        spoke_vnet = {
            'name': 'spoke-prod-east',
            'peerings': ['spoke-prod-east_to_hub-prod-central']
        }
        hub_vnets = [
            {
                'name': 'hub-prod-central',
                'peerings': ['hub-prod-central_to_spoke-prod-east', 'hub-prod-central_to_spoke-prod-west']
            }
        ]
        
        result = determine_hub_for_spoke(spoke_vnet, hub_vnets)
        assert result == 'hub_0'


class TestPeeringNameParsing:
    """Test peering name parsing functionality"""

    def test_parse_peering_name_underscore_format(self):
        """Test parsing peering name with underscore format"""
        result = parse_peering_name("vnet1_to_vnet2")
        assert result == ("vnet1", "vnet2")

    def test_parse_peering_name_dash_format(self):
        """Test parsing peering name with dash format"""
        result = parse_peering_name("vnet1-to-vnet2")
        assert result == ("vnet1", "vnet2")

    def test_parse_peering_name_direct_reference(self):
        """Test parsing peering name with direct reference"""
        result = parse_peering_name("target-vnet")
        assert result == (None, "target-vnet")

    def test_parse_peering_name_complex_names(self):
        """Test parsing peering names with complex VNet names"""
        result = parse_peering_name("hub-vnet-prod_to_spoke-vnet-dev")
        assert result == ("hub-vnet-prod", "spoke-vnet-dev")

    def test_parse_peering_name_with_numbers(self):
        """Test parsing peering names with numbers"""
        result = parse_peering_name("vnet1-prod_to_vnet2-dev")
        assert result == ("vnet1-prod", "vnet2-dev")

    def test_parse_peering_name_multiple_separators(self):
        """Test parsing peering names with multiple separators"""
        # Should only split on first occurrence
        result = parse_peering_name("vnet_to_hub_to_spoke")
        assert result == (None, "vnet_to_hub_to_spoke")

    def test_parse_peering_name_empty_parts(self):
        """Test parsing peering names with empty parts"""
        result = parse_peering_name("_to_vnet2")
        assert result == ("", "vnet2")
        
        result = parse_peering_name("vnet1_to_")
        assert result == ("vnet1", "")

    def test_parse_peering_name_no_separator(self):
        """Test parsing peering names without separator"""
        result = parse_peering_name("simple-vnet-name")
        assert result == (None, "simple-vnet-name")

    def test_parse_peering_name_mixed_separators(self):
        """Test parsing peering names with mixed separators"""
        # Should prefer underscore format
        result = parse_peering_name("vnet1_to_vnet2-to-vnet3")
        assert result == ("vnet1", "vnet2-to-vnet3")


class TestVNetIdMapping:
    """Test VNet ID mapping creation for diagram generation"""

    def test_create_vnet_id_mapping_single_zone(self):
        """Test VNet ID mapping with single zone"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'spoke1'},
            {'name': 'spoke2'},
            {'name': 'isolated1'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': [
                    {'name': 'spoke1'},
                    {'name': 'spoke2'}
                ]
            }
        ]
        
        all_non_peered = [{'name': 'isolated1'}]
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        assert result['hub1'] == 'hub_0'
        assert result['spoke1'] == 'right_spoke0_0'
        assert result['spoke2'] == 'right_spoke0_1'
        assert result['isolated1'] == 'nonpeered_spoke0'

    def test_create_vnet_id_mapping_multiple_zones(self):
        """Test VNet ID mapping with multiple zones"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'hub2'},
            {'name': 'spoke1'},
            {'name': 'spoke2'},
            {'name': 'spoke3'},
            {'name': 'spoke4'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': [
                    {'name': 'spoke1'},
                    {'name': 'spoke2'}
                ]
            },
            {
                'hub': {'name': 'hub2'},
                'hub_index': 1,
                'spokes': [
                    {'name': 'spoke3'},
                    {'name': 'spoke4'}
                ]
            }
        ]
        
        all_non_peered = []
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        assert result['hub1'] == 'hub_0'
        assert result['hub2'] == 'hub_1'
        assert result['spoke1'] == 'right_spoke0_0'
        assert result['spoke2'] == 'right_spoke0_1'
        assert result['spoke3'] == 'right_spoke1_0'
        assert result['spoke4'] == 'right_spoke1_1'

    def test_create_vnet_id_mapping_dual_column_layout(self):
        """Test VNet ID mapping with dual column layout"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'spoke1'},
            {'name': 'spoke2'},
            {'name': 'spoke3'},
            {'name': 'spoke4'},
            {'name': 'spoke5'},
            {'name': 'spoke6'},
            {'name': 'spoke7'},
            {'name': 'spoke8'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': [
                    {'name': 'spoke1'},
                    {'name': 'spoke2'},
                    {'name': 'spoke3'},
                    {'name': 'spoke4'},
                    {'name': 'spoke5'},
                    {'name': 'spoke6'},
                    {'name': 'spoke7'},
                    {'name': 'spoke8'}
                ]
            }
        ]
        
        all_non_peered = []
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # With 8 spokes (>6), should use dual column layout
        # First 4 spokes go to left column, next 4 to right column
        assert result['hub1'] == 'hub_0'
        assert result['spoke1'] == 'left_spoke0_0'
        assert result['spoke2'] == 'left_spoke0_1'
        assert result['spoke3'] == 'left_spoke0_2'
        assert result['spoke4'] == 'left_spoke0_3'
        assert result['spoke5'] == 'right_spoke0_0'
        assert result['spoke6'] == 'right_spoke0_1'
        assert result['spoke7'] == 'right_spoke0_2'
        assert result['spoke8'] == 'right_spoke0_3'

    def test_create_vnet_id_mapping_odd_number_spokes(self):
        """Test VNet ID mapping with odd number of spokes for dual column"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'spoke1'},
            {'name': 'spoke2'},
            {'name': 'spoke3'},
            {'name': 'spoke4'},
            {'name': 'spoke5'},
            {'name': 'spoke6'},
            {'name': 'spoke7'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': [
                    {'name': 'spoke1'},
                    {'name': 'spoke2'},
                    {'name': 'spoke3'},
                    {'name': 'spoke4'},
                    {'name': 'spoke5'},
                    {'name': 'spoke6'},
                    {'name': 'spoke7'}
                ]
            }
        ]
        
        all_non_peered = []
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # With 7 spokes (>6), should use dual column layout
        # Left column gets 4 spokes, right column gets 3
        assert result['hub1'] == 'hub_0'
        assert result['spoke1'] == 'left_spoke0_0'
        assert result['spoke2'] == 'left_spoke0_1'
        assert result['spoke3'] == 'left_spoke0_2'
        assert result['spoke4'] == 'left_spoke0_3'
        assert result['spoke5'] == 'right_spoke0_0'
        assert result['spoke6'] == 'right_spoke0_1'
        assert result['spoke7'] == 'right_spoke0_2'

    def test_create_vnet_id_mapping_no_spokes(self):
        """Test VNet ID mapping with no spokes"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'isolated1'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': []
            }
        ]
        
        all_non_peered = [{'name': 'isolated1'}]
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        assert result['hub1'] == 'hub_0'
        assert result['isolated1'] == 'nonpeered_spoke0'

    def test_create_vnet_id_mapping_empty_zones(self):
        """Test VNet ID mapping with empty zones"""
        vnets = [
            {'name': 'isolated1'},
            {'name': 'isolated2'}
        ]
        
        zones = []
        
        all_non_peered = [
            {'name': 'isolated1'},
            {'name': 'isolated2'}
        ]
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        assert result['isolated1'] == 'nonpeered_spoke0'
        assert result['isolated2'] == 'nonpeered_spoke1'

    def test_create_vnet_id_mapping_missing_vnets(self):
        """Test VNet ID mapping with missing VNets in zones"""
        vnets = [
            {'name': 'hub1'},
            {'name': 'spoke1'}
        ]
        
        zones = [
            {
                'hub': {'name': 'hub1'},
                'hub_index': 0,
                'spokes': [
                    {'name': 'spoke1'},
                    {'name': 'missing-spoke'}  # This spoke is not in vnets list
                ]
            }
        ]
        
        all_non_peered = []
        
        result = create_vnet_id_mapping(vnets, zones, all_non_peered)
        
        # Should still create mapping for existing VNets
        assert result['hub1'] == 'hub_0'
        assert result['spoke1'] == 'right_spoke0_0'
        assert result['missing-spoke'] == 'right_spoke0_1'  # Still gets mapped