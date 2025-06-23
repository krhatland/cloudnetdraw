@description('Location for all resources')
param location string = resourceGroup().location

@description('Name for the Function App')
param functionAppName string

@description('Name for the Storage Account (AzureWebJobsStorage)')
param storageAccountName string

@description('Name for the Storage Account to store drawings')
param drawingStorageAccountName string

@description('Name for the App Service Plan')
param appServicePlanName string

@description('Name for the container to store diagrams')
param containerName string = 'drawfunc'

@description('Python version to use (e.g., 3.10)')
param pythonVersion string = '3.10'

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
    }
    accessTier: 'Hot'
  }
}

resource drawingStorageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' = {
  name: drawingStorageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Deny'
    }
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: { enabled: true }
        file: { enabled: true }
      }
    }
    accessTier: 'Hot'
  }
}

resource drawContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-09-01' = {
  name: '${drawingStorageAccount.name}/default/${containerName}'
  properties: {
    publicAccess: 'None'
  }
  dependsOn: [drawingStorageAccount]
}

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: appServicePlanName
  location: location
  sku: {
    name: 'FC1'
    tier: 'FlexConsumption'
    size: 'FC1'
    family: 'FC'
    capacity: 0
  }
  kind: 'functionapp'
  properties: {
    perSiteScaling: false
    elasticScaleEnabled: false
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2022-03-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|${pythonVersion}'
      appSettings: [
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, '2022-09-01').keys[0].value};EndpointSuffix=${environment().suffixes.storage}'
        }
        {
          name: 'DRAWING_STORAGE_URL'
          value: reference(drawingStorageAccount.id, '2022-09-01').primaryEndpoints.blob
        }
        {
          name: 'DRAWING_CONTAINER_NAME'
          value: containerName
        }
      ]
    }
    httpsOnly: true
  }
  dependsOn: [
    appServicePlan
    storageAccount
    drawingStorageAccount
  ]
}

resource drawingStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.name, drawingStorageAccount.id, 'blobcontrib')
  scope: drawingStorageAccount
  properties: {
    principalId: reference(functionApp.id, '2022-03-01', 'full').identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
  }
  dependsOn: [
    functionApp
    drawingStorageAccount
  ]
}

output functionAppEndpoint string = 'https://${functionApp.properties.defaultHostName}'
