#!/usr/bin/env python3
"""
Validate JSON topology files against their corresponding DrawIO diagrams.
Compares VNet counts, edge counts, and connection relationships to ensure
the DrawIO diagrams accurately represent the JSON topology.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import Dict, List, Set, Tuple


def parse_json_topology(json_file: str) -> Tuple[Dict[str, str], Set[Tuple[str, str]]]:
    """
    Parse JSON topology file to extract VNets and their peering relationships.
    
    Returns:
        - vnet_mapping: dict mapping resource_id to vnet name
        - expected_edges: set of normalized edge tuples (name1, name2)
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
        
        vnets = data.get("vnets", [])
        vnet_mapping = {}
        expected_edges = set()
        
        # Create resource_id to name mapping
        for vnet in vnets:
            if 'resource_id' in vnet and 'name' in vnet:
                vnet_mapping[vnet['resource_id']] = vnet['name']
        
        # Extract peering relationships
        for vnet in vnets:
            vnet_name = vnet.get('name')
            vnet_id = vnet.get('resource_id')
            peering_ids = vnet.get('peering_resource_ids', [])
            
            for peer_id in peering_ids:
                peer_name = vnet_mapping.get(peer_id)
                if peer_name and vnet_name:
                    # Create normalized edge (alphabetically sorted names)
                    edge = tuple(sorted([vnet_name, peer_name]))
                    expected_edges.add(edge)
        
        return vnet_mapping, expected_edges
    
    except Exception as e:
        print(f"Error parsing JSON file {json_file}: {e}")
        return {}, set()


def parse_drawio_topology(drawio_file: str) -> Tuple[Dict[str, str], Set[Tuple[str, str]]]:
    """
    Parse DrawIO file to extract VNet objects and edge connections.
    
    Returns:
        - vnet_objects: dict mapping object_id to vnet name
        - actual_edges: set of normalized edge tuples (name1, name2)
    """
    try:
        tree = ET.parse(drawio_file)
        root = tree.getroot()
        
        vnet_objects = {}
        actual_edges = set()
        
        # Extract VNet objects from DrawIO
        for obj in root.iter('object'):
            obj_id = obj.get('id')
            label = obj.get('label', '')
            
            # Look for VNet labels that contain subscription info
            if 'Subscription:' in label and obj_id:
                lines = label.strip().split('\n')
                if len(lines) >= 2:
                    vnet_name = lines[1].strip()
                    vnet_objects[obj_id] = vnet_name
        
        # Extract edges from DrawIO
        for cell in root.iter('mxCell'):
            if cell.get('edge') == '1':
                source_id = cell.get('source')
                target_id = cell.get('target')
                
                if source_id and target_id:
                    source_name = vnet_objects.get(source_id)
                    target_name = vnet_objects.get(target_id)
                    
                    if source_name and target_name:
                        # Create normalized edge (alphabetically sorted names)
                        edge = tuple(sorted([source_name, target_name]))
                        actual_edges.add(edge)
        
        return vnet_objects, actual_edges
    
    except Exception as e:
        print(f"Error parsing DrawIO file {drawio_file}: {e}")
        return {}, set()


def validate_topology_pair(json_file: str, hld_file: str, mld_file: str) -> bool:
    """
    Validate a JSON file against its HLD and MLD DrawIO files.
    
    Returns:
        True if all validations pass, False otherwise
    """
    # Parse JSON topology
    json_vnets, json_edges = parse_json_topology(json_file)
    if not json_vnets:
        print(f"FAILED {os.path.basename(json_file)}: Failed to parse JSON file")
        return False
    
    json_vnet_count = len(json_vnets)
    json_edge_count = len(json_edges)
    
    errors = []
    
    # Validate HLD file
    if not os.path.exists(hld_file):
        errors.append("HLD file missing")
    else:
        hld_vnets, hld_edges = parse_drawio_topology(hld_file)
        hld_vnet_count = len(hld_vnets)
        hld_edge_count = len(hld_edges)
        
        if json_vnet_count != hld_vnet_count:
            errors.append(f"HLD VNet count mismatch ({json_vnet_count} vs {hld_vnet_count})")
        
        if json_edge_count != hld_edge_count:
            errors.append(f"HLD edge count mismatch ({json_edge_count} vs {hld_edge_count})")
        
        missing_edges = json_edges - hld_edges
        extra_edges = hld_edges - json_edges
        if missing_edges or extra_edges:
            errors.append(f"HLD edge relationship mismatch")
    
    # Validate MLD file
    if not os.path.exists(mld_file):
        errors.append("MLD file missing")
    else:
        mld_vnets, mld_edges = parse_drawio_topology(mld_file)
        mld_vnet_count = len(mld_vnets)
        mld_edge_count = len(mld_edges)
        
        if json_vnet_count != mld_vnet_count:
            errors.append(f"MLD VNet count mismatch ({json_vnet_count} vs {mld_vnet_count})")
        
        if json_edge_count != mld_edge_count:
            errors.append(f"MLD edge count mismatch ({json_edge_count} vs {mld_edge_count})")
        
        missing_edges = json_edges - mld_edges
        extra_edges = mld_edges - json_edges
        if missing_edges or extra_edges:
            errors.append(f"MLD edge relationship mismatch")
    
    # Output result
    if errors:
        print(f"FAILED {os.path.basename(json_file)}: {'; '.join(errors)}")
        return False
    else:
        print(f"PASSED {os.path.basename(json_file)}: {json_vnet_count} VNets, {json_edge_count} edges")
        return True


def main():
    """
    Main validation function that processes all JSON files and their DrawIO pairs.
    """
    examples_dir = "."
    
    # Dynamically build file mapping by scanning for JSON files
    file_mapping = {}
    
    # Find all JSON files in the examples directory
    for filename in os.listdir(examples_dir):
        if filename.endswith('.json'):
            # Extract base name (without .json extension)
            base_name = filename[:-5]  # Remove '.json'
            
            # Handle special naming pattern: files ending with '_example'
            # map to DrawIO files without '_example'
            if base_name.endswith('_example'):
                drawio_base = base_name[:-8]  # Remove '_example'
            else:
                drawio_base = base_name
            
            # Build corresponding DrawIO filenames
            hld_file = f"{drawio_base}_hld.drawio"
            mld_file = f"{drawio_base}_mld.drawio"
            
            file_mapping[filename] = (hld_file, mld_file)
    
    all_passed = True
    
    # Sort JSON files for consistent output order
    for json_file in sorted(file_mapping.keys()):
        hld_file, mld_file = file_mapping[json_file]
        
        json_path = os.path.join(examples_dir, json_file)
        hld_path = os.path.join(examples_dir, hld_file)
        mld_path = os.path.join(examples_dir, mld_file)
        
        if not os.path.exists(json_path):
            print(f"FAILED {json_file}: JSON file not found")
            all_passed = False
            continue
        
        passed = validate_topology_pair(json_path, hld_path, mld_path)
        if not passed:
            all_passed = False
    
    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    main()