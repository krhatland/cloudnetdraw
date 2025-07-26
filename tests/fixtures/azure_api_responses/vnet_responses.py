"""Mock responses for Azure Virtual Network API calls."""

VNET_LIST_RESPONSE = {
    "value": [
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet",
            "name": "hub-vnet",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "properties": {
                "provisioningState": "Succeeded",
                "resourceGuid": "12345678-1234-1234-1234-123456789012",
                "addressSpace": {
                    "addressPrefixes": ["10.0.0.0/16"]
                },
                "subnets": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/GatewaySubnet",
                        "name": "GatewaySubnet",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "addressPrefix": "10.0.1.0/24",
                            "serviceEndpoints": [],
                            "delegations": [],
                            "privateEndpointNetworkPolicies": "Enabled",
                            "privateLinkServiceNetworkPolicies": "Enabled"
                        }
                    },
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet/subnets/default",
                        "name": "default",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "addressPrefix": "10.0.2.0/24",
                            "serviceEndpoints": [],
                            "delegations": [],
                            "privateEndpointNetworkPolicies": "Enabled",
                            "privateLinkServiceNetworkPolicies": "Enabled"
                        }
                    }
                ],
                "virtualNetworkPeerings": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet/virtualNetworkPeerings/hub-to-spoke1",
                        "name": "hub-to-spoke1",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "peeringState": "Connected",
                            "remoteVirtualNetwork": {
                                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke1-vnet"
                            },
                            "allowVirtualNetworkAccess": True,
                            "allowForwardedTraffic": True,
                            "allowGatewayTransit": True,
                            "useRemoteGateways": False,
                            "remoteAddressSpace": {
                                "addressPrefixes": ["10.1.0.0/16"]
                            }
                        }
                    },
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet/virtualNetworkPeerings/hub-to-spoke2",
                        "name": "hub-to-spoke2",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "peeringState": "Connected",
                            "remoteVirtualNetwork": {
                                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke2-vnet"
                            },
                            "allowVirtualNetworkAccess": True,
                            "allowForwardedTraffic": True,
                            "allowGatewayTransit": True,
                            "useRemoteGateways": False,
                            "remoteAddressSpace": {
                                "addressPrefixes": ["10.2.0.0/16"]
                            }
                        }
                    }
                ]
            }
        },
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke1-vnet",
            "name": "spoke1-vnet",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "properties": {
                "provisioningState": "Succeeded",
                "resourceGuid": "87654321-4321-4321-4321-210987654321",
                "addressSpace": {
                    "addressPrefixes": ["10.1.0.0/16"]
                },
                "subnets": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke1-vnet/subnets/default",
                        "name": "default",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "addressPrefix": "10.1.1.0/24",
                            "serviceEndpoints": [],
                            "delegations": [],
                            "privateEndpointNetworkPolicies": "Enabled",
                            "privateLinkServiceNetworkPolicies": "Enabled"
                        }
                    }
                ],
                "virtualNetworkPeerings": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke1-vnet/virtualNetworkPeerings/spoke1-to-hub",
                        "name": "spoke1-to-hub",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "peeringState": "Connected",
                            "remoteVirtualNetwork": {
                                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/hub-rg/providers/Microsoft.Network/virtualNetworks/hub-vnet"
                            },
                            "allowVirtualNetworkAccess": True,
                            "allowForwardedTraffic": True,
                            "allowGatewayTransit": False,
                            "useRemoteGateways": True,
                            "remoteAddressSpace": {
                                "addressPrefixes": ["10.0.0.0/16"]
                            }
                        }
                    }
                ]
            }
        }
    ]
}

EMPTY_VNET_RESPONSE = {
    "value": []
}

VIRTUAL_WAN_HUB_RESPONSE = {
    "value": [
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/wan-rg/providers/Microsoft.Network/virtualHubs/virtual-wan-hub",
            "name": "virtual-wan-hub",
            "type": "Microsoft.Network/virtualHubs",
            "location": "eastus",
            "properties": {
                "provisioningState": "Succeeded",
                "virtualWan": {
                    "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/wan-rg/providers/Microsoft.Network/virtualWans/virtual-wan"
                },
                "addressPrefix": "10.100.0.0/24",
                "virtualNetworkConnections": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/wan-rg/providers/Microsoft.Network/virtualHubs/virtual-wan-hub/hubVirtualNetworkConnections/hub-to-spoke",
                        "name": "hub-to-spoke",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "remoteVirtualNetwork": {
                                "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/spoke-rg/providers/Microsoft.Network/virtualNetworks/spoke-vnet"
                            },
                            "allowHubToRemoteVnetTransit": True,
                            "allowRemoteVnetToHubTransit": True,
                            "enableInternetSecurity": True
                        }
                    }
                ]
            }
        }
    ]
}

VNET_ERROR_RESPONSES = {
    "403_forbidden": {
        "error": {
            "code": "Forbidden",
            "message": "The client does not have authorization to perform action 'Microsoft.Network/virtualNetworks/read' over scope '/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet'."
        }
    },
    "404_not_found": {
        "error": {
            "code": "ResourceNotFound",
            "message": "The Resource 'Microsoft.Network/virtualNetworks/test-vnet' under resource group 'test-rg' was not found."
        }
    },
    "429_throttled": {
        "error": {
            "code": "TooManyRequests",
            "message": "Too many requests, please try again later."
        }
    },
    "timeout": {
        "error": {
            "code": "GatewayTimeout",
            "message": "The gateway did not receive a response from 'Microsoft.Network' within the specified time period."
        }
    }
}

MALFORMED_VNET_RESPONSE = {
    "value": [
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/malformed-vnet",
            # Missing name field
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "properties": {
                "provisioningState": "Succeeded",
                "addressSpace": {
                    # Missing addressPrefixes
                },
                "subnets": [
                    {
                        # Missing id field
                        "name": "default",
                        "properties": {
                            # Missing addressPrefix
                            "provisioningState": "Succeeded"
                        }
                    }
                ],
                "virtualNetworkPeerings": [
                    {
                        "id": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/malformed-vnet/virtualNetworkPeerings/invalid-peering",
                        "name": "invalid-peering",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "peeringState": "Connected",
                            "remoteVirtualNetwork": {
                                # Missing id field
                            },
                            "allowVirtualNetworkAccess": True,
                            "allowForwardedTraffic": True,
                            "allowGatewayTransit": False,
                            "useRemoteGateways": False
                        }
                    }
                ]
            }
        }
    ]
}