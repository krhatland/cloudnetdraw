"""
Topology processing and VNet classification functions
Handles filtering, peering analysis, and VNet classification logic
"""
import logging
import sys
from typing import Dict, List, Any

from .azure_client import find_hub_vnet_using_resource_graph, find_peered_vnets


def get_filtered_vnet_topology(hub_vnet_identifier: str, subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing only the specified hub and its directly peered spokes"""
    
    # Find the hub VNet
    hub_vnet = find_hub_vnet_using_resource_graph(hub_vnet_identifier)
    if not hub_vnet:
        logging.error(f"Hub VNet '{hub_vnet_identifier}' not found in any of the specified subscriptions")
        sys.exit(1)
    
    logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")
    
    # Get peering resource IDs from the hub VNet
    hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
    
    logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs")
    
    # Use direct API calls to get peered VNets efficiently using exact resource IDs
    directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)
    
    # Update hub VNet to only include accessible peering resource IDs
    hub_vnet["peering_resource_ids"] = accessible_peering_resource_ids
    hub_vnet["peerings_count"] = len(accessible_peering_resource_ids)
    
    # Return filtered topology
    filtered_vnets = [hub_vnet] + directly_peered_vnets
    logging.info(f"Filtered topology contains {len(filtered_vnets)} VNets: {[v['name'] for v in filtered_vnets]}")
    logging.info(f"Hub VNet has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")
    
    return {"vnets": filtered_vnets}


def get_filtered_vnets_topology(vnet_identifiers: List[str], subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing multiple specified hubs and their directly peered spokes"""
    
    all_vnets = {}  # Use dict to avoid duplicates by resource_id
    
    for vnet_identifier in vnet_identifiers:
        # Find the hub VNet
        hub_vnet = find_hub_vnet_using_resource_graph(vnet_identifier)
        if not hub_vnet:
            logging.error(f"Hub VNet '{vnet_identifier}' not found in any of the specified subscriptions")
            sys.exit(1)
        
        logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")
        
        # Add hub VNet to collection using resource_id as key to avoid duplicates
        resource_id = hub_vnet.get('resource_id')
        if resource_id and resource_id not in all_vnets:
            all_vnets[resource_id] = hub_vnet
        
        # Get peering resource IDs from the hub VNet
        hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
        
        logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs for {hub_vnet['name']}")
        
        # Use direct API calls to get peered VNets efficiently using exact resource IDs
        directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)
        
        # Update hub VNet to only include accessible peering resource IDs
        if resource_id in all_vnets:
            all_vnets[resource_id]["peering_resource_ids"] = accessible_peering_resource_ids
            all_vnets[resource_id]["peerings_count"] = len(accessible_peering_resource_ids)
        
        # Add peered VNets to collection using resource_id as key to avoid duplicates
        for peered_vnet in directly_peered_vnets:
            peered_resource_id = peered_vnet.get('resource_id')
            if peered_resource_id and peered_resource_id not in all_vnets:
                all_vnets[peered_resource_id] = peered_vnet
        
        logging.info(f"Hub VNet {hub_vnet['name']} has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")
    
    # Convert dict back to list
    filtered_vnets = list(all_vnets.values())
    logging.info(f"Combined filtered topology contains {len(filtered_vnets)} unique VNets: {[v['name'] for v in filtered_vnets]}")
    
    return {"vnets": filtered_vnets}


