# drawio_generator.py
import json
import logging
from lxml import etree

def create_drawio_vnet_hub_and_spokes_diagram_MLD(output_filename: str, json_input_file: str):
    # Configure logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Load topology data
    with open(json_input_file, 'r') as file:
        topology = json.load(file)
    logging.info("Loaded topology data from JSON file.")

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
    hub_id = "hub"
    num_subnets = len(hub_vnet.get("subnets", []))
    vnet_height = 50 if hub_vnet.get("type") == "virtual_hub" else 30 + (num_subnets * 30)

    hub = etree.SubElement(
        root,
        "mxCell",
        id=hub_id,
        style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB;verticalAlign=top",
        vertex="1",
        parent="1",
    )
    hub.set("value", f"Subscription: {hub_vnet['subscription_name']}\n{hub_vnet.get('name', 'Hub VNet')}\n{hub_vnet.get('address_space', 'N/A')}")
    etree.SubElement(
        hub,
        "mxGeometry",
        attrib={"x": "200", "y": "400", "width": "400", "height": str(vnet_height), "as": "geometry"},
    )

    # Add vnet-image to the bottom right of the Hub
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
        attrib={"x": "580", "y": str(400 + vnet_height - 10), "width": "20", "height": "20", "as": "geometry"},
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
            attrib={"x": "190", "y": str(375 + vnet_height - 10), "width": "20", "height": "20", "as": "geometry"},
        )
    
    # Add extra icons for ExpressRoute, Firewall, VPN Gateway if applicable
    icon_x_base = 560  # Starting from right edge of hub
    icon_y = 400 + vnet_height - 10
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
        

    # Add subnets to the Hub if it's a regular VNet
    if hub_vnet.get("type") != "virtual_hub":
        for subnet_index, subnet in enumerate(hub_vnet.get("subnets", [])):
            subnet_cell = etree.SubElement(
                root,
                "mxCell",
                id=f"hub_subnet_{subnet_index}",
                style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#C8C6C4;fontColor=#323130;fillColor=#FAF9F8",
                vertex="1",
                parent=hub_id,
            )
            subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
            y_offset = 35 + subnet_index * 30
            etree.SubElement(subnet_cell, "mxGeometry", attrib={"x": "25", "y": str(y_offset), "width": "350", "height": "20", "as": "geometry"})

            #Add NSG icon if NSG is attached to the subnet
            if subnet.get("nsg", "").lower() == "yes":
                nsg_icon = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"hub_subnet_{subnet_index}_nsg",
                    style="shape=image;html=1;image=img/lib/azure2/networking/Network_Security_Groups.svg;",
                    vertex="1",
                    parent=hub_id,
                )
                etree.SubElement(
                    nsg_icon,
                    "mxGeometry",
                    attrib={"x": "25", "y": str(y_offset), "width": "20", "height": "20", "as": "geometry"},
                )

            #Add UDR icon if UDR is attached to the subnet
            if subnet.get("udr", "").lower() == "yes":
                udr_icon = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"hub_subnet_{subnet_index}_udr",
                    style="shape=image;html=1;image=img/lib/azure2/networking/Route_Tables.svg;",
                    vertex="1",
                    parent=hub_id,
                )
                etree.SubElement(
                    udr_icon,
                    "mxGeometry",
                    attrib={"x": "355", "y": str(y_offset), "width": "20", "height": "20", "as": "geometry"},
                )

    # Dynamic spacing for spokes
    start_y = 200
    padding = 20
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

    #Draw out the spokes
    def draw_spokes(spokes_list, side, base_x, current_y):
        for idx, spoke in enumerate(spokes_list):
            spoke_id = f"{side}_spoke{idx}"
            y_position = current_y
            num_subnets = len(spoke.get("subnets", []))
            vnet_height = 30 + (num_subnets * 30)

            spoke_cell = etree.SubElement(
                root,
                "mxCell",
                id=spoke_id,
                style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#CC6600;fontColor=#CC6600;fillColor=#f2f7fc;verticalAlign=top",
                vertex="1",
                parent="1",
            )
            spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']} {spoke['address_space']}")
            etree.SubElement(
                spoke_cell,
                "mxGeometry",
                attrib={"x": str(base_x), "y": str(y_position), "width": "400", "height": str(40 + (num_subnets * 30)), "as": "geometry"},
            )
            #Add vNet icon to spokes
            image = etree.SubElement(
                root,
                "mxCell",
                id=f"{spoke_id}_image",
                style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
                vertex="1",
                parent="1",
            )
            etree.SubElement(
                image,
                "mxGeometry",
                attrib={
                    "x": str(base_x + 380),
                    "y": str(y_position + vnet_height),
                    "width": "20",
                    "height": "20",
                    "as": "geometry",
                },
            )
            #Add subnets to vNets
            for subnet_index, subnet in enumerate(spoke.get("subnets", [])):
                subnet_cell = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{spoke_id}_subnet_{subnet_index}",
                    style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#C8C6C4;fontColor=#323130;fillColor=#FAF9F8",
                    vertex="1",
                    parent=spoke_id,
                )
                subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
                etree.SubElement(
                    subnet_cell,
                    "mxGeometry",
                    attrib={"x": "25", "y": str(40 + (subnet_index * 30)), "width": "350", "height": "20", "as": "geometry"},
                )
                #Add NSG icon if NSG is connected to the subnet
                if subnet.get("nsg", "").lower() == "yes":
                    nsg_icon = etree.SubElement(
                        root,
                        "mxCell",
                        id=f"{spoke_id}_subnet_{subnet_index}_nsg",
                        style="shape=image;html=1;image=img/lib/azure2/networking/Network_Security_Groups.svg;",
                        vertex="1",
                        parent=spoke_id,
                    )
                    etree.SubElement(
                        nsg_icon,
                        "mxGeometry",
                        attrib={"x": "25", "y": str(40 + (subnet_index * 30)), "width": "20", "height": "20", "as": "geometry"},
                    )
                #Add UDR icon if UDR is connected to the subnet
                if subnet.get("udr", "").lower() == "yes":
                    udr_icon = etree.SubElement(
                        root,
                        "mxCell",
                        id=f"{spoke_id}_subnet_{subnet_index}_udr",
                        style="shape=image;html=1;image=img/lib/azure2/networking/Route_Tables.svg;",
                        vertex="1",
                        parent=spoke_id,
                    )
                    etree.SubElement(
                        udr_icon,
                        "mxGeometry",
                        attrib={"x": "355", "y": str(40 + (subnet_index * 30)), "width": "20", "height": "20", "as": "geometry"},
                    )
            #Add connections between hub and spokes
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"edge_{side}_{idx}_{spoke['name']}",
                edge="1",
                source="hub",
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

    # Add non-peered spokes to the far right
    for index, spoke in enumerate(non_peered_spokes):
        y_position = current_y_nonpeered
        vnet_height = 40 + (len(spoke.get("subnets", [])) * 30)
        spoke_id = f"nonpeered_spoke{index}"

        spoke_cell = etree.SubElement(
            root,
            "mxCell",
            id=spoke_id,
            style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=gray;fontColor=gray;fillColor=#f5f5f5;verticalAlign=top",
            vertex="1",
            parent="1",
        )
        spoke_cell.set("value", f"Subscription: {spoke['subscription_name']}\n{spoke['name']} {spoke['address_space']}")
        etree.SubElement(
            spoke_cell,
            "mxGeometry",
            attrib={"x": "1200", "y": str(y_position), "width": "400", "height": str(vnet_height), "as": "geometry"},
        )
        #Add VNET icon
        image = etree.SubElement(
            root,
            "mxCell",
            id=f"{spoke_id}_image",
            style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_Networks.svg;",
            vertex="1",
            parent="1",
        )
        etree.SubElement(
            image,
            "mxGeometry",
            attrib={"x": "1580", "y": str(y_position + vnet_height - 10), "width": "20", "height": "20", "as": "geometry"},
        )
        
        #Add subnets to the non-peered spokes
        for subnet_index, subnet in enumerate(spoke.get("subnets", [])):
            subnet_cell = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{spoke_id}_subnet_{subnet_index}",
                    style="shape=rectangle;rounded=1;whiteSpace=wrap;html=1;strokeColor=#C8C6C4;fontColor=#323130;fillColor=#FAF9F8",
                    vertex="1",
                    parent=spoke_id,
            )
            subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
            etree.SubElement(
                    subnet_cell,
                    "mxGeometry",
                    attrib={"x": "25", "y": str(40 + (subnet_index * 30)), "width": "350", "height": "20", "as": "geometry"},
                )
            #Add NSG icon if NSG is present
            if subnet.get("nsg", "").lower() == "yes":
                nsg_icon = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{spoke_id}_subnet_{subnet_index}_nsg",
                    style="shape=image;html=1;image=img/lib/azure2/networking/Network_Security_Groups.svg;",
                    vertex="1",
                    parent=spoke_id,
                    )
                etree.SubElement(
                    nsg_icon,
                    "mxGeometry",
                    attrib={"x": "25", "y": str(40 + (subnet_index * 30)), "width": "20", "height": "20", "as": "geometry"},
                    )
            #Add UDR icon if UDR is present
            if subnet.get("udr", "").lower() == "yes":
                udr_icon = etree.SubElement(
                    root,
                    "mxCell",
                    id=f"{spoke_id}_subnet_{subnet_index}_udr",
                    style="shape=image;html=1;image=img/lib/azure2/networking/Route_Tables.svg;",
                    vertex="1",
                    parent=spoke_id,
                    )
                etree.SubElement(
                    udr_icon,
                    "mxGeometry",
                     attrib={"x": "355", "y": str(40 + (subnet_index * 30)), "width": "20", "height": "20", "as": "geometry"},
                    )

        current_y_nonpeered += vnet_height + padding

    # Write to file
    tree = etree.ElementTree(mxfile)
    with open(output_filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {output_filename}")

# Generate the diagram from the JSON file
if __name__ == "__main__":
    logging.info("Starting diagram generation...")
    create_drawio_vnet_hub_and_spokes_diagram_MLD("/tmp/network_diagram_MLD.drawio", "/tmp/network_topology.json")
    logging.info("Diagram generation complete.")