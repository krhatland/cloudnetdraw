"""
Configuration loader for CloudNet Draw
Loads YAML configuration and provides easy access to settings
"""
import yaml
import os
from typing import Dict, Any

class Config:
    """Configuration manager for CloudNet Draw"""
    
    def __init__(self, config_file: str = "config.yaml"):
        self.config_file = config_file
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not os.path.exists(self.config_file):
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        
        with open(self.config_file, 'r') as file:
            return yaml.safe_load(file)
    
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
        
        return (f"shape=rectangle;rounded=1;whiteSpace=wrap;html=1;"
                f"strokeColor={style['border_color']};"
                f"fontColor={style['font_color']};"
                f"fillColor={style['fill_color']};verticalAlign=top")
    
    def get_subnet_style_string(self) -> str:
        """Get formatted style string for subnet elements"""
        subnet = self.subnet_style
        return (f"shape=rectangle;rounded=1;whiteSpace=wrap;html=1;"
                f"strokeColor={subnet['border_color']};"
                f"fontColor={subnet['font_color']};"
                f"fillColor={subnet['fill_color']}")
    
    def get_edge_style_string(self) -> str:
        """Get formatted style string for edge connections"""
        return self.edges['style']
    
    def get_icon_path(self, icon_type: str) -> str:
        """Get the path for a specific icon type"""
        return self.icons[icon_type]['path']
    
    def get_icon_size(self, icon_type: str) -> tuple:
        """Get width and height for a specific icon type"""
        icon = self.icons[icon_type]
        return icon['width'], icon['height']
    
    def get_canvas_attributes(self) -> Dict[str, str]:
        """Get draw.io canvas attributes"""
        return self.drawio['canvas']

# Global configuration instance
config = Config()