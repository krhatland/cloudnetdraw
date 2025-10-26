"""
Utility functions for CloudNet Draw
Contains helper functions for ID generation, file operations, and parsing
"""
import json
import logging
from typing import Dict, List, Any, Optional, Tuple


def extract_resource_group(resource_id: str) -> str:
    """Helper function to extract resource group from resource ID"""
    return resource_id.split("/")[4]  # Resource group is at index 4 (5th element)


def parse_vnet_identifier(vnet_identifier: str) -> Tuple[Optional[str], Optional[str], str]:
    """Parse VNet identifier (resource ID or subscription/resource_group/vnet_name) and return (subscription_id, resource_group, vnet_name)"""
    if vnet_identifier.startswith('/'):
        # Resource ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}
        parts = vnet_identifier.split('/')
        if len(parts) >= 9 and parts[1] == 'subscriptions' and parts[3] == 'resourceGroups' and parts[5] == 'providers' and parts[6] == 'Microsoft.Network' and parts[7] == 'virtualNetworks':
            subscription_id = parts[2]
            resource_group = parts[4]
            vnet_name = parts[8]
            return subscription_id, resource_group, vnet_name
        else:
            raise ValueError(f"Invalid VNet resource ID format: {vnet_identifier}")
    elif '/' in vnet_identifier:
        parts = vnet_identifier.split('/')
        if len(parts) == 3:
            # Format: subscription/resource_group/vnet_name
            subscription_id = parts[0]
            resource_group = parts[1]
            vnet_name = parts[2]
            return subscription_id, resource_group, vnet_name
        elif len(parts) == 2:
            # Format: resource_group/vnet_name
            resource_group = parts[0]
            vnet_name = parts[1]
            return None, resource_group, vnet_name
        else:
            raise ValueError(f"Invalid VNet identifier format. Expected 'subscription/resource_group/vnet_name' or full resource ID, got: {vnet_identifier}")
    else:
        # Simple VNet name or empty string
        return None, None, vnet_identifier


def extract_vnet_name_from_resource_id(resource_id: str) -> str:
    """Extract VNet name from Azure resource ID"""
    parts = resource_id.split('/')
    if len(parts) >= 9 and parts[7] == 'virtualNetworks':
        return parts[8]
    raise ValueError(f"Invalid VNet resource ID: {resource_id}")


def generate_hierarchical_id(vnet_data: Dict[str, Any], element_type: str, suffix: Optional[str] = None) -> str:
    """Generate consistent hierarchical IDs for DrawIO elements using Azure resource path format
    
    Args:
        vnet_data: VNet data dictionary containing Azure resource information
        element_type: Type of element ('group', 'main', 'subnet', 'icon')
        suffix: Optional suffix for element_type (e.g., '0' for subnet index, 'vpn' for icon type)
    
    Returns:
        Hierarchical ID in format: subscription.resourcegroup.vnet[.element_type[.suffix]]
        Falls back to simple vnet-based ID if Azure metadata is missing (for tests)
    """
    # Extract and sanitize Azure resource components
    subscription_name = vnet_data.get('subscription_name', '').replace('.', '_')
    resourcegroup_name = vnet_data.get('resourcegroup_name', '').replace('.', '_')
    vnet_name = vnet_data.get('name', '').replace('.', '_')
    
    # Check if we have sufficient metadata for hierarchical IDs
    if not subscription_name or not resourcegroup_name:
        # Fallback to simple ID for test scenarios or missing metadata
        if element_type == 'group':
            return vnet_name
        elif element_type == 'main':
            return f"{vnet_name}_main"
        elif element_type == 'subnet':
            if suffix is not None:
                return f"{vnet_name}_subnet_{suffix}"
            else:
                return f"{vnet_name}_subnet"
        elif element_type == 'icon':
            if suffix is not None:
                return f"{vnet_name}_icon_{suffix}"
            else:
                return f"{vnet_name}_icon"
        else:
            # Fallback for unknown element types
            if suffix is not None:
                return f"{vnet_name}_{element_type}_{suffix}"
            else:
                return f"{vnet_name}_{element_type}"
    
    # Build hierarchical base ID with full Azure metadata
    base_id = f"{subscription_name}.{resourcegroup_name}.{vnet_name}"
    
    # Add element type if specified
    if element_type == 'group':
        return base_id
    elif element_type == 'main':
        return f"{base_id}.main"
    elif element_type == 'subnet':
        if suffix is not None:
            return f"{base_id}.subnet.{suffix}"
        else:
            return f"{base_id}.subnet"
    elif element_type == 'icon':
        if suffix is not None:
            return f"{base_id}.icon.{suffix}"
        else:
            return f"{base_id}.icon"
    else:
        # Fallback for unknown element types
        if suffix is not None:
            return f"{base_id}.{element_type}.{suffix}"
        else:
            return f"{base_id}.{element_type}"


def save_to_json(data: Dict[str, Any], filename: str = "network_topology.json") -> None:
    """Save the data to a JSON file"""
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"Network topology saved to {filename}")