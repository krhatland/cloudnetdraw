import json
import logging
from lxml import etree
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
def create_drawio_vnet_hub_and_spokes_diagram_HLD(output_filename: str, json_input_file: str):

    # Load the topology JSON data
    with open(json_input_file, 'r') as file:
        topology = json.load(file)

    logging.info("Loaded topology data from JSON")
    hub_vnet = topology.get("hub", {})
    spokes = topology.get("spokes", [])

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

    # Add Hub VNet
    hub = etree.SubElement(
        root,
        "mxCell",
        id="hub",
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
        attrib={"x": "400", "y": "400", "width": "400", "height": "50", "as": "geometry"},
    )

    # Add VNET image to the bottom right of the Hub
    image = etree.SubElement(
        root,
        "mxCell",
        id="hub_image",
        style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
        vertex="1",
        parent="1",
    )
    etree.SubElement(
        image,
        "mxGeometry",
        attrib={"x": "780", "y": "440", "width": "20", "height": "20", "as": "geometry"},
    )
    
    # If the hub is a virtual hub, show the Virtual Hub icon on the left
    if hub_vnet.get("type", "") == "virtual_hub":
        virtual_hub_icon = etree.SubElement(
            root,
            "mxCell",
            id="hub_virtualhub_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_WANs.svg;",
            vertex="1",
            parent="1",
        )
        etree.SubElement(
            virtual_hub_icon,
            "mxGeometry",
            attrib={"x": "390", "y": str(375 + 50 - 10), "width": "20", "height": "20", "as": "geometry"},
        )
        
    # Add extra icons for ExpressRoute, Firewall, VPN Gateway if applicable
    icon_x_base = 755  # Starting from right edge of hub
    icon_y = 400 + 50 - 10
    icon_spacing = -25  # Distance between icons

    if hub_vnet.get("expressroute", "").lower() == "yes":
        express_icon = etree.SubElement(
            root,
            "mxCell",
            id="hub_expressroute_image",
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
            id="hub_firewall_image",
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
            id="hub_vpn_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/VPN_Gateways.svg;",
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
    left_spokes = []
    right_spokes = []
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
        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_right_{index}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#323130;fillColor=#f2f7fc",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']}\n{spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": "900", "y": str(y_position), "width": "400", "height": "50", "as": "geometry"},
        )
        
        # Add image to the bottom right of each Spoke
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke{index}_image",
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

        # Add connection from Hub to Spokes
        edge = etree.SubElement(
            root,
            "mxCell",
            id=f"edge_right_{index}",
            edge="1",
            source="hub",
            target=f"spoke_right_{index}",
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
            parent="1",
        )
        edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
        edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
        etree.SubElement(edge_points, "mxPoint", attrib={"x": "800", "y": str(y_position + 25)})
        etree.SubElement(edge_points, "mxPoint", attrib={"x": "900", "y": str(y_position + 25)})

    # Add spokes on the left-hand side
    for index, spoke in enumerate(left_spokes):
        y_position = start_y + index * spacing
        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_left_{index}",
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#323130;fillColor=#f2f7fc",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']}\n{spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": "-100", "y": str(y_position), "width": "400", "height": "50", "as": "geometry"},
        )
        # Add image to the bottom right of each Spoke
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"spoke_left{index}_image",
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

        # Add connection from Hub to Spokes
        edge = etree.SubElement(
            root,
            "mxCell",
            id=f"edge_left_{index}",
            edge="1",
            source="hub",
            target=f"spoke_left_{index}",
            style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;",
            parent="1",
        )
        edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
        edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})
        etree.SubElement(edge_points, "mxPoint", attrib={"x": "400", "y": str(y_position + 25)})
        etree.SubElement(edge_points, "mxPoint", attrib={"x": "300", "y": str(y_position + 25)})
    
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
            attrib={"x": "1450", "y": str(y_position), "width": "400", "height": "50", "as": "geometry"},
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
    with open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {output_filename}")


# Generate the diagram from the JSON file
if __name__ == "__main__":
    logging.info("Starting HLD diagram generation...")
    create_drawio_vnet_hub_and_spokes_diagram_HLD("network_hld.drawio", "network_topology.json")
    logging.info("Diagram generation complete.")
    print("Diagram generation complete.")
