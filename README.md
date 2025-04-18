# Azure Network Topology Visualization

A Python-based tool to automatically visualize Azure virtual network topology using data from the Azure API. Generates multiple network diagrams from a single JSON export, supporting both high-level (HLD) and mid-level (MLD) views.

## 🚀 Features

- 🔍 Queries Azure for virtual network, subnet, and peering information
- 🧭 Automatically generates:
  - High-Level Diagram (HLD)
  - Mid-Level Diagram (MLD)
  - HLD + Internal Spoke Peerings
  - MLD + Internal Spoke Peerings
- 🎨 Visual layout with consistent spoke distribution and un-peered network handling
- 📁 Outputs diagrams in SVG/PNG format (or customizable)

## 📸 Example Output

*(Add screenshots or diagrams here once you have some)*

## 🛠️ Requirements

- Python 3.8+
- Azure CLI (for authentication)
- Required Python packages:
  ```bash
  pip install -r requirements.txt
