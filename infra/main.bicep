targetScope = 'resourceGroup'

param environmentName string = 'dev'
param containerAppsLocation string = 'brazilsouth'
// Existing resource base names are identities, not current product branding.
param staticWebAppName string
param containerAppsEnvironmentName string
param containerAppName string
@minLength(5)
@maxLength(37)
param containerRegistryBaseName string = 'openthreaddevacr'

@description('False prepares ACR and the existing app identity using the public placeholder. True rolls out the backend only after bootstrap and image push.')
param deployBackend bool = false
param backendImageReference string = ''
@secure()
@description('Supply only through a protected deployment parameter file. No real key in source, CLI arguments or outputs.')
param foundryApiKey string = ''

@minLength(1)
param entraAuthority string
@minLength(1)
param entraApiAudience string
@minLength(1)
param entraRequiredScope string
@minLength(1)
param foundryEndpoint string
param foundryDeployment string = 'openthread-chat'
@minLength(1)
param frontendOrigin string

@minValue(1)
param chatRateLimitRequests int = 5
@minValue(1)
param chatRateLimitWindowSeconds int = 60
@minValue(1)
param chatMaxConcurrency int = 1
@minValue(1)
param chatMaxBodyBytes int = 65536
@minValue(1)
param chatMaxMessageBytes int = 512
@minValue(1)
param foundryMaxOutputTokens int = 256

param storageAccountName string = 'openthread${take(environmentName, 3)}${take(uniqueString(resourceGroup().id), 10)}'

param appGitSha string = ''
param appBuildId string = ''
param appReleaseId string = ''
param appImageDigest string = ''

var nameSuffix = uniqueString(resourceGroup().id)
var registryName = toLower('${containerRegistryBaseName}${nameSuffix}')
var registryLoginServer = '${registryName}.azurecr.io'
var appName = '${containerAppName}-${nameSuffix}'
var commonTags = {
  project: 'open-thread'
  environment: environmentName
  managedBy: 'bicep'
}

// Preserve these existing resources without changing SKU, properties or names.
resource staticWebApp 'Microsoft.Web/staticSites@2025-03-01' existing = {
  name: '${staticWebAppName}-${nameSuffix}'
}
resource containerAppsEnvironment 'Microsoft.App/managedEnvironments@2025-07-01' existing = {
  name: '${containerAppsEnvironmentName}-${nameSuffix}'
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: registryName
  location: containerAppsLocation
  sku: { name: 'Basic' }
  properties: { adminUserEnabled: false }
  tags: commonTags
}

module containerApp './backend.bicep' = {
  name: 'openthread-backend-config'
  params: {
    containerAppName: appName
    containerAppsEnvironmentId: containerAppsEnvironment.id
    registryLoginServer: registryLoginServer
    environmentName: environmentName
    containerAppsLocation: containerAppsLocation
    deployBackend: deployBackend
    backendImageReference: backendImageReference
    foundryApiKey: foundryApiKey
    entraAuthority: entraAuthority
    entraApiAudience: entraApiAudience
    entraRequiredScope: entraRequiredScope
    foundryEndpoint: foundryEndpoint
    foundryDeployment: foundryDeployment
    frontendOrigin: frontendOrigin
    chatRateLimitRequests: chatRateLimitRequests
    chatRateLimitWindowSeconds: chatRateLimitWindowSeconds
    chatMaxConcurrency: chatMaxConcurrency
    chatMaxBodyBytes: chatMaxBodyBytes
    chatMaxMessageBytes: chatMaxMessageBytes
    foundryMaxOutputTokens: foundryMaxOutputTokens
    storageAccountName: storageAccountName
    appGitSha: appGitSha
    appBuildId: appBuildId
    appReleaseId: appReleaseId
    appImageDigest: appImageDigest
  }
}

resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistry.id, resourceId('Microsoft.App/containerApps', appName), 'AcrPull')
  scope: containerRegistry
  properties: {
    principalId: containerApp.outputs.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7f951dda-4ed3-4680-a7ca-43fe172d538d'
    )
  }
}

output staticWebAppName string = staticWebApp.name
output frontendOrigin string = 'https://${staticWebApp.properties.defaultHostname}'
output frontendRedirectUri string = 'https://${staticWebApp.properties.defaultHostname}/redirect.html'
output containerAppName string = containerApp.outputs.containerAppName
output containerRegistryName string = containerRegistry.name
output containerRegistryLoginServer string = registryLoginServer
