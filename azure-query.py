from azure.identity import AzureCliCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient
import json

# Azure authentication using CLI credentials
credential = AzureCliCredential()

# Initialize Subscription client to get all subscriptions
subscription_client = SubscriptionClient(credential)

# Helper function to extract resource group from resource ID
def extract_resource_group(resource_id):
    return resource_id.split("/")[4]  # Resource group is always the 5th item

# Collect all VNets and their details across selected subscriptions
def get_vnet_topology_for_selected_subscriptions(subscription_ids):
    network_data = {"hubs": [], "spokes": [], "peerings": []}
    vnet_candidates = []

    for subscription_id in subscription_ids:
        print(f"Processing Subscription: {subscription_id}")
        network_client = NetworkManagementClient(credential, subscription_id)

        # Get subscription name
        subscription = subscription_client.subscriptions.get(subscription_id)
        subscription_name = subscription.display_name

        # Detect Virtual WAN Hub if it exists
        try:
            for vwan in network_client.virtual_wans.list():
                try:
                    # Correctly retrieve virtual hubs associated with the Virtual WAN
                    hubs = network_client.virtual_hubs.list_by_resource_group(extract_resource_group(vwan.id))
                    for hub in hubs:
                        # Detect ExpressRoute or VPN based on hub properties (fallback to flags if needed)
                        has_expressroute = hasattr(hub, "express_route_gateway") and hub.express_route_gateway is not None
                        has_vpn_gateway = hasattr(hub, "vpn_gateway") and hub.vpn_gateway is not None
                        has_firewall = hasattr(hub, "azure_firewall") and hub.azure_firewall is not None

                        network_data["hubs"].append({
                            "name": hub.name,
                            "address_space": hub.address_prefix,
                            "type": "virtual_hub",
                            "subscription_name": subscription_name,
                            "expressroute": "Yes" if has_expressroute else "No",
                            "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                            "firewall": "Yes" if has_firewall else "No"
                        })
                except Exception as e:
                    print(f"Warning: Could not retrieve virtual hub details for {vwan.name} in subscription {subscription_id}. Error: {e}")
        except Exception as e:
            print(f"Warning: Could not list virtual WANs for subscription {subscription_id}. Error: {e}")

        # Process VNets
        for vnet in network_client.virtual_networks.list_all():
            resource_group_name = extract_resource_group(vnet.id)
            subnet_names = [subnet.name for subnet in vnet.subnets]

            vnet_info = {
                "name": vnet.name,
                "address_space": vnet.address_space.address_prefixes[0],
                "subnets": [
                    {
                        "name": subnet.name,
                        "address": (
                            subnet.address_prefixes[0]
                            if hasattr(subnet, "address_prefixes") and subnet.address_prefixes
                            else subnet.address_prefix or "N/A"
                        ),
                        "nsg": 'Yes' if subnet.network_security_group else 'No',
                        "udr": 'Yes' if subnet.route_table else 'No'
                    }
                    for subnet in vnet.subnets
                ],
                "peerings": [],
                "subscription_name": subscription_name,
                "expressroute": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "vpn_gateway": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "firewall": "Yes" if "AzureFirewallSubnet" in subnet_names else "No"
            }

            peerings = network_client.virtual_network_peerings.list(resource_group_name, vnet.name)
            for peering in peerings:
                vnet_info["peerings"].append(peering.name)

            vnet_info["peerings_count"] = len(vnet_info["peerings"])
            vnet_candidates.append(vnet_info)
        
        # Now let's get the peerings
        for peering in network_client.virtual_network_peerings.list():
            network_data["peerings"].append({
                "name": peering.name,
                "remote_virtual_network": peering.remote_virtual_network.id,
                "remote_address_space": peering.remote_address_space.address_prefixes[0] if peering.remote_address_space.address_prefixes else "N/A",
            })

    # If no virtual hub found, select the VNet with the most peerings
    if len(network_data["hubs"])==0 and vnet_candidates:
        vnet_candidates.sort(key=lambda x: x["peerings_count"], reverse=True)
        network_data["hubs"].append(vnet_candidates.pop(0))

    network_data["spokes"] = vnet_candidates
    return network_data

# List all subscriptions and allow user to select
def list_and_select_subscriptions():
    subscriptions = list(subscription_client.subscriptions.list())
    for idx, subscription in enumerate(subscriptions):
        print(f"[{idx}] {subscription.display_name} ({subscription.subscription_id})")

    selected_indices = input("Enter the indices of subscriptions to include (comma-separated): ")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",")]
    return [subscriptions[idx].subscription_id for idx in selected_indices]

# Save the data to a JSON file
def save_to_json(data, filename="network_topology.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Network topology saved to {filename}")

# Main execution
if __name__ == "__main__":
    print("Listing available subscriptions...")
    selected_subscriptions = list_and_select_subscriptions()
    print("Collecting VNets and topology...")
    topology = get_vnet_topology_for_selected_subscriptions(selected_subscriptions)
    save_to_json(topology)