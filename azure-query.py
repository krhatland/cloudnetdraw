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
    # Azure subscription ID pattern: 8-4-4-4-12 hexadecimal digits
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
    
    # Create name-to-ID mapping
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

# Helper function to extract resource group from resource ID
def extract_resource_group(resource_id: str) -> str:
    return resource_id.split("/")[4]  # Resource group is at index 4 (5th element)

def parse_vnet_identifier(vnet_identifier: str) -> Tuple[Optional[str], Optional[str], str]:
    """Parse VNet identifier (resource ID or subscription/resource_group/vnet_name) and return (subscription_id, resource_group, vnet_name)"""
    if vnet_identifier.startswith('/'):
        # Resource ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}
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
            # Format: subscription/resource_group/vnet_name
            subscription_id = parts[0]
            resource_group = parts[1]
            vnet_name = parts[2]
            return subscription_id, resource_group, vnet_name
        elif len(parts) == 2:
            # Format: resource_group/vnet_name
            resource_group = parts[0]
            vnet_name = parts[1]
            return None, resource_group, vnet_name
        else:
            raise ValueError(f"Invalid VNet identifier format. Expected 'subscription/resource_group/vnet_name' or full resource ID, got: {vnet_identifier}")
    else:
        # Simple VNet name or empty string
        return None, None, vnet_identifier

def find_hub_vnet_using_resource_graph(vnet_identifier: str) -> Dict[str, Any]:
    """Find the specified hub VNet using Azure Resource Graph API for efficient search"""
    target_subscription_id, target_resource_group, target_vnet_name = parse_vnet_identifier(vnet_identifier)
    
    # Must have resource group - either from subscription/resource_group/vnet_name format or from resource ID
    if not target_resource_group:
        logging.error(f"VNet identifier must be in 'subscription/resource_group/vnet_name' format or full resource ID, got: {vnet_identifier}")
        sys.exit(1)
    
    # Create Resource Graph client
    resource_graph_client = ResourceGraphClient(get_credentials())
    
    # Query by resource group and VNet name
    # If we have subscription ID from resource ID or path format, we can add it as additional filter
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
        # Execute the query
        logging.info(f"Resource Graph query: {query}")
        logging.info(f"Target values: name='{target_vnet_name}', resourceGroup='{target_resource_group}', subscriptionId='{target_subscription_id}'")
        
        query_request = QueryRequest(query=query)
        # Try to add subscription scopes for better access
        if not target_subscription_id:
            subscription_client = SubscriptionClient(get_credentials())
            all_subscriptions = list(subscription_client.subscriptions.list())
            subscription_ids = [sub.subscription_id for sub in all_subscriptions]
            logging.info(f"Available subscriptions for Resource Graph: {len(subscription_ids)}")
            query_request = QueryRequest(query=query, subscriptions=subscription_ids)
        
        response = resource_graph_client.resources(query_request)
        
        # Debug: Let's also try a simpler query to see if we can find ANY VNets
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
        
        # Exactly one result found
        vnet_result = response.data[0]
        subscription_id = vnet_result['subscriptionId']
        resource_group = vnet_result['resourceGroup']
        vnet_name = vnet_result['name']
        
        logging.info(f"Found VNet '{vnet_name}' in resource group '{resource_group}' in subscription '{subscription_id}'")
        
        # Now get detailed information using the Network Management Client
        network_client = NetworkManagementClient(get_credentials(), subscription_id)
        subscription_client = SubscriptionClient(get_credentials())
        
        # Get subscription name and tenant info
        subscription = subscription_client.subscriptions.get(subscription_id)
        subscription_name = subscription.display_name
        tenant_id = subscription.tenant_id
        
        # Get VNet details
        vnet = network_client.virtual_networks.get(resource_group, vnet_name)
        subnet_names = [subnet.name for subnet in vnet.subnets]
        
        # Construct resourcegroup_id from resource_id
        resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
        
        # Construct Azure console hyperlink
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
    """Find peered VNets using direct API calls with resource IDs from peering objects
    
    Returns:
        Tuple of (peered_vnets_list, accessible_resource_ids_list)
    """
    if not peering_resource_ids:
        return [], []
    
    subscription_client = SubscriptionClient(get_credentials())
    peered_vnets = []
    processed_vnets = set()  # Track processed VNets to avoid duplicates
    accessible_resource_ids = []  # Track successfully resolved resource IDs
    
    for resource_id in peering_resource_ids:
        try:
            # Parse resource ID: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}
            parts = resource_id.split('/')
            if len(parts) < 9 or parts[5] != 'providers' or parts[6] != 'Microsoft.Network' or parts[7] != 'virtualNetworks':
                logging.error(f"Invalid VNet resource ID format: {resource_id}")
                continue
                
            subscription_id = parts[2]
            resource_group = parts[4]
            vnet_name = parts[8]
            
            # Create unique key to avoid duplicates
            vnet_key = f"{subscription_id}/{resource_group}/{vnet_name}"
            if vnet_key in processed_vnets:
                continue
            processed_vnets.add(vnet_key)
            
            # Get detailed information using the Network Management Client
            network_client = NetworkManagementClient(get_credentials(), subscription_id)
            
            # Get subscription name and tenant info
            subscription = subscription_client.subscriptions.get(subscription_id)
            subscription_name = subscription.display_name
            tenant_id = subscription.tenant_id
            
            # Get VNet details
            vnet = network_client.virtual_networks.get(resource_group, vnet_name)
            subnet_names = [subnet.name for subnet in vnet.subnets]
            
            # Construct resourcegroup_id from resource_id
            resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}"
            
            # Construct Azure console hyperlink
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
            
            # Get peerings for this VNet - store resource IDs instead of names
            peerings = network_client.virtual_network_peerings.list(resource_group, vnet.name)
            peering_resource_ids = []
            for peering in peerings:
                if peering.remote_virtual_network and peering.remote_virtual_network.id:
                    peering_resource_ids.append(peering.remote_virtual_network.id)
            
            vnet_info["peering_resource_ids"] = peering_resource_ids
            vnet_info["peerings_count"] = len(peering_resource_ids)
            peered_vnets.append(vnet_info)
            accessible_resource_ids.append(resource_id)  # Track this successful resolution
            
            logging.info(f"Found peered VNet '{vnet_name}' in resource group '{resource_group}' in subscription '{subscription_name}'")
        
        except Exception as e:
            # Check if this is a ResourceNotFound error (common when VNet was deleted but peering still exists)
            if "ResourceNotFound" in str(e):
                logging.warning(f"Skipping deleted VNet: {vnet_name} in resource group '{resource_group}' (resource ID: {resource_id})")
                logging.warning("This is normal when a VNet has been deleted but peering relationships still reference it")
            else:
                # Clean up exception message - only show the main error without Azure SDK details
                error_lines = str(e).split('\n')
                main_error = error_lines[0] if error_lines else str(e)
                # Remove Code: and Message: parts that Azure SDK adds
                if 'Code:' in main_error:
                    main_error = main_error.split('Code:')[0].strip()
                logging.warning(f"Error getting VNet details for resource ID {resource_id}: {main_error}")
            continue
    
    return peered_vnets, accessible_resource_ids

