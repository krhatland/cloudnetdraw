from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from azure.core.exceptions import ResourceNotFoundError
from typing import Dict, List, Any, Optional, Union, Tuple
import json
import argparse
import logging
import sys
import os
import re

# Global credentials
_credentials: Optional[Union[ClientSecretCredential, AzureCliCredential]] = None


def get_sp_credentials() -> ClientSecretCredential:
    """Get Service Principal credentials from environment variables"""
    client_id = os.getenv('AZURE_CLIENT_ID')
    client_secret = os.getenv('AZURE_CLIENT_SECRET')
    tenant_id = os.getenv('AZURE_TENANT_ID')

    if not all([client_id, client_secret, tenant_id]):
        logging.error("Service Principal credentials not set. Please set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID.")
        sys.exit(1)

    return ClientSecretCredential(tenant_id, client_id, client_secret)


def initialize_credentials(use_service_principal: bool = False) -> None:
    """Initialize global credentials based on authentication method"""
    global _credentials
    if use_service_principal:
        _credentials = get_sp_credentials()
    else:
        _credentials = AzureCliCredential()


def get_credentials() -> Union[ClientSecretCredential, AzureCliCredential]:
    """Get the global credentials instance"""
    global _credentials
    if _credentials is None:
        raise RuntimeError("Credentials not initialized. Call initialize_credentials() first.")
    return _credentials


def is_subscription_id(subscription_string: str) -> bool:
    """Check if a subscription string is in UUID format (ID) or name format"""
    if subscription_string is None:
        return False
    uuid_pattern = r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    return re.match(uuid_pattern, subscription_string) is not None


def read_subscriptions_from_file(file_path: str) -> List[str]:
    """Read subscriptions from file, one per line"""
    try:
        with open(file_path, 'r') as f:
            subscriptions = [line.strip() for line in f if line.strip()]
        return subscriptions
    except FileNotFoundError:
        logging.error(f"Subscriptions file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading subscriptions file {file_path}: {e}")
        sys.exit(1)


def resolve_subscription_names_to_ids(subscription_names: List[str]) -> List[str]:
    """Resolve subscription names to IDs using the Azure API"""
    subscription_client = SubscriptionClient(get_credentials())
    all_subscriptions = list(subscription_client.subscriptions.list())
    name_to_id = {sub.display_name: sub.subscription_id for sub in all_subscriptions}

    resolved_ids = []
    for name in subscription_names:
        if name in name_to_id:
            resolved_ids.append(name_to_id[name])
        else:
            logging.error(f"Subscription not found: {name}")
            logging.info(f"Available subscriptions: {list(name_to_id.keys())}")
            sys.exit(1)

    return resolved_ids


def get_all_subscription_ids() -> List[str]:
    """Get all subscription IDs from Azure API"""
    subscription_client = SubscriptionClient(get_credentials())
    all_subscriptions = list(subscription_client.subscriptions.list())
    subscription_ids = [sub.subscription_id for sub in all_subscriptions]
    logging.info(f"Found {len(subscription_ids)} subscriptions")
    return subscription_ids


def extract_resource_group(resource_id: str) -> str:
    """Helper function to extract resource group from resource ID"""
    return resource_id.split("/")[4]  # Resource group is at index 4 (5th element)


def parse_vnet_identifier(vnet_identifier: str) -> Tuple[Optional[str], Optional[str], str]:
    """Parse VNet identifier (resource ID or subscription/resource_group/vnet_name) and return (subscription_id, resource_group, vnet_name)"""
    if vnet_identifier.startswith('/'):
        parts = vnet_identifier.split('/')
        if len(parts) >= 9 and parts[1] == 'subscriptions' and parts[3] == 'resourceGroups' and parts[5] == 'providers' and parts[6] == 'Microsoft.Network' and parts[7] == 'virtualNetworks':
            subscription_id = parts[2]
            resource_group = parts[4]
            vnet_name = parts[8]
            return subscription_id, resource_group, vnet_name
        else:
            raise ValueError(f"Invalid VNet resource ID format: {vnet_identifier}")
    elif '/' in vnet_identifier:
        parts = vnet_identifier.split('/')
        if len(parts) == 3:
            subscription_id = parts[0]
            resource_group = parts[1]
            vnet_name = parts[2]
            return subscription_id, resource_group, vnet_name
        elif len(parts) == 2:
            resource_group = parts[0]
            vnet_name = parts[1]
            return None, resource_group, vnet_name
        else:
            raise ValueError(f"Invalid VNet identifier format. Expected 'subscription/resource_group/vnet_name' or full resource ID, got: {vnet_identifier}")
    else:
        return None, None, vnet_identifier


def find_hub_vnet_using_resource_graph(vnet_identifier: str) -> Dict[str, Any]:
    """Find the specified hub VNet using Azure Resource Graph API for efficient search"""
    target_subscription_id, target_resource_group, target_vnet_name = parse_vnet_identifier(vnet_identifier)

    if not target_resource_group:
        logging.error(f"VNet identifier must be in 'subscription/resource_group/vnet_name' format or full resource ID, got: {vnet_identifier}")
        sys.exit(1)

    resource_graph_client = ResourceGraphClient(get_credentials())

    if target_subscription_id:
        query = f"""
        Resources
        | where type =~ 'microsoft.network/virtualnetworks'
        | where name =~ '{target_vnet_name}'
        | where resourceGroup =~ '{target_resource_group}'
        | where subscriptionId =~ '{target_subscription_id}'
        | project name, type, location, resourceGroup, subscriptionId, id, properties
        """
    else:
        query = f"""
        Resources
        | where type =~ 'microsoft.network/virtualnetworks'
        | where name =~ '{target_vnet_name}'
        | where resourceGroup =~ '{target_resource_group}'
        | project name, type, location, resourceGroup, subscriptionId, id, properties
        """

    try:
        logging.info(f"Resource Graph query: {query}")
        logging.info(f"Target values: name='{target_vnet_name}', resourceGroup='{target_resource_group}', subscriptionId='{target_subscription_id}'")

        query_request = QueryRequest(query=query)
        if not target_subscription_id:
            subscription_client = SubscriptionClient(get_credentials())
            all_subscriptions = list(subscription_client.subscriptions.list())
            subscription_ids = [sub.subscription_id for sub in all_subscriptions]
            logging.info(f"Available subscriptions for Resource Graph: {len(subscription_ids)}")
            query_request = QueryRequest(query=query, subscriptions=subscription_ids)

        response = resource_graph_client.resources(query_request)

        debug_query = f"Resources | where type =~ 'microsoft.network/virtualnetworks' | where subscriptionId =~ '{target_subscription_id or 'a4007e29-3c9e-47b5-bdce-0c2a2e57c1c1'}' | project name, resourceGroup, subscriptionId"
        logging.info(f"Debug query: {debug_query}")
        debug_request = QueryRequest(query=debug_query)
        debug_response = resource_graph_client.resources(debug_request)
        logging.info(f"Debug response: {len(debug_response.data) if debug_response.data else 0} VNets found")
        if debug_response.data:
            for vnet in debug_response.data:
                logging.info(f"Debug VNet found: name='{vnet.get('name')}', resourceGroup='{vnet.get('resourceGroup')}', subscriptionId='{vnet.get('subscriptionId')}'")

        if not response.data:
            logging.error(f"No VNets found matching '{vnet_identifier}'. Please verify the VNet identifier format (subscription/resource_group/vnet_name) and ensure the VNet exists.")
            if debug_response.data:
                logging.error("Available VNets in the target subscription/resource group:")
                for vnet in debug_response.data:
                    if vnet.get('resourceGroup') == target_resource_group or not target_resource_group:
                        logging.error(f"  - {vnet.get('name')} (resource group: {vnet.get('resourceGroup')})")
            sys.exit(1)

        if len(response.data) > 1:
            vnet_list = [f"{vnet['resourceGroup']}/{vnet['name']} (subscription: {vnet['subscriptionId']})" for vnet in response.data]
            logging.error(f"Multiple VNets found matching '{vnet_identifier}': {vnet_list}. Please use a more specific identifier to uniquely identify the VNet.")
            sys.exit(1)

        vnet_result = response.data[0]
        subscription_id = vnet_result['subscriptionId']
        resource_group = vnet_result['resourceGroup']
        vnet_name = vnet_result['name']

        logging.info(f"Found VNet '{vnet_name}' in resource group '{resource_group}' in subscription '{subscription_id}'")

        network_client = NetworkManagementClient(get_credentials(), subscription_id)
        subscription_client = SubscriptionClient(get_credentials())

        subscription = subscription_client.subscriptions.get(subscription_id)
        subscription_name = subscription.display_name
        tenant_id = subscription.tenant_id

        vnet = network_client.virtual_networks.get(resource_group, vnet_name)
        subnet_names = [subnet.name for subnet in vnet.subnets]

        resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        azure_console_url = f"https://portal.azure.com/#@{tenant_id}/resource{vnet.id}"

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
            "resource_id": vnet.id,
            "tenant_id": tenant_id,
            "subscription_id": subscription_id,
            "subscription_name": subscription_name,
            "resourcegroup_id": resourcegroup_id,
            "resourcegroup_name": resource_group,
            "azure_console_url": azure_console_url,
            "expressroute": "Yes" if "GatewaySubnet" in subnet_names else "No",
            "vpn_gateway": "Yes" if "GatewaySubnet" in subnet_names else "No",
            "firewall": "Yes" if "AzureFirewallSubnet" in subnet_names else "No",
            "is_explicit_hub": True
        }

        # Get peerings for this VNet - store resource IDs instead of names
        peerings = network_client.virtual_network_peerings.list(resource_group, vnet.name)
        peering_resource_ids = []
        for peering in peerings:
            if peering.remote_virtual_network and peering.remote_virtual_network.id:
                peering_resource_ids.append(peering.remote_virtual_network.id)

        vnet_info["peering_resource_ids"] = peering_resource_ids
        vnet_info["peerings_count"] = len(peering_resource_ids)
        return vnet_info

    except Exception as e:
        logging.error(f"Error searching for VNet using Resource Graph: {e}")
        return None


