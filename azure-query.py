from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient
from azure.core.exceptions import ResourceNotFoundError
import json
import argparse
import logging
import sys
import os
import re

def get_sp_credentials():
    """Get Service Principal credentials from environment variables"""
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')

    if not all([client_id, client_secret, tenant_id]):
        logging.error("Service Principal credentials not set. Please set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID.")
        sys.exit(1)

    return ClientSecretCredential(tenant_id, client_id, client_secret)

def get_credentials(use_service_principal=False):
    """Get appropriate credentials based on authentication method"""
    if use_service_principal:
        return get_sp_credentials()
    else:
        return AzureCliCredential()

def is_subscription_id(subscription_string):
    """Check if a subscription string is in UUID format (ID) or name format"""
    # Azure subscription ID pattern: 8-4-4-4-12 hexadecimal digits
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    return re.match(uuid_pattern, subscription_string) is not None

def read_subscriptions_from_file(file_path):
    """Read subscriptions from file, one per line"""
    try:
        with open(file_path, 'r') as f:
            subscriptions = [line.strip() for line in f if line.strip()]
        return subscriptions
    except FileNotFoundError:
        logging.error(f"Subscriptions file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading subscriptions file {file_path}: {e}")
        sys.exit(1)

def resolve_subscription_names_to_ids(subscription_names, credentials):
    """Resolve subscription names to IDs using the Azure API"""
    subscription_client = SubscriptionClient(credentials)
    all_subscriptions = list(subscription_client.subscriptions.list())
    
    # Create name-to-ID mapping
    name_to_id = {sub.display_name: sub.subscription_id for sub in all_subscriptions}
    
    resolved_ids = []
    for name in subscription_names:
        if name in name_to_id:
            resolved_ids.append(name_to_id[name])
        else:
            logging.error(f"Subscription not found: {name}")
            logging.info(f"Available subscriptions: {list(name_to_id.keys())}")
            sys.exit(1)
    
    return resolved_ids

# Helper function to extract resource group from resource ID
def extract_resource_group(resource_id):
    return resource_id.split("/")[4]  # Resource group is always the 5th item

# Collect all VNets and their details across selected subscriptions
def get_vnet_topology_for_selected_subscriptions(subscription_ids, credentials):
    network_data = {"vnets": []}
    vnet_candidates = []
    
    subscription_client = SubscriptionClient(credentials)

    for subscription_id in subscription_ids:
        print(f"Processing Subscription: {subscription_id}")
        network_client = NetworkManagementClient(credentials, subscription_id)

        # Get subscription name
        subscription = subscription_client.subscriptions.get(subscription_id)
        subscription_name = subscription.display_name

        # Detect Virtual WAN Hub if it exists - add to vnets array
        try:
            for vwan in network_client.virtual_wans.list():
                try:
                    # Correctly retrieve virtual hubs associated with the Virtual WAN
                    hubs = network_client.virtual_hubs.list_by_resource_group(extract_resource_group(vwan.id))
                    for hub in hubs:
                        # Detect ExpressRoute or VPN based on hub properties (fallback to flags if needed)
                        has_expressroute = hasattr(hub, "express_route_gateway") and hub.express_route_gateway is not None
                        has_vpn_gateway = hasattr(hub, "vpn_gateway") and hub.vpn_gateway is not None
                        has_firewall = hasattr(hub, "azure_firewall") and hub.azure_firewall is not None

                        virtual_hub_info = {
                            "name": hub.name,
                            "address_space": hub.address_prefix,
                            "type": "virtual_hub",
                            "subnets": [],  # Virtual hubs don't have traditional subnets
                            "peerings": [],  # Will be populated if needed
                            "subscription_name": subscription_name,
                            "expressroute": "Yes" if has_expressroute else "No",
                            "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                            "firewall": "Yes" if has_firewall else "No",
                            "peerings_count": 0  # Virtual hubs use different connectivity model
                        }
                        vnet_candidates.append(virtual_hub_info)
                except Exception as e:
                    print(f"Warning: Could not retrieve virtual hub details for {vwan.name} in subscription {subscription_id}. Error: {e}")
        except Exception as e:
            print(f"Warning: Could not list virtual WANs for subscription {subscription_id}. Error: {e}")

        # Process VNets
        for vnet in network_client.virtual_networks.list_all():
            resource_group_name = extract_resource_group(vnet.id)
            subnet_names = [subnet.name for subnet in vnet.subnets]

            vnet_info = {
                "name": vnet.name,
                "address_space": vnet.address_space.address_prefixes[0],
                "subnets": [
                    {
                        "name": subnet.name,
                        "address": (
                            subnet.address_prefixes[0]
                            if hasattr(subnet, "address_prefixes") and subnet.address_prefixes
                            else subnet.address_prefix or "N/A"
                        ),
                        "nsg": 'Yes' if subnet.network_security_group else 'No',
                        "udr": 'Yes' if subnet.route_table else 'No'
                    }
                    for subnet in vnet.subnets
                ],
                "peerings": [],
                "subscription_name": subscription_name,
                "expressroute": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "vpn_gateway": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "firewall": "Yes" if "AzureFirewallSubnet" in subnet_names else "No"
            }

            peerings = network_client.virtual_network_peerings.list(resource_group_name, vnet.name)
            for peering in peerings:
                vnet_info["peerings"].append(peering.name)

            vnet_info["peerings_count"] = len(vnet_info["peerings"])
            vnet_candidates.append(vnet_info)

    # All VNets are equal - no hub detection needed
    network_data["vnets"] = vnet_candidates
    return network_data

