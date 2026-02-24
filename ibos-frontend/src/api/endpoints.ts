export const endpoints = {
  auth: {
    register: "/auth/register",
    registerWithInvite: "/auth/register-with-invite",
    login: "/auth/login",
    token: "/auth/token",
    google: "/auth/google",
    refresh: "/auth/refresh",
    logout: "/auth/logout",
    changePassword: "/auth/change-password",
    me: "/auth/me"
  },
  dashboard: {
    summary: "/dashboard/summary",
    customerInsights: "/dashboard/customer-insights",
    creditProfile: "/dashboard/credit-profile",
    creditProfileV2: "/dashboard/credit-profile/v2",
    creditForecast: "/dashboard/credit-forecast",
    creditScenarioSimulate: "/dashboard/credit-scenarios/simulate",
    creditExportPack: "/dashboard/credit-export-pack",
    financeGuardrailsPolicy: "/dashboard/finance-guardrails/policy",
    financeGuardrailsEvaluate: "/dashboard/finance-guardrails/evaluate",
    creditImprovementPlan: "/dashboard/credit-improvement-plan"
  },
  products: {
    base: "/products",
    variants: (productId: string) => `/products/${productId}/variants`,
    publish: (productId: string) => `/products/${productId}/publish`,
    publishVariant: (productId: string, variantId: string) =>
      `/products/${productId}/variants/${variantId}/publish`
  },
  storefront: {
    config: "/storefront/config",
    domainStatus: "/storefront/config/domain/status",
    domainChallenge: "/storefront/config/domain/challenge",
    domainVerify: "/storefront/config/domain/verify",
    publicStore: (slug: string) => `/storefront/public/${slug}`,
    publicProducts: (slug: string) => `/storefront/public/${slug}/products`,
    publicProductDetail: (slug: string, productId: string) =>
      `/storefront/public/${slug}/products/${productId}`
  },
  checkout: {
    sessions: "/checkout-sessions",
    sessionRetryPayment: (checkoutSessionId: string) =>
      `/checkout-sessions/${checkoutSessionId}/retry-payment`,
    paymentsSummary: "/checkout-sessions/payments-summary"
  },
  shipping: {
    settings: "/shipping/settings",
    quoteCheckoutRate: (sessionToken: string) => `/shipping/checkout/${sessionToken}/quote`,
    selectCheckoutRate: (sessionToken: string) => `/shipping/checkout/${sessionToken}/select-rate`,
    selectedCheckoutRate: (sessionToken: string) => `/shipping/checkout/${sessionToken}/selected-rate`,
    shipments: "/shipping/shipments",
    syncTracking: (shipmentId: string) => `/shipping/shipments/${shipmentId}/sync-tracking`
  },
  locations: {
    base: "/locations",
    location: (locationId: string) => `/locations/${locationId}`,
    membershipScopes: (locationId: string) => `/locations/${locationId}/membership-scopes`,
    membershipScope: (locationId: string, membershipId: string) =>
      `/locations/${locationId}/membership-scopes/${membershipId}`,
    stockIn: (locationId: string) => `/locations/${locationId}/stock-in`,
    adjust: (locationId: string) => `/locations/${locationId}/adjust`,
    stock: (locationId: string, variantId: string) => `/locations/${locationId}/stock/${variantId}`,
    stockOverview: (variantId: string) => `/locations/stock-overview/${variantId}`,
    transfers: "/locations/transfers",
    lowStock: "/locations/low-stock",
    orderAllocations: "/locations/order-allocations"
  },
  integrations: {
    secrets: "/integrations/secrets",
    apps: "/integrations/apps",
    installApp: "/integrations/apps/install",
    disconnectApp: (installationId: string) => `/integrations/apps/${installationId}/disconnect`,
    emitOutbox: "/integrations/outbox/emit",
    outboxEvents: "/integrations/outbox/events",
    dispatchOutbox: "/integrations/outbox/dispatch",
    messages: "/integrations/messages",
    sendMessage: "/integrations/messages/send"
  },
  developer: {
    scopeCatalog: "/developer/api/scopes",
    apiKeys: "/developer/api-keys",
    rotateApiKey: (apiKeyId: string) => `/developer/api-keys/${apiKeyId}/rotate`,
    revokeApiKey: (apiKeyId: string) => `/developer/api-keys/${apiKeyId}/revoke`,
    webhookSubscriptions: "/developer/webhooks/subscriptions",
    webhookSubscription: (subscriptionId: string) => `/developer/webhooks/subscriptions/${subscriptionId}`,
    rotateWebhookSecret: (subscriptionId: string) => `/developer/webhooks/subscriptions/${subscriptionId}/rotate-secret`,
    webhookDeliveries: "/developer/webhooks/deliveries",
    dispatchWebhookDeliveries: "/developer/webhooks/deliveries/dispatch",
    portalDocs: "/developer/portal/docs",
    marketplaceApps: "/developer/marketplace/apps",
    submitMarketplaceApp: (listingId: string) => `/developer/marketplace/apps/${listingId}/submit`,
    reviewMarketplaceApp: (listingId: string) => `/developer/marketplace/apps/${listingId}/review`,
    publishMarketplaceApp: (listingId: string) => `/developer/marketplace/apps/${listingId}/publish`
  },
  publicApi: {
    me: "/public/v1/me",
    products: "/public/v1/products",
    orders: "/public/v1/orders",
    customers: "/public/v1/customers"
  },
  campaigns: {
    segments: "/campaigns/segments",
    segment: (segmentId: string) => `/campaigns/segments/${segmentId}`,
    previewSegment: (segmentId: string) => `/campaigns/segments/${segmentId}/preview`,
    templates: "/campaigns/templates",
    template: (templateId: string) => `/campaigns/templates/${templateId}`,
    consent: "/campaigns/consent",
    base: "/campaigns",
    campaignDispatch: (campaignId: string) => `/campaigns/${campaignId}/dispatch`,
    campaignRecipients: (campaignId: string) => `/campaigns/${campaignId}/recipients`,
    metrics: "/campaigns/metrics",
    campaignMetrics: (campaignId: string) => `/campaigns/${campaignId}/metrics`,
    retentionTriggers: "/campaigns/retention-triggers",
    runRetentionTrigger: (triggerId: string) => `/campaigns/retention-triggers/${triggerId}/run`
  },
  automation: {
    templates: "/automations/templates",
    installTemplate: "/automations/templates/install",
    rules: "/automations/rules",
    rule: (ruleId: string) => `/automations/rules/${ruleId}`,
    testRule: (ruleId: string) => `/automations/rules/${ruleId}/test`,
    runOutbox: "/automations/outbox/run",
    runs: "/automations/runs",
    run: (runId: string) => `/automations/runs/${runId}`
  },
  analytics: {
    refreshMart: "/analytics/mart/refresh",
    channelProfitability: "/analytics/channel-profitability",
    cohorts: "/analytics/cohorts",
    inventoryAging: "/analytics/inventory-aging",
    attributionEvents: "/analytics/attribution-events",
    exportReport: "/analytics/reports/export",
    reportSchedules: "/analytics/reports/schedules"
  },
  pos: {
    openShift: "/pos/shifts/open",
    currentShift: "/pos/shifts/current",
    closeShift: (shiftId: string) => `/pos/shifts/${shiftId}/close`,
    syncOfflineOrders: "/pos/offline-orders/sync"
  },
  privacy: {
    rbacMatrix: "/privacy/rbac/matrix",
    exportCustomer: (customerId: string) => `/privacy/customers/${customerId}/export`,
    deleteCustomer: (customerId: string) => `/privacy/customers/${customerId}`,
    archiveAuditLogs: "/privacy/audit-archive"
  },
  inventory: {
    stockIn: "/inventory/stock-in",
    adjust: "/inventory/adjust",
    stock: (variantId: string) => `/inventory/stock/${variantId}`,
    ledger: "/inventory/ledger",
    lowStock: "/inventory/low-stock"
  },
  sales: {
    base: "/sales",
    refund: (saleId: string) => `/sales/${saleId}/refund`,
    refundOptions: (saleId: string) => `/sales/${saleId}/refund-options`
  },
  orders: {
    base: "/orders",
    status: (orderId: string) => `/orders/${orderId}/status`
  },
  invoices: {
    base: "/invoices",
    fxQuote: "/invoices/fx-quote",
    templates: "/invoices/templates",
    aging: "/invoices/aging",
    statements: "/invoices/statements",
    statementsExport: "/invoices/statements/export",
    runDueReminders: "/invoices/reminders/run-due",
    send: (invoiceId: string) => `/invoices/${invoiceId}/send`,
    markPaid: (invoiceId: string) => `/invoices/${invoiceId}/mark-paid`,
    reminders: (invoiceId: string) => `/invoices/${invoiceId}/reminders`,
    payments: (invoiceId: string) => `/invoices/${invoiceId}/payments`,
    installments: (invoiceId: string) => `/invoices/${invoiceId}/installments`,
    reminderPolicy: (invoiceId: string) => `/invoices/${invoiceId}/reminder-policy`
  },
  customers: {
    base: "/customers",
    customer: (customerId: string) => `/customers/${customerId}`,
    tags: "/customers/tags",
    customerTag: (customerId: string, tagId: string) => `/customers/${customerId}/tags/${tagId}`
  },
  expenses: {
    base: "/expenses"
  },
  ai: {
    ask: "/ai/ask",
    daily: "/ai/insights/daily",
    refreshFeatureStore: "/ai/feature-store/refresh",
    latestFeatureStore: "/ai/feature-store/latest",
    generateInsightsV2: "/ai/insights/v2/generate",
    insightsV2: "/ai/insights/v2",
    actions: "/ai/actions",
    actionDecision: (actionId: string) => `/ai/actions/${actionId}/decision`,
    analyticsAssistantQuery: "/ai/analytics-assistant/query",
    riskAlertsConfig: "/ai/risk-alerts/config",
    riskAlertsRun: "/ai/risk-alerts/run",
    riskAlertsEvents: "/ai/risk-alerts/events",
    governanceTraces: "/ai/governance/traces",
    governanceTraceDetail: (traceId: string) => `/ai/governance/traces/${traceId}`
  },
  team: {
    members: "/team/members",
    member: (membershipId: string) => `/team/members/${membershipId}`,
    invitations: "/team/invitations",
    invitation: (invitationId: string) => `/team/invitations/${invitationId}`,
    acceptInvitation: "/team/invitations/accept"
  },
  audit: {
    base: "/audit-logs"
  }
} as const;
