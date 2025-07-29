#!/usr/bin/env python3
"""
Comprehensive validation script for CloudNet Draw sample topologies
Validates JSON topology files and their corresponding DrawIO diagrams for duplicate edges
"""

import json
import xml.etree.ElementTree as ET
import os
import sys
from typing import Dict, List, Tuple, Set
import re


def load_json_topology(filepath: str) -> Dict:
    """Load and parse JSON topology file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR: Failed to load {filepath}: {e}")
        return {}


def parse_drawio_edges(filepath: str) -> List[Tuple[str, str]]:
    """Parse DrawIO XML file and extract edge connections"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        edges = []
        
        # Find all edge elements in the DrawIO XML
        # DrawIO edges have source and target attributes
        for element in root.iter():
            if element.tag == 'mxCell' and element.get('edge') == '1':
                source = element.get('source')
                target = element.get('target')
                if source and target:
                    edges.append((source, target))
        
        return edges
    except Exception as e:
        print(f"ERROR: Failed to parse {filepath}: {e}")
        return []


def parse_drawio_vnets(filepath: str) -> List[Dict[str, str]]:
    """Parse DrawIO XML file and extract VNet information using XML IDs as primary identifiers"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        vnets = []
        seen_resource_ids = set()  # Track resource_ids to avoid duplicates
        
        # Find all VNet group containers using XML IDs
        for element in root.iter():
            if element.tag == 'object':
                element_id = element.get('id', '')
                resource_id = element.get('resource_id', '')
                label = element.get('label', '')
                
                # Only include group containers with resource_id (avoid inner .main duplicates)
                # Group containers have mxCell children with style="group"
                if resource_id and resource_id not in seen_resource_ids:
                    # Check if this is a group container by looking for group style in children
                    is_group = False
                    for child in element:
                        if child.tag == 'mxCell' and child.get('style') == 'group':
                            is_group = True
                            break
                    
                    if is_group:
                        seen_resource_ids.add(resource_id)
                        
                        # Use XML ID directly as primary identifier
                        # Names are only extracted for error reporting
                        vnet_name = extract_vnet_name_from_hierarchical_id(element_id)
                        
                        vnet_info = {
                            'xml_id': element_id,  # Primary identifier
                            'id': element_id,      # Backward compatibility
                            'label': label,
                            'resource_id': resource_id,
                            'name': vnet_name      # For error messages only
                        }
                        vnets.append(vnet_info)
        
        return vnets
    except Exception as e:
        print(f"ERROR: Failed to parse VNets from {filepath}: {e}")
        return []


def extract_vnet_name_from_hierarchical_id(hierarchical_id: str) -> str:
    """Extract VNet name from hierarchical ID format
    
    Examples:
        'Test Subscription.test-rg.connectivity-hub-01' -> 'connectivity-hub-01'
        'Test Subscription.test-rg.connectivity-hub-01.main' -> 'connectivity-hub-01'
        'simple-vnet' -> 'simple-vnet' (fallback for test scenarios)
    """
    if not hierarchical_id:
        return ""
    
    # Split by dots and get the VNet name (third component in full format)
    parts = hierarchical_id.split('.')
    
    if len(parts) >= 3:
        # Full hierarchical format: subscription.resourcegroup.vnet[.element_type[.suffix]]
        return parts[2]
    elif len(parts) == 1:
        # Simple format (test scenarios): just the VNet name
        return parts[0]
    else:
        # Fallback: return the last part before any element type suffixes
        return parts[-1] if not parts[-1] in ['main', 'group', 'subnet', 'icon'] else parts[-2]


def extract_vnet_name_from_label(label: str) -> str:
    """Extract VNet name from DrawIO label"""
    lines = label.split('\n')
    if len(lines) >= 2:
        # Second line typically contains the VNet name
        return lines[1].strip()
    return ""


def parse_drawio_edge_endpoints(filepath: str) -> List[Tuple[str, str, str, str]]:
    """Parse DrawIO XML file and extract edge information using XML IDs and resource_ids"""
    try:
        tree = ET.parse(filepath)
        root = tree.getroot()
        
        # Build mapping from XML IDs to resource_ids
        id_to_resource_id = {}
        
        for element in root.iter():
            if element.tag == 'object':
                element_id = element.get('id', '')
                resource_id = element.get('resource_id', '')
                
                # Map XML ID to resource_id if available
                if element_id and resource_id:
                    id_to_resource_id[element_id] = resource_id
        
        edges = []
        edge_styles = {}  # Track edge styles for validation
        
        # Find all edge elements and resolve their endpoints using XML IDs
        for element in root.iter():
            if element.tag == 'mxCell' and element.get('edge') == '1':
                source_xml_id = element.get('source')
                target_xml_id = element.get('target')
                edge_style = element.get('style', '')
                
                if source_xml_id and target_xml_id:
                    source_resource_id = id_to_resource_id.get(source_xml_id, '')
                    target_resource_id = id_to_resource_id.get(target_xml_id, '')
                    
                    # Store edge style for analysis using resource_ids
                    if source_resource_id and target_resource_id:
                        edge_key = tuple(sorted([source_resource_id, target_resource_id]))
                        edge_styles[edge_key] = edge_style
                    
                    # Return XML IDs and resource_ids for validation
                    edges.append((source_xml_id, target_xml_id, source_resource_id, target_resource_id))
        
        return edges
    except Exception as e:
        print(f"ERROR: Failed to parse edge endpoints from {filepath}: {e}")
        return []


def get_json_peering_relationships(topology: Dict) -> Set[Tuple[str, str]]:
    """Get all peering relationships from JSON topology using resource_ids as normalized pairs"""
    if not topology or 'vnets' not in topology:
        return set()
    
    peering_pairs = set()
    vnets = topology['vnets']
    
    for vnet in vnets:
        vnet_resource_id = vnet.get('resource_id', '')
        peering_resource_ids = vnet.get('peering_resource_ids', [])
        
        for peering_resource_id in peering_resource_ids:
            if peering_resource_id and vnet_resource_id != peering_resource_id:
                # Create normalized pair using resource_ids (always sort to avoid duplicates)
                pair = tuple(sorted([vnet_resource_id, peering_resource_id]))
                peering_pairs.add(pair)
    
    return peering_pairs


def get_drawio_peering_relationships(filepath: str) -> Set[Tuple[str, str]]:
    """Get all peering relationships from DrawIO file using resource_ids as normalized pairs"""
    edges = parse_drawio_edge_endpoints(filepath)
    peering_pairs = set()
    
    for source_xml_id, target_xml_id, source_resource_id, target_resource_id in edges:
        if source_resource_id and target_resource_id and source_resource_id != target_resource_id:
            # Create normalized pair using resource_ids (always sort to avoid duplicates)
            pair = tuple(sorted([source_resource_id, target_resource_id]))
            peering_pairs.add(pair)
    
    return peering_pairs


def count_json_peering_relationships(topology: Dict) -> int:
    """Count actual peering relationships from JSON topology (CloudNet Draw format)"""
    if not topology or 'vnets' not in topology:
        return 0
    
    peering_pairs = set()
    vnets = topology['vnets']
    
    # Create mapping from resource_id to VNet for lookups
    resource_id_to_vnet = {vnet.get('resource_id'): vnet for vnet in vnets if vnet.get('resource_id')}
    
    for vnet in vnets:
        vnet_resource_id = vnet.get('resource_id', '')
        peering_resource_ids = vnet.get('peering_resource_ids', [])
        
        for peering_resource_id in peering_resource_ids:
            # Only count if the target VNet exists in our topology
            if peering_resource_id in resource_id_to_vnet:
                # Create normalized pair (always sort to avoid duplicates)
                pair = tuple(sorted([vnet_resource_id, peering_resource_id]))
                peering_pairs.add(pair)
    
    return len(peering_pairs)


def extract_vnet_name_from_id(vnet_id: str) -> str:
    """Extract VNet name from Azure resource ID"""
    if '/virtualNetworks/' in vnet_id:
        return vnet_id.split('/virtualNetworks/')[-1]
    return vnet_id


def count_hub_spoke_cross_zone_edges(topology: Dict) -> Tuple[int, int]:
    """Count hub-spoke and cross-zone connectivity edges expected from JSON (CloudNet Draw format)"""
    if not topology or 'vnets' not in topology:
        return 0, 0
    
    vnets = topology['vnets']
    hub_threshold = 10
    
    # Create mapping from resource_id to VNet for lookups
    resource_id_to_vnet = {vnet.get('resource_id'): vnet for vnet in vnets if vnet.get('resource_id')}
    
    # Classify VNets based on peering count
    hubs = []
    spokes = []
    
    for vnet in vnets:
        peering_count = len(vnet.get('peering_resource_ids', []))
        if peering_count >= hub_threshold:
            hubs.append(vnet)
        elif peering_count > 0:
            spokes.append(vnet)
    
    # Count hub-spoke edges
    hub_spoke_edges = 0
    for hub in hubs:
        hub_peerings = hub.get('peering_resource_ids', [])
        # Only count peerings to VNets that exist in our topology
        valid_peerings = [p for p in hub_peerings if p in resource_id_to_vnet]
        hub_spoke_edges += len(valid_peerings)
    
    # Count cross-zone connectivity edges (spoke-to-spoke through different hubs)
    cross_zone_edges = 0
    if len(hubs) > 1:
        # Group spokes by their hub
        hub_spoke_groups = {}
        for hub in hubs:
            hub_resource_id = hub.get('resource_id', '')
            hub_name = extract_vnet_name_from_id(hub_resource_id)
            hub_spoke_groups[hub_name] = []
            
            hub_peerings = hub.get('peering_resource_ids', [])
            for peering_resource_id in hub_peerings:
                if peering_resource_id in resource_id_to_vnet:
                    peered_vnet = resource_id_to_vnet[peering_resource_id]
                    peered_vnet_name = extract_vnet_name_from_id(peering_resource_id)
                    hub_spoke_groups[hub_name].append(peered_vnet_name)
        
        # Count cross-zone edges (cartesian product of spokes from different hubs)
        hub_names = list(hub_spoke_groups.keys())
        for i in range(len(hub_names)):
            for j in range(i + 1, len(hub_names)):
                hub1_spokes = len(hub_spoke_groups[hub_names[i]])
                hub2_spokes = len(hub_spoke_groups[hub_names[j]])
                cross_zone_edges += hub1_spokes * hub2_spokes
    
    return hub_spoke_edges, cross_zone_edges


def validate_endpoint_consistency(json_file: str, drawio_file: str) -> bool:
    """Validate that endpoints match between JSON and DrawIO files using resource_id as primary key"""
    topology = load_json_topology(json_file)
    if not topology:
        return False
    
    vnets = topology.get('vnets', [])
    base_name = os.path.basename(json_file)
    validation_passed = True
    
    # Create mapping from JSON resource_id to their peering connections
    json_vnet_peerings = {}
    resource_id_to_name = {}
    
    for vnet in vnets:
        resource_id = vnet.get('resource_id')
        vnet_name = vnet.get('name')
        if resource_id and vnet_name:
            resource_id_to_name[resource_id] = vnet_name
            json_vnet_peerings[resource_id] = set(vnet.get('peering_resource_ids', []))
    
    # Parse DrawIO VNets and build resource_id mapping
    drawio_vnets = parse_drawio_vnets(drawio_file)
    drawio_vnet_peerings = {}
    drawio_resource_ids = set()
    
    for vnet_info in drawio_vnets:
        resource_id = vnet_info.get('resource_id')
        if resource_id:
            drawio_resource_ids.add(resource_id)
            drawio_vnet_peerings[resource_id] = set()
    
    # Parse DrawIO edges and map them to resource_ids
    drawio_edges = parse_drawio_edge_endpoints(drawio_file)
    
    # Build reverse mapping from DrawIO element IDs to resource_ids
    element_id_to_resource_id = {}
    for vnet_info in drawio_vnets:
        element_id = vnet_info.get('id')
        resource_id = vnet_info.get('resource_id')
        if element_id and resource_id:
            element_id_to_resource_id[element_id] = resource_id
    
    # Process edges using resource_ids
    for source_id, target_id, source_name, target_name in drawio_edges:
        source_resource_id = element_id_to_resource_id.get(source_id)
        target_resource_id = element_id_to_resource_id.get(target_id)
        
        if source_resource_id and target_resource_id:
            if source_resource_id not in drawio_vnet_peerings:
                drawio_vnet_peerings[source_resource_id] = set()
            if target_resource_id not in drawio_vnet_peerings:
                drawio_vnet_peerings[target_resource_id] = set()
                
            drawio_vnet_peerings[source_resource_id].add(target_resource_id)
            drawio_vnet_peerings[target_resource_id].add(source_resource_id)
    
    # Compare JSON and DrawIO using resource_ids
    json_resource_ids = set(json_vnet_peerings.keys())
    
    # Check for missing VNets in DrawIO
    missing_resource_ids = json_resource_ids - drawio_resource_ids
    if missing_resource_ids:
        missing_names = {resource_id_to_name.get(rid, rid) for rid in missing_resource_ids}
        print(f"ERROR: {base_name} VNets missing in DrawIO: {missing_names}")
        validation_passed = False
    
    # Check for extra VNets in DrawIO
    extra_resource_ids = drawio_resource_ids - json_resource_ids
    if extra_resource_ids:
        extra_names = {resource_id_to_name.get(rid, rid) for rid in extra_resource_ids}
        print(f"ERROR: {base_name} Extra VNets in DrawIO: {extra_names}")
        validation_passed = False
    
    # Check peering consistency for each VNet using resource_ids
    for resource_id in json_resource_ids:
        if resource_id not in drawio_vnet_peerings:
            continue
            
        json_peers = json_vnet_peerings[resource_id]
        drawio_peers = drawio_vnet_peerings[resource_id]
        
        missing_peers = json_peers - drawio_peers
        extra_peers = drawio_peers - json_peers
        
        vnet_name = resource_id_to_name.get(resource_id, resource_id)
        
        if missing_peers:
            missing_names = {resource_id_to_name.get(rid, rid) for rid in missing_peers}
            print(f"ERROR: {base_name} VNet '{vnet_name}' missing peering connections in DrawIO: {missing_names}")
            validation_passed = False
            
        if extra_peers:
            extra_names = {resource_id_to_name.get(rid, rid) for rid in extra_peers}
            print(f"ERROR: {base_name} VNet '{vnet_name}' has extra peering connections in DrawIO: {extra_names}")
            validation_passed = False
    
    return validation_passed


def validate_multi_hub_connections(json_file: str, drawio_file: str) -> bool:
    """Validate multi-hub spoke connections are properly represented using resource_id indexing"""
    topology = load_json_topology(json_file)
    if not topology:
        return False
    
    vnets = topology.get('vnets', [])
    base_name = os.path.basename(json_file)
    validation_passed = True
    
    # Classify VNets by peering count (using same threshold as config)
    hub_threshold = 10
    hub_vnets = [vnet for vnet in vnets if len(vnet.get('peering_resource_ids', [])) >= hub_threshold]
    spoke_vnets = [vnet for vnet in vnets if len(vnet.get('peering_resource_ids', [])) < hub_threshold and vnet.get('peering_resource_ids')]
    
    if len(hub_vnets) <= 1:
        # No multi-hub scenarios possible
        return True
    
    # Create resource ID to name mapping
    resource_id_to_name = {vnet.get('resource_id'): vnet.get('name') for vnet in vnets if vnet.get('resource_id') and vnet.get('name')}
    hub_resource_ids = {vnet.get('resource_id') for vnet in hub_vnets if vnet.get('resource_id')}
    
    # Find spokes that connect to multiple hubs using resource_ids
    multi_hub_spokes = []
    for spoke in spoke_vnets:
        spoke_resource_id = spoke.get('resource_id')
        spoke_name = spoke.get('name')
        connected_hub_resource_ids = set()
        
        for peering_resource_id in spoke.get('peering_resource_ids', []):
            if peering_resource_id in hub_resource_ids:
                connected_hub_resource_ids.add(peering_resource_id)
        
        if len(connected_hub_resource_ids) > 1:
            connected_hub_names = {resource_id_to_name.get(rid) for rid in connected_hub_resource_ids}
            multi_hub_spokes.append((spoke_resource_id, spoke_name, connected_hub_resource_ids, connected_hub_names))
    
    # Parse DrawIO VNets and create resource_id mapping
    drawio_vnets = parse_drawio_vnets(drawio_file)
    element_id_to_resource_id = {}
    for vnet_info in drawio_vnets:
        element_id = vnet_info.get('id')
        resource_id = vnet_info.get('resource_id')
        if element_id and resource_id:
            element_id_to_resource_id[element_id] = resource_id
    
    # Parse DrawIO edges and build resource_id connections
    drawio_edges = parse_drawio_edge_endpoints(drawio_file)
    drawio_connections = set()
    
    for source_id, target_id, source_name, target_name in drawio_edges:
        source_resource_id = element_id_to_resource_id.get(source_id)
        target_resource_id = element_id_to_resource_id.get(target_id)
        if source_resource_id and target_resource_id:
            drawio_connections.add(tuple(sorted([source_resource_id, target_resource_id])))
    
    # Check each multi-hub spoke using resource_ids
    for spoke_resource_id, spoke_name, connected_hub_resource_ids, connected_hub_names in multi_hub_spokes:
        for hub_resource_id in connected_hub_resource_ids:
            connection_key = tuple(sorted([spoke_resource_id, hub_resource_id]))
            if connection_key not in drawio_connections:
                hub_name = resource_id_to_name.get(hub_resource_id, hub_resource_id)
                print(f"ERROR: {base_name} Multi-hub connection missing in DrawIO: {spoke_name} ↔ {hub_name}")
                validation_passed = False
    
    if multi_hub_spokes:
        print(f"INFO: {base_name} Found {len(multi_hub_spokes)} multi-hub spokes")
    
    return validation_passed


def validate_json_duplicate_peerings(json_file: str) -> bool:
    """Check for duplicate peerings in JSON topology"""
    topology = load_json_topology(json_file)
    if not topology:
        return False
    
    vnets = topology.get('vnets', [])
    base_name = os.path.basename(json_file)
    validation_passed = True
    
    # Create mapping from resource_id to VNet name
    resource_id_to_name = {vnet.get('resource_id'): vnet.get('name') for vnet in vnets if vnet.get('resource_id') and vnet.get('name')}
    
    # Check each VNet for duplicate peerings
    for vnet in vnets:
        vnet_name = vnet.get('name', '')
        peering_resource_ids = vnet.get('peering_resource_ids', [])
        
        # Check for duplicates within the same VNet's peering list
        unique_peerings = set(peering_resource_ids)
        if len(peering_resource_ids) != len(unique_peerings):
            duplicate_count = len(peering_resource_ids) - len(unique_peerings)
            print(f"ERROR: {base_name} VNet '{vnet_name}' has {duplicate_count} duplicate peering entries")
            validation_passed = False
        
        # Check for self-peering (VNet peering to itself)
        vnet_resource_id = vnet.get('resource_id', '')
        if vnet_resource_id in peering_resource_ids:
            print(f"ERROR: {base_name} VNet '{vnet_name}' has self-peering (peering to itself)")
            validation_passed = False
    
    # Check for asymmetric peerings (A->B without B->A)
    vnet_peerings = {}
    for vnet in vnets:
        vnet_resource_id = vnet.get('resource_id', '')
        if vnet_resource_id:
            vnet_peerings[vnet_resource_id] = set(vnet.get('peering_resource_ids', []))
    
    for vnet_resource_id, peering_set in vnet_peerings.items():
        vnet_name = resource_id_to_name.get(vnet_resource_id, vnet_resource_id)
        
        for peering_resource_id in peering_set:
            if peering_resource_id in vnet_peerings:
                # Check if the peering is bidirectional
                if vnet_resource_id not in vnet_peerings[peering_resource_id]:
                    peer_name = resource_id_to_name.get(peering_resource_id, peering_resource_id)
                    print(f"ERROR: {base_name} Asymmetric peering: '{vnet_name}' -> '{peer_name}' (missing reverse peering)")
                    validation_passed = False
    
    return validation_passed


def validate_topology_file(json_file: str, hld_file: str = None, mld_file: str = None) -> bool:
    """Comprehensive validation of topology file and its corresponding diagrams"""
    # Load JSON topology
    topology = load_json_topology(json_file)
    if not topology:
        return False
    
    vnets = topology.get('vnets', [])
    json_vnet_count = len(vnets)
    json_resource_ids = {vnet.get('resource_id') for vnet in vnets if vnet.get('resource_id')}
    json_peering_relationships = get_json_peering_relationships(topology)
    
    base_name = os.path.basename(json_file)
    validation_passed = True
    
    # Check for duplicate peerings in JSON
    if not validate_json_duplicate_peerings(json_file):
        validation_passed = False
    
    # Enhanced validation for endpoint consistency
    if hld_file and os.path.exists(hld_file):
        if not validate_endpoint_consistency(json_file, hld_file):
            validation_passed = False
        if not validate_multi_hub_connections(json_file, hld_file):
            validation_passed = False
    
    if mld_file and os.path.exists(mld_file):
        if not validate_endpoint_consistency(json_file, mld_file):
            validation_passed = False
        if not validate_multi_hub_connections(json_file, mld_file):
            validation_passed = False
    
    # Validate HLD file if provided
    if hld_file and os.path.exists(hld_file):
        # Check for duplicate edges
        hld_edges = parse_drawio_edges(hld_file)
        unique_hld_edges = set(hld_edges)
        hld_duplicates = len(hld_edges) - len(unique_hld_edges)
        
        if hld_duplicates > 0:
            print(f"ERROR: {base_name} HLD has {hld_duplicates} duplicate edges")
            validation_passed = False
        
        # Parse VNets from DrawIO
        drawio_vnets = parse_drawio_vnets(hld_file)
        drawio_vnet_count = len(drawio_vnets)
        drawio_resource_ids = {vnet['resource_id'] for vnet in drawio_vnets if vnet['resource_id']}
        
        # Parse peering relationships from DrawIO
        drawio_peering_relationships = get_drawio_peering_relationships(hld_file)
        
        # 1. Validate VNet count matches
        if json_vnet_count != drawio_vnet_count:
            print(f"ERROR: {base_name} VNet count mismatch - JSON: {json_vnet_count}, HLD: {drawio_vnet_count}")
            validation_passed = False
        
        # 2. Validate VNet resource_ids match (using resource_ids as primary keys)
        missing_in_drawio = json_resource_ids - drawio_resource_ids
        extra_in_drawio = drawio_resource_ids - json_resource_ids
        
        if missing_in_drawio:
            # Extract names for error reporting only
            missing_names = {extract_vnet_name_from_id(rid) for rid in missing_in_drawio}
            print(f"ERROR: {base_name} VNets missing in HLD: {missing_names}")
            validation_passed = False
        
        if extra_in_drawio:
            # Extract names for error reporting only
            extra_names = {extract_vnet_name_from_id(rid) for rid in extra_in_drawio}
            print(f"ERROR: {base_name} Extra VNets in HLD: {extra_names}")
            validation_passed = False
        
        # 3. Validate edge count matches
        if len(json_peering_relationships) != len(drawio_peering_relationships):
            print(f"ERROR: {base_name} Edge count mismatch - JSON: {len(json_peering_relationships)}, HLD: {len(drawio_peering_relationships)}")
            validation_passed = False
        
        # 4. Validate peering relationships match
        missing_peerings = json_peering_relationships - drawio_peering_relationships
        extra_peerings = drawio_peering_relationships - json_peering_relationships
        
        if missing_peerings:
            print(f"ERROR: {base_name} Peerings missing in HLD: {missing_peerings}")
            validation_passed = False
        
        if extra_peerings:
            print(f"ERROR: {base_name} Extra peerings in HLD: {extra_peerings}")
            validation_passed = False
    
    # Validate MLD file if provided
    if mld_file and os.path.exists(mld_file):
        # Check for duplicate edges
        mld_edges = parse_drawio_edges(mld_file)
        unique_mld_edges = set(mld_edges)
        mld_duplicates = len(mld_edges) - len(unique_mld_edges)
        
        if mld_duplicates > 0:
            print(f"ERROR: {base_name} MLD has {mld_duplicates} duplicate edges")
            validation_passed = False
        
        # Parse VNets from DrawIO
        drawio_vnets = parse_drawio_vnets(mld_file)
        drawio_vnet_count = len(drawio_vnets)
        drawio_resource_ids = {vnet['resource_id'] for vnet in drawio_vnets if vnet['resource_id']}
        
        # Parse peering relationships from DrawIO
        drawio_peering_relationships = get_drawio_peering_relationships(mld_file)
        
        # 1. Validate VNet count matches
        if json_vnet_count != drawio_vnet_count:
            print(f"ERROR: {base_name} VNet count mismatch - JSON: {json_vnet_count}, MLD: {drawio_vnet_count}")
            validation_passed = False
        
        # 2. Validate VNet resource_ids match (using resource_ids as primary keys)
        missing_in_drawio = json_resource_ids - drawio_resource_ids
        extra_in_drawio = drawio_resource_ids - json_resource_ids
        
        if missing_in_drawio:
            # Extract names for error reporting only
            missing_names = {extract_vnet_name_from_id(rid) for rid in missing_in_drawio}
            print(f"ERROR: {base_name} VNets missing in MLD: {missing_names}")
            validation_passed = False
        
        if extra_in_drawio:
            # Extract names for error reporting only
            extra_names = {extract_vnet_name_from_id(rid) for rid in extra_in_drawio}
            print(f"ERROR: {base_name} Extra VNets in MLD: {extra_names}")
            validation_passed = False
        
        # 3. Validate edge count matches
        if len(json_peering_relationships) != len(drawio_peering_relationships):
            print(f"ERROR: {base_name} Edge count mismatch - JSON: {len(json_peering_relationships)}, MLD: {len(drawio_peering_relationships)}")
            validation_passed = False
        
        # 4. Validate peering relationships match
        missing_peerings = json_peering_relationships - drawio_peering_relationships
        extra_peerings = drawio_peering_relationships - json_peering_relationships
        
        if missing_peerings:
            print(f"ERROR: {base_name} Peerings missing in MLD: {missing_peerings}")
            validation_passed = False
        
        if extra_peerings:
            print(f"ERROR: {base_name} Extra peerings in MLD: {extra_peerings}")
            validation_passed = False
    
    # Print validation result
    if validation_passed:
        # Use the most appropriate edge count for reporting
        if hld_file and os.path.exists(hld_file):
            diagram_edge_count = len(parse_drawio_edges(hld_file))
        elif mld_file and os.path.exists(mld_file):
            diagram_edge_count = len(parse_drawio_edges(mld_file))
        else:
            diagram_edge_count = len(json_peering_relationships)
        
        print(f"PASSED {base_name}: {json_vnet_count} VNets, {diagram_edge_count} edges")
    
    return validation_passed


def get_file_mappings() -> List[Tuple[str, str, str]]:
    """Get dynamic file mappings for JSON, HLD, and MLD files"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    examples_dir = os.path.join(script_dir, '..', 'examples')  # This script is in utils, examples is one level up
    mappings = []
    
    # Find all JSON files
    json_files = [f for f in os.listdir(examples_dir) if f.endswith('.json')]
    
    for json_file in json_files:
        base_name = json_file.replace('.json', '')
        json_path = os.path.join(examples_dir, json_file)
        hld_path = os.path.join(examples_dir, f"{base_name}_hld.drawio")
        mld_path = os.path.join(examples_dir, f"{base_name}_mld.drawio")
        
        mappings.append((json_path, hld_path, mld_path))
    
    return mappings


