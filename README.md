# CLOUDNET DRAW

Python tool to automatically discovery Azure virtual network infrastructures and
generate Draw.io visual diagrams from topology data.

![GitHub stars](https://img.shields.io/github/stars/krhatland/cloudnet-draw?style=social)

Website: [CloudNetDraw](https://www.cloudnetdraw.com/)

Blog: [Technical Deep Dive](https://hatnes.no/posts/cloudnetdraw/)

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

### 1. Install CloudNet Draw

CloudNet is a PyPi package. Use uv or pip.

Option A: Using uvx (Recommended - Run without installing)

```bash
uvx cloudnetdraw --help
```

Option B: Using uv

```bash
uv tool install cloudnetdraw
```

Option C: Install via PyPI

```bash
pip install cloudnetdraw
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
<<<<<<< Updated upstream
# Query Azure and save topology
uv run azure-query.py query

# Generate high-level diagram (VNets only)
uv run azure-query.py hld

# Generate mid-level diagram (VNets + subnets)
uv run azure-query.py mld
=======
cloudnetdraw query
cloudnetdraw hld
>>>>>>> Stashed changes
```

### 4. View Results

Open the generated `network_hld.drawio` file with [Draw.io
Desktop](https://github.com/jgraph/drawio-desktop/releases) or the web version
at [diagrams.net](https://diagrams.net).

## Installation

### Prerequisites

- Python 3.8+
- Azure CLI (`az`)
- Azure access to subscriptions and vnets
- uv for package management (preferred over pip)
- [Draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) (recommended for viewing diagrams)

## Configuration

CloudNet Draw uses [`config.yaml`](config.yaml) for diagram styling and layout settings. Key configuration sections:

<<<<<<< Updated upstream
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
=======
```bash
# Create a local config file for customization
cloudnetdraw init-config

# Use custom config with other commands
cloudnetdraw query --config-file config.yaml
>>>>>>> Stashed changes
```

The `init-config` command copies the default configuration to your current directory where you can customize diagram styling, layout parameters, and other settings.

<<<<<<< Updated upstream
### Example 1: Basic Usage

```bash
# Query all subscriptions interactively
uv run azure-query.py query
=======
## Examples

### Single Hub with Multiple Spokes

```bash
# Query specific subscription
cloudnetdraw query --subscriptions "Production-Network"

# Generate both diagram types
cloudnetdraw hld
cloudnetdraw mld
```

**Expected Output:**

- `network_hld.drawio` - High-level view showing VNet relationships
- `network_mld.drawio` - Detailed view including subnets and services

### Interactive Mode

```bash
# Interactive subscription selection
cloudnetdraw query
>>>>>>> Stashed changes

# Query specific subscriptions
uv run azure-query.py query --subscriptions "Production-Network,Dev-Network"

<<<<<<< Updated upstream
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
=======
# Generate consolidated diagrams
cloudnetdraw hld
```

### VNet Filtering
>>>>>>> Stashed changes

Filter topology to focus on specific hub VNets and their directly connected spokes:

```bash
<<<<<<< Updated upstream
# Multiple VNet identifier formats supported:

# Format 1: Full Azure resource ID
uv run azure-query.py query --vnets "/subscriptions/sub-id/resourceGroups/rg-name/providers/Microsoft.Network/virtualNetworks/vnet-name"

# Format 2: subscription/resource_group/vnet_name
uv run azure-query.py query --vnets "production-sub/network-rg/hub-vnet"

# Format 3: resource_group/vnet_name (searches all accessible subscriptions)
uv run azure-query.py query --vnets "network-rg/hub-vnet"

# Multiple VNets (comma-separated)
uv run azure-query.py query --vnets "prod-rg/hub-prod,dev-rg/hub-dev"
=======
# Filter by subscription/resource-group/vnet path
cloudnetdraw query --vnets "production-sub/network-rg/hub-vnet" --verbose

# Filter by full Azure resource ID
cloudnetdraw query --vnets "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet"

# Multiple VNets using path syntax
cloudnetdraw query --vnets "prod-sub/network-rg/hub-vnet-east,prod-sub/network-rg/hub-vnet-west"
>>>>>>> Stashed changes

# Generate diagrams from filtered topology
cloudnetdraw hld
cloudnetdraw mld
```

<<<<<<< Updated upstream
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

=======
>>>>>>> Stashed changes
## Testing

### Running Tests

```bash
# Run all tests with coverage
make test

# Run specific test tiers
make unit          # Unit tests only
make integration   # Integration tests only
make coverage      # code coverage
make random        # generate and validate random topologies
```

## Development

### Make Commands

The project includes several make commands for development and testing:

```bash
# Setup and help
make setup         # Set up development environment
make help          # Show all available targets

# Generate example topologies and diagrams
make examples

# Package management and publishing
make build           # Build distribution packages
make test-publish    # Publish to TestPyPI for testing
make publish         # Publish to production PyPI
make prepare-release # Run full test suite and build for release

# Cleanup
make clean         # Clean up test artifacts
make clean-build   # Clean build artifacts (dist/, *.egg-info/)
make clean-all     # Clean everything including .venv
```

### Utility Scripts

The [`utils/`](utils/) directory contains development tools for generating and testing topologies:

#### topology-generator.py

Generate Azure network topology JSON files with configurable parameters:

```bash
cd utils
# Basic usage
python3 topology-generator.py --vnets 50 --centralization 8 --connectivity 6 --isolation 2 --output topology.json

# With advanced options
python3 topology-generator.py -v 100 -c 7 -n 5 -i 3 -o large_topology.json --seed 42 --ensure-all-edge-types
```

**Required Parameters:**

- `-v, --vnets` - Number of VNets to generate
- `-c, --centralization` - Hub concentration (0-10, controls hub-spoke bias)
- `-n, --connectivity` - Peering density (0-10, controls outlier scenarios)
- `-i, --isolation` - Disconnected VNets (0-10, controls unpeered VNets)
- `-o, --output` - Output JSON filename

**Advanced Options:**

- `--seed` - Random seed for reproducible generation
- `--ensure-all-edge-types` - Ensure all 6 EdgeTypes are present
- `--spoke-to-spoke-rate` - Override spoke-to-spoke connection rate (0.0-1.0)
- `--cross-zone-rate` - Override cross-zone connection rate (0.0-1.0)
- `--multi-hub-rate` - Override multi-hub spoke rate (0.0-1.0)
- `--hub-count` - Override hub count (ignores centralization weight)

#### topology-randomizer.py

Generate and validate many topologies in parallel

```bash
cd utils
# Basic usage
python3 topology-randomizer.py --iterations 25 --vnets 100 --parallel-jobs 4

# With advanced options
python3 topology-randomizer.py -i 50 -v 200 -p 8 --seed 42 --ensure-all-edge-types
```

**Parameters:**

- `-i, --iterations` - Number of test iterations (default: 10)
- `-v, --vnets` - Fixed number of VNets for all iterations (default: 100)
- `-p, --parallel-jobs` - Maximum number of parallel jobs (default: 4)
- `--max-centralization` - Upper bound for centralization weight (default: 10)
- `--max-connectivity` - Upper bound for connectivity weight (default: 10)
- `--max-isolation` - Upper bound for isolation weight (default: 10)
- `--seed` - Random seed for reproducible generation
- `--ensure-all-edge-types` - Ensure all 6 EdgeTypes are present in generated topologies

#### topology-validator.py

Validates JSON topologies and generated diagrams for structural integrity:

```bash
cd utils
# Validate all files in examples directory (default behavior)
python3 topology-validator.py

# Validate specific files
python3 topology-validator.py --topology topology.json --hld topology_hld.drawio --mld topology_mld.drawio

# Validate just topology file
python3 topology-validator.py -t topology.json
```

**Parameters:**

- `-t, --topology` - JSON topology file to validate
- `-H, --hld` - HLD (High Level Design) DrawIO file to validate
- `-M, --mld` - MLD (Mid Level Design) DrawIO file to validate
- `--quiet` - Suppress informational output

All scripts support `--help` for detailed usage information.

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

Made with ❤️ for the Azure community