def find_peered_vnets(peering_resource_ids: List[str]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Find peered VNets using direct API calls with resource IDs from peering objects"""
    if not peering_resource_ids:
        return [], []

    subscription_client = SubscriptionClient(get_credentials())
    peered_vnets = []
    processed_vnets = set()
    accessible_resource_ids = []

    for resource_id in peering_resource_ids:
        try:
            parts = resource_id.split('/')
            if len(parts) < 9 or parts[5] != 'providers' or parts[6] != 'Microsoft.Network' or parts[7] != 'virtualNetworks':
                logging.error(f"Invalid VNet resource ID format: {resource_id}")
                continue

            subscription_id = parts[2]
            resource_group = parts[4]
            vnet_name = parts[8]

            vnet_key = f"{subscription_id}/{resource_group}/{vnet_name}"
            if vnet_key in processed_vnets:
                continue
            processed_vnets.add(vnet_key)

            network_client = NetworkManagementClient(get_credentials(), subscription_id)
            subscription = subscription_client.subscriptions.get(subscription_id)
            subscription_name = subscription.display_name
            tenant_id = subscription.tenant_id

            vnet = network_client.virtual_networks.get(resource_group, vnet_name)
            subnet_names = [subnet.name for subnet in vnet.subnets]

            resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            azure_console_url = f"https://portal.azure.com/#@{tenant_id}/resource{vnet.id}"

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
                "resource_id": vnet.id,
                "tenant_id": tenant_id,
                "subscription_id": subscription_id,
                "subscription_name": subscription_name,
                "resourcegroup_id": resourcegroup_id,
                "resourcegroup_name": resource_group,
                "azure_console_url": azure_console_url,
                "expressroute": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "vpn_gateway": "Yes" if "GatewaySubnet" in subnet_names else "No",
                "firewall": "Yes" if "AzureFirewallSubnet" in subnet_names else "No"
            }

            peerings = network_client.virtual_network_peerings.list(resource_group, vnet.name)
            peering_ids = []
            for peering in peerings:
                if peering.remote_virtual_network and peering.remote_virtual_network.id:
                    peering_ids.append(peering.remote_virtual_network.id)

            vnet_info["peering_resource_ids"] = peering_ids
            vnet_info["peerings_count"] = len(peering_ids)
            peered_vnets.append(vnet_info)
            accessible_resource_ids.append(resource_id)

            logging.info(f"Found peered VNet '{vnet_name}' in resource group '{resource_group}' in subscription '{subscription_name}'")

        except Exception as e:
            if "ResourceNotFound" in str(e):
                logging.warning(f"Skipping deleted VNet: {vnet_name} in resource group '{resource_group}' (resource ID: {resource_id})")
                logging.warning("This is normal when a VNet has been deleted but peering relationships still reference it")
            else:
                error_lines = str(e).split('\n')
                main_error = error_lines[0] if error_lines else str(e)
                if 'Code:' in main_error:
                    main_error = main_error.split('Code:')[0].strip()
                logging.warning(f"Error getting VNet details for resource ID {resource_id}: {main_error}")
            continue

    return peered_vnets, accessible_resource_ids


def get_filtered_vnet_topology(hub_vnet_identifier: str, subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing only the specified hub and its directly peered spokes"""
    hub_vnet = find_hub_vnet_using_resource_graph(hub_vnet_identifier)
    if not hub_vnet:
        logging.error(f"Hub VNet '{hub_vnet_identifier}' not found in any of the specified subscriptions")
        sys.exit(1)

    logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")

    hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
    logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs")

    directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)

    hub_vnet["peering_resource_ids"] = accessible_peering_resource_ids
    hub_vnet["peerings_count"] = len(accessible_peering_resource_ids)

    filtered_vnets = [hub_vnet] + directly_peered_vnets
    logging.info(f"Filtered topology contains {len(filtered_vnets)} VNets: {[v['name'] for v in filtered_vnets]}")
    logging.info(f"Hub VNet has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")

    return {"vnets": filtered_vnets}


