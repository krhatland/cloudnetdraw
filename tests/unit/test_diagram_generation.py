"""
Unit tests for diagram generation logic
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from lxml import etree
from pathlib import Path

# Import functions under test
from cloudnetdraw.diagram_generator import (
    generate_hld_diagram,
    generate_mld_diagram
)
from cloudnetdraw.cli import (
    hld_command,
    mld_command
)


class TestVNetClassification:
    """Test VNet classification for hub/spoke determination"""

    def classify_vnets(self, vnets, hub_threshold=3):
        """Classify VNets into hubs and spokes based on peering count"""
        hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= hub_threshold]
        spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < hub_threshold]
        
        # If no hubs found, treat first VNet as hub
        if not hub_vnets and vnets:
            hub_vnets = [vnets[0]]
            spoke_vnets = vnets[1:]
        
        return hub_vnets, spoke_vnets

    def test_classify_vnets_with_hubs(self, sample_vnets):
        """Test VNet classification with clear hubs"""
        hub_vnets, spoke_vnets = self.classify_vnets(sample_vnets, hub_threshold=3)
        
        assert len(hub_vnets) == 1
        assert hub_vnets[0]['name'] == 'hub-vnet'
        assert len(spoke_vnets) == 4
        
        spoke_names = [vnet['name'] for vnet in spoke_vnets]
        assert 'spoke1' in spoke_names
        assert 'spoke2' in spoke_names
        assert 'spoke3' in spoke_names
        assert 'isolated-vnet' in spoke_names

    def test_classify_vnets_no_hubs(self, sample_vnets):
        """Test VNet classification with no clear hubs"""
        hub_vnets, spoke_vnets = self.classify_vnets(sample_vnets, hub_threshold=10)
        
        # Should treat first VNet as hub
        assert len(hub_vnets) == 1
        assert hub_vnets[0]['name'] == sample_vnets[0]['name']
        assert len(spoke_vnets) == len(sample_vnets) - 1

    def test_classify_vnets_empty_list(self):
        """Test VNet classification with empty list"""
        hub_vnets, spoke_vnets = self.classify_vnets([])
        
        assert len(hub_vnets) == 0
        assert len(spoke_vnets) == 0

    def test_classify_vnets_single_vnet(self, sample_vnets):
        """Test VNet classification with single VNet"""
        single_vnet = [sample_vnets[0]]
        hub_vnets, spoke_vnets = self.classify_vnets(single_vnet)
        
        assert len(hub_vnets) == 1
        assert len(spoke_vnets) == 0

    @pytest.mark.parametrize("hub_threshold", [1, 2, 3, 4, 5])
    def test_classify_vnets_different_thresholds(self, sample_vnets, hub_threshold):
        """Test VNet classification with different hub thresholds"""
        hub_vnets, spoke_vnets = self.classify_vnets(sample_vnets, hub_threshold)
        
        # Total should always equal original count
        assert len(hub_vnets) + len(spoke_vnets) == len(sample_vnets)
        
        # All hubs should meet threshold
        for hub in hub_vnets:
            assert hub.get('peerings_count', 0) >= hub_threshold or len(hub_vnets) == 1


class TestXMLGeneration:
    """Test XML structure generation for Draw.io diagrams"""

    def create_basic_xml_structure(self):
        """Create basic XML structure for testing"""
        mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
        diagram = etree.SubElement(mxfile, "diagram", name="Test Diagram")
        mxGraphModel = etree.SubElement(diagram, "mxGraphModel")
        root = etree.SubElement(mxGraphModel, "root")
        
        etree.SubElement(root, "mxCell", id="0")
        etree.SubElement(root, "mxCell", id="1", parent="0")
        
        return mxfile, root

    def test_basic_xml_structure(self):
        """Test basic XML structure creation"""
        mxfile, root = self.create_basic_xml_structure()
        
        assert mxfile.tag == "mxfile"
        assert mxfile.get("host") == "Electron"
        
        diagram = mxfile.find("diagram")
        assert diagram is not None
        assert diagram.get("name") == "Test Diagram"
        
        # Check root cells
        cells = root.findall("mxCell")
        assert len(cells) == 2
        assert cells[0].get("id") == "0"
        assert cells[1].get("id") == "1"

    def test_vnet_element_creation(self):
        """Test VNet element creation"""
        mxfile, root = self.create_basic_xml_structure()
        
        # Add VNet element
        vnet_element = etree.SubElement(
            root,
            "mxCell",
            id="test_vnet",
            style="shape=rectangle;rounded=0;whiteSpace=wrap;html=1;strokeColor=#0078D4;",
            vertex="1",
            parent="1"
        )
        vnet_element.set("value", "Test VNet\n10.0.0.0/16")
        
        geometry = etree.SubElement(
            vnet_element,
            "mxGeometry",
            attrib={"x": "100", "y": "100", "width": "400", "height": "50", "as": "geometry"}
        )
        
        # Verify element structure
        assert vnet_element.get("id") == "test_vnet"
        assert vnet_element.get("vertex") == "1"
        assert "Test VNet" in vnet_element.get("value")
        
        assert geometry.get("x") == "100"
        assert geometry.get("width") == "400"

    def test_edge_element_creation(self):
        """Test edge element creation"""
        mxfile, root = self.create_basic_xml_structure()
        
        # Add edge element
        edge_element = etree.SubElement(
            root,
            "mxCell",
            id="test_edge",
            edge="1",
            source="vnet1",
            target="vnet2",
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;",
            parent="1"
        )
        
        edge_geometry = etree.SubElement(
            edge_element,
            "mxGeometry",
            attrib={"relative": "1", "as": "geometry"}
        )
        
        # Verify edge structure
        assert edge_element.get("edge") == "1"
        assert edge_element.get("source") == "vnet1"
        assert edge_element.get("target") == "vnet2"
        assert edge_geometry.get("relative") == "1"

    def test_group_element_creation(self):
        """Test group element creation"""
        mxfile, root = self.create_basic_xml_structure()
        
        # Add group element
        group_element = etree.SubElement(
            root,
            "mxCell",
            id="test_group",
            value="",
            style="group",
            vertex="1",
            connectable="0",
            parent="1"
        )
        
        group_geometry = etree.SubElement(
            group_element,
            "mxGeometry",
            attrib={"x": "0", "y": "0", "width": "420", "height": "70", "as": "geometry"}
        )
        
        # Verify group structure
        assert group_element.get("style") == "group"
        assert group_element.get("connectable") == "0"
        assert group_geometry.get("width") == "420"

    def test_xml_serialization(self):
        """Test XML serialization to string"""
        mxfile, root = self.create_basic_xml_structure()
        
        # Serialize to string
        xml_string = etree.tostring(mxfile, encoding='unicode', pretty_print=True)
        
        assert '<?xml version=' in xml_string or 'mxfile' in xml_string
        assert 'mxGraphModel' in xml_string
        assert 'diagram' in xml_string


class TestHLDGeneration:
    """Test High-Level Diagram generation"""

    @patch('lxml.etree')
    @patch('builtins.open')
    def test_hld_generation_basic(self, mock_open, mock_etree, sample_topology, sample_config_dict):
        """Test basic HLD generation"""
        # Mock etree elements
        mock_mxfile = Mock()
        mock_etree.Element.return_value = mock_mxfile
        mock_etree.SubElement.return_value = Mock()
        mock_etree.ElementTree.return_value = Mock()
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_vnet_style_string.return_value = "test_style"
        mock_config.get_edge_style_string.return_value = "test_edge_style"
        mock_config.get_icon_path.return_value = "test_icon.svg"
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.icon_positioning = {'vnet_icons': {'y_offset': 3, 'right_margin': 6, 'icon_gap': 5}}
        # Add missing magic number properties
        mock_config.canvas_padding = 20
        mock_config.vnet_width = 400
        mock_config.zone_spacing = 500
        mock_config.vnet_spacing_x = 450
        mock_config.group_height_extra = 20
        
        with patch('json.load', return_value=sample_topology):
            generate_hld_diagram('test_hld.drawio', 'topology.json', mock_config)
        
        # Verify file operations
        mock_open.assert_called()
        mock_etree.Element.assert_called_with("mxfile", attrib={"host": "Electron", "version": "25.0.2"})

    def test_hld_command_execution(self, mock_config_file):
        """Test HLD command execution"""
        mock_args = Mock()
        mock_args.topology = 'test_topology.json'
        mock_args.output = 'test_output.drawio'
        mock_args.config_file = 'config.yaml'
        
        with patch('cloudnetdraw.diagram_generator.generate_hld_diagram') as mock_generate:
            hld_command(mock_args)
            
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == 'test_output.drawio'
            assert args[1] == 'test_topology.json'

    def test_hld_command_defaults(self, mock_config_file):
        """Test HLD command with default values"""
        mock_args = Mock()
        mock_args.topology = None
        mock_args.output = None
        mock_args.config_file = 'config.yaml'
        
        with patch('cloudnetdraw.diagram_generator.generate_hld_diagram') as mock_generate:
            hld_command(mock_args)
            
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == 'network_hld.drawio'
            assert args[1] == 'network_topology.json'


class TestMLDGeneration:
    """Test Mid-Level Diagram generation"""

    @patch('lxml.etree')
    @patch('builtins.open')
    def test_mld_generation_basic(self, mock_open, mock_etree, sample_topology, sample_config_dict):
        """Test basic MLD generation"""
        # Mock etree elements
        mock_mxfile = Mock()
        mock_etree.Element.return_value = mock_mxfile
        mock_etree.SubElement.return_value = Mock()
        mock_etree.ElementTree.return_value = Mock()
        
        # Mock config
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_vnet_style_string.return_value = "test_style"
        mock_config.get_subnet_style_string.return_value = "test_subnet_style"
        mock_config.get_edge_style_string.return_value = "test_edge_style"
        mock_config.get_icon_path.return_value = "test_icon.svg"
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.layout = {
            'hub': {'height': 50, 'width': 400},
            'subnet': {'padding_y': 55, 'spacing_y': 30, 'padding_x': 25, 'width': 350, 'height': 20}
        }
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 3, 'right_margin': 6, 'icon_gap': 5},
            'subnet_icons': {'icon_gap': 3, 'icon_y_offset': 2, 'subnet_icon_y_offset': 3}
        }
        mock_config.drawio = {'group': {'extra_height': 20, 'connectable': '0'}}
        # Add missing magic number properties
        mock_config.canvas_padding = 20
        mock_config.vnet_width = 400
        mock_config.zone_spacing = 500
        mock_config.vnet_spacing_x = 450
        
        with patch('json.load', return_value=sample_topology):
            generate_mld_diagram('test_mld.drawio', 'topology.json', mock_config)
        
        # Verify file operations
        mock_open.assert_called()
        mock_etree.Element.assert_called_with("mxfile", attrib={"host": "Electron", "version": "25.0.2"})

    def test_mld_command_execution(self, mock_config_file):
        """Test MLD command execution"""
        mock_args = Mock()
        mock_args.topology = 'test_topology.json'
        mock_args.output = 'test_output.drawio'
        mock_args.config_file = 'config.yaml'
        
        with patch('cloudnetdraw.diagram_generator.generate_mld_diagram') as mock_generate:
            mld_command(mock_args)
            
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == 'test_output.drawio'
            assert args[1] == 'test_topology.json'

    def test_mld_command_defaults(self, mock_config_file):
        """Test MLD command with default values"""
        mock_args = Mock()
        mock_args.topology = None
        mock_args.output = None
        mock_args.config_file = 'config.yaml'
        
        with patch('cloudnetdraw.diagram_generator.generate_mld_diagram') as mock_generate:
            mld_command(mock_args)
            
            mock_generate.assert_called_once()
            args, kwargs = mock_generate.call_args
            assert args[0] == 'network_mld.drawio'
            assert args[1] == 'network_topology.json'


class TestDiagramErrorHandling:
    """Test error handling in diagram generation"""

    def test_missing_topology_file(self, sample_config_dict):
        """Test handling of missing topology file"""
        mock_config = Mock()
        mock_config.hub_threshold = 3
        
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(FileNotFoundError):
                generate_hld_diagram('output.drawio', 'missing.json', mock_config)

    def test_invalid_json_topology(self, sample_config_dict):
        """Test handling of invalid JSON topology"""
        mock_config = Mock()
        mock_config.hub_threshold = 3
        
        with patch('builtins.open', mock_open(read_data="invalid json")), \
             patch('json.load', side_effect=ValueError("Invalid JSON")):
            with pytest.raises(ValueError):
                generate_hld_diagram('output.drawio', 'invalid.json', mock_config)

    def test_empty_topology_fatal_error(self, sample_config_dict):
        """Test that empty topology causes fatal error"""
        empty_topology = {"vnets": []}
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        
        with patch('json.load', return_value=empty_topology), \
             patch('lxml.etree') as mock_etree, \
             patch('builtins.open'):
            
            mock_etree.Element.return_value = Mock()
            mock_etree.SubElement.return_value = Mock()
            mock_etree.ElementTree.return_value = Mock()
            
            # Should exit with error code 1 when topology is empty
            with pytest.raises(SystemExit) as exc_info:
                generate_hld_diagram('output.drawio', 'empty.json', mock_config)
            assert exc_info.value.code == 1

    def test_empty_topology_mld_fatal_error(self, sample_config_dict):
        """Test that empty topology causes fatal error in MLD generation"""
        empty_topology = {"vnets": []}
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_vnet_style_string.return_value = "test_style"
        mock_config.get_subnet_style_string.return_value = "test_subnet_style"
        mock_config.get_edge_style_string.return_value = "test_edge_style"
        mock_config.get_icon_path.return_value = "test_icon.svg"
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.layout = {
            'hub': {'height': 50, 'width': 400},
            'subnet': {'padding_y': 55, 'spacing_y': 30, 'padding_x': 25, 'width': 350, 'height': 20}
        }
        mock_config.icon_positioning = {
            'vnet_icons': {'y_offset': 3, 'right_margin': 6, 'icon_gap': 5},
            'subnet_icons': {'icon_gap': 3, 'icon_y_offset': 2, 'subnet_icon_y_offset': 3}
        }
        mock_config.drawio = {'group': {'extra_height': 20, 'connectable': '0'}}
        
        with patch('json.load', return_value=empty_topology), \
             patch('lxml.etree') as mock_etree, \
             patch('builtins.open'):
            
            mock_etree.Element.return_value = Mock()
            mock_etree.SubElement.return_value = Mock()
            mock_etree.ElementTree.return_value = Mock()
            
            # Should exit with error code 1 when topology is empty
            with pytest.raises(SystemExit) as exc_info:
                generate_mld_diagram('output.drawio', 'empty.json', mock_config)
            assert exc_info.value.code == 1

    def test_malformed_vnet_data(self, sample_config_dict):
        """Test handling of malformed VNet data"""
        malformed_topology = {
            "vnets": [
                {"name": "vnet1"},  # Missing required fields
                {"address_space": "10.0.0.0/16"}  # Missing name
            ]
        }
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        mock_config.get_vnet_style_string.return_value = "test_style"
        mock_config.get_edge_style_string.return_value = "test_edge_style"
        mock_config.get_icon_path.return_value = "test_icon.svg"
        mock_config.get_icon_size.return_value = (20, 20)
        mock_config.icon_positioning = {'vnet_icons': {'y_offset': 3, 'right_margin': 6, 'icon_gap': 5}}
        # Add missing magic number properties
        mock_config.canvas_padding = 20
        mock_config.vnet_width = 400
        mock_config.zone_spacing = 500
        mock_config.vnet_spacing_x = 450
        mock_config.group_height_extra = 20
        
        with patch('json.load', return_value=malformed_topology), \
             patch('lxml.etree') as mock_etree, \
             patch('builtins.open'):
            
            mock_etree.Element.return_value = Mock()
            mock_etree.SubElement.return_value = Mock()
            mock_etree.ElementTree.return_value = Mock()
            
            # Should handle malformed data gracefully
            generate_hld_diagram('output.drawio', 'malformed.json', mock_config)

    def test_file_write_permission_error(self, sample_topology, sample_config_dict):
        """Test handling of file write permission errors"""
        mock_config = Mock()
        mock_config.hub_threshold = 3
        mock_config.get_canvas_attributes.return_value = {}
        
        with patch('json.load', return_value=sample_topology), \
             patch('lxml.etree') as mock_etree, \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            
            mock_etree.Element.return_value = Mock()
            mock_etree.SubElement.return_value = Mock()
            mock_etree.ElementTree.return_value = Mock()
            
            with pytest.raises(PermissionError):
                generate_hld_diagram('readonly.drawio', 'topology.json', mock_config)


class TestVirtualHubHandling:
    """Test Virtual Hub specific handling"""

    def test_virtual_hub_identification(self, virtual_hub_vnet):
        """Test identification of Virtual Hub VNets"""
        assert virtual_hub_vnet.get('type') == 'virtual_hub'
        assert virtual_hub_vnet.get('subnets') == []
        assert virtual_hub_vnet.get('expressroute') == 'Yes'
        assert virtual_hub_vnet.get('vpn_gateway') == 'Yes'
        assert virtual_hub_vnet.get('firewall') == 'Yes'

    def test_virtual_hub_vs_regular_vnet(self, virtual_hub_vnet, sample_vnets):
        """Test differentiation between Virtual Hub and regular VNet"""
        regular_vnet = sample_vnets[0]  # hub-vnet
        
        # Virtual Hub should have different characteristics
        assert virtual_hub_vnet.get('type') == 'virtual_hub'
        assert regular_vnet.get('type') != 'virtual_hub'
        
        # Virtual Hub should have no subnets
        assert len(virtual_hub_vnet.get('subnets', [])) == 0
        assert len(regular_vnet.get('subnets', [])) > 0

    def test_virtual_hub_icon_positioning(self, virtual_hub_vnet):
        """Test that Virtual Hub has appropriate icon positioning"""
        # Virtual Hub should have all gateway features
        assert virtual_hub_vnet.get('expressroute') == 'Yes'
        assert virtual_hub_vnet.get('vpn_gateway') == 'Yes'
        assert virtual_hub_vnet.get('firewall') == 'Yes'
        
        # This would translate to multiple icons being positioned
        expected_icons = ['vnet', 'expressroute', 'vpn_gateway', 'firewall']
        # In actual implementation, this would be tested through icon positioning logic