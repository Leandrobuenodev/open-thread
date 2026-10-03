targetScope = 'resourceGroup'

@description('Name of the resource-group-scoped monthly cost budget.')
param budgetName string

@description('Monthly budget amount in the subscription currency.')
param monthlyAmount int

@description('Email address that receives budget notifications.')
param notificationEmail string

@description('First day of the month from which budget tracking starts.')
param budgetStartDate string

@description('End date for the budget tracking period.')
param budgetEndDate string

resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: budgetName
  properties: {
    amount: monthlyAmount
    category: 'Cost'
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
      endDate: budgetEndDate
    }
    notifications: {
      'Actual_GreaterThanOrEqualTo_50.000000_Percent': {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactEmails: [
          notificationEmail
        ]
        locale: 'pt-br'
      }
      'Actual_GreaterThanOrEqualTo_80.000000_Percent': {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 80
        thresholdType: 'Actual'
        contactEmails: [
          notificationEmail
        ]
        locale: 'pt-br'
      }
      'Actual_GreaterThanOrEqualTo_100.000000_Percent': {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Actual'
        contactEmails: [
          notificationEmail
        ]
        locale: 'pt-br'
      }
    }
  }
}

output budgetName string = budget.name
output monthlyAmount int = monthlyAmount
output notificationEmail string = notificationEmail
