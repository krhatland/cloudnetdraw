"""
Comprehensive tests for validating metadata in DrawIO diagram generation.

This test suite validates that metadata exists and is consistent in both group objects 
and VNet mxCell elements in the DrawIO diagram generation, ensuring proper hyperlink 
functionality and metadata consistency across different VNet types.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from lxml import etree
import tempfile
import os

# Import functions under test
from cloudnetdraw.diagram_generator import (
    generate_diagram,
    generate_hld_diagram,
    generate_mld_diagram,
    _add_vnet_with_optional_subnets,
    generate_hierarchical_id
)


class TestDrawIOMetadataValidation:
    """Test metadata validation in DrawIO diagram generation"""

    @pytest.fixture
    def sample_vnet_with_full_metadata(self):
        """Sample VNet with complete Azure metadata"""
        return {
            'name': 'hub-vnet-001',
            'address_space': '10.0.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.0.0.0/24', 'nsg': 'Yes', 'udr': 'No'},
                {'name': 'GatewaySubnet', 'address': '10.0.1.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-hub/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'tenant_id': '87654321-4321-4321-4321-210987654321',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'subscription_name': 'Production Subscription',
            'resourcegroup_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-hub',
            'resourcegroup_name': 'rg-hub',
            'azure_console_url': 'https://portal.azure.com/#@87654321-4321-4321-4321-210987654321/resource/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-hub/providers/Microsoft.Network/virtualNetworks/hub-vnet-001',
            'peerings_count': 3,
            'expressroute': 'Yes',
            'vpn_gateway': 'Yes',
            'firewall': 'No'
        }

    @pytest.fixture
    def sample_spoke_vnet_with_metadata(self):
        """Sample spoke VNet with complete Azure metadata"""
        return {
            'name': 'spoke-vnet-001',
            'address_space': '10.1.0.0/16',
            'subnets': [
                {'name': 'web-subnet', 'address': '10.1.0.0/24', 'nsg': 'Yes', 'udr': 'Yes'},
                {'name': 'app-subnet', 'address': '10.1.1.0/24', 'nsg': 'Yes', 'udr': 'Yes'}
            ],
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-spoke/providers/Microsoft.Network/virtualNetworks/spoke-vnet-001',
            'tenant_id': '87654321-4321-4321-4321-210987654321',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'subscription_name': 'Production Subscription',
            'resourcegroup_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-spoke',
            'resourcegroup_name': 'rg-spoke',
            'azure_console_url': 'https://portal.azure.com/#@87654321-4321-4321-4321-210987654321/resource/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-spoke/providers/Microsoft.Network/virtualNetworks/spoke-vnet-001',
            'peerings_count': 1,
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No'
        }

    @pytest.fixture
    def sample_virtual_hub_with_metadata(self):
        """Sample Virtual Hub with complete Azure metadata"""
        return {
            'name': 'virtual-hub-001',
            'address_space': '10.100.0.0/24',
            'type': 'virtual_hub',
            'subnets': [],  # Virtual hubs don't have traditional subnets
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-vwan/providers/Microsoft.Network/virtualHubs/virtual-hub-001',
            'tenant_id': '87654321-4321-4321-4321-210987654321',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'subscription_name': 'Production Subscription',
            'resourcegroup_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-vwan',
            'resourcegroup_name': 'rg-vwan',
            'azure_console_url': 'https://portal.azure.com/#@87654321-4321-4321-4321-210987654321/resource/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-vwan/providers/Microsoft.Network/virtualHubs/virtual-hub-001',
            'peerings_count': 0,
            'expressroute': 'Yes',
            'vpn_gateway': 'Yes',
            'firewall': 'Yes'
        }

    @pytest.fixture
    def sample_nonpeered_vnet_with_metadata(self):
        """Sample non-peered VNet with complete Azure metadata"""
        return {
            'name': 'isolated-vnet-001',
            'address_space': '10.200.0.0/16',
            'subnets': [
                {'name': 'default', 'address': '10.200.0.0/24', 'nsg': 'No', 'udr': 'No'}
            ],
            'resource_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-isolated/providers/Microsoft.Network/virtualNetworks/isolated-vnet-001',
            'tenant_id': '87654321-4321-4321-4321-210987654321',
            'subscription_id': '12345678-1234-1234-1234-123456789012',
            'subscription_name': 'Development Subscription',
            'resourcegroup_id': '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-isolated',
            'resourcegroup_name': 'rg-isolated',
            'azure_console_url': 'https://portal.azure.com/#@87654321-4321-4321-4321-210987654321/resource/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-isolated/providers/Microsoft.Network/virtualNetworks/isolated-vnet-001',
            'peerings_count': 0,
            'expressroute': 'No',
            'vpn_gateway': 'No',
            'firewall': 'No'
        }

    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing"""
        config = Mock()
        config.hub_threshold = 3
        config.get_canvas_attributes.return_value = {}
        config.get_vnet_style_string.return_value = "test_style"
        config.get_subnet_style_string.return_value = "test_subnet_style"
        config.get_edge_style_string.return_value = "test_edge_style"
        config.get_hub_spoke_edge_style.return_value = "hub_spoke_style"
        config.get_cross_zone_edge_style.return_value = "cross_zone_style"
        config.get_icon_path.return_value = "test_icon.svg"
        config.get_icon_size.return_value = (20, 20)
        config.layout = {
            'hub': {'height': 50, 'width': 400},
            'subnet': {'padding_y': 55, 'spacing_y': 30, 'padding_x': 25, 'width': 350, 'height': 20}
        }
        config.icon_positioning = {
            'vnet_icons': {'y_offset': 3, 'right_margin': 6, 'icon_gap': 5},
            'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
            'subnet_icons': {'icon_gap': 3, 'icon_y_offset': 2, 'subnet_icon_y_offset': 3}
        }
        config.drawio = {'group': {'extra_height': 20, 'connectable': '0'}}
        config.canvas_padding = 20
        config.vnet_width = 400
        config.zone_spacing = 500
        config.vnet_spacing_x = 450
        config.group_height_extra = 20
        return config

    def create_test_xml_with_vnet(self, vnet_data, config, show_subnets=False):
        """Create test XML structure with a single VNet for validation"""
        # Create XML root structure
        mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
        diagram = etree.SubElement(mxfile, "diagram", name="Test Diagram")
        mxGraphModel = etree.SubElement(diagram, "mxGraphModel")
        root = etree.SubElement(mxGraphModel, "root")
        
        etree.SubElement(root, "mxCell", id="0")
        etree.SubElement(root, "mxCell", id="1", parent="0")
        
        # Add VNet using the actual function
        _add_vnet_with_optional_subnets(vnet_data, 100, 100, root, config, show_subnets=show_subnets)
        
        return mxfile, root

    def test_group_object_metadata_attributes(self, sample_vnet_with_full_metadata, mock_config):
        """Test that group objects contain all expected metadata attributes"""
        mxfile, root = self.create_test_xml_with_vnet(sample_vnet_with_full_metadata, mock_config, show_subnets=True)
        
        # Find group object element
        group_objects = root.xpath("//object[@label='']")
        assert len(group_objects) == 1, "Should have exactly one group object"
        
        group_obj = group_objects[0]
        
        # Validate all required metadata attributes exist
        required_attrs = [
            'subscription_name', 'subscription_id', 'tenant_id',
            'resourcegroup_id', 'resourcegroup_name', 'resource_id',
            'azure_console_url', 'link'
        ]
        
        for attr in required_attrs:
            assert group_obj.get(attr) is not None, f"Group object missing {attr} attribute"
            assert group_obj.get(attr) != '', f"Group object {attr} attribute is empty"
        
        # Validate specific attribute values
        assert group_obj.get('subscription_name') == 'Production Subscription'
        assert group_obj.get('subscription_id') == '12345678-1234-1234-1234-123456789012'
        assert group_obj.get('tenant_id') == '87654321-4321-4321-4321-210987654321'
        assert group_obj.get('resourcegroup_name') == 'rg-hub'
        assert 'portal.azure.com' in group_obj.get('azure_console_url')
        assert group_obj.get('link') == group_obj.get('azure_console_url'), "Link should match azure_console_url"

    def test_vnet_main_element_metadata_attributes(self, sample_vnet_with_full_metadata, mock_config):
        """Test that VNet main elements contain all expected metadata attributes"""
        mxfile, root = self.create_test_xml_with_vnet(sample_vnet_with_full_metadata, mock_config, show_subnets=True)
        
        # Find VNet main object element (has a label with subscription info)
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        assert len(vnet_objects) == 1, "Should have exactly one VNet main object"
        
        vnet_obj = vnet_objects[0]
        
        # Validate all required metadata attributes exist
        required_attrs = [
            'subscription_name', 'subscription_id', 'tenant_id',
            'resourcegroup_id', 'resourcegroup_name', 'resource_id',
            'azure_console_url', 'link'
        ]
        
        for attr in required_attrs:
            assert vnet_obj.get(attr) is not None, f"VNet main object missing {attr} attribute"
            assert vnet_obj.get(attr) != '', f"VNet main object {attr} attribute is empty"
        
        # Validate specific attribute values
        assert vnet_obj.get('subscription_name') == 'Production Subscription'
        assert vnet_obj.get('subscription_id') == '12345678-1234-1234-1234-123456789012'
        assert vnet_obj.get('tenant_id') == '87654321-4321-4321-4321-210987654321'
        assert vnet_obj.get('resourcegroup_name') == 'rg-hub'
        assert 'portal.azure.com' in vnet_obj.get('azure_console_url')
        assert vnet_obj.get('link') == vnet_obj.get('azure_console_url'), "Link should match azure_console_url"

    def test_metadata_consistency_between_group_and_vnet(self, sample_vnet_with_full_metadata, mock_config):
        """Test that metadata values are identical between group objects and their VNet main elements"""
        mxfile, root = self.create_test_xml_with_vnet(sample_vnet_with_full_metadata, mock_config, show_subnets=True)
        
        # Find both objects
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        assert len(group_objects) == 1 and len(vnet_objects) == 1
        
        group_obj = group_objects[0]
        vnet_obj = vnet_objects[0]
        
        # Validate that metadata values are identical
        metadata_attrs = [
            'subscription_name', 'subscription_id', 'tenant_id',
            'resourcegroup_id', 'resourcegroup_name', 'resource_id',
            'azure_console_url', 'link'
        ]
        
        for attr in metadata_attrs:
            group_value = group_obj.get(attr)
            vnet_value = vnet_obj.get(attr)
            assert group_value == vnet_value, f"Metadata mismatch for {attr}: group='{group_value}' != vnet='{vnet_value}'"

    def test_hyperlink_functionality_validation(self, sample_vnet_with_full_metadata, mock_config):
        """Test that both group and VNet elements have working hyperlinks pointing to Azure console"""
        mxfile, root = self.create_test_xml_with_vnet(sample_vnet_with_full_metadata, mock_config, show_subnets=True)
        
        # Find both objects
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        for obj in group_objects + vnet_objects:
            # Validate hyperlink exists and is properly formatted
            link = obj.get('link')
            azure_url = obj.get('azure_console_url')
            
            assert link is not None, "Link attribute must exist"
            assert azure_url is not None, "Azure console URL attribute must exist"
            assert link == azure_url, "Link must match azure_console_url"
            assert link.startswith('https://portal.azure.com/#@'), "Link must be valid Azure portal URL"
            assert sample_vnet_with_full_metadata['tenant_id'] in link, "Link must contain tenant ID"
            assert sample_vnet_with_full_metadata['resource_id'] in link, "Link must contain resource ID"

    def test_virtual_hub_metadata_handling(self, sample_virtual_hub_with_metadata, mock_config):
        """Test metadata handling for Virtual Hub VNets"""
        mxfile, root = self.create_test_xml_with_vnet(sample_virtual_hub_with_metadata, mock_config, show_subnets=True)
        
        # Virtual hubs should still have group and main objects with metadata
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        assert len(group_objects) == 1, "Virtual hub should have group object"
        assert len(vnet_objects) == 1, "Virtual hub should have main object"
        
        # Validate metadata consistency
        group_obj = group_objects[0]
        vnet_obj = vnet_objects[0]
        
        metadata_attrs = ['subscription_name', 'resource_id', 'azure_console_url', 'link']
        for attr in metadata_attrs:
            assert group_obj.get(attr) == vnet_obj.get(attr), f"Virtual hub metadata mismatch for {attr}"
        
        # Validate Virtual Hub specific attributes
        assert group_obj.get('resourcegroup_name') == 'rg-vwan'
        assert 'virtualHubs' in group_obj.get('resource_id')

    def test_spoke_vnet_metadata_handling(self, sample_spoke_vnet_with_metadata, mock_config):
        """Test metadata handling for spoke VNets"""
        mxfile, root = self.create_test_xml_with_vnet(sample_spoke_vnet_with_metadata, mock_config, show_subnets=True)
        
        # Spoke VNets should have complete metadata
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        assert len(group_objects) == 1 and len(vnet_objects) == 1
        
        group_obj = group_objects[0]
        vnet_obj = vnet_objects[0]
        
        # Validate spoke-specific metadata
        assert group_obj.get('subscription_name') == 'Production Subscription'
        assert group_obj.get('resourcegroup_name') == 'rg-spoke'
        assert 'spoke-vnet-001' in group_obj.get('resource_id')
        
        # Ensure hyperlinks work for spokes
        assert group_obj.get('link') == group_obj.get('azure_console_url')
        assert vnet_obj.get('link') == vnet_obj.get('azure_console_url')

    def test_non_peered_vnet_metadata_handling(self, sample_nonpeered_vnet_with_metadata, mock_config):
        """Test metadata handling for non-peered VNets"""
        mxfile, root = self.create_test_xml_with_vnet(sample_nonpeered_vnet_with_metadata, mock_config, show_subnets=True)
        
        # Non-peered VNets should still have complete metadata
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        assert len(group_objects) == 1 and len(vnet_objects) == 1
        
        group_obj = group_objects[0]
        
        # Validate non-peered VNet metadata completeness
        required_attrs = [
            'subscription_name', 'subscription_id', 'tenant_id',
            'resourcegroup_id', 'resourcegroup_name', 'resource_id',
            'azure_console_url', 'link'
        ]
        
        for attr in required_attrs:
            assert group_obj.get(attr) is not None, f"Non-peered VNet missing {attr}"
            assert group_obj.get(attr) != '', f"Non-peered VNet {attr} is empty"

    @pytest.mark.parametrize("show_subnets", [True, False])
    def test_metadata_in_both_hld_and_mld_modes(self, sample_vnet_with_full_metadata, mock_config, show_subnets):
        """Test that metadata exists in both HLD (show_subnets=False) and MLD (show_subnets=True) modes"""
        mxfile, root = self.create_test_xml_with_vnet(sample_vnet_with_full_metadata, mock_config, show_subnets=show_subnets)
        
        # Both modes should have group and main objects with metadata
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        mode_name = "MLD" if show_subnets else "HLD"
        assert len(group_objects) == 1, f"{mode_name} mode should have group object"
        assert len(vnet_objects) == 1, f"{mode_name} mode should have main object"
        
        # Validate metadata exists in both modes
        group_obj = group_objects[0]
        vnet_obj = vnet_objects[0]
        
        for obj in [group_obj, vnet_obj]:
            assert obj.get('subscription_name') is not None, f"{mode_name} mode missing subscription_name"
            assert obj.get('azure_console_url') is not None, f"{mode_name} mode missing azure_console_url"
            assert obj.get('link') is not None, f"{mode_name} mode missing link"

    def test_metadata_with_missing_azure_data(self, mock_config):
        """Test metadata handling when some Azure data is missing (fallback scenario)"""
        vnet_with_partial_metadata = {
            'name': 'test-vnet',
            'address_space': '10.0.0.0/16',
            'subnets': [],
            # Missing subscription_name, resource_id, etc. to test fallback behavior
        }
        
        mxfile, root = self.create_test_xml_with_vnet(vnet_with_partial_metadata, mock_config, show_subnets=True)
        
        # Should still create group and main objects, with empty metadata attributes
        group_objects = root.xpath("//object[@label='']")
        vnet_objects = root.xpath("//object[contains(@label, 'Subscription:')]")
        
        assert len(group_objects) == 1, "Should have group object even with missing metadata"
        assert len(vnet_objects) == 1, "Should have main object even with missing metadata"
        
        group_obj = group_objects[0]
        
        # Attributes should exist but may be empty
        assert group_obj.get('subscription_name') == '', "Missing metadata should result in empty string"
        assert group_obj.get('azure_console_url') == '', "Missing URL should result in empty string"
        assert group_obj.get('link') == '', "Missing link should result in empty string"

    def test_hierarchical_id_generation_with_metadata(self, sample_vnet_with_full_metadata):
        """Test that hierarchical IDs are generated correctly using Azure metadata"""
        # Test group ID generation
        group_id = generate_hierarchical_id(sample_vnet_with_full_metadata, 'group')
        expected_group_id = "Production Subscription.rg-hub.hub-vnet-001"
        assert group_id == expected_group_id, f"Expected {expected_group_id}, got {group_id}"
        
        # Test main ID generation
        main_id = generate_hierarchical_id(sample_vnet_with_full_metadata, 'main')
        expected_main_id = "Production Subscription.rg-hub.hub-vnet-001.main"
        assert main_id == expected_main_id, f"Expected {expected_main_id}, got {main_id}"
        
        # Test subnet ID generation
        subnet_id = generate_hierarchical_id(sample_vnet_with_full_metadata, 'subnet', '0')
        expected_subnet_id = "Production Subscription.rg-hub.hub-vnet-001.subnet.0"
        assert subnet_id == expected_subnet_id, f"Expected {expected_subnet_id}, got {subnet_id}"

    def test_hierarchical_id_fallback_without_metadata(self):
        """Test that hierarchical ID generation falls back correctly without Azure metadata"""
        vnet_without_metadata = {
            'name': 'test-vnet',
            'address_space': '10.0.0.0/16',
            # No subscription_name or resourcegroup_name
        }
        
        # Test fallback ID generation
        group_id = generate_hierarchical_id(vnet_without_metadata, 'group')
        assert group_id == "test-vnet", f"Expected test-vnet, got {group_id}"
        
        main_id = generate_hierarchical_id(vnet_without_metadata, 'main')
        assert main_id == "test-vnet_main", f"Expected test-vnet_main, got {main_id}"

    def test_full_diagram_metadata_validation_hld(self, sample_vnet_with_full_metadata, sample_spoke_vnet_with_metadata, mock_config):
        """Test metadata validation in a complete HLD diagram"""
        topology = {
            'vnets': [sample_vnet_with_full_metadata, sample_spoke_vnet_with_metadata]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(topology, f)
            topology_file = f.name
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
                output_file = f.name
            
            # Generate HLD diagram
            generate_hld_diagram(output_file, topology_file, mock_config)
            
            # Parse and validate the generated XML
            with open(output_file, 'rb') as f:
                tree = etree.parse(f)
                root = tree.getroot()
                
                # Find all objects with metadata
                objects_with_metadata = root.xpath("//object[@subscription_name]")
                
                # Should have metadata for both VNets (group + main objects = 4 total)
                assert len(objects_with_metadata) >= 4, "Should have metadata objects for both VNets"
                
                # Validate all objects have required metadata
                for obj in objects_with_metadata:
                    assert obj.get('subscription_name') is not None
                    assert obj.get('azure_console_url') is not None
                    assert obj.get('link') is not None
                    assert obj.get('link') == obj.get('azure_console_url')
                
        finally:
            # Clean up temp files
            os.unlink(topology_file)
            os.unlink(output_file)

    def test_full_diagram_metadata_validation_mld(self, sample_vnet_with_full_metadata, sample_spoke_vnet_with_metadata, mock_config):
        """Test metadata validation in a complete MLD diagram"""
        topology = {
            'vnets': [sample_vnet_with_full_metadata, sample_spoke_vnet_with_metadata]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump(topology, f)
            topology_file = f.name
        
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.drawio', delete=False) as f:
                output_file = f.name
            
            # Generate MLD diagram
            generate_mld_diagram(output_file, topology_file, mock_config)
            
            # Parse and validate the generated XML
            with open(output_file, 'rb') as f:
                tree = etree.parse(f)
                root = tree.getroot()
                
                # Find all objects with metadata
                objects_with_metadata = root.xpath("//object[@subscription_name]")
                
                # Should have metadata for both VNets (group + main objects = 4 total)
                assert len(objects_with_metadata) >= 4, "Should have metadata objects for both VNets in MLD"
                
                # Validate all objects have required metadata
                for obj in objects_with_metadata:
                    assert obj.get('subscription_name') is not None
                    assert obj.get('azure_console_url') is not None
                    assert obj.get('link') is not None
                    assert obj.get('link') == obj.get('azure_console_url')
                    
                    # MLD should also have hyperlinks working
                    if obj.get('azure_console_url'):
                        assert obj.get('azure_console_url').startswith('https://portal.azure.com')
                
        finally:
            # Clean up temp files
            os.unlink(topology_file)
            os.unlink(output_file)

    @pytest.mark.parametrize("vnet_type,expected_resource_type", [
        ("regular", "virtualNetworks"),
        ("virtual_hub", "virtualHubs"),
        ("spoke", "virtualNetworks"),
        ("non_peered", "virtualNetworks")
    ])
    def test_metadata_resource_type_validation(self, mock_config, vnet_type, expected_resource_type, sample_vnet_with_full_metadata, sample_virtual_hub_with_metadata):
        """Test that metadata correctly reflects different VNet resource types"""
        if vnet_type == "virtual_hub":
            vnet_data = sample_virtual_hub_with_metadata
        else:
            vnet_data = sample_vnet_with_full_metadata
        
        mxfile, root = self.create_test_xml_with_vnet(vnet_data, mock_config, show_subnets=True)
        
        # Find objects with resource_id
        objects = root.xpath("//object[@resource_id]")
        
        for obj in objects:
            resource_id = obj.get('resource_id')
            if resource_id:
                assert expected_resource_type in resource_id, f"Resource ID should contain {expected_resource_type}"


if __name__ == "__main__":
    pytest.main([__file__])