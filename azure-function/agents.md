# cloudnet-draw-full-selfhost
This solution aims to do the following.
Deploy an azure function with system assigned identity running the code within /function on a time-trigger each 24hrs

The function uses the identity to query the azure environment with azure_query.py and then store the network information as a json file in memory.
The python files HLD.py and MLD.py will then in turn use the JSON file to generate drawio diagrams.
When done the function will then again use its managed identity to store the created files in a blob storage which is provisioned with the solution.
The function identity must be assigned "Storage Blob Data Contributor" on the storage account during build.
The storage account is referenced in the function, so this needs to be a variable shared from the bicep to get the storage account working with the function.

The solution is to be hosted in a public repo so that we can use the Deploy To Azure button in readme to deploy the full solution in any tenant.



