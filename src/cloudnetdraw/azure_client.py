"""
Azure client and authentication functions
Handles Azure SDK operations, credentials, and VNet discovery
"""
import os
import re
import sys
import logging
from typing import Dict, List, Any, Optional, Union, Tuple

from azure.identity import AzureCliCredential, ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import SubscriptionClient
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest
from azure.core.exceptions import ResourceNotFoundError

from .utils import extract_resource_group, parse_vnet_identifier

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


def get_vnet_topology_for_selected_subscriptions(subscription_ids: List[str]) -> Dict[str, Any]:
    """Collect all VNets and their details across selected subscriptions"""
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


def list_and_select_subscriptions() -> List[str]:
    """List all subscriptions and allow user to select"""
    subscription_client = SubscriptionClient(get_credentials())
    subscriptions = list(subscription_client.subscriptions.list())
    # Sort subscriptions alphabetically by display_name to ensure consistent ordinals
    subscriptions.sort(key=lambda sub: sub.display_name)
    
    for idx, subscription in enumerate(subscriptions):
        logging.info(f"[{idx}] {subscription.display_name} ({subscription.subscription_id})")

    selected_indices = input("Enter the indices of subscriptions to include (comma-separated): ")
    selected_indices = [int(idx.strip()) for idx in selected_indices.split(",")]
    return [subscriptions[idx].subscription_id for idx in selected_indices]


def get_subscriptions_non_interactive(args) -> List[str]:
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