# CLOUDNET DRAW

Python tool for automatically generating visual diagrams of Azure virtual network infrastructures from topology data. CloudNet Draw converts Azure VNet topology JSON into `.drawio` diagram files, targeting Hub-and-Spoke network architectures.

![GitHub stars](https://img.shields.io/github/stars/krhatland/cloudnet-draw?style=social)

Website: [CloudNetDraw](https://www.cloudnetdraw.com/)

Blog: [Technical Deep Dive](https://hatnes.no/posts/cloudnet-draw/) 

## Deploy to Azure

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fkrhatland%2Fcloudnet-draw%2Fmain%2Fazure-function%2Finfra%2Fmain.json)

## 📌 Key Features

- 🔎 Converts Azure VNet topology (JSON) into visual diagrams
- 📄 Outputs `.drawio` files (open with [draw.io / diagrams.net](https://draw.io))
- 🖼️ Supports hub, spoke, subnets, peerings, and Azure service icons (NSG, UDR, Firewall, etc.)
- 🧠 Logic-based layout:
  - Peered vs non-peered spokes
  - Left/right layout split
  - Icon placement and subnet expansion
- 🧩 Extendable for MLD, HLD, and custom peerings

---

## Quick Start Guide

Setup:

### 1. Install and Setup
```bash
git clone https://github.com/krhatland/cloudnet-draw.git
cd cloudnet-draw
uv venv
uv pip install -r requirements.txt
```

### 2. Authenticate with Azure
```bash
az login
```

### 3. Generate Your First Diagram
```bash
uv run azure-query.py query
uv run azure-query.py hld
uv run azure-query.py mld
```

### 4. View Results
Open the generated `network_hld.drawio` and `network_mld.drawio` files with [Draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) or the web version at [diagrams.net](https://diagrams.net).

## Installation

### Prerequisites
- Python 3.8+
- Azure cli (`az`)
- Azure access to subscriptions and vnets
- [Draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) (recommended for viewing diagrams)
- make (optional, for testing with Makefile)

### Setup

**MacOS/Linux:**
```bash
git clone https://github.com/krhatland/cloudnet-draw.git
cd cloudnet-draw
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```cmd
git clone https://github.com/krhatland/cloudnet-draw.git
cd cloudnet-draw
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

CloudNet Draw uses YAML-based configuration for diagram styling and layout settings.

### Configuration Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `thresholds.hub_peering_count` | `3` | VNets with this many peerings are classified as hubs |
| `styles.hub.border_color` | `"#0078D4"` | Hub VNet border color |
| `styles.hub.fill_color` | `"#E6F1FB"` | Hub VNet background color |
| `styles.hub.font_color` | `"#004578"` | Hub VNet text color |
| `styles.hub.line_color` | `"#0078D4"` | Hub VNet line color |
| `styles.hub.text_align` | `"left"` | Hub VNet text alignment |
| `styles.spoke.border_color` | `"#CC6600"` | Spoke VNet border color |
| `styles.spoke.fill_color` | `"#f2f7fc"` | Spoke VNet background color |
| `styles.spoke.font_color` | `"#CC6600"` | Spoke VNet text color |
| `styles.spoke.line_color` | `"#0078D4"` | Spoke VNet line color |
| `styles.spoke.text_align` | `"left"` | Spoke VNet text alignment |
| `styles.non_peered.border_color` | `"gray"` | Non-peered VNet border color |
| `styles.non_peered.fill_color` | `"#f5f5f5"` | Non-peered VNet background color |
| `styles.non_peered.font_color` | `"gray"` | Non-peered VNet text color |
| `styles.non_peered.line_color` | `"gray"` | Non-peered VNet line color |
| `styles.non_peered.text_align` | `"left"` | Non-peered VNet text alignment |
| `subnet.border_color` | `"#C8C6C4"` | Subnet border color |
| `subnet.fill_color` | `"#FAF9F8"` | Subnet background color |
| `subnet.font_color` | `"#323130"` | Subnet text color |
| `subnet.text_align` | `"left"` | Subnet text alignment |
| `layout.canvas.padding` | `20` | Padding from canvas edges |
| `layout.zone.spacing` | `500` | Gap between different zones |
| `layout.vnet.width` | `400` | Standard width for VNet boxes |
| `layout.vnet.spacing_x` | `450` | Horizontal spacing between VNets |
| `layout.vnet.spacing_y` | `100` | Vertical spacing between VNets |
| `layout.hub.spacing_x` | `450` | Horizontal spacing between hubs |
| `layout.hub.spacing_y` | `400` | Vertical position of hubs |
| `layout.hub.width` | `400` | Width of hub VNet boxes |
| `layout.hub.height` | `50` | Height of hub VNet boxes |
| `layout.spoke.spacing_y` | `100` | Vertical spacing between spokes |
| `layout.spoke.start_y` | `200` | Starting Y position for spokes |
| `layout.spoke.width` | `400` | Width of spoke VNet boxes |
| `layout.spoke.height` | `50` | Height of spoke VNet boxes |
| `layout.spoke.left_x` | `-100` | X position for left-side spokes |
| `layout.spoke.right_x` | `900` | X position for right-side spokes |
| `layout.non_peered.spacing_y` | `100` | Vertical spacing between non-peered VNets |
| `layout.non_peered.start_y` | `200` | Starting Y position for non-peered VNets |
| `layout.non_peered.x` | `1450` | X position for non-peered spokes |
| `layout.non_peered.width` | `400` | Width of non-peered VNet boxes |
| `layout.non_peered.height` | `50` | Height of non-peered VNet boxes |
| `layout.subnet.width` | `350` | Width of subnet boxes |
| `layout.subnet.height` | `20` | Height of subnet boxes |
| `layout.subnet.padding_x` | `25` | Horizontal padding for subnets |
| `layout.subnet.padding_y` | `55` | Vertical padding for subnets |
| `layout.subnet.spacing_y` | `30` | Vertical spacing between subnets |
| `edges.stroke_color` | `"#0078D4"` | Edge stroke color |
| `edges.stroke_width` | `2` | Edge stroke width |
| `edges.style` | `"edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#0078D4;strokeWidth=2;endArrow=block;startArrow=block;"` | Edge style string |
| `icons.vnet.path` | `"img/lib/azure2/networking/Virtual_Networks.svg"` | VNet icon path |
| `icons.vnet.width` | `20` | VNet icon width |
| `icons.vnet.height` | `20` | VNet icon height |
| `icons.virtual_hub.path` | `"img/lib/azure2/networking/Virtual_WANs.svg"` | Virtual Hub icon path |
| `icons.virtual_hub.width` | `20` | Virtual Hub icon width |
| `icons.virtual_hub.height` | `20` | Virtual Hub icon height |
| `icons.expressroute.path` | `"img/lib/azure2/networking/ExpressRoute_Circuits.svg"` | ExpressRoute icon path |
| `icons.expressroute.width` | `20` | ExpressRoute icon width |
| `icons.expressroute.height` | `20` | ExpressRoute icon height |
| `icons.firewall.path` | `"img/lib/azure2/networking/Firewalls.svg"` | Azure Firewall icon path |
| `icons.firewall.width` | `20` | Azure Firewall icon width |
| `icons.firewall.height` | `20` | Azure Firewall icon height |
| `icons.vpn_gateway.path` | `"img/lib/azure2/networking/Virtual_Network_Gateways.svg"` | VPN Gateway icon path |
| `icons.vpn_gateway.width` | `20` | VPN Gateway icon width |
| `icons.vpn_gateway.height` | `20` | VPN Gateway icon height |
| `icons.nsg.path` | `"img/lib/azure2/networking/Network_Security_Groups.svg"` | NSG icon path |
| `icons.nsg.width` | `16` | NSG icon width |
| `icons.nsg.height` | `16` | NSG icon height |
| `icons.route_table.path` | `"img/lib/azure2/networking/Route_Tables.svg"` | Route Table icon path |
| `icons.route_table.width` | `16` | Route Table icon width |
| `icons.route_table.height` | `16` | Route Table icon height |
| `icons.subnet.path` | `"img/lib/azure2/networking/Subnet.svg"` | Subnet icon path |
| `icons.subnet.width` | `20` | Subnet icon width |
| `icons.subnet.height` | `12` | Subnet icon height |
| `icon_positioning.vnet_icons.y_offset` | `3.39` | Y position from top of VNet |
| `icon_positioning.vnet_icons.right_margin` | `6` | Margin from right edge of VNet |
| `icon_positioning.vnet_icons.icon_gap` | `5` | Gap between icons |
| `icon_positioning.virtual_hub_icon.offset_x` | `-10` | X offset from VNet left edge |
| `icon_positioning.virtual_hub_icon.offset_y` | `-15` | Y offset from VNet bottom |
| `icon_positioning.subnet_icons.icon_y_offset` | `2` | Y offset from subnet top edge |
| `icon_positioning.subnet_icons.subnet_icon_y_offset` | `3` | Subnet icon height alignment offset |
| `icon_positioning.subnet_icons.icon_gap` | `3` | Gap between icons in pixels |
| `drawio.canvas.dx` | `"371"` | Canvas X offset |
| `drawio.canvas.dy` | `"1462"` | Canvas Y offset |
| `drawio.canvas.grid` | `"0"` | Grid display setting |
| `drawio.canvas.gridSize` | `"10"` | Grid size |
| `drawio.canvas.guides` | `"1"` | Guides display setting |
| `drawio.canvas.tooltips` | `"1"` | Tooltips display setting |
| `drawio.canvas.connect` | `"1"` | Connection display setting |
| `drawio.canvas.arrows` | `"1"` | Arrow display setting |
| `drawio.canvas.fold` | `"1"` | Fold display setting |
| `drawio.canvas.page` | `"0"` | Page display setting |
| `drawio.canvas.pageScale` | `"1"` | Page scale setting |
| `drawio.canvas.pageWidth` | `"827"` | Page width |
| `drawio.canvas.pageHeight` | `"1169"` | Page height |
| `drawio.canvas.background` | `"#ffffff"` | Canvas background color |
| `drawio.canvas.math` | `"0"` | Math display setting |
| `drawio.canvas.shadow` | `"0"` | Shadow display setting |
| `drawio.group.extra_height` | `20` | Extra space in group for icons below VNet |
| `drawio.group.connectable` | `"0"` | Group connectable setting |

## Usage Examples

### Example 1: Single Hub with Multiple Spokes

```bash
# Query specific subscription
uv run azure-query.py query --subscriptions "Production-Network"

# Generate both diagram types
uv run azure-query.py hld
uv run azure-query.py mld
```

**Expected Output:**
- `network_hld.drawio` - High-level view showing VNet relationships
- `network_mld.drawio` - Detailed view including subnets and services

### Example 2: Multi-Subscription Environment

```bash
# Interactive subscription selection
uv run azure-query.py query

# Follow prompts to select subscriptions
# Example: 1,3,5 for subscriptions 1, 3, and 5

# Generate consolidated diagrams
uv run azure-query.py hld
```

### Example 3: Custom Configuration

```bash
# Create custom config
cp config.yaml my_config.yaml
# Edit my_config.yaml with your settings

# Use custom config
uv run azure-query.py query --config-file my_config.yaml
```

### Example 4: Hub VNet Filtering

Filter topology to focus on a specific hub VNet and its directly connected spokes:

```bash
# Filter by resource group and VNet name (recommended - fast and precise)
uv run azure-query.py query --vnet "ops-mcg-vnet-dev-rg/OPS-network-dev-vnet" --verbose

# Filter by full Azure resource ID
uv run azure-query.py query --vnet "/subscriptions/98e9a6c7-c9c0-4419-bd65-2b18c741a0f4/resourceGroups/ops-mcg-vnet-dev-rg/providers/Microsoft.Network/virtualNetworks/OPS-network-dev-vnet"

# Generate diagrams from filtered topology
uv run azure-query.py hld
uv run azure-query.py mld
```

**Key Features:**
- **⚡ Fast Azure Resource Graph API**: Single efficient query instead of scanning all subscriptions
- **🎯 Unique identification**: Uses `resource_group/vnet_name` format for precise VNet identification
- **🔍 Automatic discovery**: No need to specify `--subscriptions` parameter
- **📊 Filtered topology**: Contains only hub and directly connected spokes

**Expected Output:**
- Filtered JSON containing only the specified hub and its directly peered spokes
- Focused diagrams showing hub-spoke relationships for the selected VNet
- Significantly faster processing compared to full topology collection

**Use Cases:**
- Focus on specific network segments in large multi-hub environments
- Troubleshoot connectivity issues for a particular hub
- Generate documentation for specific application network boundaries
- Isolate network components for security or compliance reviews

## Testing

### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific test tiers
make unit          # Unit tests only
make integration   # Integration tests only

# Generate coverage report
make coverage
```





## License and Contact

### License
This project is licensed under the MIT License.
You are free to use, modify, and distribute it with attribution.

### Author
**Kristoffer Hatland**  
🔗 [LinkedIn](https://www.linkedin.com/in/hatland) • 🐙 [GitHub](https://github.com/krhatland)

### Resources
- **Website**: [CloudNetDraw.com](https://www.cloudnetdraw.com/)
- **Blog**: [Technical Deep Dive](https://hatnes.no/posts/cloudnet-draw/)
- **Issues**: [GitHub Issues](https://github.com/krhatland/cloudnet-draw/issues)
- **Discussions**: [GitHub Discussions](https://github.com/krhatland/cloudnet-draw/discussions)



---

**Made with ❤️ for the Azure community**