def get_filtered_vnet_topology(hub_vnet_identifier: str, subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing only the specified hub and its directly peered spokes"""
    
    # Find the hub VNet
    hub_vnet = find_hub_vnet_using_resource_graph(hub_vnet_identifier)
    if not hub_vnet:
        logging.error(f"Hub VNet '{hub_vnet_identifier}' not found in any of the specified subscriptions")
        sys.exit(1)
    
    logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")
    
    # Get peering resource IDs from the hub VNet
    hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
    
    logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs")
    
    # Use direct API calls to get peered VNets efficiently using exact resource IDs
    directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)
    
    # Update hub VNet to only include accessible peering resource IDs
    hub_vnet["peering_resource_ids"] = accessible_peering_resource_ids
    hub_vnet["peerings_count"] = len(accessible_peering_resource_ids)
    
    # Return filtered topology
    filtered_vnets = [hub_vnet] + directly_peered_vnets
    logging.info(f"Filtered topology contains {len(filtered_vnets)} VNets: {[v['name'] for v in filtered_vnets]}")
    logging.info(f"Hub VNet has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")
    
    return {"vnets": filtered_vnets}

def get_filtered_vnets_topology(vnet_identifiers: List[str], subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect filtered topology containing multiple specified hubs and their directly peered spokes"""
    
    all_vnets = {}  # Use dict to avoid duplicates by resource_id
    
    for vnet_identifier in vnet_identifiers:
        # Find the hub VNet
        hub_vnet = find_hub_vnet_using_resource_graph(vnet_identifier)
        if not hub_vnet:
            logging.error(f"Hub VNet '{vnet_identifier}' not found in any of the specified subscriptions")
            sys.exit(1)
        
        logging.info(f"Found hub VNet: {hub_vnet['name']} in subscription {hub_vnet['subscription_name']}")
        
        # Add hub VNet to collection using resource_id as key to avoid duplicates
        resource_id = hub_vnet.get('resource_id')
        if resource_id and resource_id not in all_vnets:
            all_vnets[resource_id] = hub_vnet
        
        # Get peering resource IDs from the hub VNet
        hub_peering_resource_ids = hub_vnet.get('peering_resource_ids', [])
        
        logging.info(f"Looking for {len(hub_peering_resource_ids)} directly peered VNets using resource IDs for {hub_vnet['name']}")
        
        # Use direct API calls to get peered VNets efficiently using exact resource IDs
        directly_peered_vnets, accessible_peering_resource_ids = find_peered_vnets(hub_peering_resource_ids)
        
        # Update hub VNet to only include accessible peering resource IDs
        if resource_id in all_vnets:
            all_vnets[resource_id]["peering_resource_ids"] = accessible_peering_resource_ids
            all_vnets[resource_id]["peerings_count"] = len(accessible_peering_resource_ids)
        
        # Add peered VNets to collection using resource_id as key to avoid duplicates
        for peered_vnet in directly_peered_vnets:
            peered_resource_id = peered_vnet.get('resource_id')
            if peered_resource_id and peered_resource_id not in all_vnets:
                all_vnets[peered_resource_id] = peered_vnet
        
        logging.info(f"Hub VNet {hub_vnet['name']} has {len(accessible_peering_resource_ids)} accessible peerings out of {len(hub_peering_resource_ids)} total peering relationships")
    
    # Convert dict back to list
    filtered_vnets = list(all_vnets.values())
    logging.info(f"Combined filtered topology contains {len(filtered_vnets)} unique VNets: {[v['name'] for v in filtered_vnets]}")
    
    return {"vnets": filtered_vnets}

# Collect all VNets and their details across selected subscriptions
def get_vnet_topology_for_selected_subscriptions(subscription_ids: List[str]) -> Dict[str, Any]:
    network_data = {"vnets": []}
    vnet_candidates = []
    
    subscription_client = SubscriptionClient(get_credentials())

    for subscription_id in subscription_ids:
        logging.info(f"Processing Subscription: {subscription_id}")
        network_client = NetworkManagementClient(get_credentials(), subscription_id)

        # Get subscription name and tenant info
        try:
            subscription = subscription_client.subscriptions.get(subscription_id)
            subscription_name = subscription.display_name
            tenant_id = subscription.tenant_id
            
        except Exception as e:
            error_msg = f"Could not access subscription {subscription_id}: {e}"
            logging.error(error_msg)
            sys.exit(1)

        # Detect Virtual WAN Hub if it exists - add to vnets array
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

                        # Extract resource group from hub resource ID
                        hub_resource_group = extract_resource_group(hub.id)
                        
                        # Construct resourcegroup_id from resource_id
                        resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{hub_resource_group}"
                        
                        # Construct Azure console hyperlink
                        azure_console_url = f"https://portal.azure.com/#@{tenant_id}/resource{hub.id}"
                        
                        virtual_hub_info = {
                            "name": hub.name,
                            "address_space": hub.address_prefix,
                            "type": "virtual_hub",
                            "subnets": [],  # Virtual hubs don't have traditional subnets
                              # Will be populated if needed
                            "resource_id": hub.id,
                            "tenant_id": tenant_id,
                            "subscription_id": subscription_id,
                            "subscription_name": subscription_name,
                            "resourcegroup_id": resourcegroup_id,
                            "resourcegroup_name": hub_resource_group,
                            "azure_console_url": azure_console_url,
                            "expressroute": "Yes" if has_expressroute else "No",
                            "vpn_gateway": "Yes" if has_vpn_gateway else "No",
                            "firewall": "Yes" if has_firewall else "No",
                            "peering_resource_ids": [],  # Virtual hubs use different connectivity model
                            "peerings_count": 0  # Virtual hubs use different connectivity model
                        }
                        vnet_candidates.append(virtual_hub_info)
                except Exception as e:
                    error_msg = f"Could not retrieve virtual hub details for {vwan.name} in subscription {subscription_id}: {e}"
                    logging.error(error_msg)
                    sys.exit(1)
        except Exception as e:
            error_msg = f"Could not list virtual WANs for subscription {subscription_id}: {e}"
            logging.error(error_msg)
            sys.exit(1)

        # Process VNets
        try:
            for vnet in network_client.virtual_networks.list_all():
                try:
                    resource_group_name = extract_resource_group(vnet.id)
                    subnet_names = [subnet.name for subnet in vnet.subnets]

                    # Construct resourcegroup_id from resource_id
                    resourcegroup_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
                    
                    # Construct Azure console hyperlink
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

                    # Get peerings for this VNet - store resource IDs instead of names
                    peerings = network_client.virtual_network_peerings.list(resource_group_name, vnet.name)
                    peering_resource_ids = []
                    for peering in peerings:
                        if peering.remote_virtual_network and peering.remote_virtual_network.id:
                            peering_resource_ids.append(peering.remote_virtual_network.id)
                    
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

    # All VNets are equal - no hub detection needed
    network_data["vnets"] = vnet_candidates
    
    # Check if no VNets were found across all subscriptions - this is fatal
    if not vnet_candidates:
        logging.error("No VNets found across all subscriptions. This is a fatal error.")
        logging.info("Individual subscriptions without VNets is normal, but finding zero VNets total is not supported.")
        sys.exit(1)
    
    return network_data

# List all subscriptions and allow user to select
def list_and_select_subscriptions() -> List[str]:
    subscription_client = SubscriptionClient(get_credentials())
    subscriptions = list(subscription_client.subscriptions.list())
    # Sort subscriptions alphabetically by display_name to ensure consistent ordinals
    subscriptions.sort(key=lambda sub: sub.display_name)
    
    for idx, subscription in enumerate(subscriptions):
        logging.info(f"[{idx}] {subscription.display_name} ({subscription.subscription_id})")

    selected_indices = input("Enter the indices of subscriptions to include (comma-separated): ")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",")]
    return [subscriptions[idx].subscription_id for idx in selected_indices]

