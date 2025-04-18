# Azure Network Topology Visualization

A Python-based tool for automatically generating visual diagrams of Azure virtual networks using topology data exported from the Azure API. This script creates `.drawio` diagram files representing Hub-and-Spoke network architectures, making it easier to audit, present, and understand complex Azure network infrastructures.

---

## 📌 Key Features

- 🔎 Converts Azure VNet topology (JSON) into visual diagrams
- 📄 Outputs `.drawio` files (open with [draw.io / diagrams.net](https://draw.io))
- 🖼️ Supports hub, spoke, subnets, peerings, and Azure service icons (NSG, UDR, Firewall, etc.)
- 🧠 Logic-based layout:
  - Peered vs non-peered spokes
  - Left/right layout split for better readability
  - Icon placement and subnet expansion
- 🧩 Extendable for MLD, HLD, and custom peerings

---

## 🖼️ Example Output

> 💡 The tool outputs `.drawio` files. You can export them to PNG, JPG, PDF, or SVG using the [Draw.io Desktop CLI](https://github.com/jgraph/drawio-desktop).

<img src="examples/example1.png" alt="Example Azure Topology" width="700"/>

---

## ⚙️ Requirements

- Python 3.8+
- Azure topology JSON export (your own format or adapted from Azure API)
- Recommended: [Draw.io Desktop](https://github.com/jgraph/drawio-desktop/releases) for viewing/exporting diagrams

Install dependencies (if any):

## 🚀 Usage
Either add a token from a service principal or manually run az login before running the script to log in to the correct tenant
Run the azure-query.py to query your current Azure environment

Run the script to generate the .drawio file:

python generate_diagram.py
By default, the script creates:

network_mld.drawio

## 📄 License
This project is licensed under the MIT License.
You are free to use, modify, and distribute it with attribution.

## 🤝 Contributing
Pull requests and suggestions are welcome!
If you have ideas for enhancements (e.g. support for internal peerings, multi-hub views, or layout options), feel free to open an issue or PR.

## 👨‍💻 Author
Kristoffer Hatland
🔗 ([LinkedIn])(https://www.linkedin.com/in/hatland)  • 🐙 ([GitHub])(https://github.com/krhatland) 


