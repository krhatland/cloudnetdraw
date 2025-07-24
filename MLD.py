import json
import logging
import re
from lxml import etree
from config import config
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_drawio_vnet_hub_and_spokes_diagram(filename, topology_file):
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

        # VNet icons will be positioned dynamically after feature icons are determined
        
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

    def create_vnet_id_mapping(vnets, hub_vnets, left_spokes, right_spokes, non_peered_spokes):
        """Create bidirectional mapping between VNet names and diagram IDs"""
        mapping = {}
        
        # Map hub VNets
        for i, hub in enumerate(hub_vnets):
            mapping[hub['name']] = f"hub_{i}"
        
        # Map spoke VNets
        for i, spoke in enumerate(right_spokes):
            mapping[spoke['name']] = f"right_spoke{i}"
        
        for i, spoke in enumerate(left_spokes):
            mapping[spoke['name']] = f"left_spoke{i}"
        
        # Map non-peered VNets
        for i, nonpeered in enumerate(non_peered_spokes):
            mapping[nonpeered['name']] = f"nonpeered_spoke{i}"
        
        return mapping

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

    # Render hub VNets (highly connected ones)
    for hub_index, hub_vnet in enumerate(hub_vnets):
        x_offset = 200 + (hub_index * config.layout['hub']['spacing_x'])
        y_offset = config.layout['hub']['spacing_y']
        hub_id = f"hub_{hub_index}"
        
        add_vnet_with_subnets(hub_vnet, hub_id, x_offset, y_offset)

    # Dynamic spacing for spokes
    start_y = config.layout['spoke']['start_y']
    padding = config.layout['spoke']['spacing_y']
    left_spokes = []
    right_spokes = []
    non_peered_spokes = []
    peered_spokes = []

    # Separate peered and non-peered spokes
    for spoke in spoke_vnets:
        if spoke.get("peerings"):
            peered_spokes.append(spoke)
        else:
            non_peered_spokes.append(spoke)

    # Split based on total number
    if len(peered_spokes) <= 6:
        right_spokes = peered_spokes
        left_spokes = []
    else:
        total_spokes = len(peered_spokes)
        half_spokes = (total_spokes + 1) // 2
        left_spokes = peered_spokes[:half_spokes]
        right_spokes = peered_spokes[half_spokes:]

    current_y_right = start_y
    current_y_left = start_y
    current_y_nonpeered = start_y

    # Draw out the spokes using universal function
    def draw_spokes(spokes_list, side, base_x, current_y):
        for idx, spoke in enumerate(spokes_list):
            spoke_id = f"{side}_spoke{idx}"
            y_position = current_y
            
            # Use universal function with spoke styling from config
            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = add_vnet_with_subnets(spoke, spoke_id, base_x, y_position, spoke_style)
            
            # Add connections between hub and spokes
            if hub_vnets:
                edge = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"edge_{side}_{idx}_{spoke['name']}",
                    edge="1",
                    source="hub_0",  # Connect to primary hub
                    target=spoke_id,
                    style=config.get_edge_style_string(),
                    parent="1",
                )
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})

                if side == "left":
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": "200", "y": str(y_position + 25)})
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(base_x + config.layout['spoke']['width']), "y": str(y_position + 25)})
                else:
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": "600", "y": str(y_position + 25)})
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(base_x), "y": str(y_position + 25)})

            current_y += vnet_height + padding

    draw_spokes(right_spokes, "right", config.layout['spoke']['right_x'], current_y_right)
    draw_spokes(left_spokes, "left", config.layout['spoke']['left_x'], current_y_left)

    # Add non-peered spokes to the far right using universal function
    for index, spoke in enumerate(non_peered_spokes):
        y_position = current_y_nonpeered
        spoke_id = f"nonpeered_spoke{index}"
        
        # Use universal function with non-peered styling from config
        nonpeered_style = config.get_vnet_style_string('non_peered')
        vnet_height = add_vnet_with_subnets(spoke, spoke_id, config.layout['non_peered']['x'], y_position, nonpeered_style)

        current_y_nonpeered += vnet_height + config.layout['non_peered']['spacing_y']

    # Create VNet ID mapping for peering connections
    vnet_mapping = create_vnet_id_mapping(vnets, hub_vnets, left_spokes, right_spokes, non_peered_spokes)
    
    # Add all peering edges to create full mesh connectivity
    add_peering_edges(vnets, vnet_mapping, root, config)
    
    logging.info(f"Added full mesh peering connections for {len(vnets)} VNets")

    # Write to file
    tree = etree.ElementTree(mxfile)
    with open(filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {filename}")

# Generate the diagram from the JSON file
if __name__ == "__main__":
    logging.info("Starting MLD diagram generation...")
    create_drawio_vnet_hub_and_spokes_diagram("network_mld.drawio", "network_topology.json")
    logging.info("Diagram generation complete.")
    print("Diagram generation complete.")
