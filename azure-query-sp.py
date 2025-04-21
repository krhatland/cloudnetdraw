from azure.identity import ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient
import json
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_sp_credentials():
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')

    if not all([client_id, client_secret, tenant_id]):
        logging.error("Service Principal credentials not set. Please set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID.")
        exit(1)

    return ClientSecretCredential(tenant_id, client_id, client_secret)

def extract_resource_group(resource_id):
    return resource_id.split("/")[4]

def get_vnet_topology(credentials):
    subscription_client = SubscriptionClient(credentials)
    subscriptions = subscription_client.subscriptions.list()

    network_data = {"hub": {}, "spokes": []}
    vnet_candidates = []

    for subscription in subscriptions:
        subscription_id = subscription.subscription_id
        subscription_name = subscription.display_name
        logging.info(f"Processing Subscription: {subscription_name} ({subscription_id})")

        network_client = NetworkManagementClient(credentials, subscription_id)

        # Detect Virtual WAN Hub
        try:
            for vwan in network_client.virtual_wans.list():
                hubs = network_client.virtual_hubs.list_by_resource_group(extract_resource_group(vwan.id))
                for hub in hubs:
                    has_expressroute = hasattr(hub, "express_route_gateway") and hub.express_route_gateway is not None
                    has_vpn_gateway = hasattr(hub, "vpn_gateway") and hub.vpn_gateway is not None
                    has_firewall = hasattr(hub, "azure_firewall") and hub.azure_firewall is not None

                    network_data["hub"] = {
                        "name": hub.name,
                        "address_space": hub.address_prefix,
                        "type": "virtual_hub",
                        "subscription_name": subscription_name,
                        "expressroute": "Yes" if has_expressroute else "No",
                        "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                        "firewall": "Yes" if has_firewall else "No"
                    }
                    break
        except Exception as e:
            logging.warning(f"Error processing vWAN hubs in subscription {subscription_id}: {e}")

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
                        "address": subnet.address_prefixes[0] if subnet.address_prefixes else subnet.address_prefix or "N/A",
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
                vnet_info["peerings"].append(peering.remote_virtual_network.id.split("/")[-1])

            vnet_info["peerings_count"] = len(vnet_info["peerings"])
            vnet_candidates.append(vnet_info)

    if not network_data["hub"] and vnet_candidates:
        vnet_candidates.sort(key=lambda x: x["peerings_count"], reverse=True)
        network_data["hub"] = vnet_candidates.pop(0)

    network_data["spokes"] = vnet_candidates
    return network_data

def save_to_json(data, filename="network_topology.json"):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"Network topology saved to {filename}")

if __name__ == "__main__":
    logging.info("Starting Azure query using Service Principal authentication...")
    credentials = get_sp_credentials()
    topology = get_vnet_topology(credentials)
    save_to_json(topology)
    logging.info("Azure query completed successfully.")