def get_filtered_vnets_topology(vnet_identifiers: List[str], subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing multiple specified hubs and their directly peered spokes"""
    all_vnets: Dict[str, Dict[str, Any]] = {}

    for vnet_identifier in vnet_identifiers:
        hub_vnet = find_hub_vnet_using_resource_graph(vnet_identifier)
        if not hub_vnet:
            logging.error(f"Hub VNet '{vnet_identifier}' not found in any of the specified subscriptions")
            sys.exit(1)

        logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")

        resource_id = hub_vnet.get('resource_id')
        if resource_id and resource_id not in all_vnets:
            all_vnets[resource_id] = hub_vnet

        hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
        logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs for {hub_vnet['name']}")

        directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)

        if resource_id in all_vnets:
            all_vnets[resource_id]["peering_resource_ids"] = accessible_peering_resource_ids
            all_vnets[resource_id]["peerings_count"] = len(accessible_peering_resource_ids)

        for peered_vnet in directly_peered_vnets:
            peered_resource_id = peered_vnet.get('resource_id')
            if peered_resource_id and peered_resource_id not in all_vnets:
                all_vnets[peered_resource_id] = peered_vnet

        logging.info(f"Hub VNet {hub_vnet['name']} has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")

    filtered_vnets = list(all_vnets.values())
    logging.info(f"Combined filtered topology contains {len(filtered_vnets)} unique VNets: {[v['name'] for v in filtered_vnets]}")

    return {"vnets": filtered_vnets}

def get_vnet_topology_for_selected_subscriptions(subscription_ids: List[str]) -> Dict[str, Any]:
    """
    Collect all VNets and their details across selected subscriptions.

    Includes detection of Virtual WAN Hubs and:
    - normal peering collection
    - normalization of HV_* hidden vWAN VNet ids to the containing vHub id (so hub gets clean connections)
    - augmentation of vHub connections from the vWAN connection API
    """
    network_data = {"vnets": []}
    vnet_candidates: List[Dict[str, Any]] = []

    subscription_client = SubscriptionClient(get_credentials())

    for subscription_id in subscription_ids:
        logging.info(f"Processing Subscription: {subscription_id}")
        network_client = NetworkManagementClient(get_credentials(), subscription_id)

        try:
            subscription = subscription_client.subscriptions.get(subscription_id)
            subscription_name = subscription.display_name
            tenant_id = subscription.tenant_id
        except Exception as e:
            error_msg = f"Could not access subscription {subscription_id}: {e}"
            logging.error(error_msg)
            sys.exit(1)

        # Detect Virtual WAN Hubs (subscription-wide; not limited to vWAN RG)
        try:
            for hub in network_client.virtual_hubs.list():  # <-- list across the subscription
                has_expressroute = getattr(hub, "express_route_gateway", None) is not None
                has_vpn_gateway = getattr(hub, "vpn_gateway", None) is not None
                has_firewall = getattr(hub, "azure_firewall", None) is not None

                hub_rg = extract_resource_group(hub.id)
                resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{hub_rg}"
                azure_console_url = f"https://portal.azure.com/#@{tenant_id}/resource{hub.id}"

                virtual_hub_info = {
                    "name": hub.name,
                    "address_space": getattr(hub, "address_prefix", None) or (hub.address_prefixes[0] if hasattr(hub, "address_prefixes") else "N/A"),
                    "type": "virtual_hub",
                    "subnets": [],
                    "resource_id": hub.id,
                    "tenant_id": tenant_id,
                    "subscription_id": subscription_id,
                    "subscription_name": subscription_name,
                    "resourcegroup_id": resourcegroup_id,
                    "resourcegroup_name": hub_rg,
                    "azure_console_url": azure_console_url,
                    "expressroute": "Yes" if has_expressroute else "No",
                    "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                    "firewall": "Yes" if has_firewall else "No",
                    "peering_resource_ids": [],
                    "peerings_count": 0,
                    "is_explicit_hub": True
                }
                vnet_candidates.append(virtual_hub_info)
        except Exception as e:
            logging.error(f"Could not list virtual hubs for subscription {subscription_id}: {e}")
            sys.exit(1)

        # Process VNets in this subscription
        try:
            for vnet in network_client.virtual_networks.list_all():
                try:
                    resource_group_name = extract_resource_group(vnet.id)
                    subnet_names = [subnet.name for subnet in vnet.subnets]

                    resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
                    azure_console_url = f"https://portal.azure.com/#@{tenant_id}/resource{vnet.id}"

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
                        "resource_id": vnet.id,
                        "tenant_id": tenant_id,
                        "subscription_id": subscription_id,
                        "subscription_name": subscription_name,
                        "resourcegroup_id": resourcegroup_id,
                        "resourcegroup_name": resource_group_name,
                        "azure_console_url": azure_console_url,
                        "expressroute": "Yes" if "GatewaySubnet" in subnet_names else "No",
                        "vpn_gateway": "Yes" if "GatewaySubnet" in subnet_names else "No",
                        "firewall": "Yes" if "AzureFirewallSubnet" in subnet_names else "No"
                    }

                    # Collect peerings, storing resource IDs; map HV_* hidden vnet ids to the actual vHub id too
                    peering_resource_ids: List[str] = []
                    peerings_iter = network_client.virtual_network_peerings.list(resource_group_name, vnet.name)
                    for peering in peerings_iter:
                        if peering.remote_virtual_network and peering.remote_virtual_network.id:
                            rid = peering.remote_virtual_network.id
                            peering_resource_ids.append(rid)

                    vnet_info["peering_resource_ids"] = peering_resource_ids
                    vnet_info["peerings_count"] = len(peering_resource_ids)
                    vnet_candidates.append(vnet_info)

                except Exception as e:
                    error_msg = f"Could not process VNet {vnet.name} in subscription {subscription_id}: {e}"
                    logging.error(error_msg)
                    sys.exit(1)

        except Exception as e:
            error_msg = f"Could not retrieve VNets for subscription {subscription_id}: {e}"
            logging.error(error_msg)
            sys.exit(1)

        # After VNets appended for this subscription, augment vHub connections
        try:
            _augment_virtual_hub_connections(network_client, subscription_client, vnet_candidates)
        except Exception as e:
            logging.warning(f"Augmenting vHub connections failed in subscription {subscription_id}: {e}")

    # Final pass: make vHub ↔ spoke mirroring consistent cross-subscription
    try:
        _finalize_cross_subscription_vhub_mirroring(vnet_candidates)
    except Exception as e:
        logging.warning(f"Final vHub mirroring pass failed: {e}")

    # Final pass: normalize HV_* hidden vWAN VNet ids to actual vHub ids
    try:
        _normalize_vhub_peerings(vnet_candidates)
    except Exception as e:
        logging.warning(f"Normalization pass failed: {e}")

    network_data["vnets"] = vnet_candidates

    if not vnet_candidates:
        logging.error("No VNets found across all subscriptions. This is a fatal error.")
        logging.info("Individual subscriptions without VNets is normal, but finding zero VNets total is not supported.")
        sys.exit(1)

    return network_data


def list_and_select_subscriptions() -> List[str]:
    subscription_client = SubscriptionClient(get_credentials())
    subscriptions = list(subscription_client.subscriptions.list())
    subscriptions.sort(key=lambda sub: sub.display_name)

    for idx, subscription in enumerate(subscriptions):
        logging.info(f"[{idx}] {subscription.display_name} ({subscription.subscription_id})")

    selected_indices = input("Enter the indices of subscriptions to include (comma-separated): ")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",")]
    return [subscriptions[idx].subscription_id for idx in selected_indices]


def save_to_json(data: Dict[str, Any], filename: str = "network_topology.json") -> None:
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"Network topology saved to {filename}")


def query_command(args: argparse.Namespace) -> None:
    """Execute the query command to collect VNet topology from Azure"""
    file_args = [
        ('--output', args.output),
        ('--subscriptions-file', getattr(args, 'subscriptions_file', None)),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)

    initialize_credentials(args.service_principal)

    exclusive_args = [
        ('--subscriptions', args.subscriptions),
        ('--subscriptions-file', args.subscriptions_file),
        ('--vnets', args.vnets)
    ]

    provided_args = []
    empty_args = []

    for arg_name, arg_value in exclusive_args:
        if arg_value is not None:
            if not arg_value.strip():
                empty_args.append(arg_name)
            elif arg_name == '--vnets':
                vnet_identifiers = [vnet.strip() for vnet in arg_value.split(',') if vnet.strip()]
                if not vnet_identifiers:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            elif arg_name == '--subscriptions':
                subscription_values = [sub.strip() for sub in arg_value.split(',') if sub.strip()]
                if not subscription_values:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            else:
                provided_args.append(arg_name)

    if empty_args:
        logging.error(f"Empty values provided for: {', '.join(empty_args)}")
        logging.error("Empty argument values are not allowed in non-interactive scenarios like GitHub Actions")
        logging.error("Either provide valid values or omit the arguments entirely to use interactive mode")
        sys.exit(1)

    if len(provided_args) > 1:
        logging.error(f"The following arguments are mutually exclusive: {', '.join(provided_args)}")
        logging.error("Please specify only one of: --subscriptions, --subscriptions-file, or --vnets")
        logging.error("Use --help for more information about these options")
        sys.exit(1)

    if args.vnets:
        vnet_identifiers = [vnet.strip() for vnet in args.vnets.split(',') if vnet.strip()]
        if not vnet_identifiers:
            logging.error("No valid VNet identifiers provided after parsing --vnets argument")
            logging.error("Please provide valid VNet identifiers in the format: subscription/resource_group/vnet_name or resource_group/vnet_name")
            sys.exit(1)

        all_subscriptions = set()
        for vnet_identifier in vnet_identifiers:
            try:
                subscription_id, resource_group, vnet_name = parse_vnet_identifier(vnet_identifier)
                if is_subscription_id(subscription_id):
                    all_subscriptions.add(subscription_id)
                else:
                    resolved_subs = resolve_subscription_names_to_ids([subscription_id])
                    all_subscriptions.update(resolved_subs)
            except ValueError as e:
                logging.error(f"Invalid VNet identifier format '{vnet_identifier}': {e}")
                sys.exit(1)

        selected_subscriptions = list(all_subscriptions)
        logging.info(f"Filtering topology for hub VNets: {args.vnets}")
        topology = get_filtered_vnets_topology(vnet_identifiers, selected_subscriptions)
    else:
        if (args.subscriptions and args.subscriptions.strip()) or (args.subscriptions_file and args.subscriptions_file.strip()):
            selected_subscriptions = get_subscriptions_non_interactive(args)
        else:
            logging.info("Listing available subscriptions...")
            selected_subscriptions = list_and_select_subscriptions()

        logging.info("Collecting VNets and topology...")
        topology = get_vnet_topology_for_selected_subscriptions(selected_subscriptions)

    _normalize_vhub_peerings(topology.get("vnets", []))

    output_file = args.output if args.output else "network_topology.json"
    save_to_json(topology, output_file)


def get_subscriptions_non_interactive(args: argparse.Namespace) -> List[str]:
    """Get subscriptions from command line arguments or file in non-interactive mode"""
    if args.subscriptions and args.subscriptions_file:
        logging.error("Cannot specify both --subscriptions and --subscriptions-file")
        sys.exit(1)

    if args.subscriptions and args.subscriptions.strip():
        subscriptions = [sub.strip() for sub in args.subscriptions.split(',') if sub.strip()]
        if not subscriptions:
            logging.error("No valid subscriptions found after parsing --subscriptions argument")
            logging.error("Please provide valid subscription names or IDs, or use 'all' to include all subscriptions")
            sys.exit(1)
    elif args.subscriptions_file and args.subscriptions_file.strip():
        subscriptions = read_subscriptions_from_file(args.subscriptions_file)
    else:
        logging.error("No valid subscription source provided")
        logging.error("This should not happen - argument validation should have caught this")
        sys.exit(1)

    if subscriptions and len(subscriptions) == 1 and subscriptions[0].lower() == "all":
        logging.info("Getting all available subscriptions")
        return get_all_subscription_ids()

    if subscriptions and is_subscription_id(subscriptions[0]):
        logging.info(f"Using subscription IDs: {subscriptions}")
        return subscriptions
    else:
        logging.info(f"Resolving subscription names to IDs: {subscriptions}")
        return resolve_subscription_names_to_ids(subscriptions)


def get_hub_connections_for_spoke(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> List[int]:
    """Find ALL hubs this spoke connects to (for cross-zone edge generation)"""
    spoke_peering_resource_ids = spoke_vnet.get('peering_resource_ids', [])
    connected_hub_indices = []

    for hub_index, hub_vnet in enumerate(hub_vnets):
        hub_resource_id = hub_vnet.get('resource_id')
        if hub_resource_id and hub_resource_id in spoke_peering_resource_ids:
            connected_hub_indices.append(hub_index)

    return connected_hub_indices


def find_first_hub_zone(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> int:
    """Find first hub zone this spoke connects to (simplified logic)"""
    spoke_peering_ids = spoke_vnet.get('peering_resource_ids', [])
    for hub_index, hub in enumerate(hub_vnets):
        if hub.get('resource_id') in spoke_peering_ids:
            return hub_index
    return 0


def determine_hub_for_spoke(spoke_vnet: Dict[str, Any], hub_vnets: List[Dict[str, Any]]) -> Optional[str]:
    """Legacy function for backward compatibility"""
    if not hub_vnets:
        return None
    zone_index = find_first_hub_zone(spoke_vnet, hub_vnets)
    return f"hub_{zone_index}"


def extract_vnet_name_from_resource_id(resource_id: str) -> str:
    """Extract VNet name from Azure resource ID"""
    parts = resource_id.split('/')
    if len(parts) >= 9 and parts[7] == 'virtualNetworks':
        return parts[8]
    raise ValueError(f"Invalid VNet resource ID: {resource_id}")


def generate_hierarchical_id(vnet_data: Dict[str, Any], element_type: str, suffix: Optional[str] = None) -> str:
    """
    Generate consistent hierarchical IDs for DrawIO elements using Azure resource path format.
    """
    subscription_name = vnet_data.get('subscription_name', '').replace('.', '_')
    resourcegroup_name = vnet_data.get('resourcegroup_name', '').replace('.', '_')
    vnet_name = vnet_data.get('name', '').replace('.', '_')

    if not subscription_name or not resourcegroup_name:
        if element_type == 'group':
            return vnet_name
        elif element_type == 'main':
            return f"{vnet_name}_main"
        elif element_type == 'subnet':
            if suffix is not None:
                return f"{vnet_name}_subnet_{suffix}"
            else:
                return f"{vnet_name}_subnet"
        elif element_type == 'icon':
            if suffix is not None:
                return f"{vnet_name}_icon_{suffix}"
            else:
                return f"{vnet_name}_icon"
        else:
            if suffix is not None:
                return f"{vnet_name}_{element_type}_{suffix}"
            else:
                return f"{vnet_name}_{element_type}"

    base_id = f"{subscription_name}.{resourcegroup_name}.{vnet_name}"

    if element_type == 'group':
        return base_id
    elif element_type == 'main':
        return f"{base_id}.main"
    elif element_type == 'subnet':
        if suffix is not None:
            return f"{base_id}.subnet.{suffix}"
        else:
            return f"{base_id}.subnet"
    elif element_type == 'icon':
        if suffix is not None:
            return f"{base_id}.icon.{suffix}"
        else:
            return f"{base_id}.icon"
    else:
        if suffix is not None:
            return f"{base_id}.{element_type}.{suffix}"
        else:
            return f"{base_id}.{element_type}"


def create_vnet_id_mapping(vnets: List[Dict[str, Any]], zones: List[Dict[str, Any]], all_non_peered: List[Dict[str, Any]]) -> Dict[str, str]:
    """Create bidirectional mapping between VNet resource IDs and diagram IDs for multi-zone layout"""
    mapping: Dict[str, str] = {}

    has_azure_metadata = False
    if zones and zones[0].get('hub'):
        hub_data = zones[0]['hub']
        has_azure_metadata = bool(hub_data.get('subscription_name') and hub_data.get('resourcegroup_name'))

    if has_azure_metadata:
        for zone in zones:
            if 'resource_id' in zone['hub']:
                main_id = generate_hierarchical_id(zone['hub'], 'main')
                mapping[zone['hub']['resource_id']] = main_id

        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']
            for spoke in peered_spokes:
                if 'resource_id' in spoke:
                    main_id = generate_hierarchical_id(spoke, 'main')
                    mapping[spoke['resource_id']] = main_id

        for nonpeered in all_non_peered:
            if 'resource_id' in nonpeered:
                main_id = generate_hierarchical_id(nonpeered, 'main')
                mapping[nonpeered['resource_id']] = main_id
    else:
        for zone in zones:
            hub_key = zone['hub'].get('resource_id') or zone['hub'].get('name')
            if hub_key:
                mapping[hub_key] = f"hub_{zone['hub_index']}"

        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']

            use_dual_column = len(peered_spokes) > 6
            if use_dual_column:
                total_spokes = len(peered_spokes)
                half_spokes = (total_spokes + 1) // 2
                left_spokes = peered_spokes[:half_spokes]
                right_spokes = peered_spokes[half_spokes:]
            else:
                left_spokes = []
                right_spokes = peered_spokes

            for i, spoke in enumerate(right_spokes):
                spoke_key = spoke.get('resource_id') or spoke.get('name')
                if spoke_key:
                    mapping[spoke_key] = f"right_spoke{zone_index}_{i}"

            for i, spoke in enumerate(left_spokes):
                spoke_key = spoke.get('resource_id') or spoke.get('name')
                if spoke_key:
                    mapping[spoke_key] = f"left_spoke{zone_index}_{i}"

        for i, nonpeered in enumerate(all_non_peered):
            nonpeered_key = nonpeered.get('resource_id') or nonpeered.get('name')
            if nonpeered_key:
                mapping[nonpeered_key] = f"nonpeered_spoke{i}"

    return mapping


def _load_and_validate_topology(topology_file: str) -> List[Dict[str, Any]]:
    """Extract common file loading and validation logic"""
    with open(topology_file, 'r') as file:
        topology = json.load(file)

    logging.info("Loaded topology data from JSON")
    vnets = topology.get("vnets", [])

    if not vnets:
        logging.error("No VNets found in topology file. Cannot generate diagram.")
        sys.exit(1)

    return vnets


def _classify_and_sort_vnets(vnets: List[Dict[str, Any]], config: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract common VNet classification and sorting logic"""
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= config.hub_threshold or vnet.get("is_explicit_hub", False)]

    if not hub_vnets and vnets:
        resource_id_to_vnet = {vnet.get('resource_id'): vnet for vnet in vnets if vnet.get('resource_id')}
        potential_hubs = []

        sorted_vnets = sorted(vnets, key=lambda x: x.get('peerings_count', 0), reverse=True)
        max_peerings = sorted_vnets[0].get('peerings_count', 0) if sorted_vnets else 0

        min_hub_peerings = max(max_peerings * 0.6, 4)
        hub_candidates = [vnet for vnet in sorted_vnets[:5] if vnet.get('peerings_count', 0) >= min_hub_peerings]

        hub_relationship_detected = False
        for candidate in hub_candidates:
            candidate_resource_id = candidate.get('resource_id')
            candidate_peerings = candidate.get('peering_resource_ids', [])

            mutual_hub_peers = []
            for peering_id in candidate_peerings:
                if peering_id in resource_id_to_vnet:
                    peer_vnet = resource_id_to_vnet[peering_id]
                    if (peer_vnet in hub_candidates and peer_vnet != candidate and
                            candidate_resource_id in peer_vnet.get('peering_resource_ids', [])):
                        mutual_hub_peers.append(peer_vnet.get('name'))

            if mutual_hub_peers:
                potential_hubs.append(candidate)
                hub_relationship_detected = True
                logging.info(f"Detected hub via mutual peer relationships: {candidate.get('name')} ({candidate.get('peerings_count')} peerings) ↔ {mutual_hub_peers}")

        if hub_relationship_detected:
            for candidate in hub_candidates:
                if candidate not in potential_hubs and candidate.get('peerings_count', 0) >= max_peerings * 0.7:
                    potential_hubs.append(candidate)
                    logging.info(f"Detected standalone hub via high connectivity: {candidate.get('name')} ({candidate.get('peerings_count')} peerings)")

        if not potential_hubs and len(hub_candidates) == 1:
            sole_candidate = hub_candidates[0]
            if sole_candidate.get('peerings_count', 0) >= 3:
                potential_hubs.append(sole_candidate)
                logging.info(f"Detected single hub via sole candidacy: {sole_candidate.get('name')} ({sole_candidate.get('peerings_count')} peerings)")

        if potential_hubs:
            hub_vnets = potential_hubs
            logging.info(f"Using relationship-based hub detection: {[v.get('name') for v in hub_vnets]}")
        else:
            hub_vnets = [vnets[0]]
            logging.info(f"Using first VNet as fallback hub: {hub_vnets[0].get('name')}")

    hub_vnets.sort(key=lambda x: x.get('name', ''))
    spoke_vnets = [vnet for vnet in vnets if vnet not in hub_vnets]

    logging.info(f"Found {len(hub_vnets)} hub VNet(s) and {len(spoke_vnets)} spoke VNet(s)")

    return hub_vnets, spoke_vnets


