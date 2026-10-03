using './foundry.bicep'

param accountBaseName = 'openthread-dev-foundry'
param location = 'brazilsouth'
param deploymentName = 'openthread-chat'

// Reconfirmed quota: 200 units free on 2026-10-01. Explicit review remains
// mandatory. Validate the 1-unit DEV candidate with ARM before provisioning.
param deploymentCapacity = int(readEnvironmentVariable('FOUNDRY_REVIEWED_CAPACITY'))
