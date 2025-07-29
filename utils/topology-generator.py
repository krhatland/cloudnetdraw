#!/usr/bin/env python3
"""
Azure-realistic topology generator for CloudNet Draw testing
Hub-and-spoke biased with controlled outlier scenarios
"""

import json
import random
import uuid
import sys
import argparse
import itertools
from typing import Dict, List, Any, Tuple, Optional, Set


def generate_vnet(name: str, subscription_id: str, resource_group: str, location: str,
                  peering_resource_ids: List[str] = None, 
                  expressroute: str = "No", vpn_gateway: str = "No", firewall: str = "No") -> Dict[str, Any]:
    """Generate a VNet object with realistic metadata and decorators"""
    if peering_resource_ids is None:
        peering_resource_ids = []
    
    net_octet = random.randint(1, 254)
    address_space = f"10.{net_octet}.0.0/16"
    subnet_address = f"10.{net_octet}.0.0/24"
    
    return {
        "name": name,
        "address_space": address_space,
        "subnets": [{
            "name": "default",
            "address": subnet_address,
            "nsg": "Yes",
            "udr": "No"
        }],
        "resource_id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{name}",
        "tenant_id": "a84894e7-87c5-40e3-9783-320d0334b3cc",
        "subscription_id": subscription_id,
        "subscription_name": "Test Subscription",
        "resourcegroup_id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}",
        "resourcegroup_name": resource_group,
        "azure_console_url": f"https://portal.azure.com/#@a84894e7-87c5-40e3-9783-320d0334b3cc/resource/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{name}",
        "expressroute": expressroute,
        "vpn_gateway": vpn_gateway,
        "firewall": firewall,
        "peering_resource_ids": peering_resource_ids,
        "peerings_count": len(peering_resource_ids)
    }


def add_bidirectional_peering(vnet_peerings: Dict[str, List[str]], 
                             resource_id_a: str, resource_id_b: str) -> None:
    """Add bidirectional peering between two VNets by resource ID"""
    if resource_id_b not in vnet_peerings[resource_id_a]:
        vnet_peerings[resource_id_a].append(resource_id_b)
    if resource_id_a not in vnet_peerings[resource_id_b]:
        vnet_peerings[resource_id_b].append(resource_id_a)


def get_decorator_combinations() -> List[Tuple[str, str, str]]:
    """Generate all combinations of decorator icons"""
    options = ["Yes", "No"]
    return list(itertools.product(options, repeat=3))


