using './storage.bicep'
param environmentName = 'dev'
param location = 'brazilsouth'
param containerAppPrincipalId = readEnvironmentVariable('OPENTHREAD_ACA_PRINCIPAL_ID')