def _setup_xml_structure(config: Any) -> Tuple[Any, Any]:
    """Extract common XML document structure setup"""
    from lxml import etree

    mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
    diagram = etree.SubElement(mxfile, "diagram", name="Hub and Spoke Topology")
    mxGraphModel = etree.SubElement(
        diagram,
        "mxGraphModel",
        attrib=config.get_canvas_attributes(),
    )
    root = etree.SubElement(mxGraphModel, "root")

    etree.SubElement(root, "mxCell", id="0")
    etree.SubElement(root, "mxCell", id="1", parent="0")

    return mxfile, root


def _classify_spoke_vnets(vnets: List[Dict[str, Any]], hub_vnets: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract common spoke VNet classification logic"""
    spoke_vnets_classified = []
    unpeered_vnets = []

    for vnet in vnets:
        if vnet in hub_vnets:
            continue
        elif vnet.get("peering_resource_ids"):
            spoke_vnets_classified.append(vnet)
        else:
            unpeered_vnets.append(vnet)

    return spoke_vnets_classified, unpeered_vnets


def _create_layout_zones(hub_vnets: List[Dict[str, Any]], spoke_vnets_classified: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Extract common zone assignment logic"""
    zone_spokes = [[] for _ in hub_vnets]
    for spoke in spoke_vnets_classified:
        zone_index = find_first_hub_zone(spoke, hub_vnets)
        zone_spokes[zone_index].append(spoke)

    return zone_spokes


def _add_vnet_with_optional_subnets(vnet_data, x_offset, y_offset, root, config,
                                    show_subnets: bool = False, style_override=None):
    """
    Universal VNet rendering function that handles both modes:
    - HLD mode: show_subnets=False (VNets only)
    - MLD mode: show_subnets=True (VNets + subnets)
    """
    from lxml import etree

    if show_subnets:
        num_subnets = len(vnet_data.get("subnets", []))
        vnet_height = config.layout['hub']['height'] if vnet_data.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
        group_width = config.layout['hub']['width']
        group_height = vnet_height + config.drawio['group']['extra_height']
    else:
        vnet_height = 50
        group_width = config.vnet_width
        group_height = vnet_height + config.group_height_extra

    group_id = generate_hierarchical_id(vnet_data, 'group')

    group_attrs = {
        "id": group_id,
        "label": "",
        "subscription_name": vnet_data.get('subscription_name', ''),
        "subscription_id": vnet_data.get('subscription_id', ''),
        "tenant_id": vnet_data.get('tenant_id', ''),
        "resourcegroup_id": vnet_data.get('resourcegroup_id', ''),
        "resourcegroup_name": vnet_data.get('resourcegroup_name', ''),
        "resource_id": vnet_data.get('resource_id', ''),
        "azure_console_url": vnet_data.get('azure_console_url', ''),
        "link": vnet_data.get('azure_console_url', '')
    }

    group_element = etree.SubElement(root, "object", attrib=group_attrs)

    group_cell = etree.SubElement(
        group_element,
        "mxCell",
        style="group",
        vertex="1",
        connectable="0" if not show_subnets else config.drawio['group']['connectable'],
        parent="1"
    )
    etree.SubElement(
        group_cell,
        "mxGeometry",
        attrib={"x": str(x_offset), "y": str(y_offset), "width": str(group_width), "height": str(group_height), "as": "geometry"},
    )

    default_style = config.get_vnet_style_string('hub') if show_subnets else "shape=rectangle;rounded=0;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB;align=left"

    main_id = generate_hierarchical_id(vnet_data, 'main')

    vnet_attrs = {
        "id": main_id,
        "label": f"Subscription: {vnet_data.get('subscription_name', 'N/A')}\n{vnet_data.get('name', 'VNet')}\n{vnet_data.get('address_space', 'N/A')}",
        "subscription_name": vnet_data.get('subscription_name', ''),
        "subscription_id": vnet_data.get('subscription_id', ''),
        "tenant_id": vnet_data.get('tenant_id', ''),
        "resourcegroup_id": vnet_data.get('resourcegroup_id', ''),
        "resourcegroup_name": vnet_data.get('resourcegroup_name', ''),
        "resource_id": vnet_data.get('resource_id', ''),
        "azure_console_url": vnet_data.get('azure_console_url', ''),
        "link": vnet_data.get('azure_console_url', '')
    }

    vnet_element = etree.SubElement(root, "object", attrib=vnet_attrs)

    vnet_cell = etree.SubElement(
        vnet_element,
        "mxCell",
        style=style_override or default_style,
        vertex="1",
        parent=group_id,
    )

    vnet_box_width = group_width if show_subnets else 400
    etree.SubElement(
        vnet_cell,
        "mxGeometry",
        attrib={"x": "0", "y": "0", "width": str(vnet_box_width), "height": str(vnet_height), "as": "geometry"},
    )

    if vnet_data.get("type") == "virtual_hub":
        if show_subnets:
            hub_icon_width, hub_icon_height = config.get_icon_size('virtual_hub')
            virtualhub_icon_id = generate_hierarchical_id(vnet_data, 'icon', 'virtualhub')
            virtual_hub_icon = etree.SubElement(
                root,
                "mxCell",
                id=virtualhub_icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('virtual_hub')};",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                virtual_hub_icon,
                "mxGeometry",
                attrib={
                    "x": str(config.icon_positioning['virtual_hub_icon']['offset_x']),
                    "y": str(vnet_height + config.icon_positioning['virtual_hub_icon']['offset_y']),
                    "width": str(hub_icon_width),
                    "height": str(hub_icon_height),
                    "as": "geometry"
                },
            )
        else:
            virtualhub_icon_id = generate_hierarchical_id(vnet_data, 'icon', 'virtualhub')
            virtual_hub_icon = etree.SubElement(
                root,
                "mxCell",
                id=virtualhub_icon_id,
                style="shape=image;html=1;image=img/lib/azure2/networking/Virtual_WANs.svg;",
                vertex="1",
                parent=group_id,
            )
            etree.SubElement(
                virtual_hub_icon,
                "mxGeometry",
                attrib={"x": "-10", "y": str(vnet_height - 15), "width": "20", "height": "20", "as": "geometry"},
            )

    vnet_width = group_width if show_subnets else config.vnet_width
    y_off = config.icon_positioning['vnet_icons']['y_offset']
    right_margin = config.icon_positioning['vnet_icons']['right_margin']
    icon_gap = config.icon_positioning['vnet_icons']['icon_gap']

    vnet_icons_to_render = []

    vnet_icon_width, vnet_icon_height = config.get_icon_size('vnet')
    vnet_icons_to_render.append({
        'type': 'vnet',
        'width': vnet_icon_width,
        'height': vnet_icon_height
    })

    if vnet_data.get("expressroute", "").lower() == "yes":
        express_width, express_height = config.get_icon_size('expressroute')
        vnet_icons_to_render.append({
            'type': 'expressroute',
            'width': express_width,
            'height': express_height
        })

    if vnet_data.get("firewall", "").lower() == "yes":
        firewall_width, firewall_height = config.get_icon_size('firewall')
        vnet_icons_to_render.append({
            'type': 'firewall',
            'width': firewall_width,
            'height': firewall_height
        })

    if vnet_data.get("vpn_gateway", "").lower() == "yes":
        vpn_width, vpn_height = config.get_icon_size('vpn_gateway')
        vnet_icons_to_render.append({
            'type': 'vpn_gateway',
            'width': vpn_width,
            'height': vpn_height
        })

    current_x = vnet_width - right_margin
    for icon in vnet_icons_to_render:
        current_x -= icon['width']
        icon['x'] = current_x

        if icon['type'] == 'vnet':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'vnet')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('vnet')};",
                vertex="1",
                parent=main_id,
            )
        elif icon['type'] == 'expressroute':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'expressroute')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('expressroute')};",
                vertex="1",
                parent=main_id,
            )
        elif icon['type'] == 'firewall':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'firewall')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('firewall')};",
                vertex="1",
                parent=main_id,
            )
        elif icon['type'] == 'vpn_gateway':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'vpn')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('vpn_gateway')};",
                vertex="1",
                parent=main_id,
            )

        etree.SubElement(
            icon_element,
            "mxGeometry",
            attrib={
                "x": str(icon['x']),
                "y": str(y_off),
                "width": str(icon['width']),
                "height": str(icon['height']),
                "as": "geometry"
            },
        )

        current_x -= icon_gap

    if show_subnets and vnet_data.get("type") != "virtual_hub":
        for subnet_index, subnet in enumerate(vnet_data.get("subnets", [])):
            subnet_id = generate_hierarchical_id(vnet_data, 'subnet', str(subnet_index))
            subnet_cell = etree.SubElement(
                root,
                "mxCell",
                id=subnet_id,
                style=config.get_subnet_style_string(),
                vertex="1",
                parent=main_id,
            )
            subnet_cell.set("value", f"{subnet['name']} {subnet['address']}")
            y_offset_subnet = config.layout['subnet']['padding_y'] + subnet_index * config.layout['subnet']['spacing_y']
            etree.SubElement(subnet_cell, "mxGeometry", attrib={
                "x": str(config.layout['subnet']['padding_x']),
                "y": str(y_offset_subnet),
                "width": str(config.layout['subnet']['width']),
                "height": str(config.layout['subnet']['height']),
                "as": "geometry"
            })

            subnet_right_edge = config.layout['subnet']['padding_x'] + config.layout['subnet']['width']
            s_icon_gap = config.icon_positioning['subnet_icons']['icon_gap']

            icons_to_render = []
            subnet_width, subnet_height = config.get_icon_size('subnet')
            icons_to_render.append({
                'type': 'subnet',
                'width': subnet_width,
                'height': subnet_height,
                'y_offset': config.icon_positioning['subnet_icons']['subnet_icon_y_offset']
            })

            if subnet.get("udr", "").lower() == "yes":
                udr_width, udr_height = config.get_icon_size('route_table')
                icons_to_render.append({
                    'type': 'udr',
                    'width': udr_width,
                    'height': udr_height,
                    'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                })

            if subnet.get("nsg", "").lower() == "yes":
                nsg_width, nsg_height = config.get_icon_size('nsg')
                icons_to_render.append({
                    'type': 'nsg',
                    'width': nsg_width,
                    'height': nsg_height,
                    'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                })

            current_x = subnet_right_edge
            for icon in icons_to_render:
                current_x -= icon['width']
                icon['x'] = current_x

                icon_y = y_offset_subnet + icon['y_offset']

                if icon['type'] == 'subnet':
                    subnet_icon_id = generate_hierarchical_id(vnet_data, 'icon', f'subnet_{subnet_index}')
                    icon_element = etree.SubElement(
                        root,
                        "mxCell",
                        id=subnet_icon_id,
                        style=f"shape=image;html=1;image={config.get_icon_path('subnet')};",
                        vertex="1",
                        parent=main_id,
                    )
                elif icon['type'] == 'udr':
                    udr_icon_id = generate_hierarchical_id(vnet_data, 'icon', f'udr_{subnet_index}')
                    icon_element = etree.SubElement(
                        root,
                        "mxCell",
                        id=udr_icon_id,
                        style=f"shape=image;html=1;image={config.get_icon_path('route_table')};",
                        vertex="1",
                        parent=main_id,
                    )
                elif icon['type'] == 'nsg':
                    nsg_icon_id = generate_hierarchical_id(vnet_data, 'icon', f'nsg_{subnet_index}')
                    icon_element = etree.SubElement(
                        root,
                        "mxCell",
                        id=nsg_icon_id,
                        style=f"shape=image;html=1;image={config.get_icon_path('nsg')};",
                        vertex="1",
                        parent=main_id,
                    )

                etree.SubElement(
                    icon_element,
                    "mxGeometry",
                    attrib={
                        "x": str(icon['x']),
                        "y": str(icon_y),
                        "width": str(icon['width']),
                        "height": str(icon['height']),
                        "as": "geometry"
                    },
                )

                current_x -= s_icon_gap

    return group_height


def generate_diagram(filename: str, topology_file: str, config: Any, render_mode: str = 'hld') -> None:
    """Unified diagram generation function that handles both HLD and MLD modes"""
    from lxml import etree

    if render_mode not in ['hld', 'mld']:
        raise ValueError(f"Invalid render_mode '{render_mode}'. Must be 'hld' or 'mld'.")

    show_subnets = render_mode == 'mld'

    vnets = _load_and_validate_topology(topology_file)
    hub_vnets, spoke_vnets = _classify_and_sort_vnets(vnets, config)
    mxfile, root = _setup_xml_structure(config)

    spoke_vnets_classified, unpeered_vnets = _classify_spoke_vnets(vnets, hub_vnets)
    zone_spokes = _create_layout_zones(hub_vnets, spoke_vnets_classified)

    canvas_padding = config.canvas_padding
    zone_width = 920 - canvas_padding + config.vnet_width
    zone_spacing = config.zone_spacing

    spacing = 20 if show_subnets else 100

    base_left_x = canvas_padding
    base_hub_x = canvas_padding + config.vnet_spacing_x
    base_right_x = canvas_padding + config.vnet_spacing_x + config.vnet_width + 50
    hub_y = canvas_padding

    zone_bottoms = []

    for zone_index, hub_vnet in enumerate(hub_vnets):
        zone_offset_x = zone_index * (zone_width + zone_spacing)

        hub_x = base_hub_x + zone_offset_x
        hub_main_id = generate_hierarchical_id(hub_vnet, 'main')
        hub_actual_height = _add_vnet_with_optional_subnets(hub_vnet, hub_x, hub_y, root, config, show_subnets=show_subnets)

        spokes = zone_spokes[zone_index]

        if len(spokes) > 6:
            total_spokes = len(spokes)
            half_spokes = (total_spokes + 1) // 2
            left_spokes = spokes[:half_spokes]
            right_spokes = spokes[half_spokes:]
        else:
            left_spokes = []
            right_spokes = spokes

        if show_subnets:
            num_subnets = len(hub_vnet.get("subnets", []))
            hub_vnet_height = config.layout['hub']['height'] if hub_vnet.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
            current_y_right = hub_y + hub_vnet_height
            current_y_left = hub_y + hub_vnet_height
        else:
            hub_height = 50
            current_y_right = hub_y + hub_height
            current_y_left = hub_y + hub_height

        for index, spoke in enumerate(right_spokes):
            y_position = current_y_right if show_subnets else hub_y + 50 + index * spacing
            x_position = base_right_x + zone_offset_x
            spoke_main_id = generate_hierarchical_id(spoke, 'main')

            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = _add_vnet_with_optional_subnets(spoke, x_position, y_position, root, config, show_subnets=show_subnets, style_override=spoke_style)

            hub_resource_id = hub_vnet.get('resource_id')
            spoke_peering_ids = spoke.get('peering_resource_ids', [])

            if hub_resource_id in spoke_peering_ids:
                edge_id = f"edge_right_{zone_index}_{index}_{spoke['name']}"
                edge = etree.SubElement(
                    root, "mxCell", id=edge_id, edge="1",
                    source=hub_main_id, target=spoke_main_id,
                    style=config.get_hub_spoke_edge_style(),
                    parent="1"
                )
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})

                if y_position != hub_y:
                    hub_center_x = base_hub_x + 200 + zone_offset_x
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x + 100), "y": str(y_position + 25)})

            if show_subnets:
                current_y_right += vnet_height + spacing

        for index, spoke in enumerate(left_spokes):
            y_position = current_y_left if show_subnets else hub_y + 50 + index * spacing
            x_position = base_left_x + zone_offset_x
            spoke_main_id = generate_hierarchical_id(spoke, 'main')

            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = _add_vnet_with_optional_subnets(spoke, x_position, y_position, root, config, show_subnets=show_subnets, style_override=spoke_style)

            hub_resource_id = hub_vnet.get('resource_id')
            spoke_peering_ids = spoke.get('peering_resource_ids', [])

            if hub_resource_id in spoke_peering_ids:
                edge_id = f"edge_left_{zone_index}_{index}_{spoke['name']}"
                edge = etree.SubElement(
                    root, "mxCell", id=edge_id, edge="1",
                    source=hub_main_id, target=spoke_main_id,
                    style=config.get_hub_spoke_edge_style(),
                    parent="1"
                )
                edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                edge_points = etree.SubElement(edge_geometry, "Array", attrib={"as": "points"})

                if y_position != hub_y:
                    hub_center_x = base_hub_x + 200 + zone_offset_x
                    etree.SubElement(edge_points, "mxPoint", attrib={"x": str(hub_center_x - 100), "y": str(y_position + 25)})

            if show_subnets:
                current_y_left += vnet_height + spacing

        if show_subnets:
            zone_bottom = hub_y + hub_vnet_height
            if left_spokes or right_spokes:
                zone_bottom = max(current_y_left, current_y_right) + 60
            else:
                zone_bottom = hub_y + hub_vnet_height + 60
        else:
            zone_bottom = hub_y + 50
            if left_spokes or right_spokes:
                left_count = len(left_spokes)
                right_count = len(right_spokes)
                if left_count > 0:
                    zone_bottom = max(zone_bottom, hub_y + 50 + left_count * spacing + 50)
                if right_count > 0:
                    zone_bottom = max(zone_bottom, hub_y + 50 + right_count * spacing + 50)
            else:
                zone_bottom = hub_y + 50 + 50

        zone_bottoms.append(zone_bottom)

    if unpeered_vnets:
        overall_bottom_y = max(zone_bottoms) if zone_bottoms else hub_y + 50
        unpeered_y = overall_bottom_y + (60 if show_subnets else 100)

        total_zones_width = len(hub_vnets) * zone_width + (len(hub_vnets) - 1) * zone_spacing
        unpeered_spacing = config.vnet_width + 50
        vnets_per_row = max(1, int(total_zones_width // unpeered_spacing))
        row_height = 120 if show_subnets else 70

        for index, spoke in enumerate(unpeered_vnets):
            row_number = index // vnets_per_row
            position_in_row = index % vnets_per_row

            x_position = base_left_x + (position_in_row * unpeered_spacing)
            y_position = unpeered_y + (row_number * row_height)
            spoke_main_id = generate_hierarchical_id(spoke, 'main')

            nonpeered_style = config.get_vnet_style_string('non_peered')
            _add_vnet_with_optional_subnets(spoke, x_position, y_position, root, config, show_subnets=show_subnets, style_override=nonpeered_style)

    zones = []
    for hub_index, hub_vnet in enumerate(hub_vnets):
        zones.append({
            'hub': hub_vnet,
            'hub_index': hub_index,
            'spokes': zone_spokes[hub_index],
            'non_peered': unpeered_vnets if hub_index == 0 else []
        })

    vnet_mapping = create_vnet_id_mapping(vnets, zones, unpeered_vnets)

    vnets_with_edges = hub_vnets + spoke_vnets_classified
    add_peering_edges(vnets_with_edges, vnet_mapping, root, config, hub_vnets=hub_vnets)

    add_cross_zone_connectivity_edges(zones, hub_vnets, vnet_mapping, root, config)

    logging.info(f"Added full mesh peering connections for {len(vnets)} VNets")

    tree = etree.ElementTree(mxfile)
    with open(filename, "wb") as f:
        tree.write(f, encoding="utf-8", xml_declaration=True, pretty_print=True)
    logging.info(f"Draw.io diagram generated and saved to {filename}")


def generate_hld_diagram(filename: str, topology_file: str, config: Any) -> None:
    """Generate high-level diagram (VNets only) from topology JSON"""
    generate_diagram(filename, topology_file, config, render_mode='hld')


def add_cross_zone_connectivity_edges(zones: List[Dict[str, Any]], hub_vnets: List[Dict[str, Any]],
                                      vnet_mapping: Dict[str, str], root: Any, config: Any) -> None:
    """Add cross-zone connectivity edges for spokes that connect to multiple hubs"""
    from lxml import etree

    edge_counter = 3000

    logging.info("Adding cross-zone connectivity edges for multi-hub spokes...")

    for zone in zones:
        zone_hub_index = zone['hub_index']
        zone_hub_resource_id = zone['hub'].get('resource_id')

        for spoke in zone['spokes']:
            spoke_name = spoke.get('name')
            spoke_resource_id = spoke.get('resource_id')
            if not spoke_name or not spoke_resource_id:
                continue

            connected_hub_indices = get_hub_connections_for_spoke(spoke, hub_vnets)

            for hub_index in connected_hub_indices:
                target_hub = hub_vnets[hub_index]
                target_hub_resource_id = target_hub.get('resource_id')

                if hub_index == zone_hub_index or target_hub_resource_id == zone_hub_resource_id:
                    continue

                target_hub_name = target_hub.get('name')
                spoke_id = vnet_mapping.get(spoke_resource_id)
                target_hub_id = vnet_mapping.get(target_hub_resource_id)

                if spoke_id and target_hub_id:
                    edge = etree.SubElement(
                        root,
                        "mxCell",
                        id=f"cross_zone_edge_{edge_counter}",
                        edge="1",
                        source=spoke_id,
                        target=target_hub_id,
                        style=config.get_cross_zone_edge_style(),
                        parent="1",
                    )

                    etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})

                    edge_counter += 1
                    logging.info(f"Added cross-zone edge: {spoke_name} → {target_hub_name} (zone {zone_hub_index} → zone {hub_index})")


