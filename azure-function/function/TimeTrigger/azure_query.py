# azure_query.py

import os
import logging
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient

def extract_resource_group(resource_id):
    return resource_id.split("/")[4]

def get_vnet_topology():
    logging.info("Starting Azure query using Managed Identity authentication...")
    credential = DefaultAzureCredential()
    subscription_client = SubscriptionClient(credential)
    subscriptions = subscription_client.subscriptions.list()

    network_data = {"hub": {}, "spokes": []}
    vnet_candidates = []

    for subscription in subscriptions:
        subscription_id = subscription.subscription_id
        subscription_name = subscription.display_name
        logging.info(f"Processing Subscription: {subscription_name} ({subscription_id})")

        network_client = NetworkManagementClient(credential, subscription_id)

        # Detect Virtual WAN Hub
        try:
            for vwan in network_client.virtual_wans.list():
                hubs = network_client.virtual_hubs.list_by_resource_group(extract_resource_group(vwan.id))
                for hub in hubs:
                    has_expressroute = getattr(hub, "express_route_gateway", None) is not None
                    has_vpn_gateway = getattr(hub, "vpn_gateway", None) is not None
                    has_firewall = getattr(hub, "azure_firewall", None) is not None

                    network_data["hub"] = {
                        "name": hub.name,
                        "address_space": hub.address_prefix,
                        "type": "virtual_hub",
                        "subscription_name": subscription_name,
                        "expressroute": "Yes" if has_expressroute else "No",
                        "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                        "firewall": "Yes" if has_firewall else "No"
                    }
                    break  # Use the first hub found
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
                        "address": subnet.address_prefixes[0] if subnet.address_prefixes else (subnet.address_prefix or "N/A"),
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

    if not network_data["hub"] and not vnet_candidates:
        # No VNets or hub found — inject synthetic hub with N/A info
        network_data["hub"] = {
            "name": "No VNet Found",
            "address_space": "0.0.0.0/0",
            "type": "virtual_hub",
            "subscription_name": "N/A",
            "expressroute": "No",
            "vpn_gateway": "No",
            "firewall": "No"
        }

    logging.info("Azure query completed successfully.")
    return network_data
