"""
Configuration loader for CloudNet Draw
Loads YAML configuration and provides easy access to settings
"""
import yaml
import os
from typing import Dict, Any, Tuple, List, Union
try:
    from importlib.resources import files
except ImportError:
    # Python < 3.9 fallback
    from importlib_resources import files

class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""
    pass

class Config:
    """Configuration manager for CloudNet Draw"""
    
    # Expected configuration schema
    EXPECTED_SCHEMA = {
        'thresholds': {
            'hub_peering_count': int
        },
        'styles': {
            'hub': {
                'border_color': str,
                'fill_color': str,
                'font_color': str,
                'line_color': str,
                'text_align': str
            },
            'spoke': {
                'border_color': str,
                'fill_color': str,
                'font_color': str,
                'line_color': str,
                'text_align': str
            },
            'non_peered': {
                'border_color': str,
                'fill_color': str,
                'font_color': str,
                'line_color': str,
                'text_align': str
            }
        },
        'subnet': {
            'border_color': str,
            'fill_color': str,
            'font_color': str,
            'text_align': str
        },
        'layout': {
            'canvas': {
                'padding': int
            },
            'zone': {
                'spacing': int
            },
            'vnet': {
                'width': int,
                'spacing_x': int,
                'spacing_y': int
            },
            'hub': {
                'spacing_x': int,
                'spacing_y': int,
                'width': int,
                'height': int
            },
            'spoke': {
                'spacing_y': int,
                'start_y': int,
                'width': int,
                'height': int,
                'left_x': int,
                'right_x': int
            },
            'non_peered': {
                'spacing_y': int,
                'start_y': int,
                'x': int,
                'width': int,
                'height': int
            },
            'subnet': {
                'width': int,
                'height': int,
                'padding_x': int,
                'padding_y': int,
                'spacing_y': int
            }
        },
        'edges': {
            'spoke_spoke': {
                'style': str
            },
            'hub_spoke': {
                'style': str
            },
            'cross_zone': {
                'style': str
            },
            'spoke_to_multi_hub': {
                'style': str
            }
        },
        'icons': dict,  # Icons section has dynamic keys, validate individually
        'icon_positioning': {
            'vnet_icons': {
                'y_offset': (int, float),
                'right_margin': int,
                'icon_gap': int
            },
            'virtual_hub_icon': {
                'offset_x': int,
                'offset_y': int
            },
            'subnet_icons': {
                'icon_y_offset': int,
                'subnet_icon_y_offset': int,
                'icon_gap': int
            }
        },
        'drawio': {
            'canvas': dict,  # Canvas has many string attributes
            'group': {
                'extra_height': int,
                'connectable': str
            }
        }
    }
    
    def __init__(self, config_file: str = None):
        self.config_file = self._find_config_file(config_file)
        self._config = self._load_config()
        self._validate_config()
    
    def _find_config_file(self, config_file: str = None) -> str:
        """Find configuration file using hierarchical search strategy"""
        # Search order: CLI argument -> current dir -> user home -> bundled default
        search_paths = [
            config_file,  # CLI argument (highest priority)
            "./config.yaml",  # Current working directory
            os.path.expanduser("~/.cloudnetdraw/config.yaml"),  # User home directory
            self._get_bundled_config_path()  # Package bundled config (fallback)
        ]
        
        for path in search_paths:
            if path and os.path.exists(path):
                return path
        
        # If no config file found, this shouldn't happen due to bundled fallback
        raise FileNotFoundError("No configuration file found in any search location")
    
    def _get_bundled_config_path(self) -> str:
        """Get path to bundled default configuration file"""
        try:
            # Try to get bundled config using importlib.resources
            config_path = files("cloudnetdraw.data").joinpath("config.yaml")
            return str(config_path)
        except (ImportError, FileNotFoundError):
            # Fallback for development or if bundled config not found
            # Use the config.yaml in the project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            fallback_path = os.path.join(project_root, "config.yaml")
            if os.path.exists(fallback_path):
                return fallback_path
            raise FileNotFoundError("No bundled configuration file found")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        
        with open(self.config_file, 'r') as file:
            return yaml.safe_load(file)
    
    def _validate_config(self) -> None:
        """Validate configuration against expected schema"""
        try:
            self._validate_section(self._config, self.EXPECTED_SCHEMA, "")
        except Exception as e:
            raise ConfigValidationError(f"Configuration validation failed: {e}")
    
    def _validate_section(self, config_section: Any, schema_section: Any, path: str) -> None:
        """Recursively validate a configuration section against its schema"""
        if isinstance(schema_section, dict):
            if not isinstance(config_section, dict):
                raise ValueError(f"Expected dict at {path}, got {type(config_section).__name__}")
            
            # Check for missing required keys
            for key, expected_type in schema_section.items():
                if key not in config_section:
                    raise ValueError(f"Missing required key '{key}' at {path}")
                
                current_path = f"{path}.{key}" if path else key
                self._validate_section(config_section[key], expected_type, current_path)
        
        elif isinstance(schema_section, tuple):
            # Multiple allowed types
            if not isinstance(config_section, schema_section):
                type_names = [t.__name__ for t in schema_section]
                raise ValueError(f"Expected {' or '.join(type_names)} at {path}, got {type(config_section).__name__}")
        
        elif schema_section == dict:
            # Dynamic dict (like icons or canvas)
            if not isinstance(config_section, dict):
                raise ValueError(f"Expected dict at {path}, got {type(config_section).__name__}")
            
            # For icons section, validate individual icon structure
            if path == "icons":
                for icon_name, icon_config in config_section.items():
                    if not isinstance(icon_config, dict):
                        raise ValueError(f"Expected dict for icon '{icon_name}' at {path}.{icon_name}")
                    
                    required_icon_fields = {'path': str, 'width': int, 'height': int}
                    for field, field_type in required_icon_fields.items():
                        if field not in icon_config:
                            raise ValueError(f"Missing required field '{field}' in icon '{icon_name}' at {path}.{icon_name}")
                        if not isinstance(icon_config[field], field_type):
                            raise ValueError(f"Expected {field_type.__name__} for '{field}' in icon '{icon_name}' at {path}.{icon_name}, got {type(icon_config[field]).__name__}")
        
        elif isinstance(schema_section, type):
            # Single type
            if not isinstance(config_section, schema_section):
                raise ValueError(f"Expected {schema_section.__name__} at {path}, got {type(config_section).__name__}")
        
        else:
            raise ValueError(f"Invalid schema definition at {path}")
    
    @property
    def hub_threshold(self) -> int:
        """Get the peering count threshold for hub classification"""
        return self._config['thresholds']['hub_peering_count']
    
    @property
    def hub_style(self) -> Dict[str, str]:
        """Get hub VNet styling"""
        return self._config['styles']['hub']
    
    @property
    def spoke_style(self) -> Dict[str, str]:
        """Get spoke VNet styling"""
        return self._config['styles']['spoke']
    
    @property
    def non_peered_style(self) -> Dict[str, str]:
        """Get non-peered VNet styling"""
        return self._config['styles']['non_peered']
    
    @property
    def subnet_style(self) -> Dict[str, str]:
        """Get subnet styling"""
        return self._config['subnet']
    
    @property
    def layout(self) -> Dict[str, Any]:
        """Get layout settings"""
        return self._config['layout']
    
    @property
    def edges(self) -> Dict[str, Any]:
        """Get edge/connection styling"""
        return self._config['edges']
    
    @property
    def icons(self) -> Dict[str, Dict[str, Any]]:
        """Get icon settings"""
        return self._config['icons']
    
    @property
    def icon_positioning(self) -> Dict[str, Any]:
        """Get icon positioning settings"""
        return self._config['icon_positioning']
    
    @property
    def drawio(self) -> Dict[str, Any]:
        """Get draw.io specific settings"""
        return self._config['drawio']
    
    def get_vnet_style_string(self, vnet_type: str) -> str:
        """Get formatted style string for draw.io VNet elements"""
        if vnet_type == 'hub':
            style = self.hub_style
        elif vnet_type == 'spoke':
            style = self.spoke_style
        elif vnet_type == 'non_peered':
            style = self.non_peered_style
        else:
            style = self.hub_style  # Default to hub style
        
        return (f"shape=rectangle;rounded=0;whiteSpace=wrap;html=1;"
                f"strokeColor={style['border_color']};"
                f"fontColor={style['font_color']};"
                f"fillColor={style['fill_color']};verticalAlign=top;align={style['text_align']}")
    
    def get_subnet_style_string(self) -> str:
        """Get formatted style string for subnet elements"""
        subnet = self.subnet_style
        return (f"shape=rectangle;rounded=0;whiteSpace=wrap;html=1;"
                f"strokeColor={subnet['border_color']};"
                f"fontColor={subnet['font_color']};"
                f"fillColor={subnet['fill_color']};align={subnet['text_align']}")
    
    def get_edge_style_string(self) -> str:
        """Get formatted style string for edge connections (spoke-to-spoke edges)"""
        return self.edges['spoke_spoke']['style']
    
    def get_hub_spoke_edge_style(self) -> str:
        """Get formatted style string for hub-to-spoke connections"""
        return self.edges['hub_spoke']['style']
    
    def get_cross_zone_edge_style(self) -> str:
        """Get formatted style string for cross-zone connections"""
        return self.edges['cross_zone']['style']
    
    def get_spoke_to_multi_hub_edge_style(self) -> str:
        """Get formatted style string for spoke-to-multi-hub connections"""
        return self.edges['spoke_to_multi_hub']['style']
    
    def get_icon_path(self, icon_type: str) -> str:
        """Get the path for a specific icon type"""
        return self.icons[icon_type]['path']
    
    def get_icon_size(self, icon_type: str) -> Tuple[int, int]:
        """Get width and height for a specific icon type"""
        icon = self.icons[icon_type]
        return icon['width'], icon['height']
    
    def get_canvas_attributes(self) -> Dict[str, str]:
        """Get draw.io canvas attributes"""
        return self.drawio['canvas']
    
    @property
    def canvas_padding(self) -> int:
        """Get canvas padding value (CANVAS_PADDING constant)"""
        return self.layout['canvas']['padding']
    
    @property
    def zone_spacing(self) -> int:
        """Get zone spacing value (ZONE_SPACING constant)"""
        return self.layout['zone']['spacing']
    
    @property
    def vnet_width(self) -> int:
        """Get VNet width value (VNET_WIDTH constant)"""
        return self.layout['vnet']['width']
    
    @property
    def vnet_spacing_x(self) -> int:
        """Get VNet horizontal spacing"""
        return self.layout['vnet']['spacing_x']
    
    @property
    def vnet_spacing_y(self) -> int:
        """Get VNet vertical spacing"""
        return self.layout['vnet']['spacing_y']
    
    @property
    def group_height_extra(self) -> int:
        """Get group extra height value (GROUP_HEIGHT_EXTRA constant)"""
        return self.drawio['group']['extra_height']

# Note: Config instances are now created dynamically in command functions
# No global instance to avoid import-time file dependencies