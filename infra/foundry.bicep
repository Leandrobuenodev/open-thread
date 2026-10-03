targetScope = 'resourceGroup'

@description('Base name for the new inference account and its custom subdomain. A resource-group suffix is appended.')
@minLength(2)
@maxLength(50)
param accountBaseName string

@description('Reviewed DEV region. Resource-group metadata location does not determine inference location.')
@allowed(['brazilsouth'])
param location string

@description('Deployment name supplied to the backend as FOUNDRY_DEPLOYMENT.')
@minLength(1)
@maxLength(64)
param deploymentName string

@description('Capacity units require subscription quota review. Reviewed DEV allocation: 1 unit; this is not a fixed-price PTU reservation or a spending limit.')
@minValue(1)
@maxValue(10)
param deploymentCapacity int

var accountName = toLower('${accountBaseName}-${uniqueString(resourceGroup().id)}')

// An OpenAI-kind account is sufficient for the existing Foundry v1 REST client.
// No project, hub, identity, role assignment, storage, or general infra modules.
resource account 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    disableLocalAuth: false
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
  tags: {
    project: 'open-thread'
    environment: 'dev'
    managedBy: 'bicep'
  }
}

resource chatDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: account
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4.1-mini'
      version: '2025-04-14'
    }
    // Keep the reviewed version explicit; revisit before its retirement date.
    versionUpgradeOption: 'NoAutoUpgrade'
  }
}

// Resource root only: the application appends /openai/v1/chat/completions.
output foundryEndpoint string = account.properties.endpoint
output foundryDeployment string = chatDeployment.name
output foundryAccountName string = account.name
