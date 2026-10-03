using './main.bicep'

param environmentName = 'dev'
param containerAppsLocation = 'brazilsouth'
// Keep existing Azure identities; these are not requests to rename resources.
param staticWebAppName = readEnvironmentVariable('OPENTHREAD_STATIC_WEB_APP_BASE_NAME', 'replace-with-swa-base-name')
param containerAppsEnvironmentName = readEnvironmentVariable('OPENTHREAD_CONTAINER_APPS_ENVIRONMENT_BASE_NAME', 'replace-with-environment-base-name')
param containerAppName = readEnvironmentVariable('OPENTHREAD_CONTAINER_APP_BASE_NAME', 'replace-with-container-app-base-name')
param containerRegistryBaseName = readEnvironmentVariable('OPENTHREAD_ACR_BASE_NAME', 'openthreaddevacr')
param deployBackend = false
param backendImageReference = ''
// Protected runtime input. Empty for bootstrap; never put a real key here.
param foundryApiKey = readEnvironmentVariable('FOUNDRY_API_KEY_FOR_DEPLOYMENT', '')
param entraAuthority = readEnvironmentVariable('ENTRA_AUTHORITY', 'https://login.microsoftonline.com/replace-with-tenant-id/v2.0')
param entraApiAudience = readEnvironmentVariable('ENTRA_API_AUDIENCE', 'replace-with-api-client-id')
param entraRequiredScope = readEnvironmentVariable('ENTRA_REQUIRED_SCOPE', 'access_as_user')
param foundryEndpoint = readEnvironmentVariable('FOUNDRY_ENDPOINT', 'https://replace-with-account.openai.azure.com/')
param foundryDeployment = readEnvironmentVariable('FOUNDRY_DEPLOYMENT', 'openthread-chat')
param frontendOrigin = readEnvironmentVariable('OPENTHREAD_FRONTEND_ORIGIN', 'https://replace-with-site.azurestaticapps.net')

// For bootstrap, set base-name inputs to match existing resource identities.
// Routine delivery overrides full target names; placeholder defaults permit CI compilation only.
