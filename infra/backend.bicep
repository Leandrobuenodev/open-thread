targetScope = 'resourceGroup'

param environmentName string = 'dev'
param containerAppsLocation string = 'brazilsouth'
// Existing resource base names are identities, not current product branding.
param containerAppName string
param containerAppsEnvironmentId string
param registryLoginServer string

@description('False retains the public placeholder for bootstrap. True rolls out the backend only after registry/identity bootstrap and image push.')
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

// Runtime storage only; resource creation remains in storage.bicep.
param storageAccountName string
param storageTableName string = 'OpenThreadWorkspace'
param storageBlobContainer string = 'attachments'

param appGitSha string = ''
param appBuildId string = ''
param appReleaseId string = ''
param appImageDigest string = ''

var commonTags = {
  project: 'open-thread'
  environment: environmentName
  managedBy: 'bicep'
}

resource containerApp 'Microsoft.App/containerApps@2025-07-01' = {
  name: containerAppName
  location: containerAppsLocation
  identity: { type: 'SystemAssigned' }
  properties: {
    environmentId: containerAppsEnvironmentId
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      // Intentionally omit maxInactiveRevisions: Azure defaults to 100 retained
      // inactive revisions, not 100 running replicas. No retention change here.
      ingress: {
        external: true
        transport: 'http'
        // HTTP uses targetPort behind HTTPS ingress. exposedPort is TCP-only;
        // omit the live zero sentinel rather than declare an unused TCP port.
        targetPort: deployBackend ? 8000 : 80
        allowInsecure: false
        traffic: [{ latestRevision: true, weight: 100 }]
      }
      registries: deployBackend ? [{ server: registryLoginServer, identity: 'system' }] : []
      secrets: deployBackend ? [{ name: 'foundry-api-key', value: foundryApiKey }] : []
    }
    template: {
      containers: [
        {
          name: deployBackend ? 'backend' : 'placeholder'
          image: deployBackend ? backendImageReference : 'mcr.microsoft.com/k8se/quickstart:latest'
          env: deployBackend
            ? [
                { name: 'STORAGE_AUTH_MODE', value: 'managed_identity' }
                { name: 'STORAGE_ACCOUNT_NAME', value: storageAccountName }
                { name: 'STORAGE_TABLE_ENDPOINT', value: 'https://${storageAccountName}.table.${environment().suffixes.storage}' }
                { name: 'STORAGE_BLOB_ENDPOINT', value: 'https://${storageAccountName}.blob.${environment().suffixes.storage}' }
                { name: 'STORAGE_TABLE_NAME', value: storageTableName }
                { name: 'STORAGE_BLOB_CONTAINER', value: storageBlobContainer }
                { name: 'ENTRA_AUTHORITY', value: entraAuthority }
                { name: 'ENTRA_API_AUDIENCE', value: entraApiAudience }
                { name: 'ENTRA_REQUIRED_SCOPE', value: entraRequiredScope }
                { name: 'FOUNDRY_ENDPOINT', value: foundryEndpoint }
                { name: 'FOUNDRY_DEPLOYMENT', value: foundryDeployment }
                { name: 'FRONTEND_ORIGIN', value: frontendOrigin }
                { name: 'CHAT_RATE_LIMIT_REQUESTS', value: string(chatRateLimitRequests) }
                { name: 'CHAT_RATE_LIMIT_WINDOW_SECONDS', value: string(chatRateLimitWindowSeconds) }
                { name: 'CHAT_MAX_CONCURRENCY', value: string(chatMaxConcurrency) }
                { name: 'CHAT_MAX_BODY_BYTES', value: string(chatMaxBodyBytes) }
                { name: 'CHAT_MAX_MESSAGE_BYTES', value: string(chatMaxMessageBytes) }
                { name: 'FOUNDRY_MAX_OUTPUT_TOKENS', value: string(foundryMaxOutputTokens) }
                { name: 'APP_GIT_SHA', value: appGitSha }
                { name: 'APP_BUILD_ID', value: appBuildId }
                { name: 'APP_RELEASE_ID', value: appReleaseId }
                { name: 'APP_ENVIRONMENT', value: environmentName }
                { name: 'APP_IMAGE_DIGEST', value: appImageDigest }
                { name: 'FOUNDRY_API_KEY', secretRef: 'foundry-api-key' }
              ]
            : []
          probes: deployBackend
            ? [
                {
                  type: 'Startup'
                  httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
                  periodSeconds: 5
                  timeoutSeconds: 3
                  failureThreshold: 30
                }
                {
                  type: 'Readiness'
                  httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
                  initialDelaySeconds: 5
                  periodSeconds: 10
                  timeoutSeconds: 3
                  failureThreshold: 3
                }
                {
                  type: 'Liveness'
                  httpGet: { path: '/health', port: 8000, scheme: 'HTTP' }
                  initialDelaySeconds: 10
                  periodSeconds: 30
                  timeoutSeconds: 3
                  failureThreshold: 3
                }
              ]
            : []
          resources: { cpu: json('0.25'), memory: '0.5Gi' }
        }
      ]
      scale: {
        // Intentionally use API defaults: cooldownPeriod=300 seconds for KEDA
        // scale-to-zero and pollingInterval=30 seconds for event-source polling.
        // Polling interval does not apply to HTTP/TCP scaling.
        minReplicas: 0
        maxReplicas: 2
      }
    }
  }
  tags: commonTags
}

output containerAppName string = containerApp.name
output containerAppId string = containerApp.id
output principalId string = containerApp.identity.principalId