def add_peering_edges(vnets, vnet_mapping, root, config, hub_vnets=None):
    """Add edges for all VNet peerings using resource IDs with proper symmetry validation
       Draws spoke-to-spoke and hub-to-hub (not hub-to-spoke which is already drawn)."""
    from lxml import etree

    edge_counter = 1000
    processed_peerings = set()

    resource_id_to_name = {vnet['resource_id']: vnet['name'] for vnet in vnets if 'resource_id' in vnet}
    vnet_name_to_resource_id = {vnet['name']: vnet['resource_id'] for vnet in vnets if 'name' in vnet and 'resource_id' in vnet}

    if hub_vnets is None:
        hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= config.hub_threshold or vnet.get("is_explicit_hub", False)]

        if not hub_vnets and vnets:
            resource_id_to_vnet = {vnet.get('resource_id'): vnet for vnet in vnets if vnet.get('resource_id')}
            potential_hubs = []

            sorted_vnets = sorted(vnets, key=lambda x: x.get('peerings_count', 0), reverse=True)
            max_peerings = sorted_vnets[0].get('peerings_count', 0) if sorted_vnets else 0

            min_hub_peerings = max(max_peerings * 0.6, 4)
            hub_candidates = [vnet for vnet in sorted_vnets[:5] if vnet.get('peerings_count', 0) >= min_hub_peerings]

            hub_relationship_detected = False
            for candidate in hub_candidates:
                candidate_resource_id = candidate.get('resource_id')
                candidate_peerings = candidate.get('peering_resource_ids', [])

                mutual_hub_peers = []
                for peering_id in candidate_peerings:
                    if peering_id in resource_id_to_vnet:
                        peer_vnet = resource_id_to_vnet[peering_id]
                        if (peer_vnet in hub_candidates and peer_vnet != candidate and
                                candidate_resource_id in peer_vnet.get('peering_resource_ids', [])):
                            mutual_hub_peers.append(peer_vnet.get('name'))

                if mutual_hub_peers:
                    potential_hubs.append(candidate)
                    hub_relationship_detected = True

            if hub_relationship_detected:
                for candidate in hub_candidates:
                    if candidate not in potential_hubs and candidate.get('peerings_count', 0) >= max_peerings * 0.7:
                        potential_hubs.append(candidate)

            if not potential_hubs and len(hub_candidates) == 1:
                sole_candidate = hub_candidates[0]
                if sole_candidate.get('peerings_count', 0) >= 3:
                    potential_hubs.append(sole_candidate)

            if potential_hubs:
                hub_vnets = potential_hubs
            else:
                hub_vnets = [vnets[0]]

    hub_resource_ids = set(hub['resource_id'] for hub in hub_vnets if 'resource_id' in hub)

    for vnet in vnets:
        if 'resource_id' not in vnet:
            continue

        source_resource_id = vnet['resource_id']
        source_vnet_name = vnet['name']
        source_id = vnet_mapping.get(source_resource_id)

        if not source_id:
            continue

        for peering_resource_id in vnet.get('peering_resource_ids', []):
            target_vnet_name = resource_id_to_name.get(peering_resource_id)

            if not target_vnet_name or target_vnet_name == source_vnet_name:
                continue

            target_id = vnet_mapping.get(peering_resource_id)
            if not target_id:
                continue

            source_is_hub = source_resource_id in hub_resource_ids
            target_is_hub = peering_resource_id in hub_resource_ids

            if (source_is_hub and not target_is_hub) or (not source_is_hub and target_is_hub):
                # Skip hub-to-spoke; drawn elsewhere
                continue

            peering_key = tuple(sorted([source_vnet_name, target_vnet_name]))
            if peering_key in processed_peerings:
                continue

            src_res_id = vnet_name_to_resource_id.get(source_vnet_name)
            target_vnet = next((v for v in vnets if v.get('name') == target_vnet_name), None)
            if target_vnet and src_res_id:
                target_peering_resource_ids = target_vnet.get('peering_resource_ids', [])
                if src_res_id not in target_peering_resource_ids:
                    logging.debug(f"Asymmetric peering detected: {source_vnet_name} peers to {target_vnet_name}, but reverse not found (Azure asymmetry is OK).")

            processed_peerings.add(peering_key)

            edge_type = "hub-to-hub" if source_is_hub and target_is_hub else "spoke-to-spoke"
            edge = etree.SubElement(
                root,
                "mxCell",
                id=f"peering_edge_{edge_counter}",
                edge="1",
                source=source_id,
                target=target_id,
                style=config.get_edge_style_string(),
                parent="1",
            )
            etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            edge_counter += 1
            logging.info(f"Added {edge_type} peering edge: {source_vnet_name} ({source_id}) ↔ {target_vnet_name} ({target_id})")