# List all subscriptions and allow user to select
def list_and_select_subscriptions(credentials):
    subscription_client = SubscriptionClient(credentials)
    subscriptions = list(subscription_client.subscriptions.list())
    # Sort subscriptions alphabetically by display_name to ensure consistent ordinals
    subscriptions.sort(key=lambda sub: sub.display_name)
    
    for idx, subscription in enumerate(subscriptions):
        print(f"[{idx}] {subscription.display_name} ({subscription.subscription_id})")

    selected_indices = input("Enter the indices of subscriptions to include (comma-separated): ")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",")]
    return [subscriptions[idx].subscription_id for idx in selected_indices]

# Save the data to a JSON file
def save_to_json(data, filename="network_topology.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Network topology saved to {filename}")

def query_command(args):
    """Execute the query command to collect VNet topology from Azure"""
    # Get credentials based on service principal flag
    credentials = get_credentials(args.service_principal)
    
    # Determine subscription selection mode
    if args.subscriptions or args.subscriptions_file:
        # Non-interactive mode
        selected_subscriptions = get_subscriptions_non_interactive(args, credentials)
    else:
        # Interactive mode (existing behavior)
        print("Listing available subscriptions...")
        selected_subscriptions = list_and_select_subscriptions(credentials)
    
    print("Collecting VNets and topology...")
    topology = get_vnet_topology_for_selected_subscriptions(selected_subscriptions, credentials)
    output_file = args.output if args.output else "network_topology.json"
    save_to_json(topology, output_file)

def get_subscriptions_non_interactive(args, credentials):
    """Get subscriptions from command line arguments or file in non-interactive mode"""
    if args.subscriptions and args.subscriptions_file:
        logging.error("Cannot specify both --subscriptions and --subscriptions-file")
        sys.exit(1)
    
    if args.subscriptions:
        # Parse comma-separated subscriptions
        subscriptions = [sub.strip() for sub in args.subscriptions.split(',')]
    else:
        # Read subscriptions from file
        subscriptions = read_subscriptions_from_file(args.subscriptions_file)
    
    # Detect if subscriptions are IDs or names by checking the first subscription
    if subscriptions and is_subscription_id(subscriptions[0]):
        # All subscriptions are assumed to be IDs
        print(f"Using subscription IDs: {subscriptions}")
        return subscriptions
    else:
        # All subscriptions are assumed to be names, resolve to IDs
        print(f"Resolving subscription names to IDs: {subscriptions}")
        return resolve_subscription_names_to_ids(subscriptions, credentials)

def determine_hub_for_spoke(spoke_vnet, hub_vnets):
    """Determine which hub this spoke is connected to based on peering relationships"""
    spoke_peerings = spoke_vnet.get('peerings', [])
    
    for hub_index, hub_vnet in enumerate(hub_vnets):
        hub_peerings = hub_vnet.get('peerings', [])
        
        # Check if any of the spoke's peerings match this hub's peerings
        for spoke_peering in spoke_peerings:
            if spoke_peering in hub_peerings:
                return f"hub_{hub_index}"
    
    # Fallback to first hub if no specific connection found
    return "hub_0" if hub_vnets else None

def parse_peering_name(peering_name):
    """Extract VNet names from peering strings"""
    # Pattern 1: "vnet1_to_vnet2" or "vnet1-to-vnet2"
    if '_to_' in peering_name:
        parts = peering_name.split('_to_')
        if len(parts) == 2:
            return parts[0], parts[1]
    elif '-to-' in peering_name:
        parts = peering_name.split('-to-')
        if len(parts) == 2:
            return parts[0], parts[1]
    
    # Pattern 2: Direct VNet name reference
    return None, peering_name

def create_vnet_id_mapping(vnets, zones, all_non_peered):
    """Create bidirectional mapping between VNet names and diagram IDs for multi-zone layout"""
    mapping = {}
    
    # Map hub VNets
    for zone in zones:
        mapping[zone['hub']['name']] = f"hub_{zone['hub_index']}"
    
    # Map spoke VNets with zone-aware IDs
    for zone_index, zone in enumerate(zones):
        peered_spokes = zone['spokes']
        
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
            mapping[spoke['name']] = f"right_spoke{zone_index}_{i}"
        
        # Map left spokes
        for i, spoke in enumerate(left_spokes):
            mapping[spoke['name']] = f"left_spoke{zone_index}_{i}"
    
    # Map non-peered VNets
    for i, nonpeered in enumerate(all_non_peered):
        mapping[nonpeered['name']] = f"nonpeered_spoke{i}"
    
    return mapping