def process_enhanced_weights(total_vnets: int, centralization: int, connectivity: int,
                           isolation: int, **kwargs) -> Dict[str, Any]:
    """Process weights with hub-and-spoke bias and outlier controls"""
    
    # Hub structure from centralization weight
    if centralization >= 7:
        num_hubs = max(1, total_vnets // 25)
        spokes_per_hub_range = (15, 30)
    elif centralization >= 4:
        num_hubs = max(2, total_vnets // 20)
        spokes_per_hub_range = (8, 15)
    else:
        num_hubs = max(3, total_vnets // 10)
        spokes_per_hub_range = (3, 8)
    
    # Override with explicit hub count
    if kwargs.get('hub_count'):
        num_hubs = kwargs['hub_count']
    
    # Calculate outlier rates from connectivity + overrides
    outlier_multiplier = connectivity / 10.0
    spoke_to_spoke_rate = kwargs.get('spoke_to_spoke_rate', 0.05 * outlier_multiplier)
    cross_zone_rate = kwargs.get('cross_zone_rate', 0.03 * outlier_multiplier)
    multi_hub_rate = kwargs.get('multi_hub_rate', 0.04 * outlier_multiplier)
    standalone_clusters_rate = kwargs.get('standalone_clusters_rate', 0.02 * outlier_multiplier)
    
    # Isolation ratio
    total_weight = centralization + connectivity + isolation
    isolation_ratio = isolation / total_weight if total_weight > 0 else 0.1
    
    return {
        'num_hubs': num_hubs,
        'spokes_per_hub_range': spokes_per_hub_range,
        'spoke_to_spoke_rate': min(spoke_to_spoke_rate, 0.4),
        'cross_zone_rate': min(cross_zone_rate, 0.3),
        'multi_hub_rate': min(multi_hub_rate, 0.3),
        'standalone_clusters_rate': min(standalone_clusters_rate, 0.15),
        'isolation_ratio': min(isolation_ratio, 0.5),
        'min_hub_degree': kwargs.get('min_hub_degree', 8),
        'max_hub_degree': kwargs.get('max_hub_degree', 40)
    }


def create_azure_realistic_topology(total_vnets: int, centralization: int, connectivity: int,
                                   isolation: int, **kwargs) -> Dict[str, Any]:
    """Create hub-and-spoke biased topology with controlled outliers"""
    
    if kwargs.get('seed') is not None:
        random.seed(kwargs['seed'])
        # Create deterministic subscription_id when seed is provided
        subscription_id = f"c{kwargs['seed']:08x}-ea2a-49e4-af49-0d47eea59963"
    else:
        subscription_id = str(uuid.uuid4())
        
    decorator_combinations = get_decorator_combinations()
    
    if total_vnets == 0:
        total_vnets = 1
    
    params = process_enhanced_weights(total_vnets, centralization, connectivity, isolation, **kwargs)
    
    # Calculate isolation count and standalone clusters
    isolation_count = int(total_vnets * params['isolation_ratio'])
    standalone_cluster_count = int(total_vnets * params['standalone_clusters_rate'])
    connected_vnets = total_vnets - isolation_count - standalone_cluster_count
    
    if connected_vnets <= 0:
        connected_vnets = 1
        isolation_count = max(0, total_vnets - connected_vnets - standalone_cluster_count)
        standalone_cluster_count = max(0, total_vnets - connected_vnets - isolation_count)
    
    # Phase 1: Create intentional hubs
    hubs = []
    hub_resource_ids = {}
    
    actual_num_hubs = min(params['num_hubs'], connected_vnets)
    
    for i in range(actual_num_hubs):
        hub_name = f"connectivity-hub-{i+1:02d}"
        hub_resource_id = f"/subscriptions/{subscription_id}/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/{hub_name}"
        
        hub_info = {
            'name': hub_name,
            'resource_id': hub_resource_id,
            'spokes': []
        }
        hubs.append(hub_info)
        hub_resource_ids[hub_resource_id] = hub_info
    
    # Phase 2: Create spokes and assign to hubs
    all_spokes = []
    spokes_to_create = connected_vnets - len(hubs)
    
    if spokes_to_create > 0:
        spokes_per_hub = spokes_to_create // len(hubs)
        extra_spokes = spokes_to_create % len(hubs)
        
        spoke_counter = 1
        for hub_idx, hub in enumerate(hubs):
            # Base spokes for this hub
            hub_spoke_count = spokes_per_hub
            
            # Distribute extra spokes
            if hub_idx < extra_spokes:
                hub_spoke_count += 1
            
            # Ensure within range
            min_spokes, max_spokes = params['spokes_per_hub_range']
            hub_spoke_count = max(min_spokes, min(hub_spoke_count, max_spokes))
            
            for _ in range(hub_spoke_count):
                spoke_name = f"app-spoke-{spoke_counter:03d}"
                spoke_resource_id = f"/subscriptions/{subscription_id}/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/{spoke_name}"
                
                spoke_info = {
                    'name': spoke_name,
                    'resource_id': spoke_resource_id,
                    'primary_hub': hub['resource_id'],
                    'hub_index': hub_idx
                }
                all_spokes.append(spoke_info)
                hub['spokes'].append(spoke_info)
                spoke_counter += 1
    
    # Phase 3: Create standalone spoke-to-spoke clusters
    standalone_clusters = []
    if standalone_cluster_count > 0:
        # Create small clusters (2-4 spokes each)
        cluster_counter = 1
        remaining_cluster_vnets = standalone_cluster_count
        
        while remaining_cluster_vnets > 0:
            cluster_size = min(random.randint(2, 4), remaining_cluster_vnets)
            cluster_vnets = []
            
            for i in range(cluster_size):
                cluster_spoke_name = f"cluster-{cluster_counter}-spoke-{i+1:02d}"
                cluster_spoke_resource_id = f"/subscriptions/{subscription_id}/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/{cluster_spoke_name}"
                
                cluster_vnet_info = {
                    'name': cluster_spoke_name,
                    'resource_id': cluster_spoke_resource_id,
                    'cluster_id': cluster_counter
                }
                cluster_vnets.append(cluster_vnet_info)
                
            standalone_clusters.append(cluster_vnets)
            remaining_cluster_vnets -= cluster_size
            cluster_counter += 1
    
    # Phase 4: Initialize peering structure
    vnet_peerings = {}
    all_resource_ids = [hub['resource_id'] for hub in hubs] + [spoke['resource_id'] for spoke in all_spokes]
    
    # Add standalone cluster VNets to peering tracking
    for cluster in standalone_clusters:
        for cluster_vnet in cluster:
            all_resource_ids.append(cluster_vnet['resource_id'])
    
    # Add isolated VNets resource_ids (they will be created later but need peering tracking)
    for i in range(isolation_count):
        isolated_resource_id = f"/subscriptions/{subscription_id}/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/isolated-{i+1:03d}"
        all_resource_ids.append(isolated_resource_id)
    
    for resource_id in all_resource_ids:
        vnet_peerings[resource_id] = []
    
    # Phase 5: Connect spokes to primary hubs
    for spoke in all_spokes:
        add_bidirectional_peering(vnet_peerings, spoke['resource_id'], spoke['primary_hub'])
    
    # Phase 6: Connect standalone clusters (full mesh within each cluster)
    for cluster in standalone_clusters:
        for i, vnet_a in enumerate(cluster):
            for vnet_b in cluster[i+1:]:
                add_bidirectional_peering(vnet_peerings, vnet_a['resource_id'], vnet_b['resource_id'])
    
    # Phase 7: Inject controlled outliers for hub-connected spokes
    if len(all_spokes) > 1:
        # Spoke-to-spoke connections
        spoke_to_spoke_count = int(len(all_spokes) * params['spoke_to_spoke_rate'])
        for _ in range(spoke_to_spoke_count):
            spoke_a = random.choice(all_spokes)
            same_hub_spokes = [s for s in all_spokes if s['hub_index'] == spoke_a['hub_index'] and s != spoke_a]
            if same_hub_spokes:
                spoke_b = random.choice(same_hub_spokes)
                add_bidirectional_peering(vnet_peerings, spoke_a['resource_id'], spoke_b['resource_id'])
        
        # Cross-zone connections (spokes to other hubs)
        if len(hubs) > 1:
            cross_zone_count = int(len(all_spokes) * params['cross_zone_rate'])
            for _ in range(cross_zone_count):
                spoke = random.choice(all_spokes)
                other_hubs = [h for h in hubs if h['resource_id'] != spoke['primary_hub']]
                if other_hubs:
                    target_hub = random.choice(other_hubs)
                    add_bidirectional_peering(vnet_peerings, spoke['resource_id'], target_hub['resource_id'])
        
        # Multi-hub spokes (additional hub connections)
        if len(hubs) > 1:
            multi_hub_count = int(len(all_spokes) * params['multi_hub_rate'])
            for _ in range(multi_hub_count):
                spoke = random.choice(all_spokes)
                other_hubs = [h for h in hubs if h['resource_id'] != spoke['primary_hub']]
                if other_hubs:
                    secondary_hub = random.choice(other_hubs)
                    add_bidirectional_peering(vnet_peerings, spoke['resource_id'], secondary_hub['resource_id'])
    
    # Phase 8: Create VNet objects
    vnets = []
    combo_index = 0
    
    # Create hub VNets
    for hub in hubs:
        hub_name = hub['name']
        peering_list = vnet_peerings[hub['resource_id']]
        
        expressroute, vpn_gateway, firewall = decorator_combinations[combo_index % len(decorator_combinations)]
        combo_index += 1
        
        vnet = generate_vnet(hub_name, subscription_id, "test-rg", "eastus",
                           peering_list, expressroute, vpn_gateway, firewall)
        vnets.append(vnet)
    
    # Create spoke VNets
    for spoke in all_spokes:
        spoke_name = spoke['name']
        peering_list = vnet_peerings[spoke['resource_id']]
        
        expressroute, vpn_gateway, firewall = decorator_combinations[combo_index % len(decorator_combinations)]
        combo_index += 1
        
        vnet = generate_vnet(spoke_name, subscription_id, "test-rg", "eastus",
                           peering_list, expressroute, vpn_gateway, firewall)
        vnets.append(vnet)
    
    # Create standalone cluster VNets
    for cluster in standalone_clusters:
        for cluster_vnet in cluster:
            cluster_name = cluster_vnet['name']
            peering_list = vnet_peerings[cluster_vnet['resource_id']]
            
            expressroute, vpn_gateway, firewall = decorator_combinations[combo_index % len(decorator_combinations)]
            combo_index += 1
            
            vnet = generate_vnet(cluster_name, subscription_id, "test-rg", "eastus",
                               peering_list, expressroute, vpn_gateway, firewall)
            vnets.append(vnet)
    
    # Phase 9: Create isolated VNets
    for i in range(isolation_count):
        isolated_name = f"isolated-{i+1:03d}"
        
        expressroute, vpn_gateway, firewall = decorator_combinations[combo_index % len(decorator_combinations)]
        combo_index += 1
        
        vnet = generate_vnet(isolated_name, subscription_id, "test-rg", "eastus",
                           [], expressroute, vpn_gateway, firewall)
        vnets.append(vnet)
    
    # Phase 10: Ensure all EdgeTypes are present (if requested)
    if kwargs.get('ensure_all_edge_types', False):
        ensure_all_edge_types(vnets, vnet_peerings)
        
        # Update VNet objects with new peering information
        update_vnet_peering_counts(vnets, vnet_peerings)
    
    return {"vnets": vnets}


def classify_edge_types(vnets: List[Dict[str, Any]]) -> Dict[str, int]:
    """Classify all edges in topology by EdgeType and return counts"""
    
    # Simplified standalone edge classification
    hub_threshold = 8
    
    # Build resource_id to vnet mapping
    resource_id_to_vnet = {vnet['resource_id']: vnet for vnet in vnets}
    
    # Classify hubs and spokes
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= hub_threshold]
    hub_vnets.sort(key=lambda x: x.get('resource_id', ''))  # Deterministic ordering
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < hub_threshold]
    
    # Build zone mapping
    vnet_to_zone = {}
    hub_resource_ids = {hub['resource_id'] for hub in hub_vnets}
    
    # Map hubs to their own zones
    for hub_index, hub in enumerate(hub_vnets):
        vnet_to_zone[hub['resource_id']] = hub_index
    
    # Map spokes to zones based on first hub connection
    for spoke in spoke_vnets:
        spoke_resource_id = spoke['resource_id']
        spoke_peering_ids = spoke.get('peering_resource_ids', [])
        zone_index = None
        
        for hub_index, hub in enumerate(hub_vnets):
            if hub['resource_id'] in spoke_peering_ids:
                zone_index = hub_index
                break
        
        if zone_index is not None:
            vnet_to_zone[spoke_resource_id] = zone_index
    
    # Count edges by type
    edge_counts = {
        'HUB_TO_HUB': 0,
        'HUB_TO_SPOKE_SAME_ZONE': 0,
        'HUB_TO_SPOKE_DIFF_ZONE': 0,
        'SPOKE_TO_SPOKE_SAME_ZONE': 0,
        'SPOKE_TO_SPOKE_DIFF_ZONE': 0,
        'SPOKE_TO_SPOKE_NO_ZONE': 0
    }
    
    processed_pairs = set()
    
    for vnet in vnets:
        source_resource_id = vnet['resource_id']
        
        for target_resource_id in vnet.get('peering_resource_ids', []):
            # Create normalized pair to avoid duplicates
            pair_key = tuple(sorted([source_resource_id, target_resource_id]))
            if pair_key in processed_pairs:
                continue
            
            # Check if bidirectional
            target_vnet = resource_id_to_vnet.get(target_resource_id)
            if not target_vnet or source_resource_id not in target_vnet.get('peering_resource_ids', []):
                continue
            
            # Classify edge type
            source_is_hub = source_resource_id in hub_resource_ids
            target_is_hub = target_resource_id in hub_resource_ids
            source_zone = vnet_to_zone.get(source_resource_id)
            target_zone = vnet_to_zone.get(target_resource_id)
            
            if source_is_hub and target_is_hub:
                edge_counts['HUB_TO_HUB'] += 1
            elif source_is_hub or target_is_hub:
                if source_zone is not None and target_zone is not None and source_zone == target_zone:
                    edge_counts['HUB_TO_SPOKE_SAME_ZONE'] += 1
                else:
                    edge_counts['HUB_TO_SPOKE_DIFF_ZONE'] += 1
            else:
                if source_zone is None or target_zone is None:
                    edge_counts['SPOKE_TO_SPOKE_NO_ZONE'] += 1
                elif source_zone == target_zone:
                    edge_counts['SPOKE_TO_SPOKE_SAME_ZONE'] += 1
                else:
                    edge_counts['SPOKE_TO_SPOKE_DIFF_ZONE'] += 1
            
            processed_pairs.add(pair_key)
    
    return edge_counts


def ensure_all_edge_types(vnets: List[Dict[str, Any]], vnet_peerings: Dict[str, List[str]]) -> None:
    """Ensure all 6 EdgeTypes are present by adding strategic connections"""
    
    # Get current edge type counts
    edge_counts = classify_edge_types(vnets)
    missing_types = [edge_type for edge_type, count in edge_counts.items() if count == 0]
    
    if not missing_types:
        return  # All types already present
    
    # Standalone hub/spoke classification
    hub_threshold = 8
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= hub_threshold]
    hub_vnets.sort(key=lambda x: x.get('resource_id', ''))
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < hub_threshold]
    
    # Build zone mapping
    vnet_to_zone = {}
    hub_resource_ids = {hub['resource_id'] for hub in hub_vnets}
    
    # Map hubs to their own zones
    for hub_index, hub in enumerate(hub_vnets):
        vnet_to_zone[hub['resource_id']] = hub_index
    
    # Map spokes to zones based on first hub connection
    for spoke in spoke_vnets:
        spoke_resource_id = spoke['resource_id']
        spoke_peering_ids = spoke.get('peering_resource_ids', [])
        
        for hub_index, hub in enumerate(hub_vnets):
            if hub['resource_id'] in spoke_peering_ids:
                vnet_to_zone[spoke_resource_id] = hub_index
                break
    
    # Create resource_id to vnet mapping
    resource_id_to_vnet = {vnet['resource_id']: vnet for vnet in vnets}
    
    # Inject missing EdgeTypes
    for edge_type in missing_types:
        if edge_type == 'HUB_TO_HUB' and len(hub_vnets) >= 2:
            # Connect two hubs
            hub_a, hub_b = hub_vnets[0], hub_vnets[1]
            add_bidirectional_peering(vnet_peerings, hub_a['resource_id'], hub_b['resource_id'])
            
        elif edge_type == 'HUB_TO_SPOKE_SAME_ZONE' and hub_vnets and spoke_vnets:
            # Find a hub-spoke pair in same zone
            for hub in hub_vnets:
                hub_zone = vnet_to_zone.get(hub['resource_id'])
                same_zone_spokes = [s for s in spoke_vnets if vnet_to_zone.get(s['resource_id']) == hub_zone]
                if same_zone_spokes:
                    spoke = same_zone_spokes[0]
                    # Check if not already connected
                    if spoke['resource_id'] not in vnet_peerings[hub['resource_id']]:
                        add_bidirectional_peering(vnet_peerings, hub['resource_id'], spoke['resource_id'])
                    break
                    
        elif edge_type == 'HUB_TO_SPOKE_DIFF_ZONE' and len(hub_vnets) >= 2 and spoke_vnets:
            # Connect spoke to hub in different zone
            for spoke in spoke_vnets:
                spoke_zone = vnet_to_zone.get(spoke['resource_id'])
                diff_zone_hubs = [h for h in hub_vnets if vnet_to_zone.get(h['resource_id']) != spoke_zone]
                if diff_zone_hubs:
                    hub = diff_zone_hubs[0]
                    add_bidirectional_peering(vnet_peerings, spoke['resource_id'], hub['resource_id'])
                    break
                    
        elif edge_type == 'SPOKE_TO_SPOKE_SAME_ZONE' and len(spoke_vnets) >= 2:
            # Connect two spokes in same zone
            for spoke_a in spoke_vnets:
                spoke_a_zone = vnet_to_zone.get(spoke_a['resource_id'])
                same_zone_spokes = [s for s in spoke_vnets if s != spoke_a and vnet_to_zone.get(s['resource_id']) == spoke_a_zone]
                if same_zone_spokes:
                    spoke_b = same_zone_spokes[0]
                    add_bidirectional_peering(vnet_peerings, spoke_a['resource_id'], spoke_b['resource_id'])
                    break
                    
        elif edge_type == 'SPOKE_TO_SPOKE_DIFF_ZONE' and len(spoke_vnets) >= 2:
            # Connect spokes from different zones
            for spoke_a in spoke_vnets:
                spoke_a_zone = vnet_to_zone.get(spoke_a['resource_id'])
                diff_zone_spokes = [s for s in spoke_vnets if s != spoke_a and vnet_to_zone.get(s['resource_id']) != spoke_a_zone]
                if diff_zone_spokes:
                    spoke_b = diff_zone_spokes[0]
                    add_bidirectional_peering(vnet_peerings, spoke_a['resource_id'], spoke_b['resource_id'])
                    break
                    
        elif edge_type == 'SPOKE_TO_SPOKE_NO_ZONE':
            # Create or connect standalone cluster vnets
            no_zone_vnets = [v for v in vnets if vnet_to_zone.get(v['resource_id']) is None]
            if len(no_zone_vnets) >= 2:
                # Connect two no-zone vnets
                vnet_a, vnet_b = no_zone_vnets[0], no_zone_vnets[1]
                add_bidirectional_peering(vnet_peerings, vnet_a['resource_id'], vnet_b['resource_id'])
            elif len(no_zone_vnets) == 1 and spoke_vnets:
                # Connect no-zone vnet to a spoke (making the spoke also no-zone)
                no_zone_vnet = no_zone_vnets[0]
                spoke = spoke_vnets[0]
                add_bidirectional_peering(vnet_peerings, no_zone_vnet['resource_id'], spoke['resource_id'])


