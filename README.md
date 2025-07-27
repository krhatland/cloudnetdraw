# CLOUDNET DRAW

Python tool for automatically generating visual diagrams of Azure virtual network infrastructures from topology data. CloudNet Draw converts Azure VNet topology JSON into `.drawio` diagram files, targeting Hub-and-Spoke network architectures.

![GitHub stars](https://img.shields.io/github/stars/krhatland/cloudnet-draw?style=social)

Website: [CloudNetDraw](https://www.cloudnetdraw.com/)

Blog: [Technical Deep Dive](https://hatnes.no/posts/cloudnet-draw/) 

## Deploy to Azure

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fkrhatland%2Fcloudnet-draw%2Fmain%2Fazure-function%2Finfra%2Fmain.json)

## 📌 Key Features

- 🔎 Azure Resource Graph integration for efficient VNet discovery
- 📄 Outputs `.drawio` files (open with [draw.io / diagrams.net](https://draw.io))
- 🖼️ Supports hub, spoke, subnets, peerings, and Azure service icons (NSG, UDR, Firewall, etc.)
- 🧠 Logic-based layout with hub-spoke architecture detection
- 🎯 VNet filtering by resource ID or path for focused diagrams
- 🔐 Multiple authentication methods (Azure CLI or Service Principal)
- 🔗 Integrated Azure portal hyperlinks and resource metadata
- 🧩 Two diagram types: HLD (VNets only) and MLD (VNets + subnets)

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
# Option 1: Azure CLI (default)
az login

# Option 2: Service Principal (set environment variables)
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"
```

### 3. Generate Your First Diagram
```bash
# Query Azure and save topology
uv run azure-query.py query

# Generate high-level diagram (VNets only)
uv run azure-query.py hld

# Generate mid-level diagram (VNets + subnets)
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

CloudNet Draw uses [`config.yaml`](config.yaml) for diagram styling and layout settings. Key configuration sections:

### Hub Classification
- `thresholds.hub_peering_count: 10` - VNets with 10+ peerings are classified as hubs

### VNet Styling
- **Hub VNets**: Blue theme (`#0078D4` border, `#E6F1FB` fill)
- **Spoke VNets**: Orange theme (`#CC6600` border, `#f2f7fc` fill)
- **Non-peered VNets**: Gray theme (`gray` border, `#f5f5f5` fill)
- **Subnets**: Light gray theme (`#C8C6C4` border, `#FAF9F8` fill)

### Layout Settings
- **Canvas**: 20px padding, 500px zone spacing
- **VNets**: 400px width, 50px height
- **Subnets**: 350px width, 20px height with 25px/55px padding

### Edge Styling
- **Hub-Spoke**: Black solid lines (3px width)
- **Spoke-Spoke**: Gray dashed lines (2px width)
- **Cross-Zone**: Blue dashed lines (2px width)

### Azure Icons
Includes paths and sizing for VNet, ExpressRoute, Firewall, VPN Gateway, NSG, Route Table, and Subnet icons from Azure icon library.

### Custom Configuration
```bash
# Copy and modify default configuration
cp config.yaml my-config.yaml

# Use custom configuration
uv run azure-query.py query --config-file my-config.yaml
uv run azure-query.py hld --config-file my-config.yaml
```

## Usage Examples

### Example 1: Basic Usage

```bash
# Query all subscriptions interactively
uv run azure-query.py query

# Query specific subscriptions
uv run azure-query.py query --subscriptions "Production-Network,Dev-Network"

# Query all subscriptions non-interactively
uv run azure-query.py query --subscriptions all

# Generate diagrams
uv run azure-query.py hld  # High-level (VNets only)
uv run azure-query.py mld  # Mid-level (VNets + subnets)
```

### Example 2: Service Principal Authentication

```bash
# Set environment variables
export AZURE_CLIENT_ID="your-client-id"
export AZURE_CLIENT_SECRET="your-client-secret"
export AZURE_TENANT_ID="your-tenant-id"

# Use service principal
uv run azure-query.py query --service-principal
```

### Example 3: VNet Filtering

Filter topology to focus on specific hub VNets and their directly connected spokes:

```bash
# Multiple VNet identifier formats supported:

# Format 1: Full Azure resource ID
uv run azure-query.py query --vnets "/subscriptions/sub-id/resourceGroups/rg-name/providers/Microsoft.Network/virtualNetworks/vnet-name"

# Format 2: subscription/resource_group/vnet_name
uv run azure-query.py query --vnets "production-sub/network-rg/hub-vnet"

# Format 3: resource_group/vnet_name (searches all accessible subscriptions)
uv run azure-query.py query --vnets "network-rg/hub-vnet"

# Multiple VNets (comma-separated)
uv run azure-query.py query --vnets "prod-rg/hub-prod,dev-rg/hub-dev"

# Generate diagrams from filtered topology
uv run azure-query.py hld
uv run azure-query.py mld
```

**VNet Filtering Benefits:**
- Uses Azure Resource Graph API for fast, precise discovery
- Automatically resolves subscription names to IDs
- Contains only specified hubs and their directly peered spokes
- Significantly faster than full topology collection

### Example 4: File-Based Configuration

```bash
# Create subscription list file
echo "Production-Network" > subscriptions.txt
echo "Development-Network" >> subscriptions.txt

# Use subscription file
uv run azure-query.py query --subscriptions-file subscriptions.txt

# Custom config file
uv run azure-query.py query --config-file my-config.yaml
uv run azure-query.py hld --config-file my-config.yaml
```

### Example 5: Verbose Logging

```bash
# Enable detailed logging for troubleshooting
uv run azure-query.py query --vnets "rg-name/hub-vnet" --verbose
uv run azure-query.py hld --verbose
```

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
