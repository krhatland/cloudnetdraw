"""
Unit tests for configuration management
"""
import pytest
import os
import tempfile
import yaml
from unittest.mock import patch, mock_open, Mock
from pathlib import Path

# Import the module under test
from config import Config, ConfigValidationError


class TestConfig:
    """Test the Config class"""

    def test_valid_config_loading(self, sample_config_dict, mock_config_file):
        """Test loading a valid configuration file"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            assert config.hub_threshold == 3
            assert config.hub_style['border_color'] == '#0078D4'

    def test_missing_config_file(self):
        """Test handling of missing configuration file"""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(FileNotFoundError, match="Configuration file.*not found"):
                Config('nonexistent.yaml')

    def test_invalid_yaml_structure(self):
        """Test handling of malformed YAML"""
        invalid_yaml = "invalid: yaml: content: ["
        with patch('builtins.open', mock_open(read_data=invalid_yaml)), \
             patch('os.path.exists', return_value=True):
            with pytest.raises(yaml.YAMLError):
                Config('invalid.yaml')

    def test_hub_threshold_property(self, sample_config_dict, mock_config_file):
        """Test hub threshold property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            assert config.hub_threshold == 3

    def test_style_properties(self, sample_config_dict, mock_config_file):
        """Test style property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            
            # Test hub style
            hub_style = config.hub_style
            assert hub_style['border_color'] == '#0078D4'
            assert hub_style['fill_color'] == '#E6F1FB'
            
            # Test spoke style
            spoke_style = config.spoke_style
            assert spoke_style['border_color'] == '#CC6600'
            
            # Test non-peered style
            non_peered_style = config.non_peered_style
            assert non_peered_style['border_color'] == 'gray'

    def test_subnet_style_property(self, sample_config_dict, mock_config_file):
        """Test subnet style property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            subnet_style = config.subnet_style
            assert subnet_style['border_color'] == '#C8C6C4'
            assert subnet_style['fill_color'] == '#FAF9F8'

    def test_layout_property(self, sample_config_dict, mock_config_file):
        """Test layout property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            layout = config.layout
            assert layout['hub']['width'] == 400
            assert layout['hub']['height'] == 50

    def test_edges_property(self, sample_config_dict, mock_config_file):
        """Test edges property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            edges = config.edges
            assert 'edgeStyle=orthogonalEdgeStyle' in edges['spoke_spoke']['style']

    def test_icons_property(self, sample_config_dict, mock_config_file):
        """Test icons property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            icons = config.icons
            assert icons['vnet']['width'] == 20
            assert icons['vnet']['height'] == 20
            assert 'Virtual_Networks.svg' in icons['vnet']['path']

    def test_icon_positioning_property(self, sample_config_dict, mock_config_file):
        """Test icon positioning property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            positioning = config.icon_positioning
            assert positioning['vnet_icons']['y_offset'] == 3.39
            assert positioning['vnet_icons']['right_margin'] == 6

    def test_drawio_property(self, sample_config_dict, mock_config_file):
        """Test draw.io property access"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            drawio = config.drawio
            assert drawio['canvas']['background'] == '#ffffff'
            assert drawio['group']['extra_height'] == 20

    def test_get_vnet_style_string_hub(self, sample_config_dict, mock_config_file):
        """Test hub VNet style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_vnet_style_string('hub')
            
            assert 'shape=rectangle' in style_string
            assert 'strokeColor=#0078D4' in style_string
            assert 'fontColor=#004578' in style_string
            assert 'fillColor=#E6F1FB' in style_string
            assert 'align=left' in style_string

    def test_get_vnet_style_string_spoke(self, sample_config_dict, mock_config_file):
        """Test spoke VNet style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_vnet_style_string('spoke')
            
            assert 'strokeColor=#CC6600' in style_string
            assert 'fontColor=#CC6600' in style_string

    def test_get_vnet_style_string_non_peered(self, sample_config_dict, mock_config_file):
        """Test non-peered VNet style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_vnet_style_string('non_peered')
            
            assert 'strokeColor=gray' in style_string
            assert 'fontColor=gray' in style_string

    def test_get_vnet_style_string_default(self, sample_config_dict, mock_config_file):
        """Test default VNet style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_vnet_style_string('unknown_type')
            
            # Should default to hub style
            assert 'strokeColor=#0078D4' in style_string

    def test_get_subnet_style_string(self, sample_config_dict, mock_config_file):
        """Test subnet style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_subnet_style_string()
            
            assert 'strokeColor=#C8C6C4' in style_string
            assert 'fontColor=#323130' in style_string
            assert 'fillColor=#FAF9F8' in style_string

    def test_get_edge_style_string(self, sample_config_dict, mock_config_file):
        """Test edge style string generation"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            style_string = config.get_edge_style_string()
            
            assert style_string == 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;'

    def test_get_icon_path(self, sample_config_dict, mock_config_file):
        """Test icon path retrieval"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            
            vnet_path = config.get_icon_path('vnet')
            assert vnet_path == 'img/lib/azure2/networking/Virtual_Networks.svg'
            
            firewall_path = config.get_icon_path('firewall')
            assert firewall_path == 'img/lib/azure2/networking/Firewalls.svg'

    def test_get_icon_size(self, sample_config_dict, mock_config_file):
        """Test icon size retrieval"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            
            vnet_width, vnet_height = config.get_icon_size('vnet')
            assert vnet_width == 20
            assert vnet_height == 20
            
            nsg_width, nsg_height = config.get_icon_size('nsg')
            assert nsg_width == 16
            assert nsg_height == 16

    def test_get_canvas_attributes(self, sample_config_dict, mock_config_file):
        """Test canvas attributes retrieval"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            canvas_attrs = config.get_canvas_attributes()
            
            assert canvas_attrs['background'] == '#ffffff'
            assert canvas_attrs['pageWidth'] == '827'
            assert canvas_attrs['pageHeight'] == '1169'

    def test_new_config_properties(self, sample_config_dict, mock_config_file):
        """Test the new configuration properties for magic number constants"""
        with patch('os.path.exists', return_value=True):
            config = Config('config.yaml')
            
            # Test canvas padding
            assert config.canvas_padding == 20
            
            # Test zone spacing
            assert config.zone_spacing == 500
            
            # Test VNet width
            assert config.vnet_width == 400
            
            # Test VNet spacing
            assert config.vnet_spacing_x == 450
            assert config.vnet_spacing_y == 100
            
            # Test group height extra
            assert config.group_height_extra == 20

    def test_config_file_path_resolution_same_directory(self, sample_config_dict):
        """Test config file resolution from same directory"""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=sample_config_dict):
            config = Config('config.yaml')
            assert config.config_file == 'config.yaml'

    def test_config_file_path_resolution_different_directory(self, sample_config_dict):
        """Test config file resolution from different directory"""
        config_path = '/path/to/custom/config.yaml'
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=sample_config_dict):
            config = Config(config_path)
            assert config.config_file == config_path

    def test_config_file_relative_path(self, sample_config_dict):
        """Test config file with relative path"""
        config_path = '../configs/test.yaml'
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=sample_config_dict):
            config = Config(config_path)
            assert config.config_file == config_path

    def test_missing_config_sections(self):
        """Test handling of incomplete configuration"""
        incomplete_config = {
            'thresholds': {
                'hub_peering_count': 3
            }
            # Missing styles, icons, etc.
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=incomplete_config):
            # Should raise ConfigValidationError during initialization
            with pytest.raises(ConfigValidationError, match="Missing required key 'styles'"):
                Config('config.yaml')

    def test_config_with_custom_values(self):
        """Test configuration with custom threshold values"""
        custom_config = {
            'thresholds': {
                'hub_peering_count': 5  # Custom threshold
            },
            'styles': {
                'hub': {
                    'border_color': '#FF0000',  # Custom color
                    'fill_color': '#FFEEEE',
                    'font_color': '#FF0000',
                    'line_color': '#FF0000',
                    'text_align': 'center'
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
                'spoke_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;'
                },
                'hub_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#000000;strokeWidth=3;endArrow=block;startArrow=block;'
                },
                'cross_zone': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0066CC;strokeWidth=2;endArrow=block;startArrow=block;dashed=1;dashPattern=8 4;'
                }
            },
            'icons': {
                'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}
            },
            'icon_positioning': {
                'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5},
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
            },
            'drawio': {
                'canvas': {'background': '#ffffff'},
                'group': {'extra_height': 20, 'connectable': '0'}
            }
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=custom_config):
            config = Config('config.yaml')
            
            assert config.hub_threshold == 5
            assert config.hub_style['border_color'] == '#FF0000'
            assert config.hub_style['text_align'] == 'center'

    def test_config_file_permissions_error(self):
        """Test handling of file permission errors"""
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', side_effect=PermissionError("Permission denied")):
            with pytest.raises(PermissionError):
                Config('config.yaml')


