"""
Unit tests for peering logic and VNet relationship handling
"""
import pytest
from unittest.mock import Mock, patch

# Import functions under test
from cloudnetdraw.topology import (
    determine_hub_for_spoke,
    create_vnet_id_mapping
)
from cloudnetdraw.utils import extract_vnet_name_from_resource_id


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

    def test_extract_vnet_name_empty_name(self):
        """Test handling of empty VNet name in resource ID"""
        resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-1/providers/Microsoft.Network/virtualNetworks/"
        result = extract_vnet_name_from_resource_id(resource_id)
        assert result == ""


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