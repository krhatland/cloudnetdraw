import json
import logging
from lxml import etree
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
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= 10]
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < 10]
    
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
        attrib={
            "dx": "371", "dy": "1462", "grid": "0", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1",
            "page": "0", "pageScale": "1", "pageWidth": "827", "pageHeight": "1169",
            "math": "0", "shadow": "0", "background": "#ffffff"
        },
    )
    root = etree.SubElement(mxGraphModel, "root")

    etree.SubElement(root, "mxCell", id="0")  # Root cell
    etree.SubElement(root, "mxCell", id="1", parent="0")  # Parent cell for all shapes

    def add_vnet_with_subnets(vnet_data, vnet_id, x_offset, y_offset, style_override=None):
        """Universal function to add any VNet with subnets and features as a grouped unit"""
        num_subnets = len(vnet_data.get("subnets", []))
        vnet_height = 50 if vnet_data.get("type") == "virtual_hub" else 30 + (num_subnets * 30)
        
        # Calculate total group dimensions to encompass all elements including icons
        group_width = 400
        group_height = vnet_height + 10  # Extra space for icons below VNet
        
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
        default_style = "shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB;verticalAlign=top"
        
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

        # Add VNet image as child of group
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"{vnet_id}_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent=group_id,
        )
        etree.SubElement(
            image,
            "mxGeometry",
            attrib={"x": "380", "y": str(vnet_height), "width": "20", "height": "20", "as": "geometry"},
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
                attrib={"x": "-10", "y": str(vnet_height - 35), "width": "20", "height": "20", "as": "geometry"},
            )
        
        # Add feature icons as children of group
        icon_x_base = 360
        icon_y = vnet_height
        icon_spacing = -25

        if vnet_data.get("expressroute", "").lower() == "yes":
            express_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"{vnet_id}_expressroute_image",
                style="shape=image;html=1;image=img/lib/azure2/networking/ExpressRoute_Circuits.svg;",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                express_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )
            icon_x_base += icon_spacing

        if vnet_data.get("firewall", "").lower() == "yes":
            firewall_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"{vnet_id}_firewall_image",
                style="shape=image;html=1;image=img/lib/azure2/networking/Firewalls.svg;",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                firewall_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )
            icon_x_base += icon_spacing

        if vnet_data.get("vpn_gateway", "").lower() == "yes":
            vpn_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"{vnet_id}_vpn_image",
                style="shape=image;html=1;image=img/lib/azure2/networking/VPN_Gateways.svg;",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                vpn_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )

        # Add subnets if it's a regular VNet (as children of the VNet, not the group)
        if vnet_data.get("type") != "virtual_hub":
            for subnet_index, subnet in enumerate(vnet_data.get("subnets", [])):
                subnet_cell = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{vnet_id}_subnet_{subnet_index}",
                    style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#C8C6C4;fontColor=#323130;fillColor=#FAF9F8",
                    vertex="1",
                    parent=vnet_id,
                )
                subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
                y_offset_subnet = 35 + subnet_index * 30
                etree.SubElement(subnet_cell, "mxGeometry", attrib={"x": "25", "y": str(y_offset_subnet), "width": "350", "height": "20", "as": "geometry"})

                # Add NSG icon if NSG is attached to the subnet (child of VNet for proper containment)
                if subnet.get("nsg", "").lower() == "yes":
                    nsg_icon = etree.SubElement(
                        root,
                        "mxCell",
                        id=f"{vnet_id}_subnet_{subnet_index}_nsg",
                        style="shape=image;html=1;image=img/lib/azure2/networking/Network_Security_Groups.svg;",
                        vertex="1",
                        parent=vnet_id,
                    )
                    etree.SubElement(
                        nsg_icon,
                        "mxGeometry",
                        attrib={"x": "25", "y": str(y_offset_subnet), "width": "20", "height": "20", "as": "geometry"},
                    )

                # Add UDR icon if UDR is attached to the subnet (child of VNet for proper containment)
                if subnet.get("udr", "").lower() == "yes":
                    udr_icon = etree.SubElement(
                        root,
                        "mxCell",
                        id=f"{vnet_id}_subnet_{subnet_index}_udr",
                        style="shape=image;html=1;image=img/lib/azure2/networking/Route_Tables.svg;",
                        vertex="1",
                        parent=vnet_id,
                    )
                    etree.SubElement(
                        udr_icon,
                        "mxGeometry",
                        attrib={"x": "355", "y": str(y_offset_subnet), "width": "20", "height": "20", "as": "geometry"},
                    )
        
        return group_height

    # Render hub VNets (highly connected ones)
    for hub_index, hub_vnet in enumerate(hub_vnets):
        x_offset = 200 + (hub_index * 450)  # Space hubs horizontally
        y_offset = 400
        hub_id = f"hub_{hub_index}"
        
        add_vnet_with_subnets(hub_vnet, hub_id, x_offset, y_offset)

    # Dynamic spacing for spokes
    start_y = 200
    padding = 20
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
            
            # Use universal function with spoke styling
            spoke_style = "shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#CC6600;fillColor=#f2f7fc;verticalAlign=top"
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
                    style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
                    parent="1",
                )
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})

                if side == "left":
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": "200", "y": str(y_position + 25)})
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(base_x + 400), "y": str(y_position + 25)})
                else:
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": "600", "y": str(y_position + 25)})
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(base_x), "y": str(y_position + 25)})

            current_y += vnet_height + padding

    draw_spokes(right_spokes, "right", 700, current_y_right)
    draw_spokes(left_spokes, "left", -400, current_y_left)

    # Add non-peered spokes to the far right using universal function
    for index, spoke in enumerate(non_peered_spokes):
        y_position = current_y_nonpeered
        spoke_id = f"nonpeered_spoke{index}"
        
        # Use universal function with non-peered styling
        nonpeered_style = "shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=gray;fontColor=gray;fillColor=#f5f5f5;verticalAlign=top"
        vnet_height = add_vnet_with_subnets(spoke, spoke_id, 1200, y_position, nonpeered_style)

        current_y_nonpeered += vnet_height + padding

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