def update_vnet_peering_counts(vnets: List[Dict[str, Any]], vnet_peerings: Dict[str, List[str]]) -> None:
    """Update peering_resource_ids and peerings_count in VNet objects"""
    for vnet in vnets:
        resource_id = vnet['resource_id']
        if resource_id in vnet_peerings:
            vnet['peering_resource_ids'] = vnet_peerings[resource_id]
            vnet['peerings_count'] = len(vnet_peerings[resource_id])


def parse_arguments():
    """Parse command line arguments with proper CLI switches"""
    parser = argparse.ArgumentParser(
        description='Generate Azure-realistic network topologies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --vnets 20 --centralization 7 --connectivity 3 --isolation 2 --output topology.json
  %(prog)s -v 50 -c 5 -n 8 -i 1 -o large_topology.json --seed 42 --ensure-all-edge-types
  %(prog)s --vnets 10 --centralization 3 --connectivity 5 --isolation 2 --output test.json --spoke-to-spoke-rate 0.1
        """
    )
    
    # Core topology parameters (required)
    required_group = parser.add_argument_group('required arguments')
    required_group.add_argument('-v', '--vnets', type=int, required=True,
                               help='Total number of VNets to generate')
    required_group.add_argument('-c', '--centralization', type=int, required=True,
                               help='Centralization weight (0-10, controls hub-spoke bias)')
    required_group.add_argument('-n', '--connectivity', type=int, required=True,
                               help='Connectivity weight (0-10, controls outlier scenarios)')
    required_group.add_argument('-i', '--isolation', type=int, required=True,
                               help='Isolation weight (0-10, controls unpeered VNets)')
    required_group.add_argument('-o', '--output', type=str, required=True,
                               help='Output JSON filename')
    
    # Outlier control parameters
    outlier_group = parser.add_argument_group('outlier scenario controls')
    outlier_group.add_argument('--spoke-to-spoke-rate', type=float,
                              help='Override spoke-to-spoke connection rate (0.0-1.0)')
    outlier_group.add_argument('--cross-zone-rate', type=float,
                              help='Override cross-zone connection rate (0.0-1.0)')
    outlier_group.add_argument('--multi-hub-rate', type=float,
                              help='Override multi-hub spoke rate (0.0-1.0)')
    outlier_group.add_argument('--standalone-clusters-rate', type=float,
                              help='Override standalone cluster rate (0.0-1.0)')
    
    # Hub structure controls
    hub_group = parser.add_argument_group('hub structure controls')
    hub_group.add_argument('--hub-count', type=int,
                          help='Override hub count (ignores centralization weight)')
    hub_group.add_argument('--min-hub-degree', type=int,
                          help='Minimum connections per hub (default: 8)')
    hub_group.add_argument('--max-hub-degree', type=int,
                          help='Maximum connections per hub (default: 40)')
    
    # Generation controls
    control_group = parser.add_argument_group('generation controls')
    control_group.add_argument('--seed', type=int,
                              help='Random seed for reproducible generation')
    control_group.add_argument('--ensure-all-edge-types', action='store_true',
                              help='Ensure all 6 EdgeTypes are present in generated topology')
    
    return parser.parse_args()


def main():
    """Generate topology based on arguments"""
    try:
        args = parse_arguments()
        
        # Collect optional parameters
        kwargs = {}
        if args.spoke_to_spoke_rate is not None:
            kwargs['spoke_to_spoke_rate'] = args.spoke_to_spoke_rate
        if args.cross_zone_rate is not None:
            kwargs['cross_zone_rate'] = args.cross_zone_rate
        if args.multi_hub_rate is not None:
            kwargs['multi_hub_rate'] = args.multi_hub_rate
        if args.standalone_clusters_rate is not None:
            kwargs['standalone_clusters_rate'] = args.standalone_clusters_rate
        if args.hub_count is not None:
            kwargs['hub_count'] = args.hub_count
        if args.min_hub_degree is not None:
            kwargs['min_hub_degree'] = args.min_hub_degree
        if args.max_hub_degree is not None:
            kwargs['max_hub_degree'] = args.max_hub_degree
        if args.seed is not None:
            kwargs['seed'] = args.seed
        if args.ensure_all_edge_types:
            kwargs['ensure_all_edge_types'] = args.ensure_all_edge_types
        
        # Generate topology
        topology = create_azure_realistic_topology(
            args.vnets, args.centralization, args.connectivity,
            args.isolation, **kwargs
        )
        
        # Calculate statistics
        vnets = topology['vnets']
        total_vnets = len(vnets)
        hub_count = len([v for v in vnets if 'connectivity-hub' in v['name']])
        spoke_count = len([v for v in vnets if 'app-spoke' in v['name']])
        cluster_count = len([v for v in vnets if 'cluster-' in v['name']])
        isolated_count = len([v for v in vnets if 'isolated' in v['name']])
        
        total_edges = sum(len(v['peering_resource_ids']) for v in vnets) // 2
        
        # Show EdgeType distribution if requested
        if args.ensure_all_edge_types:
            edge_counts = classify_edge_types(vnets)
            edge_types_str = ", ".join([f"{et}: {count}" for et, count in edge_counts.items() if count > 0])
            print(f"EdgeTypes: {edge_types_str}")
        
        # Single line output
        if cluster_count > 0:
            print(f"Generated {args.output}: {hub_count} hubs, {spoke_count} spokes, {cluster_count} standalone, {isolated_count} isolated ({total_vnets} total VNets, {total_edges} edges)")
        else:
            print(f"Generated {args.output}: {hub_count} hubs, {spoke_count} spokes, {isolated_count} isolated ({total_vnets} total VNets, {total_edges} edges)")
        
        # Write to file
        with open(args.output, "w") as f:
            json.dump(topology, f, indent=2)
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()