def _augment_virtual_hub_connections(network_client, subscription_client, vnet_candidates: List[Dict[str, Any]]) -> None:
    """
    For each virtual hub in vnet_candidates, list its VNet connections and
    mirror them as 'peering_resource_ids' on both the hub and the connected VNets.
    """
    by_id = {v["resource_id"]: v for v in vnet_candidates if "resource_id" in v}
    virtual_hubs = [v for v in vnet_candidates if v.get("type") == "virtual_hub"]

    for vhub in virtual_hubs:
        try:
            vhub_id = vhub["resource_id"]
            vhub_rg = extract_resource_group(vhub_id)
            vhub_name = vhub["name"]

            try:
                connections = list(network_client.virtual_hub_vnet_connections.list(vhub_rg, vhub_name))
            except AttributeError:
                connections = list(network_client.virtual_hubs.list_vnet_connections(vhub_rg, vhub_name))

            for conn in connections:
                remote_vnet_id = None
                if getattr(conn, "remote_virtual_network", None) and getattr(conn.remote_virtual_network, "id", None):
                    remote_vnet_id = conn.remote_virtual_network.id
                elif getattr(conn, "properties", None):
                    rvn = getattr(conn.properties, "remote_virtual_network", None)
                    if rvn and getattr(rvn, "id", None):
                        remote_vnet_id = rvn.id

                if not remote_vnet_id:
                    continue

                vhub.setdefault("peering_resource_ids", []).append(remote_vnet_id)

                if remote_vnet_id in by_id:
                    by_id[remote_vnet_id].setdefault("peering_resource_ids", []).append(vhub_id)

            vhub["peerings_count"] = len(vhub.get("peering_resource_ids", []))

        except Exception as e:
            logging.warning(f"Could not augment connections for vHub {vhub.get('name')}: {e}")

