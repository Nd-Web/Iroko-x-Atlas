// Separate scheduled worker; the existing manual job is retained.
param location string = 'eastus2'
param environmentId string
param registryIdentityId string
param image string
param embeddingEndpoint string
param cronExpression string = '*/5 * * * *'
// Compliance graph extraction (graph:* and graph_ws:* jobs). The worker uses the primary
// Responses model only: an outage defers jobs instead of downgrading to a test model.
param responsesEndpoint string
param responsesDeployment string = 'gpt-6.1-sol-1'
param complianceGraphEnabled bool = true
param graphDailyTokenBudget string = '2000000'
param graphWorkspaceDailyTokenBudget string = '1000000'
param graphTokensPerMinute string = '30000'

@secure()
param responsesApiKey string
@secure()
param databaseUrl string
@secure()
param storageConnectionString string
@secure()
param searchKey string
@secure()
param embeddingKey string
@secure()
param documentIntelligenceKey string

resource worker 'Microsoft.App/jobs@2024-03-01' = {
  name: 'iroko-document-worker'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${registryIdentityId}': {} }
  }
  properties: {
    environmentId: environmentId
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 900
      replicaRetryLimit: 0
      scheduleTriggerConfig: {
        cronExpression: cronExpression
        parallelism: 1
        replicaCompletionCount: 1
      }
      registries: [{ server: 'irokoai.azurecr.io', identity: registryIdentityId }]
      secrets: [
        { name: 'database-url', value: databaseUrl }
        { name: 'storage-conn', value: storageConnectionString }
        { name: 'search-key', value: searchKey }
        { name: 'embedding-key', value: embeddingKey }
        { name: 'docintel-key', value: documentIntelligenceKey }
        { name: 'responses-key', value: responsesApiKey }
      ]
    }
    template: {
      containers: [{
        name: 'ingestion'
        image: image
        command: ['python']
        args: ['-m', 'ingestion', 'scheduled-drain', '--max-seconds', '240']
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: [
          { name: 'DATABASE_URL', secretRef: 'database-url' }
          { name: 'DOCUMENT_PIPELINE_ENABLED', value: 'true' }
          { name: 'AZURE_STORAGE_CONNECTION_STRING', secretRef: 'storage-conn' }
          { name: 'AZURE_STORAGE_CONTAINER', value: 'iroko-documents' }
          { name: 'AZURE_SEARCH_ENDPOINT', value: 'https://irokoai.search.windows.net' }
          { name: 'AZURE_SEARCH_INDEX_NAME', value: 'iroko-chunks' }
          { name: 'AZURE_SEARCH_SEMANTIC_CONFIG', value: 'iroko-semantic' }
          { name: 'AZURE_SEARCH_API_KEY', secretRef: 'search-key' }
          { name: 'AZURE_OPENAI_EMBEDDING_ENDPOINT', value: embeddingEndpoint }
          { name: 'AZURE_OPENAI_EMBEDDING_API_VERSION', value: '2025-01-01-preview' }
          { name: 'AZURE_OPENAI_EMBEDDING_DEPLOYMENT', value: 'text-embedding-3-large' }
          { name: 'AZURE_OPENAI_EMBEDDING_API_KEY', secretRef: 'embedding-key' }
          { name: 'AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT', value: 'https://irokoai.cognitiveservices.azure.com/' }
          { name: 'AZURE_DOCUMENT_INTELLIGENCE_KEY', secretRef: 'docintel-key' }
          { name: 'DOCINTEL_DAILY_PAGE_BUDGET', value: '500' }
          { name: 'DOCINTEL_MAX_PAGES_PER_DOCUMENT', value: '50' }
          { name: 'WORKSPACE_DAILY_OCR_PAGES', value: '200' }
          { name: 'AZURE_OPENAI_RESPONSES_ENDPOINT', value: responsesEndpoint }
          { name: 'AZURE_OPENAI_RESPONSES_DEPLOYMENT', value: responsesDeployment }
          { name: 'AZURE_OPENAI_RESPONSES_API_KEY', secretRef: 'responses-key' }
          { name: 'LLM_FALLBACK', value: 'false' }
          { name: 'COMPLIANCE_GRAPH_ENABLED', value: complianceGraphEnabled ? 'true' : 'false' }
          { name: 'GRAPH_DAILY_TOKEN_BUDGET', value: graphDailyTokenBudget }
          { name: 'GRAPH_WORKSPACE_DAILY_TOKEN_BUDGET', value: graphWorkspaceDailyTokenBudget }
          { name: 'GRAPH_TOKENS_PER_MINUTE', value: graphTokensPerMinute }
          { name: 'GRAPH_JOB_TIME_BOX_SECONDS', value: '150' }
        ]
      }]
    }
  }
}

output workerId string = worker.id
