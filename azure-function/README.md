# cloudnet-draw-full-selfhost
IaC and Function code

## Deploy to Azure


[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fkrhatland%2Fcloudnet-draw%2Fmain%2Fazure-function%2Fmain.json)


### Parameters

| Parameter            | Description                                  |
|-----------------------|----------------------------------------------|
| `functionAppName`    | Name of the Function App                     |
| `storageAccountName` | Name of the Storage Account                  |
| `drawingStorageAccountName` | Name of the Storage Account for diagrams |
| `appServicePlanName` | Name of the App Service Plan (Consumption)   |

### Configuration

The Function runs daily at midnight UTC (`0 0 0 * * *`). Diagrams are uploaded
to the storage account specified by `drawingStorageAccountName` using managed
identity authentication.

### Details
I found no good way to deploy both the code and the IaC in one go, so this will only deploy the IaC and then instruct the function to download the function code from a public storage account through a environment variable:
https://cloudnetdrawappstorage.blob.core.windows.net/cloudnetdrawapp/function.zip 

Environment variables provided to the Function App:

- `DRAWING_STORAGE_URL` – blob endpoint of the drawing storage account
- `DRAWING_CONTAINER_NAME` – container where diagrams are stored (`drawfunc`)

### Requirements
After the function is deployed the user needs to add access to the azure environment they would like to map! The function will create a managed identity (system assigned identity) during deployment.
The function will use this identity to access azure resources, so without granting access to the identity there will only be empty drawings.

### Additional
I added CORS header for https://portal.azure.com which allows us to run the function manually from within the portal.
