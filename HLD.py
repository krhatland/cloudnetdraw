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

        # VNet icons will be positioned dynamically after feature icons are determined
        
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

    def create_vnet_id_mapping(vnets, hub_vnets, left_spokes, right_spokes, non_peered_spokes):
        """Create bidirectional mapping between VNet names and diagram IDs"""
        mapping = {}
        
        # Map hub VNets
        for i, hub in enumerate(hub_vnets):
            mapping[hub['name']] = f"hub_{i}"
        
        # Map spoke VNets
        for i, spoke in enumerate(right_spokes):
            mapping[spoke['name']] = f"spoke_right_{i}"
        
        for i, spoke in enumerate(left_spokes):
            mapping[spoke['name']] = f"spoke_left_{i}"
        
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

    # Render hub VNets (highly connected ones)
    for hub_index, hub_vnet in enumerate(hub_vnets):
        x_offset = 400 + (hub_index * config.layout['hub']['spacing_x'])
        y_offset = config.layout['hub']['spacing_y']
        hub_id = f"hub_{hub_index}"
        
        # Use new grouped function for hubs
        add_vnet_with_features(hub_vnet, hub_id, x_offset, y_offset)

    # Dynamic spacing for spokes
    spacing = config.layout['spoke']['spacing_y']
    start_y = config.layout['spoke']['start_y']
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

    # Add spokes on the right-hand side
    for index, spoke in enumerate(right_spokes):
        y_position = start_y + index * spacing
        x_position = config.layout['spoke']['right_x']
        spoke_id = f"spoke_right_{index}"
        
        # Use new grouped function for spokes with custom styling
        spoke_style = config.get_vnet_style_string('spoke')
        add_vnet_with_features(spoke, spoke_id, x_position, y_position, spoke_style)

        # Add connection from primary Hub to Spokes
        if hub_vnets:
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_right_{index}",
                edge="1",
                source="hub_0",  # Connect to primary hub
                target=f"spoke_right_{index}",
                style=config.get_edge_style_string(),
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": "800", "y": str(y_position + 25)})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": str(x_position), "y": str(y_position + 25)})

    # Add spokes on the left-hand side
    for index, spoke in enumerate(left_spokes):
        y_position = start_y + index * spacing
        x_position = config.layout['spoke']['left_x']
        spoke_id = f"spoke_left_{index}"
        
        # Use new grouped function for spokes with custom styling
        spoke_style = config.get_vnet_style_string('spoke')
        add_vnet_with_features(spoke, spoke_id, x_position, y_position, spoke_style)

        # Add connection from primary Hub to Spokes
        if hub_vnets:
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_left_{index}",
                edge="1",
                source="hub_0",  # Connect to primary hub
                target=f"spoke_left_{index}",
                style=config.get_edge_style_string(),
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": "400", "y": str(y_position + 25)})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": "300", "y": str(y_position + 25)})
    
    # Add non-peered spokes to the right
    for index, spoke in enumerate(non_peered_spokes):
        y_position = start_y + index * spacing
        x_position = config.layout['non_peered']['x']
        spoke_id = f"nonpeered_spoke{index}"
        
        # Use new grouped function for non-peered spokes with custom styling
        nonpeered_style = config.get_vnet_style_string('non_peered')
        add_vnet_with_features(spoke, spoke_id, x_position, y_position, nonpeered_style)

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
    logging.info("Starting HLD diagram generation...")
    create_drawio_vnet_hub_and_spokes_diagram("network_hld.drawio", "network_topology.json")
    logging.info("Diagram generation complete.")
    print("Diagram generation complete.")