# Save the data to a JSON file
def save_to_json(data: Dict[str, Any], filename: str = "network_topology.json") -> None:
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    logging.info(f"Network topology saved to {filename}")

def query_command(args: argparse.Namespace) -> None:
    """Execute the query command to collect VNet topology from Azure"""
    # Validate file arguments - they should not be empty strings
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
    
    # Initialize credentials based on service principal flag
    initialize_credentials(args.service_principal)
    
    # Validate mutually exclusive arguments
    exclusive_args = [
        ('--subscriptions', args.subscriptions),
        ('--subscriptions-file', args.subscriptions_file),
        ('--vnets', args.vnets)
    ]
    
    # Check for arguments that are provided (not None) and not empty
    # For comma-separated arguments like vnets, we need to check if there are any valid values after parsing
    provided_args = []
    empty_args = []
    
    for arg_name, arg_value in exclusive_args:
        if arg_value is not None:
            if not arg_value.strip():
                # Completely empty argument
                empty_args.append(arg_name)
            elif arg_name == '--vnets':
                # Special handling for comma-separated vnets - check if any valid identifiers exist
                vnet_identifiers = [vnet.strip() for vnet in arg_value.split(',') if vnet.strip()]
                if not vnet_identifiers:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            elif arg_name == '--subscriptions':
                # Special handling for comma-separated subscriptions - check if any valid values exist
                subscription_values = [sub.strip() for sub in arg_value.split(',') if sub.strip()]
                if not subscription_values:
                    empty_args.append(arg_name)
                else:
                    provided_args.append(arg_name)
            else:
                # For other arguments (like --subscriptions-file), just check if not empty after strip
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
    
    # Determine subscription selection mode
    if args.vnets:
        # VNet filtering mode - parse comma-separated VNet identifiers
        vnet_identifiers = [vnet.strip() for vnet in args.vnets.split(',') if vnet.strip()]
        
        if not vnet_identifiers:
            logging.error("No valid VNet identifiers provided after parsing --vnets argument")
            logging.error("Please provide valid VNet identifiers in the format: subscription/resource_group/vnet_name or resource_group/vnet_name")
            sys.exit(1)
            
        # Collect all subscriptions needed for the VNets
        all_subscriptions = set()
        
        for vnet_identifier in vnet_identifiers:
            try:
                subscription_id, resource_group, vnet_name = parse_vnet_identifier(vnet_identifier)
                
                # Subscription specified in vnet identifier (resource ID or path format)
                # Check if it's a subscription name or ID and resolve if needed
                if is_subscription_id(subscription_id):
                    all_subscriptions.add(subscription_id)
                else:
                    # It's a subscription name, resolve to ID
                    resolved_subs = resolve_subscription_names_to_ids([subscription_id])
                    all_subscriptions.update(resolved_subs)
            except ValueError as e:
                logging.error(f"Invalid VNet identifier format '{vnet_identifier}': {e}")
                sys.exit(1)
        
        selected_subscriptions = list(all_subscriptions)
        logging.info(f"Filtering topology for hub VNets: {args.vnets}")
        topology = get_filtered_vnets_topology(vnet_identifiers, selected_subscriptions)
    else:
        # Original behavior for non-VNet filtering
        if (args.subscriptions and args.subscriptions.strip()) or (args.subscriptions_file and args.subscriptions_file.strip()):
            # Non-interactive mode
            selected_subscriptions = get_subscriptions_non_interactive(args)
        else:
            # Interactive mode (existing behavior)
            logging.info("Listing available subscriptions...")
            selected_subscriptions = list_and_select_subscriptions()
        
        logging.info("Collecting VNets and topology...")
        topology = get_vnet_topology_for_selected_subscriptions(selected_subscriptions)
    
    output_file = args.output if args.output else "network_topology.json"
    save_to_json(topology, output_file)