# Hidden HV VNet path (case-insensitive)
_HV_VNET_RE = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/(?P<rg>RG_[^/]+)/providers/Microsoft\.Network/virtualNetworks/HV_[^/]+$",
    re.IGNORECASE,
)

# Real virtualHub id
_VHUB_ID_RE = re.compile(
    r"^/subscriptions/[^/]+/resourceGroups/[^/]+/providers/Microsoft\.Network/virtualHubs/(?P<name>[^/]+)$",
    re.IGNORECASE,
)
def _vhub_name_from_hidden_rg(rg_name: str) -> Optional[str]:
    """
    'RG_p-virtualwan-norwayeast-vhub_88fdc9ad-...' -> 'p-virtualwan-norwayeast-vhub'
    Keep robust for weird tails.
    """
    if not rg_name:
        return None
    base = rg_name[3:] if rg_name.upper().startswith("RG_") else rg_name
    # Drop a *final* underscore tail if it looks like a GUID-ish blob
    parts = base.rsplit("_", 1)
    if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F-]{6,}", parts[1] or ""):
        base = parts[0]
    base = base.strip()
    return base or None


def _normalize_vhub_peerings(vnets: List[Dict[str, Any]]) -> None:
    """
    In-place:
    - Rewrite HV_* peers to the real virtualHub resource_id
    - Mirror spoke -> hub on the hub object
    - Dedup + recount on both sides
    """
    if not vnets:
        return

    # Lookups
    vhub_by_name_lc: Dict[str, Dict[str, Any]] = {}
    vhub_by_id: Dict[str, Dict[str, Any]] = {}
    by_id: Dict[str, Dict[str, Any]] = {}

    for v in vnets:
        rid = v.get("resource_id")
        if isinstance(rid, str) and rid:
            by_id[rid] = v
        if (v.get("type") or "").lower() == "virtual_hub":
            name = (v.get("name") or "").strip()
            if name:
                vhub_by_name_lc[name.lower()] = v
            if rid:
                vhub_by_id[rid] = v
            # Ensure the list exists for mirroring
            v.setdefault("peering_resource_ids", [])

    if not vhub_by_name_lc and not vhub_by_id:
        logging.debug("normalize_vhub_peerings: no virtual_hub entries found; nothing to map.")
        # Still normalize counts for consistency
        for v in vnets:
            peers = v.get("peering_resource_ids")
            v["peering_resource_ids"] = list(dict.fromkeys(p for p in peers or [] if isinstance(p, str)))
            v["peerings_count"] = len(v["peering_resource_ids"])
        return

    rewrites = 0
    mirrors_from_hv = 0
    mirrors_from_direct = 0

    # First pass: rewrite HV_* -> vHub id, and opportunistically mirror
    for v in vnets:
        if (v.get("type") or "").lower() == "virtual_hub":
            continue

        spoke_id = v.get("resource_id")
        peers_in = v.get("peering_resource_ids")
        peers: List[str] = (
            [p for p in peers_in if isinstance(p, str) and p]
            if isinstance(peers_in, list) else []
        )
        if not peers:
            v["peering_resource_ids"] = []
            v["peerings_count"] = 0
            continue

        new_peers: List[str] = []
        for pid in peers:
            # Direct vHub id → keep and mirror by ID (most reliable)
            if _VHUB_ID_RE.match(pid):
                new_peers.append(pid)
                hub = vhub_by_id.get(pid)
                if hub and isinstance(spoke_id, str) and spoke_id:
                    hub_list = hub.setdefault("peering_resource_ids", [])
                    if spoke_id not in hub_list:
                        hub_list.append(spoke_id)
                        mirrors_from_direct += 1
                continue

            # Hidden HV_* → resolve by hub *name* from RG, rewrite to real vHub id and mirror
            m_hv = _HV_VNET_RE.match(pid)
            if m_hv:
                rg_name = m_hv.group("rg")
                inferred = _vhub_name_from_hidden_rg(rg_name or "")
                hub: Optional[Dict[str, Any]] = None
                if inferred:
                    # Use the name only (case-insensitive), regardless of subscription_id
                    for key, hub_obj in vhub_by_name_lc.items():
                        if key == inferred.lower():
                            hub = hub_obj
                            break

                if hub and hub.get("resource_id"):
                    vhub_id = hub["resource_id"]
                    new_peers.append(vhub_id)
                    rewrites += 1
                    if isinstance(spoke_id, str) and spoke_id:
                        hub_list = hub.setdefault("peering_resource_ids", [])
                        if spoke_id not in hub_list:
                            hub_list.append(spoke_id)
                            mirrors_from_hv += 1
                else:
                    # Keep unresolved HV_* so we don't lose info
                    new_peers.append(pid)
                continue

            # Regular VNet/VNet
            new_peers.append(pid)

        # Dedup preserve order
        seen = set()
        deduped = []
        for x in new_peers:
            if x and x not in seen:
                seen.add(x)
                deduped.append(x)
        v["peering_resource_ids"] = deduped
        v["peerings_count"] = len(deduped)

    # Second pass (belt & suspenders):
    # After all rewrites, mirror any remaining *direct* vHub ids we now see.
    for v in vnets:
        if (v.get("type") or "").lower() == "virtual_hub":
            continue
        spoke_id = v.get("resource_id")
        for pid in v.get("peering_resource_ids") or []:
            if not isinstance(pid, str):
                continue
            if _VHUB_ID_RE.match(pid):
                hub = vhub_by_id.get(pid)
                if hub and isinstance(spoke_id, str) and spoke_id:
                    hub_list = hub.setdefault("peering_resource_ids", [])
                    if spoke_id not in hub_list:
                        hub_list.append(spoke_id)
                        mirrors_from_direct += 1

    # Final normalize: dedup & recount everywhere (including hubs)
    for v in vnets:
        peers = v.get("peering_resource_ids")
        if isinstance(peers, list):
            v["peering_resource_ids"] = list(dict.fromkeys(p for p in peers if isinstance(p, str) and p))
            v["peerings_count"] = len(v["peering_resource_ids"])
        else:
            v["peering_resource_ids"] = []
            v["peerings_count"] = 0

    logging.info(
        "normalize_vhub_peerings: rewrote %d HV_* → vHub ids; mirrored %d (HV) + %d (direct vHub) spokes on hubs.",
        rewrites, mirrors_from_hv, mirrors_from_direct
    )