def parse_arguments():
    """Parse command line arguments with proper CLI switches"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Comprehensive validation script for CloudNet Draw topology files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Validate all topology files in examples directory
  %(prog)s --topology topology.json          # Validate just topology file
  %(prog)s --topology topology.json --hld topology_hld.drawio --mld topology_mld.drawio
  %(prog)s -t topology.json -H topology_hld.drawio -M topology_mld.drawio
        """
    )
    
    # File specification options
    files_group = parser.add_argument_group('file specification')
    files_group.add_argument('-t', '--topology', type=str,
                            help='JSON topology file to validate')
    files_group.add_argument('-H', '--hld', type=str,
                            help='HLD (High Level Design) DrawIO file to validate')
    files_group.add_argument('-M', '--mld', type=str,
                            help='MLD (Mid Level Design) DrawIO file to validate')
    
    # Validation options
    validation_group = parser.add_argument_group('validation options')
    validation_group.add_argument('--quiet', action='store_true',
                                 help='Suppress informational output')
    
    return parser.parse_args()


def main():
    """Main validation function"""
    args = parse_arguments()
    
    # Validate argument combinations
    if args.hld and not args.topology:
        print("ERROR: --hld requires --topology to be specified")
        sys.exit(1)
    if args.mld and not args.topology:
        print("ERROR: --mld requires --topology to be specified")
        sys.exit(1)
    
    # Case 1: Validate specific files
    if args.topology:
        if not os.path.exists(args.topology):
            print(f"ERROR: Topology file not found: {args.topology}")
            sys.exit(1)
        
        hld_file = args.hld if args.hld and os.path.exists(args.hld) else None
        mld_file = args.mld if args.mld and os.path.exists(args.mld) else None
        
        if not validate_topology_file(args.topology, hld_file, mld_file):
            sys.exit(1)
        return 0
    
    # Case 2: Default behavior - validate all files in examples directory
    if not args.quiet:
        print("Validating generated diagrams...")
    
    # Get dynamic file mappings
    file_mappings = get_file_mappings()
    
    if not file_mappings:
        print("ERROR: No JSON topology files found in examples directory")
        sys.exit(1)
    
    all_valid = True
    
    for json_file, hld_file, mld_file in file_mappings:
        if not os.path.exists(json_file):
            if not args.quiet:
                print(f"ERROR: JSON file not found: {json_file}")
            all_valid = False
            continue
            
        # Validate the topology file and its diagrams
        if not validate_topology_file(json_file, hld_file, mld_file):
            all_valid = False
    
    if not all_valid:
        print("VALIDATION FAILED: Some files have errors")
        sys.exit(1)
    
    return 0


if __name__ == "__main__":
    main()