class TestConfigValidation:
    """Test configuration schema validation"""

    def test_valid_config_passes_validation(self, sample_config_dict, mock_config_file):
        """Test that a valid configuration passes validation"""
        with patch('os.path.exists', return_value=True):
            # Should not raise any exception
            config = Config('config.yaml')
            assert config.hub_threshold == 3

    def test_missing_required_section_fails_validation(self):
        """Test that missing required sections fail validation"""
        invalid_configs = [
            # Missing thresholds section
            {
                'styles': {'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'}},
                'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
                'layout': {'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50}},
                'edges': {'spoke_spoke': {'style': 'edgeStyle=orthogonalEdgeStyle'}},
                'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
                'icon_positioning': {'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5}},
                'drawio': {'canvas': {'background': '#ffffff'}, 'group': {'extra_height': 20, 'connectable': '0'}}
            },
            # Missing styles section
            {
                'thresholds': {'hub_peering_count': 3},
                'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
                'layout': {'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50}},
                'edges': {'spoke_spoke': {'style': 'edgeStyle=orthogonalEdgeStyle'}},
                'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
                'icon_positioning': {'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5}},
                'drawio': {'canvas': {'background': '#ffffff'}, 'group': {'extra_height': 20, 'connectable': '0'}}
            }
        ]

        for invalid_config in invalid_configs:
            with patch('os.path.exists', return_value=True), \
                 patch('builtins.open', mock_open()), \
                 patch('yaml.safe_load', return_value=invalid_config):
                with pytest.raises(ConfigValidationError):
                    Config('config.yaml')

    def test_missing_required_subsection_fails_validation(self):
        """Test that missing required subsections fail validation"""
        # Missing hub style
        invalid_config = {
            'thresholds': {'hub_peering_count': 3},
            'styles': {
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50}},
            'edges': {'spoke_spoke': {'style': 'edgeStyle=orthogonalEdgeStyle'}},
            'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
            'icon_positioning': {'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5}},
            'drawio': {'canvas': {'background': '#ffffff'}, 'group': {'extra_height': 20, 'connectable': '0'}}
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=invalid_config):
            with pytest.raises(ConfigValidationError, match="Missing required key 'hub'"):
                Config('config.yaml')

    def test_invalid_type_fails_validation(self):
        """Test that invalid types fail validation"""
        # hub_peering_count should be int, not string
        invalid_config = {
            'thresholds': {'hub_peering_count': 'three'},  # Should be int
            'styles': {
                'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'},
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {
                'canvas': {'padding': 20},
                'zone': {'spacing': 500},
                'vnet': {'width': 400, 'spacing_x': 450, 'spacing_y': 100},
                'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50}
            },
            'edges': {'spoke_spoke': {'style': 'edgeStyle=orthogonalEdgeStyle'}},
            'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
            'icon_positioning': {'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5}},
            'drawio': {'canvas': {'background': '#ffffff'}, 'group': {'extra_height': 20, 'connectable': '0'}}
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=invalid_config):
            with pytest.raises(ConfigValidationError, match="Expected int.*got str"):
                Config('config.yaml')

    def test_icon_validation_missing_required_fields(self):
        """Test that icons missing required fields fail validation"""
        invalid_config = {
            'thresholds': {'hub_peering_count': 3},
            'styles': {
                'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'},
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {
                'canvas': {'padding': 20},
                'zone': {'spacing': 500},
                'vnet': {'width': 400, 'spacing_x': 450, 'spacing_y': 100},
                'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50},
                'spoke': {'spacing_y': 100, 'start_y': 200, 'width': 400, 'height': 50, 'left_x': -100, 'right_x': 900},
                'non_peered': {'spacing_y': 100, 'start_y': 200, 'x': 1450, 'width': 400, 'height': 50},
                'subnet': {'width': 350, 'height': 20, 'padding_x': 25, 'padding_y': 55, 'spacing_y': 30}
            },
            'edges': {
                'spoke_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle'
                },
                'hub_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#000000;strokeWidth=3;endArrow=block;startArrow=block;'
                },
                'cross_zone': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0066CC;strokeWidth=2;endArrow=block;startArrow=block;dashed=1;dashPattern=8 4;'
                }
            },
            'icons': {
                'vnet': {'path': 'test.svg', 'width': 20},  # Missing height
                'firewall': {'path': 'firewall.svg'}  # Missing width and height
            },
            'icon_positioning': {
                'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5},
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
            },
            'drawio': {
                'canvas': {'background': '#ffffff'},
                'group': {'extra_height': 20, 'connectable': '0'}
            }
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=invalid_config):
            with pytest.raises(ConfigValidationError, match="Missing required field 'height' in icon 'vnet' at icons.vnet"):
                Config('config.yaml')

    def test_icon_validation_invalid_field_types(self):
        """Test that icons with invalid field types fail validation"""
        invalid_config = {
            'thresholds': {'hub_peering_count': 3},
            'styles': {
                'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'},
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {
                'canvas': {'padding': 20},
                'zone': {'spacing': 500},
                'vnet': {'width': 400, 'spacing_x': 450, 'spacing_y': 100},
                'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50},
                'spoke': {'spacing_y': 100, 'start_y': 200, 'width': 400, 'height': 50, 'left_x': -100, 'right_x': 900},
                'non_peered': {'spacing_y': 100, 'start_y': 200, 'x': 1450, 'width': 400, 'height': 50},
                'subnet': {'width': 350, 'height': 20, 'padding_x': 25, 'padding_y': 55, 'spacing_y': 30}
            },
            'edges': {
                'spoke_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle'
                },
                'hub_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#000000;strokeWidth=3;endArrow=block;startArrow=block;'
                },
                'cross_zone': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0066CC;strokeWidth=2;endArrow=block;startArrow=block;dashed=1;dashPattern=8 4;'
                }
            },
            'icons': {
                'vnet': {'path': 'test.svg', 'width': 'twenty', 'height': 20}  # width should be int
            },
            'icon_positioning': {
                'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5},
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
            },
            'drawio': {
                'canvas': {'background': '#ffffff'},
                'group': {'extra_height': 20, 'connectable': '0'}
            }
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=invalid_config):
            with pytest.raises(ConfigValidationError, match="Expected int for 'width' in icon 'vnet'.*got str"):
                Config('config.yaml')

    def test_float_type_validation(self):
        """Test that float values are accepted where appropriate"""
        config_with_float = {
            'thresholds': {'hub_peering_count': 3},
            'styles': {
                'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'},
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {
                'canvas': {'padding': 20},
                'zone': {'spacing': 500},
                'vnet': {'width': 400, 'spacing_x': 450, 'spacing_y': 100},
                'hub': {'spacing_x': 450, 'spacing_y': 400, 'width': 400, 'height': 50},
                'spoke': {'spacing_y': 100, 'start_y': 200, 'width': 400, 'height': 50, 'left_x': -100, 'right_x': 900},
                'non_peered': {'spacing_y': 100, 'start_y': 200, 'x': 1450, 'width': 400, 'height': 50},
                'subnet': {'width': 350, 'height': 20, 'padding_x': 25, 'padding_y': 55, 'spacing_y': 30}
            },
            'edges': {
                'spoke_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle'
                },
                'hub_spoke': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#000000;strokeWidth=3;endArrow=block;startArrow=block;'
                },
                'cross_zone': {
                    'style': 'edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0066CC;strokeWidth=2;endArrow=block;startArrow=block;dashed=1;dashPattern=8 4;'
                }
            },
            'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
            'icon_positioning': {
                'vnet_icons': {'y_offset': 3.5, 'right_margin': 6, 'icon_gap': 5},  # Float is allowed
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
            },
            'drawio': {
                'canvas': {'background': '#ffffff'},
                'group': {'extra_height': 20, 'connectable': '0'}
            }
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=config_with_float):
            # Should not raise exception - floats are allowed for y_offset
            config = Config('config.yaml')
            assert config.icon_positioning['vnet_icons']['y_offset'] == 3.5

    def test_nested_section_validation_error_path(self):
        """Test that validation error messages include correct path information"""
        invalid_config = {
            'thresholds': {'hub_peering_count': 3},
            'styles': {
                'hub': {'border_color': '#0078D4', 'fill_color': '#E6F1FB', 'font_color': '#004578', 'line_color': '#0078D4', 'text_align': 'left'},
                'spoke': {'border_color': '#CC6600', 'fill_color': '#f2f7fc', 'font_color': '#CC6600', 'line_color': '#0078D4', 'text_align': 'left'},
                'non_peered': {'border_color': 'gray', 'fill_color': '#f5f5f5', 'font_color': 'gray', 'line_color': 'gray', 'text_align': 'left'}
            },
            'subnet': {'border_color': '#C8C6C4', 'fill_color': '#FAF9F8', 'font_color': '#323130', 'text_align': 'left'},
            'layout': {
                'canvas': {'padding': 20},
                'zone': {'spacing': 500},
                'vnet': {'width': 400, 'spacing_x': 450, 'spacing_y': 100},
                'hub': {'spacing_x': 'invalid', 'spacing_y': 400, 'width': 400, 'height': 50},  # spacing_x should be int
                'spoke': {'spacing_y': 100, 'start_y': 200, 'width': 400, 'height': 50, 'left_x': -100, 'right_x': 900},
                'non_peered': {'spacing_y': 100, 'start_y': 200, 'x': 1450, 'width': 400, 'height': 50},
                'subnet': {'width': 350, 'height': 20, 'padding_x': 25, 'padding_y': 55, 'spacing_y': 30}
            },
            'edges': {'spoke_spoke': {'style': 'edgeStyle=orthogonalEdgeStyle'}},
            'icons': {'vnet': {'path': 'test.svg', 'width': 20, 'height': 20}},
            'icon_positioning': {
                'vnet_icons': {'y_offset': 3.39, 'right_margin': 6, 'icon_gap': 5},
                'virtual_hub_icon': {'offset_x': -10, 'offset_y': -15},
                'subnet_icons': {'icon_y_offset': 2, 'subnet_icon_y_offset': 3, 'icon_gap': 3}
            },
            'drawio': {'canvas': {'background': '#ffffff'}, 'group': {'extra_height': 20, 'connectable': '0'}}
        }

        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open()), \
             patch('yaml.safe_load', return_value=invalid_config):
            with pytest.raises(ConfigValidationError, match="Expected int at layout.hub.spacing_x, got str"):
                Config('config.yaml')