def hld_command(args: argparse.Namespace) -> None:
    """Execute the HLD command to generate high-level diagrams"""
    from config import Config

    file_args = [
        ('--output', args.output),
        ('--topology', args.topology),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)

    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_hld.drawio"
    config_file = args.config_file

    config = Config(config_file)

    logging.info("Starting HLD diagram generation...")
    generate_hld_diagram(output_file, topology_file, config)
    logging.info("HLD diagram generation complete.")
    logging.info(f"HLD diagram saved to {output_file}")


def generate_mld_diagram(filename: str, topology_file: str, config: Any) -> None:
    """Generate mid-level diagram (VNets + subnets) from topology JSON"""
    generate_diagram(filename, topology_file, config, render_mode='mld')


def _finalize_cross_subscription_vhub_mirroring(vnet_candidates: List[Dict[str, Any]]) -> None:
    by_id = {v["resource_id"]: v for v in vnet_candidates if "resource_id" in v}
    vhubs = [v for v in vnet_candidates if v.get("type") == "virtual_hub"]
    for vhub in vhubs:
        vhub_id = vhub.get("resource_id")
        for remote_id in vhub.get("peering_resource_ids", []):
            spoke = by_id.get(remote_id)
            if not spoke:
                continue
            spoke.setdefault("peering_resource_ids", [])
            if vhub_id not in spoke["peering_resource_ids"]:
                spoke["peering_resource_ids"].append(vhub_id)
    for v in vnet_candidates:
        if "peering_resource_ids" in v:
            v["peering_resource_ids"] = list(dict.fromkeys(v["peering_resource_ids"]))
            v["peerings_count"] = len(v["peering_resource_ids"])


def mld_command(args: argparse.Namespace) -> None:
    """Execute the MLD command to generate mid-level diagrams"""
    from config import Config

    file_args = [
        ('--output', args.output),
        ('--topology', args.topology),
        ('--config-file', getattr(args, 'config_file', None))
    ]
    empty_file_args = [arg_name for arg_name, arg_value in file_args if arg_value is not None and not arg_value.strip()]
    if empty_file_args:
        logging.error(f"Empty file path provided for: {', '.join(empty_file_args)}")
        logging.error("File arguments cannot be empty strings in non-interactive scenarios")
        logging.error("Either provide valid file paths or omit the arguments to use defaults")
        sys.exit(1)

    topology_file = args.topology if args.topology else "network_topology.json"
    output_file = args.output if args.output else "network_mld.drawio"
    config_file = args.config_file

    config = Config(config_file)

    logging.info("Starting MLD diagram generation...")
    generate_mld_diagram(output_file, topology_file, config)
    logging.info("MLD diagram generation complete.")
    logging.info(f"MLD diagram saved to {output_file}")


class CustomHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """Custom formatter to prevent help text from wrapping to multiple lines"""
    def __init__(self, prog: str) -> None:
        super().__init__(prog, max_help_position=70, width=180)


def main() -> None:
    """Main CLI entry point with subcommand dispatch"""
    parser = argparse.ArgumentParser(
        description="CloudNet Draw - Azure VNet topology visualization tool",
        formatter_class=CustomHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command')
    subparsers.required = True

    # Query command
    query_parser = subparsers.add_parser('query', help='Query Azure and collect VNet topology',
                                         formatter_class=CustomHelpFormatter)
    query_parser.add_argument('-o', '--output', default='network_topology.json',
                              help='Output JSON file (default: network_topology.json)')
    query_parser.add_argument('-p', '--service-principal', action='store_true',
                              help='Use Service Principal authentication')
    query_parser.add_argument('-s', '--subscriptions',
                              help='Comma separated list of subscriptions (names or IDs), or "all" to include all subscriptions')
    query_parser.add_argument('-f', '--subscriptions-file',
                              help='File containing subscriptions (one per line)')
    query_parser.add_argument('-c', '--config-file', default='config.yaml',
                              help='Configuration file (default: config.yaml)')
    query_parser.add_argument('-n', '--vnets',
                              help='Specify hub VNets as comma-separated resource_ids (starting with /) or paths (subscription/resource_group/vnet_name) to filter topology')
    query_parser.add_argument('-v', '--verbose', action='store_true',
                              help='Enable verbose logging')
    query_parser.set_defaults(func=query_command)

    # HLD command
    hld_parser = subparsers.add_parser('hld', help='Generate high-level diagram (VNets only)',
                                       formatter_class=CustomHelpFormatter)
    hld_parser.add_argument('-o', '--output', default='network_hld.drawio',
                            help='Output diagram file (default: network_hld.drawio)')
    hld_parser.add_argument('-t', '--topology', default='network_topology.json',
                            help='Input topology JSON file (default: network_topology.json)')
    hld_parser.add_argument('-c', '--config-file', default='config.yaml',
                            help='Configuration file (default: config.yaml)')
    hld_parser.add_argument('-v', '--verbose', action='store_true',
                            help='Enable verbose logging')
    hld_parser.set_defaults(func=hld_command)

    # MLD command
    mld_parser = subparsers.add_parser('mld', help='Generate mid-level diagram (VNets + subnets)',
                                       formatter_class=CustomHelpFormatter)
    mld_parser.add_argument('-o', '--output', default='network_mld.drawio',
                            help='Output diagram file (default: network_mld.drawio)')
    mld_parser.add_argument('-t', '--topology', default='network_topology.json',
                            help='Input topology JSON file (default: network_topology.json)')
    mld_parser.add_argument('-c', '--config-file', default='config.yaml',
                            help='Configuration file (default: config.yaml)')
    mld_parser.add_argument('-v', '--verbose', action='store_true',
                            help='Enable verbose logging')
    mld_parser.set_defaults(func=mld_command)

    args = parser.parse_args()

    log_level = logging.INFO if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format='%(asctime)s - %(levelname)s - %(message)s')

    try:
        args.func(args)
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