def get_hub_connections_for_spoke(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> List[int]:
    """Find ALL hubs this spoke connects to (for cross-zone edge generation)"""
    spoke_peering_resource_ids = spoke_vnet.get('peering_resource_ids', [])
    connected_hub_indices = []
    
    for hub_index, hub_vnet in enumerate(hub_vnets):
        hub_resource_id = hub_vnet.get('resource_id')
        if hub_resource_id and hub_resource_id in spoke_peering_resource_ids:
            connected_hub_indices.append(hub_index)
    
    return connected_hub_indices


def find_first_hub_zone(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> int:
    """Find first hub zone this spoke connects to (simplified logic)"""
    spoke_peering_ids = spoke_vnet.get('peering_resource_ids', [])
    for hub_index, hub in enumerate(hub_vnets):
        if hub.get('resource_id') in spoke_peering_ids:
            return hub_index
    return 0  # Default to first zone


def determine_hub_for_spoke(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> str:
    """Legacy function for backward compatibility"""
    if not hub_vnets:
        return None
    zone_index = find_first_hub_zone(spoke_vnet, hub_vnets)
    return f"hub_{zone_index}"


def create_vnet_id_mapping(vnets: List[Dict[str, Any]], zones: List[Dict[str, Any]], all_non_peered: List[Dict[str, Any]]) -> Dict[str, str]:
    """Create bidirectional mapping between VNet resource IDs and diagram IDs for multi-zone layout
    
    Uses resource IDs as unique identifiers to avoid name collisions.
    Uses hierarchical Azure-based IDs when Azure metadata is available,
    falls back to synthetic IDs for backward compatibility (tests).
    Handles hubless zones where hub is None.
    """
    from .utils import generate_hierarchical_id
    
    mapping = {}
    
    # Check if we have Azure metadata available in the data
    has_azure_metadata = False
    # Find first zone with a hub to check metadata
    for zone in zones:
        if zone.get('hub'):
            hub_data = zone['hub']
            has_azure_metadata = bool(hub_data.get('subscription_name') and hub_data.get('resourcegroup_name'))
            break
    
    if has_azure_metadata:
        # Production mode: Use hierarchical Azure-based IDs
        # Map hub VNets to hierarchical main IDs using resource_id as key
        for zone in zones:
            if zone.get('hub') and 'resource_id' in zone['hub']:
                group_id = generate_hierarchical_id(zone['hub'], 'group')
                mapping[zone['hub']['resource_id']] = group_id
        
        # Map spoke VNets to hierarchical main IDs using resource_id as key
        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']
            
            for spoke in peered_spokes:
                if 'resource_id' in spoke:
                    group_id = generate_hierarchical_id(spoke, 'group')
                    mapping[spoke['resource_id']] = group_id
        
        # Map non-peered VNets to hierarchical main IDs using resource_id as key
        for nonpeered in all_non_peered:
            if 'resource_id' in nonpeered:
                group_id = generate_hierarchical_id(nonpeered, 'group')
                mapping[nonpeered['resource_id']] = group_id
    else:
        # Test/backward compatibility mode: Use original synthetic IDs with resource_id as key, fallback to name
        # Map hub VNets (skip hubless zones)
        for zone in zones:
            if zone.get('hub'):  # Only process zones with hubs
                hub_key = zone['hub'].get('resource_id') or zone['hub'].get('name')
                if hub_key:
                    mapping[hub_key] = f"hub_{zone['hub_index']}"
        
        # Map spoke VNets with zone-aware IDs
        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']
            
            if zone.get('hub'):
                # Regular hub zone - use existing logic
                # Determine layout for this zone
                use_dual_column = len(peered_spokes) > 6
                if use_dual_column:
                    total_spokes = len(peered_spokes)
                    half_spokes = (total_spokes + 1) // 2
                    left_spokes = peered_spokes[:half_spokes]
                    right_spokes = peered_spokes[half_spokes:]
                else:
                    left_spokes = []
                    right_spokes = peered_spokes
                
                # Map right spokes
                for i, spoke in enumerate(right_spokes):
                    spoke_key = spoke.get('resource_id') or spoke.get('name')
                    if spoke_key:
                        mapping[spoke_key] = f"right_spoke{zone_index}_{i}"
                
                # Map left spokes
                for i, spoke in enumerate(left_spokes):
                    spoke_key = spoke.get('resource_id') or spoke.get('name')
                    if spoke_key:
                        mapping[spoke_key] = f"left_spoke{zone_index}_{i}"
            else:
                # Hubless zone - use hubless naming
                for i, spoke in enumerate(peered_spokes):
                    spoke_key = spoke.get('resource_id') or spoke.get('name')
                    if spoke_key:
                        mapping[spoke_key] = f"hubless_spoke_{i}"
        
        # Map non-peered VNets
        for i, nonpeered in enumerate(all_non_peered):
            nonpeered_key = nonpeered.get('resource_id') or nonpeered.get('name')
            if nonpeered_key:
                mapping[nonpeered_key] = f"nonpeered_spoke{i}"
    
    return mapping