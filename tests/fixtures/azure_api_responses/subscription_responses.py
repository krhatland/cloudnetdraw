"""Mock responses for Azure Subscription API calls."""

SUBSCRIPTION_LIST_RESPONSE = {
    "value": [
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012",
            "subscriptionId": "12345678-1234-1234-1234-123456789012",
            "displayName": "Production Subscription",
            "state": "Enabled",
            "subscriptionPolicies": {
                "locationPlacementId": "Public_2014-09-01",
                "quotaId": "PayAsYouGo_2014-09-01",
                "spendingLimit": "Off"
            }
        },
        {
            "id": "/subscriptions/87654321-4321-4321-4321-210987654321",
            "subscriptionId": "87654321-4321-4321-4321-210987654321",
            "displayName": "Development Subscription",
            "state": "Enabled",
            "subscriptionPolicies": {
                "locationPlacementId": "Public_2014-09-01",
                "quotaId": "PayAsYouGo_2014-09-01",
                "spendingLimit": "Off"
            }
        },
        {
            "id": "/subscriptions/11111111-2222-3333-4444-555555555555",
            "subscriptionId": "11111111-2222-3333-4444-555555555555",
            "displayName": "Test Subscription",
            "state": "Enabled",
            "subscriptionPolicies": {
                "locationPlacementId": "Public_2014-09-01",
                "quotaId": "PayAsYouGo_2014-09-01",
                "spendingLimit": "Off"
            }
        }
    ]
}

SINGLE_SUBSCRIPTION_RESPONSE = {
    "value": [
        {
            "id": "/subscriptions/12345678-1234-1234-1234-123456789012",
            "subscriptionId": "12345678-1234-1234-1234-123456789012",
            "displayName": "Production Subscription",
            "state": "Enabled",
            "subscriptionPolicies": {
                "locationPlacementId": "Public_2014-09-01",
                "quotaId": "PayAsYouGo_2014-09-01",
                "spendingLimit": "Off"
            }
        }
    ]
}

EMPTY_SUBSCRIPTION_RESPONSE = {
    "value": []
}

SUBSCRIPTION_ERROR_RESPONSES = {
    "403_forbidden": {
        "error": {
            "code": "Forbidden",
            "message": "The client does not have authorization to perform action 'Microsoft.Resources/subscriptions/read' over scope '/subscriptions'."
        }
    },
    "404_not_found": {
        "error": {
            "code": "SubscriptionNotFound",
            "message": "The subscription '12345678-1234-1234-1234-123456789012' could not be found."
        }
    },
    "429_throttled": {
        "error": {
            "code": "TooManyRequests",
            "message": "Too many requests, please try again later."
        }
    },
    "500_internal_error": {
        "error": {
            "code": "InternalServerError",
            "message": "The server encountered an internal error and was unable to complete your request."
        }
    }
}