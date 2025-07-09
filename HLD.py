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
    hubs_vnet = topology.get("hubs", [])
    spokes = topology.get("spokes", [])
    peerings = topology.get("peerings", [])

    spoke_y_positions = {}
    spoke_x_positions = {}
    hub_y_positions = {}

    h_box_width = 400
    h_box_spacing = 200

    colors = ['#008187', '#acd653', '#fcd116', '#f8842c', '#e44418', '#543b9c', '#0072c6', '#5cbbff', '#000520']

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

    hub_spacing = len([s for s in spokes if s.get('peerings')]) // 2 * 100 / len(hubs_vnet)

    for index, hub_vnet in enumerate(hubs_vnet):
        y_position = 400 + index * hub_spacing
        hub_y_positions[hub_vnet.get('name')] = y_position

        # Add Hub VNet
        hub = etree.SubElement(
            root,
            "mxCell",
            id=f"hub_{hub_vnet.get('name')}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB",
            vertex="1",
            parent="1",
        )
        #Verify if there is a Virtual-Hub vWAN environment HUB
        if hub_vnet.get("type") == "virtual_hub":
            hub.set("value", f"Subscription: {hub_vnet['subscription_name']}\n{hub_vnet.get('name', 'Hub VNet')}\n{hub_vnet.get('address_space', 'N/A')}")
        else:
            hub.set("value", f"Subscription: {hub_vnet['subscription_name']}\n{hub_vnet.get('name', 'Hub VNet')}\n{hub_vnet.get('address_space', 'N/A')}")

        etree.SubElement(
            hub,
            "mxGeometry",
            attrib={"x": str(h_box_width+h_box_spacing), "y": str(y_position), "width": str(h_box_width), "height": "50", "as": "geometry"},
        )

        # Add VNET image to the bottom right of the Hub
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"hub_image_{hub_vnet.get('name')}",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent="1",
        )
        etree.SubElement(
            image,
            "mxGeometry",
            attrib={"x": str(2*h_box_width+h_box_spacing-20), "y": str(y_position + 40), "width": "20", "height": "20", "as": "geometry"},
        )

        # If the hub is a virtual hub, show the Virtual Hub icon on the left
        if hub_vnet.get("type", "") == "virtual_hub":
            virtual_hub_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"hub_virtualhub_image_{hub_vnet.get('name')}",
                style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_WANs.svg;",
                vertex="1",
                parent="1",
            )
            etree.SubElement(
                virtual_hub_icon,
                "mxGeometry",
                attrib={"x": str(h_box_width+h_box_spacing+30), "y": str(y_position + 15), "width": "20", "height": "20", "as": "geometry"},
            )

        # Add extra icons for ExpressRoute, Firewall, VPN Gateway if applicable
        icon_x_base = 2*h_box_width+h_box_spacing-45  # Starting from right edge of hub
        icon_y = 400 + 50 - 10 + index * hub_spacing
        icon_spacing = -25  # Distance between icons

        if hub_vnet.get("expressroute", "").lower() == "yes":
            express_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"hub_expressroute_image_{hub_vnet.get('name')}",
                style="shape=image;html=1;image=img/lib/azure2/networking/ExpressRoute_Circuits.svg;",
                vertex="1",
                parent="1",
            )
            etree.SubElement(
                express_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )
            icon_x_base += icon_spacing

        if hub_vnet.get("firewall", "").lower() == "yes":
            firewall_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"hub_firewall_image_{hub_vnet.get('name')}",
                style="shape=image;html=1;image=img/lib/azure2/networking/Firewalls.svg;",
                vertex="1",
                parent="1",
            )
            etree.SubElement(
                firewall_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )
            icon_x_base += icon_spacing

        if hub_vnet.get("vpn_gateway", "").lower() == "yes":
            vpn_icon = etree.SubElement(
                root,
                "mxCell",
                id=f"hub_vpn_image_{hub_vnet.get('name')}",
                style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Network_Gateways.svg;",
                vertex="1",
                parent="1",
            )
            etree.SubElement(
                vpn_icon,
                "mxGeometry",
                attrib={"x": str(icon_x_base), "y": str(icon_y), "width": "20", "height": "20", "as": "geometry"},
            )

    # Dynamic spacing for spokes
    spacing = 100
    start_y = 200
    non_peered_spokes = []
    peered_spokes = []
    
    # Separate peered and non-peered spokes
    for spoke in spokes:
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
        # save spoke position for later
        spoke_y_positions[spoke.get('name')] = y_position
        spoke_x_positions[spoke.get('name')] = 2*h_box_width+1.5*h_box_spacing

        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_{spoke.get('name')}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#323130;fillColor=#f2f7fc",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']}\n{spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": str(2*h_box_width+2*h_box_spacing), "y": str(y_position), "width": str(h_box_width), "height": "50", "as": "geometry"},
        )
        
        # Add image to the bottom right of each Spoke
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_{spoke.get('name')}_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent="1",
        )
        # Ensure 'x' and 'y' are integers before adding
        spoke_x = int(spoke_cell.find(".//mxGeometry").attrib['x'])
        spoke_y = int(spoke_cell.find(".//mxGeometry").attrib['y'])
        
        etree.SubElement(
            image,
            "mxGeometry",
            attrib={
                "x": str(spoke_x + 380),
                "y": str(spoke_y + 40),
                "width": "20",
                "height": "20",
                "as": "geometry",
            },
        )

    # Add spokes on the left-hand side
    for index, spoke in enumerate(left_spokes):
        y_position = start_y + index * spacing
        # save spoke position for later
        spoke_y_positions[spoke.get('name')] = y_position
        spoke_x_positions[spoke.get('name')] = h_box_width+0.5*h_box_spacing
        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_{spoke.get('name')}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#323130;fillColor=#f2f7fc",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']}\n{spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": "0", "y": str(y_position), "width": str(h_box_width), "height": "50", "as": "geometry"},
        )
        # Add image to the bottom right of each Spoke
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_{spoke.get('name')}_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent="1",
        )
        # Ensure 'x' and 'y' are integers before adding
        spoke_x = int(spoke_cell.find(".//mxGeometry").attrib['x'])
        spoke_y = int(spoke_cell.find(".//mxGeometry").attrib['y'])
        
        etree.SubElement(
            image,
            "mxGeometry",
            attrib={
                "x": str(spoke_x + 380),
                "y": str(spoke_y + 40),
                "width": "20",
                "height": "20",
                "as": "geometry",
            },
        )

    for index, peering in enumerate(peerings):
        hub_info = [(hub.get('name'), idx) for idx, hub in enumerate(hubs_vnet) if hub.get('address_space')==peering.get('remote_address_space')]
        if len(hub_info) == 0:
            continue

        source_hub = hub_info[0][0]
        hub_idx = hub_info[0][1]

        target_spokes = [spoke.get('name') for spoke in spokes if peering.get('name') in spoke.get('peerings')]
        color_index = index % len(colors)

        offset_step = h_box_spacing / (len(hubs_vnet) + 1)
        offset = - h_box_spacing / 2 + offset_step*(1 + hub_idx)

        for spoke in target_spokes:
            # Add connection from Hub to Spokes
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_{index}_{spoke}",
                edge="1",
                source=f"hub_{source_hub}",
                target=f"spoke_{spoke}",
                style=f"edgeStyle=elbowEdgeStyle;rounded=1;strokeColor={colors[color_index]};strokeWidth=2;endArrow=block;startArrow=block;",
                parent="1",
            )
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": str(spoke_x_positions[spoke]+offset), "y": str(spoke_y_positions[spoke] + 25)})
            etree.SubElement(edge_points, "mxPoint", attrib={"x": str(spoke_x_positions[spoke]+offset), "y": str(hub_y_positions[source_hub] + 25)})
    
    # Add non-peered spokes to the right
    for index, spoke in enumerate(non_peered_spokes):
        y_position = start_y + index * spacing
        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=f"nonpeered_spoke{index}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#A19F9D;fontColor=#201F1E;fillColor=#F3F2F1",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']}\n{spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": str(3*h_box_width+3*h_box_spacing), "y": str(y_position), "width": str(h_box_width), "height": "50", "as": "geometry"},
        )

        # Add image to the bottom right of the non-peered spoke
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"nonpeered_spoke{index}_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent="1",
        )
        # Ensure 'x' and 'y' are integers before adding
        spoke_x = int(spoke_cell.find(".//mxGeometry").attrib['x'])
        spoke_y = int(spoke_cell.find(".//mxGeometry").attrib['y'])

        etree.SubElement(
            image,
            "mxGeometry",
            attrib={
                "x": str(spoke_x + 380),
                "y": str(spoke_y + 40),
                "width": "20",
                "height": "20",
                "as": "geometry",
            },
        )    

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
