# CLOUDNET DRAW

![GitHub Stars](https://img.shields.io/github/stars/krhatland/cloudnet-draw?style=flat&logo=github&logoColor=white&label=stars&color=yellow)

Python tool to automatically discovery Azure virtual network infrastructures and
generate Draw.io visual diagrams from topology data.

<img src="img/example_diagram.jpeg" alt="Example Diagram" width="600">

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
cloudnetdraw query
cloudnetdraw hld
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

```bash
# Create a local config file for customization
cloudnetdraw init-config

# Use custom config with other commands
cloudnetdraw query --config-file config.yaml
```

The `init-config` command copies the default configuration to your current directory where you can customize diagram styling, layout parameters, and other settings.

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

# Query specific subscriptions
uv run azure-query.py query --subscriptions "Production-Network,Dev-Network"

# Generate consolidated diagrams
cloudnetdraw hld
```

### VNet Filtering

Filter topology to focus on specific hub VNets and their directly connected spokes:

```bash
# Filter by subscription/resource-group/vnet path
cloudnetdraw query --vnets "production-sub/network-rg/hub-vnet" --verbose

# Filter by full Azure resource ID
cloudnetdraw query --vnets "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet"

# Multiple VNets using path syntax
cloudnetdraw query --vnets "prod-sub/network-rg/hub-vnet-east,prod-sub/network-rg/hub-vnet-west"

# Generate diagrams from filtered topology
cloudnetdraw hld
cloudnetdraw mld
```

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
