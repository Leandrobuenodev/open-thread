using './budget.bicep'

param budgetName = readEnvironmentVariable('OPENTHREAD_BUDGET_NAME', 'budget-openthread-dev')
param monthlyAmount = 20
param notificationEmail = readEnvironmentVariable('OPENTHREAD_BUDGET_NOTIFICATION_EMAIL')
param budgetStartDate = '2026-09-01T00:00:00Z'
param budgetEndDate = '2036-09-01T00:00:00Z'