def get_subscriptions_non_interactive(args: argparse.Namespace) -> List[str]:
    """Get subscriptions from command line arguments or file in non-interactive mode"""
    if args.subscriptions and args.subscriptions_file:
        logging.error("Cannot specify both --subscriptions and --subscriptions-file")
        sys.exit(1)
    
    if args.subscriptions and args.subscriptions.strip():
        # Parse comma-separated subscriptions
        subscriptions = [sub.strip() for sub in args.subscriptions.split(',') if sub.strip()]
        if not subscriptions:
            logging.error("No valid subscriptions found after parsing --subscriptions argument")
            logging.error("Please provide valid subscription names or IDs, or use 'all' to include all subscriptions")
            sys.exit(1)
    elif args.subscriptions_file and args.subscriptions_file.strip():
        # Read subscriptions from file
        subscriptions = read_subscriptions_from_file(args.subscriptions_file)
    else:
        logging.error("No valid subscription source provided")
        logging.error("This should not happen - argument validation should have caught this")
        sys.exit(1)
    
    # Handle special "all" value to get all subscriptions
    if subscriptions and len(subscriptions) == 1 and subscriptions[0].lower() == "all":
        logging.info("Getting all available subscriptions")
        return get_all_subscription_ids()
    
    # Detect if subscriptions are IDs or names by checking the first subscription
    if subscriptions and is_subscription_id(subscriptions[0]):
        # All subscriptions are assumed to be IDs
        logging.info(f"Using subscription IDs: {subscriptions}")
        return subscriptions
    else:
        # All subscriptions are assumed to be names, resolve to IDs
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
    return 0  # Default to first zone

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
    """Generate consistent hierarchical IDs for DrawIO elements using Azure resource path format
    
    Args:
        vnet_data: VNet data dictionary containing Azure resource information
        element_type: Type of element ('group', 'main', 'subnet', 'icon')
        suffix: Optional suffix for element_type (e.g., '0' for subnet index, 'vpn' for icon type)
    
    Returns:
        Hierarchical ID in format: subscription.resourcegroup.vnet[.element_type[.suffix]]
        Falls back to simple vnet-based ID if Azure metadata is missing (for tests)
    """
    # Extract and sanitize Azure resource components
    subscription_name = vnet_data.get('subscription_name', '').replace('.', '_')
    resourcegroup_name = vnet_data.get('resourcegroup_name', '').replace('.', '_')
    vnet_name = vnet_data.get('name', '').replace('.', '_')
    
    # Check if we have sufficient metadata for hierarchical IDs
    if not subscription_name or not resourcegroup_name:
        # Fallback to simple ID for test scenarios or missing metadata
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
            # Fallback for unknown element types
            if suffix is not None:
                return f"{vnet_name}_{element_type}_{suffix}"
            else:
                return f"{vnet_name}_{element_type}"
    
    # Build hierarchical base ID with full Azure metadata
    base_id = f"{subscription_name}.{resourcegroup_name}.{vnet_name}"
    
    # Add element type if specified
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
        # Fallback for unknown element types
        if suffix is not None:
            return f"{base_id}.{element_type}.{suffix}"
        else:
            return f"{base_id}.{element_type}"