def generate_hld_diagram(filename, topology_file, config):
    """Generate high-level diagram (VNets only) from topology JSON"""
    from lxml import etree
    
    # Load the topology JSON data
    with open(topology_file, 'r') as file:
        topology = json.load(file)

    logging.info("Loaded topology data from JSON")
    vnets = topology.get("vnets", [])
    
    # Classify VNets for layout purposes (keep existing layout logic)
    # Highly connected VNets (hubs) vs others
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= config.hub_threshold]
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < config.hub_threshold]
    
    # If no highly connected VNets, treat the first one as primary for layout
    if not hub_vnets and vnets:
        hub_vnets = [vnets[0]]
        spoke_vnets = vnets[1:]
    
    logging.info(f"Found {len(hub_vnets)} hub VNet(s) and {len(spoke_vnets)} spoke VNet(s)")

    # Root XML structure
    mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
    diagram = etree.SubElement(mxfile, "diagram", name="Hub and Spoke Topology")
    mxGraphModel = etree.SubElement(
        diagram,
        "mxGraphModel",
        attrib=config.get_canvas_attributes(),
    )
    root = etree.SubElement(mxGraphModel, "root")

    etree.SubElement(root, "mxCell", id="0")  # Root cell
    etree.SubElement(root, "mxCell", id="1", parent="0")  # Parent cell for all shapes

    def add_vnet_with_features(vnet_data, vnet_id, x_offset, y_offset, style_override=None):
        """Universal function to add any VNet with feature decorators as a grouped unit"""
        vnet_height = 50 if vnet_data.get("type") == "virtual_hub" else 50
        
        # Calculate total group dimensions to encompass all elements including icons
        group_width = 400
        group_height = vnet_height + 20  # Extra space for icons below VNet
        
        # Create group container for this VNet and all its elements
        group_id = f"{vnet_id}_group"
        group_element = etree.SubElement(
            root,
            "mxCell",
            id=group_id,
            value="",
            style="group",
            vertex="1",
            connectable="0",
            parent="1",
        )
        etree.SubElement(
            group_element,
            "mxGeometry",
            attrib={"x": str(x_offset), "y": str(y_offset), "width": str(group_width), "height": str(group_height), "as": "geometry"},
        )
        
        # Default style for hub VNets
        default_style = "shape=rectangle;rounded=0;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB;align=left"
        
        # Add VNet box as child of group (using relative positioning)
        vnet_element = etree.SubElement(
            root,
            "mxCell",
            id=vnet_id,
            style=style_override or default_style,
            vertex="1",
            parent=group_id,
        )
        vnet_element.set("value", f"Subscription: {vnet_data['subscription_name']}\n{vnet_data.get('name', 'VNet')}\n{vnet_data.get('address_space', 'N/A')}")
        etree.SubElement(
            vnet_element,
            "mxGeometry",
            attrib={"x": "0", "y": "0", "width": "400", "height": str(vnet_height), "as": "geometry"},
        )

        # Add Virtual Hub icon if applicable
        if vnet_data.get("type") == "virtual_hub":
            virtual_hub_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"{vnet_id}_virtualhub_image",
                style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_WANs.svg;",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                virtual_hub_icon,
                "mxGeometry",
                attrib={"x": "-10", "y": str(vnet_height - 15), "width": "20", "height": "20", "as": "geometry"},
            )
        
        # Dynamic VNet icon positioning (top-right aligned)
        vnet_width = 400  # VNet box width
        y_offset = config.icon_positioning['vnet_icons']['y_offset']
        right_margin = config.icon_positioning['vnet_icons']['right_margin']
        icon_gap = config.icon_positioning['vnet_icons']['icon_gap']
        
        # Build list of VNet decorator icons to display (right to left order)
        vnet_icons_to_render = []
        
        # VNet icon is always present (rightmost)
        vnet_icon_width, vnet_icon_height = config.get_icon_size('vnet')
        vnet_icons_to_render.append({
            'type': 'vnet',
            'width': vnet_icon_width,
            'height': vnet_icon_height
        })
        
        # ExpressRoute icon (if present)
        if vnet_data.get("expressroute", "").lower() == "yes":
            express_width, express_height = config.get_icon_size('expressroute')
            vnet_icons_to_render.append({
                'type': 'expressroute',
                'width': express_width,
                'height': express_height
            })
        
        # Firewall icon (if present)
        if vnet_data.get("firewall", "").lower() == "yes":
            firewall_width, firewall_height = config.get_icon_size('firewall')
            vnet_icons_to_render.append({
                'type': 'firewall',
                'width': firewall_width,
                'height': firewall_height
            })
        
        # VPN Gateway icon (if present, leftmost)
        if vnet_data.get("vpn_gateway", "").lower() == "yes":
            vpn_width, vpn_height = config.get_icon_size('vpn_gateway')
            vnet_icons_to_render.append({
                'type': 'vpn_gateway',
                'width': vpn_width,
                'height': vpn_height
            })
        
        # Calculate positions from right to left
        current_x = vnet_width - right_margin
        for icon in vnet_icons_to_render:
            current_x -= icon['width']
            icon['x'] = current_x
            
            # Create the icon element as child of VNet
            if icon['type'] == 'vnet':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('vnet')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'expressroute':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_expressroute_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('expressroute')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'firewall':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_firewall_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('firewall')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'vpn_gateway':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_vpn_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('vpn_gateway')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            
            etree.SubElement(
                icon_element,
                "mxGeometry",
                attrib={
                    "x": str(icon['x']),
                    "y": str(y_offset),
                    "width": str(icon['width']),
                    "height": str(icon['height']),
                    "as": "geometry"
                },
            )
            
            current_x -= icon_gap
        
        return group_height

    def add_peering_edges(vnets, vnet_mapping, root, config):
        """Add edges for all VNet peerings to create full mesh connectivity"""
        edge_counter = 1000  # Start high to avoid conflicts with existing edge IDs
        
        for vnet in vnets:
            source_vnet_name = vnet['name']
            source_id = vnet_mapping.get(source_vnet_name)
            
            if not source_id:
                continue  # Skip if source VNet not in diagram
                
            for peering in vnet.get('peerings', []):
                # Parse the peering name to get target VNet
                vnet1, vnet2 = parse_peering_name(peering)
                
                # Determine which is the target VNet (not the source)
                target_vnet_name = None
                if vnet1 and vnet1 != source_vnet_name:
                    target_vnet_name = vnet1
                elif vnet2 and vnet2 != source_vnet_name:
                    target_vnet_name = vnet2
                elif vnet2:  # Direct reference case
                    target_vnet_name = vnet2
                
                if not target_vnet_name:
                    continue
                    
                target_id = vnet_mapping.get(target_vnet_name)
                if not target_id:
                    continue  # Skip if target VNet not in diagram
                
                # Skip if this is a hub-to-spoke connection (already drawn)
                if source_id.startswith('hub_') and (target_id.startswith('spoke_') or target_id.startswith('nonpeered_')):
                    continue
                if target_id.startswith('hub_') and (source_id.startswith('spoke_') or source_id.startswith('nonpeered_')):
                    continue
                
                # Create edge for spoke-to-spoke or hub-to-hub connections
                edge = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"peering_edge_{edge_counter}",
                    edge="1",
                    source=source_id,
                    target=target_id,
                    style=config.get_edge_style_string(),
                    parent="1",
                )
                
                # Add basic geometry (draw.io will auto-route)
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                
                edge_counter += 1
                logging.info(f"Added peering edge: {source_vnet_name} ({source_id}) → {target_vnet_name} ({target_id})")

    # Group spokes by their hub for multi-zone layout
    zones = []
    for hub_index, hub_vnet in enumerate(hub_vnets):
        zone_spokes = []
        zone_non_peered = []
        
        # Find spokes that belong to this hub
        for spoke in spoke_vnets:
            if spoke.get("peerings"):
                hub_id = determine_hub_for_spoke(spoke, hub_vnets)
                if hub_id == f"hub_{hub_index}":
                    zone_spokes.append(spoke)
            else:
                zone_non_peered.append(spoke)
        
        zones.append({
            'hub': hub_vnet,
            'hub_index': hub_index,
            'spokes': zone_spokes,
            'non_peered': zone_non_peered if hub_index == 0 else []  # Only first zone gets non-peered
        })
    
    # Calculate zone width for horizontal positioning with top-left alignment
    canvas_padding = 20  # 20px padding from canvas edge
    zone_width = 1300  # Adjusted zone width: 920 - 20 + 400 = 1300
    zone_spacing = 500  # Increased gap between zones to prevent overlap
    
    # Dynamic spacing for spokes - adjusted for hub above spokes
    spacing = 100  # Original HLD.py spacing
    hub_height = 50  # HLD hub height (fixed)
    
    # Calculate base positions for top-left alignment
    # Original positions: left=-100, hub=400, right=900
    # Adjusted for 20px padding with proper spacing: left=20, hub=470, right=920
    base_left_x = canvas_padding
    base_hub_x = canvas_padding + 450  # Hub positioned with 50px gap after left spokes (400px wide)
    base_right_x = canvas_padding + 900  # Right spokes with 50px gap after hub (400px wide)
    hub_y = canvas_padding  # Hub positioned at top, above spokes
    
    # Process each zone
    for zone_index, zone in enumerate(zones):
        # Calculate zone offset
        zone_offset_x = zone_index * (zone_width + zone_spacing)
        
        # Position hub
        hub_x = base_hub_x + zone_offset_x
        hub_y = hub_y
        hub_id = f"hub_{zone['hub_index']}"
        add_vnet_with_features(zone['hub'], hub_id, hub_x, hub_y)
        
        # Separate peered spokes into left and right
        peered_spokes = zone['spokes']
        left_spokes = []
        right_spokes = []
        
        # Determine if we should use dual-column layout
        use_dual_column = len(peered_spokes) > 6
        if use_dual_column:
            total_spokes = len(peered_spokes)
            half_spokes = (total_spokes + 1) // 2
            left_spokes = peered_spokes[:half_spokes]
            right_spokes = peered_spokes[half_spokes:]
        else:
            left_spokes = []
            right_spokes = peered_spokes
        
        # Add right spokes
        for index, spoke in enumerate(right_spokes):
            y_position = hub_y + hub_height + index * spacing
            x_position = base_right_x + zone_offset_x
            spoke_id = f"right_spoke{zone_index}_{index}"
            
            spoke_style = config.get_vnet_style_string('spoke')
            add_vnet_with_features(spoke, spoke_id, x_position, y_position, spoke_style)
            
            # Add connection to zone's hub
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_right_{zone_index}_{index}",
                edge="1",
                source=hub_id,
                target=spoke_id,
                style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            
            # Add waypoint only if spoke is not aligned with hub
            if y_position != hub_y:
                hub_center_x = base_hub_x + 200 + zone_offset_x  # Hub center
                etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x + 100), "y": str(y_position + 25)})
        
        # Add left spokes
        for index, spoke in enumerate(left_spokes):
            y_position = hub_y + hub_height + index * spacing
            x_position = base_left_x + zone_offset_x
            spoke_id = f"left_spoke{zone_index}_{index}"
            
            spoke_style = config.get_vnet_style_string('spoke')
            add_vnet_with_features(spoke, spoke_id, x_position, y_position, spoke_style)
            
            # Add connection to zone's hub
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_left_{zone_index}_{index}",
                edge="1",
                source=hub_id,
                target=spoke_id,
                style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            
            # Add waypoint only if spoke is not aligned with hub
            if y_position != hub_y:
                hub_center_x = base_hub_x + 200 + zone_offset_x  # Hub center
                etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x - 100), "y": str(y_position + 25)})
    
    # Calculate overall bottom boundary for unpeered VNets
    overall_bottom_y = hub_y + hub_height
    for zone in zones:
        peered_spokes = zone['spokes']
        use_dual_column = len(peered_spokes) > 6
        if use_dual_column:
            total_spokes = len(peered_spokes)
            half_spokes = (total_spokes + 1) // 2
            left_count = half_spokes
            right_count = total_spokes - half_spokes
        else:
            left_count = 0
            right_count = len(peered_spokes)
        
        zone_bottom = hub_y + hub_height
        if left_count > 0:
            zone_bottom = max(zone_bottom, hub_y + hub_height + left_count * spacing + 50)
        if right_count > 0:
            zone_bottom = max(zone_bottom, hub_y + hub_height + right_count * spacing + 50)
        
        # If no spokes, position below hub
        if left_count == 0 and right_count == 0:
            zone_bottom = hub_y + hub_height + 50
        
        overall_bottom_y = max(overall_bottom_y, zone_bottom)
    
    # Add non-peered spokes in horizontal row below all zones
    all_non_peered = []
    for zone in zones:
        all_non_peered.extend(zone['non_peered'])
    
    if all_non_peered:
        unpeered_y = overall_bottom_y + 100  # 100px buffer below lowest spoke
        
        # Calculate total width of all zones
        total_zones_width = len(zones) * zone_width + (len(zones) - 1) * zone_spacing
        
        # Calculate unpeered network layout with row wrapping
        unpeered_spacing = 450  # VNet width (400) + gap (50)
        vnets_per_row = max(1, int(total_zones_width // unpeered_spacing))  # How many fit in one row
        row_height = 70  # Height for each row (VNet height + gap)
        
        for index, spoke in enumerate(all_non_peered):
            row_number = index // vnets_per_row
            position_in_row = index % vnets_per_row
            
            x_position = base_left_x + (position_in_row * unpeered_spacing)
            y_position = unpeered_y + (row_number * row_height)
            spoke_id = f"nonpeered_spoke{index}"
            
            nonpeered_style = config.get_vnet_style_string('non_peered')
            add_vnet_with_features(spoke, spoke_id, x_position, y_position, nonpeered_style)

    # Create VNet ID mapping for peering connections
    vnet_mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
    
    # Add all peering edges to create full mesh connectivity
    add_peering_edges(vnets, vnet_mapping, root, config)
    
    logging.info(f"Added full mesh peering connections for {len(vnets)} VNets")

    # Write to file
    tree = etree.ElementTree(mxfile)
    with open(filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {filename}")

def hld_command(args):
    """Execute the HLD command to generate high-level diagrams"""
    from config import Config
    
    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_hld.drawio"
    config_file = args.config_file
    
    # Create config instance with specified file
    config = Config(config_file)
    
    logging.info("Starting HLD diagram generation...")
    generate_hld_diagram(output_file, topology_file, config)
    logging.info("HLD diagram generation complete.")
    print(f"HLD diagram saved to {output_file}")

def generate_mld_diagram(filename, topology_file, config):
    """Generate mid-level diagram (VNets + subnets) from topology JSON"""
    from lxml import etree
    
    # Load the topology JSON data
    with open(topology_file, 'r') as file:
        topology = json.load(file)

    logging.info("Loaded topology data from JSON")
    vnets = topology.get("vnets", [])
    
    # Classify VNets for layout purposes (keep existing layout logic)
    # Highly connected VNets (hubs) vs others
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= config.hub_threshold]
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < config.hub_threshold]
    
    # If no highly connected VNets, treat the first one as primary for layout
    if not hub_vnets and vnets:
        hub_vnets = [vnets[0]]
        spoke_vnets = vnets[1:]
    
    logging.info(f"Found {len(hub_vnets)} hub VNet(s) and {len(spoke_vnets)} spoke VNet(s)")

    # Root XML structure
    mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
    diagram = etree.SubElement(mxfile, "diagram", name="Hub and Spoke Topology")
    mxGraphModel = etree.SubElement(
        diagram,
        "mxGraphModel",
        attrib=config.get_canvas_attributes(),
    )
    root = etree.SubElement(mxGraphModel, "root")

    etree.SubElement(root, "mxCell", id="0")  # Root cell
    etree.SubElement(root, "mxCell", id="1", parent="0")  # Parent cell for all shapes

    def add_vnet_with_subnets(vnet_data, vnet_id, x_offset, y_offset, style_override=None):
        """Universal function to add any VNet with subnets and features as a grouped unit"""
        num_subnets = len(vnet_data.get("subnets", []))
        vnet_height = config.layout['hub']['height'] if vnet_data.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
        
        # Calculate total group dimensions to encompass all elements including icons
        group_width = config.layout['hub']['width']
        group_height = vnet_height + config.drawio['group']['extra_height']
        
        # Create group container for this VNet and all its elements
        group_id = f"{vnet_id}_group"
        group_element = etree.SubElement(
            root,
            "mxCell",
            id=group_id,
            value="",
            style="group",
            vertex="1",
            connectable=config.drawio['group']['connectable'],
            parent="1",
        )
        etree.SubElement(
            group_element,
            "mxGeometry",
            attrib={"x": str(x_offset), "y": str(y_offset), "width": str(group_width), "height": str(group_height), "as": "geometry"},
        )
        
        # Default style for hub VNets
        default_style = config.get_vnet_style_string('hub')
        
        # Add VNet box as child of group (using relative positioning)
        vnet_element = etree.SubElement(
            root,
            "mxCell",
            id=vnet_id,
            style=style_override or default_style,
            vertex="1",
            parent=group_id,
        )
        vnet_element.set("value", f"Subscription: {vnet_data['subscription_name']}\n{vnet_data.get('name', 'VNet')}\n{vnet_data.get('address_space', 'N/A')}")
        etree.SubElement(
            vnet_element,
            "mxGeometry",
            attrib={"x": "0", "y": "0", "width": str(config.layout['hub']['width']), "height": str(vnet_height), "as": "geometry"},
        )

        # Add Virtual Hub icon if applicable
        if vnet_data.get("type") == "virtual_hub":
            hub_icon_width, hub_icon_height = config.get_icon_size('virtual_hub')
            virtual_hub_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"{vnet_id}_virtualhub_image",
                style=f"shape=image;html=1;image={config.get_icon_path('virtual_hub')};",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                virtual_hub_icon,
                "mxGeometry",
                attrib={
                    "x": str(config.icon_positioning['virtual_hub_icon']['offset_x']),
                    "y": str(vnet_height + config.icon_positioning['virtual_hub_icon']['offset_y']),
                    "width": str(hub_icon_width),
                    "height": str(hub_icon_height),
                    "as": "geometry"
                },
            )
        
        # Dynamic VNet icon positioning (top-right aligned)
        vnet_width = config.layout['hub']['width']  # VNet box width (400)
        y_offset = config.icon_positioning['vnet_icons']['y_offset']
        right_margin = config.icon_positioning['vnet_icons']['right_margin']
        icon_gap = config.icon_positioning['vnet_icons']['icon_gap']
        
        # Build list of VNet decorator icons to display (right to left order)
        vnet_icons_to_render = []
        
        # VNet icon is always present (rightmost)
        vnet_icon_width, vnet_icon_height = config.get_icon_size('vnet')
        vnet_icons_to_render.append({
            'type': 'vnet',
            'width': vnet_icon_width,
            'height': vnet_icon_height
        })
        
        # ExpressRoute icon (if present)
        if vnet_data.get("expressroute", "").lower() == "yes":
            express_width, express_height = config.get_icon_size('expressroute')
            vnet_icons_to_render.append({
                'type': 'expressroute',
                'width': express_width,
                'height': express_height
            })
        
        # Firewall icon (if present)
        if vnet_data.get("firewall", "").lower() == "yes":
            firewall_width, firewall_height = config.get_icon_size('firewall')
            vnet_icons_to_render.append({
                'type': 'firewall',
                'width': firewall_width,
                'height': firewall_height
            })
        
        # VPN Gateway icon (if present, leftmost)
        if vnet_data.get("vpn_gateway", "").lower() == "yes":
            vpn_width, vpn_height = config.get_icon_size('vpn_gateway')
            vnet_icons_to_render.append({
                'type': 'vpn_gateway',
                'width': vpn_width,
                'height': vpn_height
            })
        
        # Calculate positions from right to left
        current_x = vnet_width - right_margin
        for icon in vnet_icons_to_render:
            current_x -= icon['width']
            icon['x'] = current_x
            
            # Create the icon element as child of VNet
            if icon['type'] == 'vnet':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('vnet')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'expressroute':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_expressroute_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('expressroute')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'firewall':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_firewall_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('firewall')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            elif icon['type'] == 'vpn_gateway':
                icon_element = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_vpn_image",
                    style=f"shape=image;html=1;image={config.get_icon_path('vpn_gateway')};",
                    vertex="1",
                    parent=vnet_id,  # Parent to VNet, not group
                )
            
            etree.SubElement(
                icon_element,
                "mxGeometry",
                attrib={
                    "x": str(icon['x']),
                    "y": str(y_offset),
                    "width": str(icon['width']),
                    "height": str(icon['height']),
                    "as": "geometry"
                },
            )
            
            current_x -= icon_gap

        # Add subnets if it's a regular VNet (as children of the VNet, not the group)
        if vnet_data.get("type") != "virtual_hub":
            for subnet_index, subnet in enumerate(vnet_data.get("subnets", [])):
                subnet_cell = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_subnet_{subnet_index}",
                    style=config.get_subnet_style_string(),
                    vertex="1",
                    parent=vnet_id,
                )
                subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
                y_offset_subnet = config.layout['subnet']['padding_y'] + subnet_index * config.layout['subnet']['spacing_y']
                etree.SubElement(subnet_cell, "mxGeometry", attrib={
                    "x": str(config.layout['subnet']['padding_x']),
                    "y": str(y_offset_subnet),
                    "width": str(config.layout['subnet']['width']),
                    "height": str(config.layout['subnet']['height']),
                    "as": "geometry"
                })

                # Calculate icon positions dynamically based on which icons are present
                # Subnet box: x=25, width=350, so right edge = 375
                subnet_right_edge = config.layout['subnet']['padding_x'] + config.layout['subnet']['width']
                icon_gap = config.icon_positioning['subnet_icons']['icon_gap']
                
                # Build list of icons to display (right to left order)
                icons_to_render = []
                
                # Subnet icon is always present (rightmost)
                subnet_width, subnet_height = config.get_icon_size('subnet')
                icons_to_render.append({
                    'type': 'subnet',
                    'width': subnet_width,
                    'height': subnet_height,
                    'y_offset': config.icon_positioning['subnet_icons']['subnet_icon_y_offset']
                })
                
                # UDR icon (if present)
                if subnet.get("udr", "").lower() == "yes":
                    udr_width, udr_height = config.get_icon_size('route_table')
                    icons_to_render.append({
                        'type': 'udr',
                        'width': udr_width,
                        'height': udr_height,
                        'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                    })
                
                # NSG icon (if present, leftmost)
                if subnet.get("nsg", "").lower() == "yes":
                    nsg_width, nsg_height = config.get_icon_size('nsg')
                    icons_to_render.append({
                        'type': 'nsg',
                        'width': nsg_width,
                        'height': nsg_height,
                        'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                    })
                
                # Calculate positions from right to left
                current_x = subnet_right_edge
                for icon in icons_to_render:
                    current_x -= icon['width']
                    icon['x'] = current_x
                    
                    # Create the icon element
                    icon_y = y_offset_subnet + icon['y_offset']
                    
                    if icon['type'] == 'subnet':
                        icon_element = etree.SubElement(
                            root,
                            "mxCell",
                            id=f"{vnet_id}_subnet_{subnet_index}_icon",
                            style=f"shape=image;html=1;image={config.get_icon_path('subnet')};",
                            vertex="1",
                            parent=vnet_id,
                        )
                    elif icon['type'] == 'udr':
                        icon_element = etree.SubElement(
                            root,
                            "mxCell",
                            id=f"{vnet_id}_subnet_{subnet_index}_udr",
                            style=f"shape=image;html=1;image={config.get_icon_path('route_table')};",
                            vertex="1",
                            parent=vnet_id,
                        )
                    elif icon['type'] == 'nsg':
                        icon_element = etree.SubElement(
                            root,
                            "mxCell",
                            id=f"{vnet_id}_subnet_{subnet_index}_nsg",
                            style=f"shape=image;html=1;image={config.get_icon_path('nsg')};",
                            vertex="1",
                            parent=vnet_id,
                        )
                    
                    etree.SubElement(
                        icon_element,
                        "mxGeometry",
                        attrib={
                            "x": str(icon['x']),
                            "y": str(icon_y),
                            "width": str(icon['width']),
                            "height": str(icon['height']),
                            "as": "geometry"
                        },
                    )
                    
                    current_x -= icon_gap
        
        return group_height

    def add_peering_edges(vnets, vnet_mapping, root, config):
        """Add edges for all VNet peerings to create full mesh connectivity"""
        edge_counter = 1000  # Start high to avoid conflicts with existing edge IDs
        
        for vnet in vnets:
            source_vnet_name = vnet['name']
            source_id = vnet_mapping.get(source_vnet_name)
            
            if not source_id:
                continue  # Skip if source VNet not in diagram
                
            for peering in vnet.get('peerings', []):
                # Parse the peering name to get target VNet
                vnet1, vnet2 = parse_peering_name(peering)
                
                # Determine which is the target VNet (not the source)
                target_vnet_name = None
                if vnet1 and vnet1 != source_vnet_name:
                    target_vnet_name = vnet1
                elif vnet2 and vnet2 != source_vnet_name:
                    target_vnet_name = vnet2
                elif vnet2:  # Direct reference case
                    target_vnet_name = vnet2
                
                if not target_vnet_name:
                    continue
                    
                target_id = vnet_mapping.get(target_vnet_name)
                if not target_id:
                    continue  # Skip if target VNet not in diagram
                
                # Skip if this is a hub-to-spoke connection (already drawn)
                if source_id.startswith('hub_') and (target_id.startswith('spoke') or target_id.startswith('nonpeered_')):
                    continue
                if target_id.startswith('hub_') and (source_id.startswith('spoke') or source_id.startswith('nonpeered_')):
                    continue
                
                # Create edge for spoke-to-spoke or hub-to-hub connections
                edge = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"peering_edge_{edge_counter}",
                    edge="1",
                    source=source_id,
                    target=target_id,
                    style=config.get_edge_style_string(),
                    parent="1",
                )
                
                # Add basic geometry (draw.io will auto-route)
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                
                edge_counter += 1
                logging.info(f"Added peering edge: {source_vnet_name} ({source_id}) → {target_vnet_name} ({target_id})")

    # Group spokes by their hub for multi-zone layout
    zones = []
    for hub_index, hub_vnet in enumerate(hub_vnets):
        zone_spokes = []
        zone_non_peered = []
        
        # Find spokes that belong to this hub
        for spoke in spoke_vnets:
            if spoke.get("peerings"):
                hub_id = determine_hub_for_spoke(spoke, hub_vnets)
                if hub_id == f"hub_{hub_index}":
                    zone_spokes.append(spoke)
            else:
                zone_non_peered.append(spoke)
        
        zones.append({
            'hub': hub_vnet,
            'hub_index': hub_index,
            'spokes': zone_spokes,
            'non_peered': zone_non_peered if hub_index == 0 else []  # Only first zone gets non-peered
        })
    
    # Calculate zone width for horizontal positioning with top-left alignment (MLD values)
    canvas_padding = 20  # 20px padding from canvas edge
    zone_width = 1300  # Adjusted zone width: 920 - 20 + 400 = 1300
    zone_spacing = 500  # Increased gap between zones to prevent overlap
    
    # Dynamic spacing for spokes - adjusted for hub above spokes
    padding = 20   # Original MLD.py padding
    
    # Calculate base positions for top-left alignment (MLD values)
    # Original positions: left=-400, hub=200, right=700
    # Adjusted for 20px padding with proper spacing: left=20, hub=470, right=920
    base_left_x = canvas_padding
    base_hub_x = canvas_padding + 450  # Hub positioned with 50px gap after left spokes (400px wide)
    base_right_x = canvas_padding + 900  # Right spokes with 50px gap after hub (400px wide)
    hub_y = canvas_padding  # Hub positioned at top, above spokes
    
    # Process each zone
    zone_bottoms = []
    
    for zone_index, zone in enumerate(zones):
        # Calculate zone offset
        zone_offset_x = zone_index * (zone_width + zone_spacing)
        
        # Position hub
        hub_x = base_hub_x + zone_offset_x
        hub_y = hub_y
        hub_id = f"hub_{zone['hub_index']}"
        hub_actual_height = add_vnet_with_subnets(zone['hub'], hub_id, hub_x, hub_y)
        
        # Separate peered spokes into left and right
        peered_spokes = zone['spokes']
        left_spokes = []
        right_spokes = []
        
        # Split based on total number
        if len(peered_spokes) <= 6:
            right_spokes = peered_spokes
            left_spokes = []
        else:
            total_spokes = len(peered_spokes)
            half_spokes = (total_spokes + 1) // 2
            left_spokes = peered_spokes[:half_spokes]
            right_spokes = peered_spokes[half_spokes:]
        
        # Calculate actual hub VNet height (not group height)
        hub_vnet = zone['hub']
        num_subnets = len(hub_vnet.get("subnets", []))
        hub_vnet_height = config.layout['hub']['height'] if hub_vnet.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
        
        current_y_right = hub_y + hub_vnet_height  # Start spokes after hub VNet
        current_y_left = hub_y + hub_vnet_height   # Start spokes after hub VNet
        
        # Draw right spokes
        for idx, spoke in enumerate(right_spokes):
            spoke_id = f"right_spoke{zone_index}_{idx}"
            y_position = current_y_right
            x_position = base_right_x + zone_offset_x
            
            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = add_vnet_with_subnets(spoke, spoke_id, x_position, y_position, spoke_style)
            
            # Add connection to zone's hub
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_right_{zone_index}_{idx}_{spoke['name']}",
                edge="1",
                source=hub_id,
                target=spoke_id,
                style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            
            # Add waypoint only if spoke is not aligned with hub
            if y_position != hub_y:
                hub_center_x = base_hub_x + 200 + zone_offset_x  # Hub center
                etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x + 100), "y": str(y_position + 25)})
            
            current_y_right += vnet_height + padding
        
        # Draw left spokes
        for idx, spoke in enumerate(left_spokes):
            spoke_id = f"left_spoke{zone_index}_{idx}"
            y_position = current_y_left
            x_position = base_left_x + zone_offset_x
            
            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = add_vnet_with_subnets(spoke, spoke_id, x_position, y_position, spoke_style)
            
            # Add connection to zone's hub
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_left_{zone_index}_{idx}_{spoke['name']}",
                edge="1",
                source=hub_id,
                target=spoke_id,
                style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            
            # Add waypoint only if spoke is not aligned with hub
            if y_position != hub_y:
                hub_center_x = base_hub_x + 200 + zone_offset_x  # Hub center
                etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x - 100), "y": str(y_position + 25)})
            
            current_y_left += vnet_height + padding
        
        # Track zone bottom
        zone_bottom = hub_y + hub_vnet_height
        if left_spokes or right_spokes:
            zone_bottom = max(current_y_left, current_y_right) + 60
        else:
            zone_bottom = hub_y + hub_vnet_height + 60  # Hub height + buffer
        zone_bottoms.append(zone_bottom)
    
    # Add non-peered spokes in horizontal row below all zones
    all_non_peered = []
    for zone in zones:
        all_non_peered.extend(zone['non_peered'])
    
    if all_non_peered:
        overall_bottom_y = max(zone_bottoms) if zone_bottoms else hub_y + hub_vnet_height
        unpeered_y = overall_bottom_y + 60  # 60px buffer below lowest spoke
        
        # Calculate total width of all zones
        total_zones_width = len(zones) * zone_width + (len(zones) - 1) * zone_spacing
        
        # Calculate unpeered network layout with row wrapping
        unpeered_spacing = 450  # VNet width (400) + gap (50)
        vnets_per_row = max(1, int(total_zones_width // unpeered_spacing))  # How many fit in one row
        row_height = 120  # Height for each row (VNet height + gap, larger for MLD with subnets)
        
        for index, spoke in enumerate(all_non_peered):
            row_number = index // vnets_per_row
            position_in_row = index % vnets_per_row
            
            x_position = base_left_x + (position_in_row * unpeered_spacing)
            y_position = unpeered_y + (row_number * row_height)
            spoke_id = f"nonpeered_spoke{index}"
            
            nonpeered_style = config.get_vnet_style_string('non_peered')
            add_vnet_with_subnets(spoke, spoke_id, x_position, y_position, nonpeered_style)

    # Create VNet ID mapping for peering connections
    vnet_mapping = create_vnet_id_mapping(vnets, zones, all_non_peered)
    
    # Add all peering edges to create full mesh connectivity
    add_peering_edges(vnets, vnet_mapping, root, config)
    
    logging.info(f"Added full mesh peering connections for {len(vnets)} VNets")

    # Write to file
    tree = etree.ElementTree(mxfile)
    with open(filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {filename}")

def mld_command(args):
    """Execute the MLD command to generate mid-level diagrams"""
    from config import Config
    
    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_mld.drawio"
    config_file = args.config_file
    
    # Create config instance with specified file
    config = Config(config_file)
    
    logging.info("Starting MLD diagram generation...")
    generate_mld_diagram(output_file, topology_file, config)
    logging.info("MLD diagram generation complete.")
    print(f"MLD diagram saved to {output_file}")

class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter to prevent help text from wrapping to multiple lines"""
    def __init__(self, prog):
        super().__init__(prog, max_help_position=70, width=180)

def main():
    """Main CLI entry point with subcommand dispatch"""
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    parser = argparse.ArgumentParser(
        description="CloudNet Draw - Azure VNet topology visualization tool",
        formatter_class=CustomHelpFormatter,
        epilog="""
Examples:
  %(prog)s query                    # Query Azure and save topology to JSON
  %(prog)s hld                      # Generate high-level diagram from topology
  %(prog)s mld                      # Generate mid-level diagram with subnets
  %(prog)s hld -o custom_hld.drawio # Generate HLD with custom output filename
  %(prog)s mld -t custom_topo.json  # Generate MLD from custom topology file
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', title='subcommands', help='Available commands')
    subparsers.required = True
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query Azure and collect VNet topology',
                                        formatter_class=CustomHelpFormatter)
    query_parser.add_argument('-o', '--output', default='network_topology.json',
                             help='Output JSON file (default: network_topology.json)')
    query_parser.add_argument('-p', '--service-principal', action='store_true',
                             help='Use Service Principal authentication')
    query_parser.add_argument('-s', '--subscriptions',
                             help='Comma separated list of subscriptions (names or IDs)')
    query_parser.add_argument('-f', '--subscriptions-file',
                             help='File containing subscriptions (one per line)')
    query_parser.add_argument('-c', '--config-file', default='config.yaml',
                             help='Configuration file (default: config.yaml)')
    query_parser.set_defaults(func=query_command)
    
    # HLD command
    hld_parser = subparsers.add_parser('hld', help='Generate high-level diagram (VNets only)',
                                      formatter_class=CustomHelpFormatter)
    hld_parser.add_argument('-o', '--output', default='network_hld.drawio',
                           help='Output diagram file (default: network_hld.drawio)')
    hld_parser.add_argument('-t', '--topology', default='network_topology.json',
                           help='Input topology JSON file')
    hld_parser.set_defaults(func=hld_command)
    hld_parser.add_argument('-c', '--config-file', default='config.yaml',
                           help='Configuration file (default: config.yaml)')
    
    # MLD command
    mld_parser = subparsers.add_parser('mld', help='Generate mid-level diagram (VNets + subnets)',
                                      formatter_class=CustomHelpFormatter)
    mld_parser.add_argument('-o', '--output', default='network_mld.drawio',
                           help='Output diagram file (default: network_mld.drawio)')
    mld_parser.add_argument('-t', '--topology', default='network_topology.json',
                           help='Input topology JSON file')
    mld_parser.set_defaults(func=mld_command)
    mld_parser.add_argument('-c', '--config-file', default='config.yaml',
                           help='Configuration file (default: config.yaml)')
    
    # Parse arguments and dispatch to appropriate function
    args = parser.parse_args()
    
    try:
        args.func(args)
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()