targetScope = 'resourceGroup'
param environmentName string = 'dev'
param location string = resourceGroup().location
@minLength(3)
@maxLength(24)
param storageAccountName string = 'openthread${take(environmentName, 3)}${take(uniqueString(resourceGroup().id), 10)}'
@description('Existing ACA system-assigned Managed Identity principal ID. No ACA changes.')
param containerAppPrincipalId string
var tags = { project: 'open-thread', environment: environmentName, managedBy: 'bicep' }
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
  }
}
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}
resource attachments 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: 'attachments'
  properties: { publicAccess: 'None' }
}
resource tableService 'Microsoft.Storage/storageAccounts/tableServices@2023-05-01' = {
  parent: storage
  name: 'default'
}
resource workspace 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-05-01' = {
  parent: tableService
  name: 'OpenThreadWorkspace'
}
var tableRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '0a9a7e1f-b9d0-4cc4-a60d-0319b160aaa3')
var blobRole = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
resource tableAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, containerAppPrincipalId, tableRole)
  properties: { roleDefinitionId: tableRole, principalId: containerAppPrincipalId, principalType: 'ServicePrincipal' }
}
resource blobAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, containerAppPrincipalId, blobRole)
  properties: { roleDefinitionId: blobRole, principalId: containerAppPrincipalId, principalType: 'ServicePrincipal' }
}
output storageAccountName string = storage.name
output tableEndpoint string = storage.properties.primaryEndpoints.table
output blobEndpoint string = storage.properties.primaryEndpoints.blob