def create_vnet_id_mapping(vnets: List[Dict[str, Any]], zones: List[Dict[str, Any]], all_non_peered: List[Dict[str, Any]]) -> Dict[str, str]:
    """Create bidirectional mapping between VNet resource IDs and diagram IDs for multi-zone layout
    
    Uses resource IDs as unique identifiers to avoid name collisions.
    Uses hierarchical Azure-based IDs when Azure metadata is available,
    falls back to synthetic IDs for backward compatibility (tests)
    """
    mapping = {}
    
    # Check if we have Azure metadata available in the data
    has_azure_metadata = False
    if zones and zones[0].get('hub'):
        hub_data = zones[0]['hub']
        has_azure_metadata = bool(hub_data.get('subscription_name') and hub_data.get('resourcegroup_name'))
    
    if has_azure_metadata:
        # Production mode: Use hierarchical Azure-based IDs
        # Map hub VNets to hierarchical main IDs using resource_id as key
        for zone in zones:
            if 'resource_id' in zone['hub']:
                main_id = generate_hierarchical_id(zone['hub'], 'main')
                mapping[zone['hub']['resource_id']] = main_id
        
        # Map spoke VNets to hierarchical main IDs using resource_id as key
        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']
            
            for spoke in peered_spokes:
                if 'resource_id' in spoke:
                    main_id = generate_hierarchical_id(spoke, 'main')
                    mapping[spoke['resource_id']] = main_id
        
        # Map non-peered VNets to hierarchical main IDs using resource_id as key
        for nonpeered in all_non_peered:
            if 'resource_id' in nonpeered:
                main_id = generate_hierarchical_id(nonpeered, 'main')
                mapping[nonpeered['resource_id']] = main_id
    else:
        # Test/backward compatibility mode: Use original synthetic IDs with resource_id as key, fallback to name
        # Map hub VNets
        for zone in zones:
            hub_key = zone['hub'].get('resource_id') or zone['hub'].get('name')
            if hub_key:
                mapping[hub_key] = f"hub_{zone['hub_index']}"
        
        # Map spoke VNets with zone-aware IDs
        for zone_index, zone in enumerate(zones):
            peered_spokes = zone['spokes']
            
            # Determine layout for this zone
            use_dual_column = len(peered_spokes) > 6
            if use_dual_column:
                total_spokes = len(peered_spokes)
                half_spokes = (total_spokes + 1) // 2
                left_spokes = peered_spokes[:half_spokes]
                right_spokes = peered_spokes[half_spokes:]
            else:
                left_spokes = []
                right_spokes = peered_spokes
            
            # Map right spokes
            for i, spoke in enumerate(right_spokes):
                spoke_key = spoke.get('resource_id') or spoke.get('name')
                if spoke_key:
                    mapping[spoke_key] = f"right_spoke{zone_index}_{i}"
            
            # Map left spokes
            for i, spoke in enumerate(left_spokes):
                spoke_key = spoke.get('resource_id') or spoke.get('name')
                if spoke_key:
                    mapping[spoke_key] = f"left_spoke{zone_index}_{i}"
        
        # Map non-peered VNets
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
    
    # Check for empty VNet list - this should be fatal
    if not vnets:
        logging.error("No VNets found in topology file. Cannot generate diagram.")
        sys.exit(1)
    
    return vnets

def _classify_and_sort_vnets(vnets: List[Dict[str, Any]], config: Any) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract common VNet classification and sorting logic"""
    # Classify VNets for layout purposes (keep existing layout logic)
    # Highly connected VNets (hubs) vs others, including explicitly specified hubs
    hub_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) >= config.hub_threshold or vnet.get("is_explicit_hub", False)]
    # Sort hubs deterministically by name to ensure consistent zone assignment
    hub_vnets.sort(key=lambda x: x.get('name', ''))
    spoke_vnets = [vnet for vnet in vnets if vnet.get("peerings_count", 0) < config.hub_threshold and not vnet.get("is_explicit_hub", False)]
    
    # If no highly connected VNets, treat the first one as primary for layout
    if not hub_vnets and vnets:
        hub_vnets = [vnets[0]]
        spoke_vnets = vnets[1:]
    
    logging.info(f"Found {len(hub_vnets)} hub VNet(s) and {len(spoke_vnets)} spoke VNet(s)")
    
    return hub_vnets, spoke_vnets

def _setup_xml_structure(config: Any) -> Tuple[Any, Any]:
    """Extract common XML document structure setup"""
    from lxml import etree
    
    # Root XML structure
    mxfile = etree.Element("mxfile", attrib={"host": "Electron", "version": "25.0.2"})
    diagram = etree.SubElement(mxfile, "diagram", name="Hub and Spoke Topology")
    mxGraphModel = etree.SubElement(
        diagram,
        "mxGraphModel",
        attrib=config.get_canvas_attributes(),
    )
    root = etree.SubElement(mxGraphModel, "root")

    etree.SubElement(root, "mxCell", id="0")  # Root cell
    etree.SubElement(root, "mxCell", id="1", parent="0")  # Parent cell for all shapes
    
    return mxfile, root

def _classify_spoke_vnets(vnets: List[Dict[str, Any]], hub_vnets: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract common spoke VNet classification logic"""
    spoke_vnets_classified = []
    unpeered_vnets = []
    
    for vnet in vnets:
        if vnet in hub_vnets:
            continue  # Skip hubs
        elif vnet.get("peering_resource_ids"):
            spoke_vnets_classified.append(vnet)
        else:
            unpeered_vnets.append(vnet)
    
    return spoke_vnets_classified, unpeered_vnets

