#!/usr/bin/env python3

"""
Simple topology generator for cloudnetdraw examples
Usage: python3 generate-sample-topology.py <hubs> <spokes> <unpeered> <output_file>
"""

import json
import sys
import uuid
import random

def generate_uuid():
    return str(uuid.uuid4())

def generate_vnet(name, vnet_type, address_space, subscription_id, resource_group):
    tenant_id = "a84894e7-87c5-40e3-9783-320d0334b3cc"
    resource_id = f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{name}"
    
    # Random services
    expressroute = "Yes" if random.random() < 0.3 else "No"
    vpn_gateway = "Yes" if random.random() < 0.3 else "No"
    firewall = "Yes" if random.random() < 0.2 else "No"
    
    # For hubs, increase chance of services
    if vnet_type == "hub":
        expressroute = "Yes" if random.random() < 0.7 else "No"
        vpn_gateway = "Yes" if random.random() < 0.7 else "No"
        firewall = "Yes" if random.random() < 0.4 else "No"
    
    # Generate subnets
    subnets = [{
        "name": "default",
        "address": f"{address_space.split('.')[0]}.{address_space.split('.')[1]}.1.0/24",
        "nsg": "Yes" if random.random() < 0.7 else "No",
        "udr": "Yes" if random.random() < 0.5 else "No"
    }]
    
    if vnet_type == "hub":
        subnets.append({
            "name": "GatewaySubnet",
            "address": f"{address_space.split('.')[0]}.{address_space.split('.')[1]}.252.0/24",
            "nsg": "No",
            "udr": "Yes"
        })
        
        if firewall == "Yes":
            subnets.append({
                "name": "AzureFirewallSubnet", 
                "address": f"{address_space.split('.')[0]}.{address_space.split('.')[1]}.253.0/24",
                "nsg": "No",
                "udr": "No"
            })
    
    vnet = {
        "name": name,
        "resource_id": resource_id,
        "tenant_id": tenant_id,
        "subscription_id": subscription_id,
        "subscription_name": f"{name}-Subscription",
        "resourcegroup_id": f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}",
        "resourcegroup_name": resource_group,
        "address_space": address_space,
        "subnets": subnets,
        "azure_console_url": f"https://portal.azure.com/#@{tenant_id}/resource{resource_id}",
        "expressroute": expressroute,
        "vpn_gateway": vpn_gateway,
        "firewall": firewall,
        "peering_resource_ids": [],
        "peerings_count": 0
    }
    
    return vnet

def main():
    if len(sys.argv) != 5:
        print("Usage: python3 generate-sample-topology.py <hubs> <spokes> <unpeered> <output_file>")
        sys.exit(1)
    
    num_hubs = int(sys.argv[1])
    num_spokes = int(sys.argv[2]) 
    num_unpeered = int(sys.argv[3])
    output_file = sys.argv[4]
    
    
    vnets = []
    
    # Generate hubs
    for i in range(1, num_hubs + 1):
        hub_name = f"hub{i}-vnet"
        subscription_id = generate_uuid()
        resource_group = f"hub{i}-rg"
        address_space = f"10.{i}.0.0/16"
        
        vnet = generate_vnet(hub_name, "hub", address_space, subscription_id, resource_group)
        vnets.append(vnet)
    
    # Generate spokes
    for i in range(1, num_spokes + 1):
        spoke_name = f"spoke{i}-vnet"
        subscription_id = generate_uuid()
        resource_group = f"spoke{i}-rg" 
        address_space = f"10.{100 + i}.0.0/16"
        
        vnet = generate_vnet(spoke_name, "spoke", address_space, subscription_id, resource_group)
        vnets.append(vnet)
    
    # Generate unpeered
    for i in range(1, num_unpeered + 1):
        unpeered_name = f"unpeered{i}-vnet"
        subscription_id = generate_uuid()
        resource_group = f"unpeered{i}-rg"
        address_space = f"10.{200 + i}.0.0/16"
        
        vnet = generate_vnet(unpeered_name, "unpeered", address_space, subscription_id, resource_group)
        vnets.append(vnet)
    
    # Add some peering relationships for diversity
    hubs = [v for v in vnets if 'hub' in v['name']]
    spokes = [v for v in vnets if 'spoke' in v['name']]
    
    # Hub to spoke peerings
    for hub in hubs:
        connected_spokes = random.sample(spokes, min(len(spokes), random.randint(1, min(8, len(spokes)))))
        for spoke in connected_spokes:
            hub['peering_resource_ids'].append(spoke['resource_id'])
            spoke['peering_resource_ids'].append(hub['resource_id'])
    
    # Hub to hub peering (for dual-zone)
    if len(hubs) > 1:
        for i, hub1 in enumerate(hubs):
            for hub2 in hubs[i+1:]:
                if random.random() < 0.4:  # 40% chance
                    hub1['peering_resource_ids'].append(hub2['resource_id'])
                    hub2['peering_resource_ids'].append(hub1['resource_id'])
    
    # Some spoke-to-spoke peering
    if len(spokes) >= 2:
        for _ in range(min(len(spokes) // 3, 3)):
            s1, s2 = random.sample(spokes, 2)
            if s2['resource_id'] not in s1['peering_resource_ids']:
                s1['peering_resource_ids'].append(s2['resource_id'])
                s2['peering_resource_ids'].append(s1['resource_id'])
    
    # Update peering counts and remove duplicates
    for vnet in vnets:
        vnet['peering_resource_ids'] = list(set(vnet['peering_resource_ids']))
        vnet['peerings_count'] = len(vnet['peering_resource_ids'])
    
    # Create topology
    topology = {"vnets": vnets}
    
    # Write to file
    with open(output_file, 'w') as f:
        json.dump(topology, f, indent=2)
    
    print(f"Generated {output_file}: {num_hubs} hubs, {num_spokes} spokes, {num_unpeered} unpeered ({len(vnets)} total VNets)")

if __name__ == "__main__":
    main()