def _create_layout_zones(hub_vnets: List[Dict[str, Any]], spoke_vnets_classified: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Extract common zone assignment logic"""
    # Direct zone assignment using simple arrays
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
    
    # Calculate VNet height based on mode
    if show_subnets:
        # MLD mode: height depends on number of subnets
        num_subnets = len(vnet_data.get("subnets", []))
        vnet_height = config.layout['hub']['height'] if vnet_data.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
        group_width = config.layout['hub']['width']
        group_height = vnet_height + config.drawio['group']['extra_height']
    else:
        # HLD mode: fixed height for all VNets
        vnet_height = 50 if vnet_data.get("type") == "virtual_hub" else 50
        group_width = config.vnet_width
        group_height = vnet_height + config.group_height_extra
    
    # Create group container for this VNet and all its elements with metadata
    group_id = generate_hierarchical_id(vnet_data, 'group')
    
    # Build attributes dictionary with metadata
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
    
    # Add mxCell child for the group styling
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
    
    # Choose default style based on mode
    if show_subnets:
        default_style = config.get_vnet_style_string('hub')
    else:
        default_style = "shape=rectangle;rounded=0;whiteSpace=wrap;html=1;strokeColor=#0078D4;fontColor=#004578;fillColor=#E6F1FB;align=left"
    
    # Add VNet box as child of group
    main_id = generate_hierarchical_id(vnet_data, 'main')
    vnet_element = etree.SubElement(
        root,
        "mxCell",
        id=main_id,
        style=style_override or default_style,
        vertex="1",
        parent=group_id,
    )
    vnet_element.set("value", f"Subscription: {vnet_data.get('subscription_name', 'N/A')}\n{vnet_data.get('name', 'VNet')}\n{vnet_data.get('address_space', 'N/A')}")
    
    # Set VNet box geometry based on mode
    vnet_box_width = group_width if show_subnets else 400
    etree.SubElement(
        vnet_element,
        "mxGeometry",
        attrib={"x": "0", "y": "0", "width": str(vnet_box_width), "height": str(vnet_height), "as": "geometry"},
    )

    # Add Virtual Hub icon if applicable
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
    
    # Dynamic VNet icon positioning (top-right aligned)
    vnet_width = group_width if show_subnets else config.vnet_width
    y_offset = config.icon_positioning['vnet_icons']['y_offset']
    right_margin = config.icon_positioning['vnet_icons']['right_margin']
    icon_gap = config.icon_positioning['vnet_icons']['icon_gap']
    
    # Build list of VNet decorator icons to display (right to left order)
    vnet_icons_to_render = []
    
    # VNet icon is always present (rightmost)
    vnet_icon_width, vnet_icon_height = config.get_icon_size('vnet')
    vnet_icons_to_render.append({
        'type': 'vnet',
        'width': vnet_icon_width,
        'height': vnet_icon_height
    })
    
    # ExpressRoute icon (if present)
    if vnet_data.get("expressroute", "").lower() == "yes":
        express_width, express_height = config.get_icon_size('expressroute')
        vnet_icons_to_render.append({
            'type': 'expressroute',
            'width': express_width,
            'height': express_height
        })
    
    # Firewall icon (if present)
    if vnet_data.get("firewall", "").lower() == "yes":
        firewall_width, firewall_height = config.get_icon_size('firewall')
        vnet_icons_to_render.append({
            'type': 'firewall',
            'width': firewall_width,
            'height': firewall_height
        })
    
    # VPN Gateway icon (if present, leftmost)
    if vnet_data.get("vpn_gateway", "").lower() == "yes":
        vpn_width, vpn_height = config.get_icon_size('vpn_gateway')
        vnet_icons_to_render.append({
            'type': 'vpn_gateway',
            'width': vpn_width,
            'height': vpn_height
        })
    
    # Calculate positions from right to left
    current_x = vnet_width - right_margin
    for icon in vnet_icons_to_render:
        current_x -= icon['width']
        icon['x'] = current_x
        
        # Create the icon element as child of VNet using hierarchical IDs
        if icon['type'] == 'vnet':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'vnet')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('vnet')};",
                vertex="1",
                parent=main_id,  # Parent to VNet main element
            )
        elif icon['type'] == 'expressroute':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'expressroute')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('expressroute')};",
                vertex="1",
                parent=main_id,  # Parent to VNet main element
            )
        elif icon['type'] == 'firewall':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'firewall')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('firewall')};",
                vertex="1",
                parent=main_id,  # Parent to VNet main element
            )
        elif icon['type'] == 'vpn_gateway':
            icon_id = generate_hierarchical_id(vnet_data, 'icon', 'vpn')
            icon_element = etree.SubElement(
                root,
                "mxCell",
                id=icon_id,
                style=f"shape=image;html=1;image={config.get_icon_path('vpn_gateway')};",
                vertex="1",
                parent=main_id,  # Parent to VNet main element
            )
        
        etree.SubElement(
            icon_element,
            "mxGeometry",
            attrib={
                "x": str(icon['x']),
                "y": str(y_offset),
                "width": str(icon['width']),
                "height": str(icon['height']),
                "as": "geometry"
            },
        )
        
        current_x -= icon_gap

    # Add subnets if in MLD mode and it's a regular VNet
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

            # Add subnet icons
            subnet_right_edge = config.layout['subnet']['padding_x'] + config.layout['subnet']['width']
            icon_gap = config.icon_positioning['subnet_icons']['icon_gap']
            
            # Build list of icons to display (right to left order)
            icons_to_render = []
            
            # Subnet icon is always present (rightmost)
            subnet_width, subnet_height = config.get_icon_size('subnet')
            icons_to_render.append({
                'type': 'subnet',
                'width': subnet_width,
                'height': subnet_height,
                'y_offset': config.icon_positioning['subnet_icons']['subnet_icon_y_offset']
            })
            
            # UDR icon (if present)
            if subnet.get("udr", "").lower() == "yes":
                udr_width, udr_height = config.get_icon_size('route_table')
                icons_to_render.append({
                    'type': 'udr',
                    'width': udr_width,
                    'height': udr_height,
                    'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                })
            
            # NSG icon (if present, leftmost)
            if subnet.get("nsg", "").lower() == "yes":
                nsg_width, nsg_height = config.get_icon_size('nsg')
                icons_to_render.append({
                    'type': 'nsg',
                    'width': nsg_width,
                    'height': nsg_height,
                    'y_offset': config.icon_positioning['subnet_icons']['icon_y_offset']
                })
            
            # Calculate positions from right to left
            current_x = subnet_right_edge
            for icon in icons_to_render:
                current_x -= icon['width']
                icon['x'] = current_x
                
                # Create the icon element
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
                
                current_x -= icon_gap
    
    return group_height

def generate_diagram(filename: str, topology_file: str, config: Any, render_mode: str = 'hld') -> None:
    """
    Unified diagram generation function that handles both HLD and MLD modes
    
    Args:
        filename: Output DrawIO filename
        topology_file: Input topology JSON file
        config: Configuration object
        render_mode: 'hld' for high-level (VNets only) or 'mld' for mid-level (VNets + subnets)
    """
    from lxml import etree
    
    # Validate render_mode
    if render_mode not in ['hld', 'mld']:
        raise ValueError(f"Invalid render_mode '{render_mode}'. Must be 'hld' or 'mld'.")
    
    show_subnets = render_mode == 'mld'
    
    # Use common helper functions
    vnets = _load_and_validate_topology(topology_file)
    hub_vnets, spoke_vnets = _classify_and_sort_vnets(vnets, config)
    mxfile, root = _setup_xml_structure(config)

    # Use common helper functions for spoke classification and zone creation
    spoke_vnets_classified, unpeered_vnets = _classify_spoke_vnets(vnets, hub_vnets)
    zone_spokes = _create_layout_zones(hub_vnets, spoke_vnets_classified)
    
    # Calculate layout parameters based on mode
    canvas_padding = config.canvas_padding
    zone_width = 920 - canvas_padding + config.vnet_width
    zone_spacing = config.zone_spacing
    
    if show_subnets:
        # MLD mode: dynamic spacing with padding for subnets
        spacing = 20  # Original MLD padding
    else:
        # HLD mode: fixed spacing
        spacing = 100
        
    # Calculate base positions
    base_left_x = canvas_padding
    base_hub_x = canvas_padding + config.vnet_spacing_x
    base_right_x = canvas_padding + config.vnet_spacing_x + config.vnet_width + 50
    hub_y = canvas_padding
    
    # Track zone bottoms for unpeered VNet placement
    zone_bottoms = []
    
    # Draw each zone using direct arrays
    for zone_index, hub_vnet in enumerate(hub_vnets):
        zone_offset_x = zone_index * (zone_width + zone_spacing)
        
        # Draw hub
        hub_x = base_hub_x + zone_offset_x
        hub_main_id = generate_hierarchical_id(hub_vnet, 'main')
        hub_actual_height = _add_vnet_with_optional_subnets(hub_vnet, hub_x, hub_y, root, config, show_subnets=show_subnets)
        
        # Get spokes for this zone using simple array access
        spokes = zone_spokes[zone_index]
        
        # Split spokes using existing layout logic
        if len(spokes) > 6:
            total_spokes = len(spokes)
            half_spokes = (total_spokes + 1) // 2
            left_spokes = spokes[:half_spokes]
            right_spokes = spokes[half_spokes:]
        else:
            left_spokes = []
            right_spokes = spokes
        
        # Calculate hub VNet height for MLD mode
        if show_subnets:
            num_subnets = len(hub_vnet.get("subnets", []))
            hub_vnet_height = config.layout['hub']['height'] if hub_vnet.get("type") == "virtual_hub" else config.layout['subnet']['padding_y'] + (num_subnets * config.layout['subnet']['spacing_y'])
            current_y_right = hub_y + hub_vnet_height
            current_y_left = hub_y + hub_vnet_height
        else:
            hub_height = 50
            current_y_right = hub_y + hub_height
            current_y_left = hub_y + hub_height
        
        # Draw right spokes
        for index, spoke in enumerate(right_spokes):
            if show_subnets:
                y_position = current_y_right
            else:
                y_position = hub_y + hub_height + index * spacing
            x_position = base_right_x + zone_offset_x
            spoke_main_id = generate_hierarchical_id(spoke, 'main')
            
            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = _add_vnet_with_optional_subnets(spoke, x_position, y_position, root, config, show_subnets=show_subnets, style_override=spoke_style)
            
            # Connect to hub
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
        
        # Draw left spokes
        for index, spoke in enumerate(left_spokes):
            if show_subnets:
                y_position = current_y_left
            else:
                y_position = hub_y + hub_height + index * spacing
            x_position = base_left_x + zone_offset_x
            spoke_main_id = generate_hierarchical_id(spoke, 'main')
            
            spoke_style = config.get_vnet_style_string('spoke')
            vnet_height = _add_vnet_with_optional_subnets(spoke, x_position, y_position, root, config, show_subnets=show_subnets, style_override=spoke_style)
            
            # Connect to hub
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
        
        # Track zone bottom for unpeered placement
        if show_subnets:
            zone_bottom = hub_y + hub_vnet_height
            if left_spokes or right_spokes:
                zone_bottom = max(current_y_left, current_y_right) + 60
            else:
                zone_bottom = hub_y + hub_vnet_height + 60
        else:
            zone_bottom = hub_y + hub_height
            if left_spokes or right_spokes:
                left_count = len(left_spokes)
                right_count = len(right_spokes)
                if left_count > 0:
                    zone_bottom = max(zone_bottom, hub_y + hub_height + left_count * spacing + 50)
                if right_count > 0:
                    zone_bottom = max(zone_bottom, hub_y + hub_height + right_count * spacing + 50)
            else:
                zone_bottom = hub_y + hub_height + 50
        
        zone_bottoms.append(zone_bottom)
    
    # Draw unpeered VNets in horizontal rows
    if unpeered_vnets:
        overall_bottom_y = max(zone_bottoms) if zone_bottoms else hub_y + (hub_vnet_height if show_subnets else hub_height)
        unpeered_y = overall_bottom_y + (60 if show_subnets else 100)
        
        # Calculate total width for unpeered layout
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

    # Create simplified zones for backward compatibility with mapping function
    zones = []
    for hub_index, hub_vnet in enumerate(hub_vnets):
        zones.append({
            'hub': hub_vnet,
            'hub_index': hub_index,
            'spokes': zone_spokes[hub_index],
            'non_peered': unpeered_vnets if hub_index == 0 else []
        })

    # Create VNet ID mapping for peering connections
    vnet_mapping = create_vnet_id_mapping(vnets, zones, unpeered_vnets)
    
    # Only draw edges for VNets that should have connectivity (exclude unpeered)
    vnets_with_edges = hub_vnets + spoke_vnets_classified
    add_peering_edges(vnets_with_edges, vnet_mapping, root, config)
    
    # Add cross-zone connectivity edges for multi-hub spokes
    add_cross_zone_connectivity_edges(zones, hub_vnets, vnet_mapping, root, config)
    
    logging.info(f"Added full mesh peering connections for {len(vnets)} VNets")

    # Write to file
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
    
    edge_counter = 3000  # Start high to avoid conflicts
    
    logging.info("Adding cross-zone connectivity edges for multi-hub spokes...")
    
    for zone in zones:
        zone_hub_index = zone['hub_index']
        
        for spoke in zone['spokes']:
            spoke_name = spoke.get('name')
            if not spoke_name:
                continue
                
            # Find ALL hubs this spoke connects to
            connected_hub_indices = get_hub_connections_for_spoke(spoke, hub_vnets)
            
            # Create edges to OTHER hubs (not the assigned zone hub)
            for hub_index in connected_hub_indices:
                if hub_index != zone_hub_index:  # Skip the already-connected hub
                    target_hub = hub_vnets[hub_index]
                    target_hub_name = target_hub.get('name')
                    
                    spoke_id = vnet_mapping.get(spoke.get('resource_id'))
                    target_hub_id = vnet_mapping.get(target_hub.get('resource_id'))
                    
                    if spoke_id and target_hub_id:
                        # Create cross-zone edge with distinct styling
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
                        
                        # Add basic geometry (draw.io will auto-route)
                        edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
                        
                        edge_counter += 1
                        logging.info(f"Added cross-zone edge: {spoke_name} → {target_hub_name} (zone {zone_hub_index} → zone {hub_index})")

def add_peering_edges(vnets, vnet_mapping, root, config):
    """Add edges for all VNet peerings using reliable resource IDs with proper symmetry validation"""
    from lxml import etree
    
    edge_counter = 1000  # Start high to avoid conflicts with existing edge IDs
    processed_peerings = set()  # Track processed peering relationships to avoid duplicates
    
    # Create resource ID to VNet name mapping for reliable peering resolution
    resource_id_to_name = {vnet['resource_id']: vnet['name'] for vnet in vnets if 'resource_id' in vnet}
    
    # Create VNet name to resource ID mapping for symmetry validation
    vnet_name_to_resource_id = {vnet['name']: vnet['resource_id'] for vnet in vnets if 'name' in vnet and 'resource_id' in vnet}
    
    for vnet in vnets:
        if 'resource_id' not in vnet:
            continue  # Skip VNets without resource IDs
            
        source_resource_id = vnet['resource_id']
        source_vnet_name = vnet['name']
        source_id = vnet_mapping.get(source_resource_id)
        
        if not source_id:
            continue  # Skip if source VNet not in diagram
            
        # Use reliable peering_resource_ids instead of parsing peering names
        for peering_resource_id in vnet.get('peering_resource_ids', []):
            target_vnet_name = resource_id_to_name.get(peering_resource_id)
            
            if not target_vnet_name or target_vnet_name == source_vnet_name:
                continue  # Skip if target VNet not found or self-reference
                
            target_id = vnet_mapping.get(peering_resource_id)
            if not target_id:
                continue  # Skip if target VNet not in diagram
            
            # Skip hub-to-spoke connections (already drawn) - now using hierarchical IDs
            # Check if this is a hub-to-spoke connection by checking if one is a main ID from a hub VNet
            # and the other is a main ID from a spoke VNet that's already connected
            source_vnet = next((v for v in vnets if v.get('name') == source_vnet_name), None)
            target_vnet = next((v for v in vnets if v.get('name') == target_vnet_name), None)
            
            # Removed hub-to-spoke filtering to create fully connected graph
            # All peering relationships will be drawn as edges
            
            # Create a deterministic peering key to avoid duplicates
            peering_key = tuple(sorted([source_vnet_name, target_vnet_name]))
            
            if peering_key in processed_peerings:
                continue  # Skip if this peering relationship has already been processed
            
            # Check for bidirectional peering (informational only)
            source_resource_id = vnet_name_to_resource_id.get(source_vnet_name)
            target_vnet = next((v for v in vnets if v.get('name') == target_vnet_name), None)
            
            if target_vnet and source_resource_id:
                target_peering_resource_ids = target_vnet.get('peering_resource_ids', [])
                if source_resource_id not in target_peering_resource_ids:
                    logging.debug(f"Asymmetric peering detected: {source_vnet_name} peers to {target_vnet_name}, but {target_vnet_name} does not peer back to {source_vnet_name}")
                    # Continue to draw the edge anyway - asymmetric peering is normal in Azure
            
            # Mark this peering relationship as processed
            processed_peerings.add(peering_key)
            
            # Create edge for spoke-to-spoke or hub-to-hub connections
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
            
            # Add basic geometry (draw.io will auto-route)
            edge_geometry = etree.SubElement(edge, "mxGeometry", attrib={"relative": "1", "as": "geometry"})
            
            edge_counter += 1
            logging.info(f"Added bidirectional peering edge: {source_vnet_name} ({source_id}) ↔ {target_vnet_name} ({target_id})")

def hld_command(args: argparse.Namespace) -> None:
    """Execute the HLD command to generate high-level diagrams"""
    from config import Config
    
    # Validate file arguments - they should not be empty strings
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
    
    # Create config instance with specified file
    config = Config(config_file)
    
    logging.info("Starting HLD diagram generation...")
    generate_hld_diagram(output_file, topology_file, config)
    logging.info("HLD diagram generation complete.")
    logging.info(f"HLD diagram saved to {output_file}")

def generate_mld_diagram(filename: str, topology_file: str, config: Any) -> None:
    """Generate mid-level diagram (VNets + subnets) from topology JSON"""
    generate_diagram(filename, topology_file, config, render_mode='mld')

def mld_command(args: argparse.Namespace) -> None:
    """Execute the MLD command to generate mid-level diagrams"""
    from config import Config
    
    # Validate file arguments - they should not be empty strings
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
    
    # Create config instance with specified file
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
    
    # Parse arguments and dispatch to appropriate function
    args = parser.parse_args()
    
    # Configure logging based on verbose flag
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