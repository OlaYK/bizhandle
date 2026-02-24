import { apiClient } from "./client";
import { endpoints } from "./endpoints";
import type {
  AIAskIn,
  AIFeatureSnapshotOut,
  AIFeatureStoreFilter,
  AIInsightV2Filter,
  AIInsightV2ListOut,
  AIInsightsGenerateOut,
  AIPrescriptiveActionFilter,
  AIPrescriptiveActionListOut,
  AIPrescriptiveActionOut,
  AIPrescriptiveDecisionIn,
  AIResponseOut,
  AnalyticsDateFilter,
  AnalyticsMartRefreshOut,
  AutomationOutboxRunOut,
  AutomationRuleCreateIn,
  AutomationRuleFilter,
  AutomationRuleListOut,
  AutomationRuleOut,
  AutomationRuleRunListOut,
  AutomationRuleRunOut,
  AutomationRuleTestIn,
  AutomationRuleUpdateIn,
  AutomationRunFilter,
  AutomationTemplateCatalogOut,
  AutomationTemplateInstallIn,
  AutomationTemplateInstallOut,
  AppInstallationIn,
  AppInstallationListOut,
  AppInstallationOut,
  AuditArchiveOut,
  AuditLogFilter,
  AuditLogListOut,
  CashflowForecastOut,
  CampaignConsentListFilter,
  CampaignCreateIn,
  CampaignDispatchIn,
  CampaignDispatchOut,
  CampaignListFilter,
  CampaignListOut,
  CampaignMetricsOut,
  CampaignOut,
  CampaignRecipientListFilter,
  CampaignRecipientListOut,
  CampaignSegmentListFilter,
  CampaignTemplateCreateIn,
  CampaignTemplateListFilter,
  CampaignTemplateListOut,
  CampaignTemplateOut,
  CampaignTemplateUpdateIn,
  ChangePasswordIn,
  CheckoutPaymentsSummaryOut,
  CheckoutSessionCreateIn,
  CheckoutSessionCreateOut,
  CheckoutSessionListOut,
  CheckoutSessionRetryPaymentOut,
  CustomerConsentListOut,
  CustomerConsentOut,
  CustomerConsentUpsertIn,
  CustomerCreateIn,
  CustomerCreateOut,
  CustomerFilter,
  CustomerPiiDeleteOut,
  CustomerPiiExportOut,
  CustomerListOut,
  CustomerOut,
  CustomerSegmentCreateIn,
  CustomerSegmentListOut,
  CustomerSegmentOut,
  CustomerSegmentUpdateIn,
  CustomerTagCreateIn,
  CustomerTagListOut,
  CustomerTagOut,
  CustomerUpdateIn,
  CreditProfileOut,
  CreditExportPackFilter,
  CreditProfileV2Filter,
  CreditProfileV2Out,
  CreditForecastFilter,
  CreditImprovementPlanFilter,
  CreditImprovementPlanOut,
  CreditScenarioSimulateIn,
  CreditScenarioSimulationOut,
  DashboardCustomerInsightsOut,
  DashboardSummaryOut,
  DeveloperPortalDocsOut,
  DateFilter,
  ExpenseCreateIn,
  ExpenseCreateOut,
  ExpenseListOut,
  FinanceGuardrailEvaluationOut,
  FinanceGuardrailEvaluateFilter,
  FinanceGuardrailPolicyIn,
  FinanceGuardrailPolicyOut,
  ChannelProfitabilityOut,
  CohortFilter,
  CohortRetentionOut,
  IntegrationDispatchOut,
  IntegrationEmitOut,
  IntegrationEventEmitIn,
  IntegrationMessageListOut,
  IntegrationMessageOut,
  IntegrationMessageSendIn,
  IntegrationOutboxEventListOut,
  IntegrationOutboxFilter,
  IntegrationSecretListOut,
  IntegrationSecretOut,
  IntegrationSecretUpsertIn,
  InventoryAgingFilter,
  InventoryAgingOut,
  InvoiceAgingDashboardOut,
  InvoiceCreateIn,
  InvoiceCreateOut,
  InvoiceFilter,
  InvoiceFxQuoteOut,
  InvoiceInstallmentListOut,
  InvoiceInstallmentUpsertIn,
  InvoiceListOut,
  InvoiceMarkPaidIn,
  InvoiceOut,
  InvoicePaymentCreateIn,
  InvoicePaymentListOut,
  InvoicePaymentOut,
  InvoiceReminderIn,
  InvoiceReminderPolicyIn,
  InvoiceReminderPolicyOut,
  InvoiceReminderRunOut,
  InvoiceStatementExportOut,
  InvoiceStatementFilter,
  InvoiceStatementListOut,
  InvoiceTemplateFilter,
  InvoiceTemplateListOut,
  InvoiceTemplateOut,
  InvoiceTemplateUpsertIn,
  LoginIn,
  LocationCreateIn,
  LocationListFilter,
  LocationListOut,
  LocationLowStockFilter,
  LocationLowStockListOut,
  LocationMembershipScopeListOut,
  LocationMembershipScopeOut,
  LocationMembershipScopeUpsertIn,
  LocationOut,
  LocationStockAdjustIn,
  LocationStockInIn,
  LocationStockOverviewOut,
  LocationUpdateIn,
  LocationVariantStockOut,
  LogoutIn,
  MarketingAttributionEventIn,
  MarketingAttributionEventOut,
  MarketplaceListingCreateIn,
  MarketplaceListingFilter,
  MarketplaceListingListOut,
  MarketplaceListingOut,
  MarketplaceListingPublishIn,
  MarketplaceListingReviewIn,
  LenderExportPackOut,
  LowStockListOut,
  OrderCreateIn,
  OrderCreateOut,
  OrderFilter,
  OrderListOut,
  OrderLocationAllocationIn,
  OrderLocationAllocationOut,
  OrderOut,
  OrderStatusUpdateIn,
  PaginationFilter,
  ProductCreateIn,
  ProductCreateOut,
  ProductListOut,
  ProductPublishIn,
  ProductPublishOut,
  PublicApiBusinessOut,
  PublicApiCustomerListOut,
  PublicApiKeyCreateIn,
  PublicApiKeyCreateOut,
  PublicApiKeyListOut,
  PublicApiKeyOut,
  PublicApiKeyRotateOut,
  PublicApiOrderListOut,
  PublicApiProductListOut,
  PublicApiScopeCatalogOut,
  PublicStorefrontOut,
  PublicStorefrontProductDetailOut,
  PublicStorefrontProductListOut,
  PermissionMatrixOut,
  PosOfflineSyncIn,
  PosOfflineSyncOut,
  PosShiftCloseIn,
  PosShiftCurrentOut,
  PosShiftOpenIn,
  PosShiftOut,
  RefundCreateIn,
  RefreshIn,
  RegisterIn,
  RegisterWithInviteIn,
  SaleCreateIn,
  SaleCreateOut,
  SaleListOut,
  SaleRefundOptionsOut,
  SalesFilter,
  SegmentPreviewOut,
  ReportExportFilter,
  ReportExportOut,
  ReportScheduleCreateIn,
  ReportScheduleListOut,
  ReportScheduleOut,
  StorefrontConfigOut,
  StorefrontConfigUpsertIn,
  StorefrontDomainChallengeOut,
  StorefrontDomainStatusOut,
  StorefrontDomainVerifyIn,
  RetentionTriggerCreateIn,
  RetentionTriggerListOut,
  RetentionTriggerOut,
  RetentionTriggerRunOut,
  RetentionTriggerRunRequestIn,
  ShipmentCreateIn,
  ShipmentListFilter,
  ShipmentListOut,
  ShipmentOut,
  ShipmentTrackingSyncOut,
  ShippingQuoteIn,
  ShippingQuoteOut,
  ShippingRateSelectIn,
  ShippingRateSelectionOut,
  ShippingSettingsOut,
  ShippingSettingsUpsertIn,
  StockTransferCreateIn,
  StockTransferListOut,
  StockTransferOut,
  StockAdjustIn,
  StockIn,
  StockLevelOut,
  StockOut,
  TeamListFilter,
  TeamInvitationAcceptIn,
  TeamInvitationCreateIn,
  TeamInvitationCreateOut,
  TeamInvitationListFilter,
  TeamInvitationListOut,
  TeamMemberCreateIn,
  TeamMemberListOut,
  TeamMemberOut,
  TeamMemberUpdateIn,
  TokenOut,
  UpdateProfileIn,
  UserProfileOut,
  VariantCreateIn,
  VariantCreateOut,
  VariantPublishIn,
  VariantPublishOut,
  VariantListOut,
  WebhookDeliveryFilter,
  WebhookDeliveryListOut,
  WebhookDispatchOut,
  WebhookSubscriptionCreateIn,
  WebhookSubscriptionCreateOut,
  WebhookSubscriptionListOut,
  WebhookSubscriptionOut,
  WebhookSubscriptionRotateSecretOut,
  WebhookSubscriptionUpdateIn,
  InventoryLedgerListOut,
  OkOut
} from "./types";

export const authService = {
  register(payload: RegisterIn) {
    return apiClient
      .post<TokenOut>(endpoints.auth.register, payload)
      .then((res) => res.data);
  },
  registerWithInvite(payload: RegisterWithInviteIn) {
    return apiClient
      .post<TokenOut>(endpoints.auth.registerWithInvite, payload)
      .then((res) => res.data);
  },
  login(payload: LoginIn) {
    return apiClient
      .post<TokenOut>(endpoints.auth.login, payload)
      .then((res) => res.data);
  },
  refresh(payload: RefreshIn) {
    return apiClient
      .post<TokenOut>(endpoints.auth.refresh, payload)
      .then((res) => res.data);
  },
  logout(payload: LogoutIn) {
    return apiClient.post<OkOut>(endpoints.auth.logout, payload).then((res) => res.data);
  },
  changePassword(payload: ChangePasswordIn) {
    return apiClient
      .post<OkOut>(endpoints.auth.changePassword, payload)
      .then((res) => res.data);
  },
  me() {
    return apiClient.get<UserProfileOut>(endpoints.auth.me).then((res) => res.data);
  },
  updateProfile(payload: UpdateProfileIn) {
    return apiClient
      .patch<UserProfileOut>(endpoints.auth.me, payload)
      .then((res) => res.data);
  }
};

export const dashboardService = {
  summary(params?: DateFilter) {
    return apiClient
      .get<DashboardSummaryOut>(endpoints.dashboard.summary, { params })
      .then((res) => res.data);
  },
  customerInsights(params?: DateFilter) {
    return apiClient
      .get<DashboardCustomerInsightsOut>(endpoints.dashboard.customerInsights, { params })
      .then((res) => res.data);
  },
  creditProfile(params?: DateFilter) {
    return apiClient
      .get<CreditProfileOut>(endpoints.dashboard.creditProfile, { params })
      .then((res) => res.data);
  },
  creditProfileV2(params?: CreditProfileV2Filter) {
    return apiClient
      .get<CreditProfileV2Out>(endpoints.dashboard.creditProfileV2, { params })
      .then((res) => res.data);
  },
  creditForecast(params?: CreditForecastFilter) {
    return apiClient
      .get<CashflowForecastOut>(endpoints.dashboard.creditForecast, { params })
      .then((res) => res.data);
  },
  simulateCreditScenario(payload: CreditScenarioSimulateIn) {
    return apiClient
      .post<CreditScenarioSimulationOut>(endpoints.dashboard.creditScenarioSimulate, payload)
      .then((res) => res.data);
  },
  generateCreditExportPack(params?: CreditExportPackFilter) {
    return apiClient
      .post<LenderExportPackOut>(endpoints.dashboard.creditExportPack, null, { params })
      .then((res) => res.data);
  },
  getFinanceGuardrailsPolicy() {
    return apiClient
      .get<FinanceGuardrailPolicyOut>(endpoints.dashboard.financeGuardrailsPolicy)
      .then((res) => res.data);
  },
  updateFinanceGuardrailsPolicy(payload: FinanceGuardrailPolicyIn) {
    return apiClient
      .put<FinanceGuardrailPolicyOut>(endpoints.dashboard.financeGuardrailsPolicy, payload)
      .then((res) => res.data);
  },
  evaluateFinanceGuardrails(params?: FinanceGuardrailEvaluateFilter) {
    return apiClient
      .post<FinanceGuardrailEvaluationOut>(endpoints.dashboard.financeGuardrailsEvaluate, null, { params })
      .then((res) => res.data);
  },
  creditImprovementPlan(params?: CreditImprovementPlanFilter) {
    return apiClient
      .get<CreditImprovementPlanOut>(endpoints.dashboard.creditImprovementPlan, { params })
      .then((res) => res.data);
  }
};

export const productService = {
  list(params?: PaginationFilter) {
    return apiClient
      .get<ProductListOut>(endpoints.products.base, { params })
      .then((res) => res.data);
  },
  create(payload: ProductCreateIn) {
    return apiClient
      .post<ProductCreateOut>(endpoints.products.base, payload)
      .then((res) => res.data);
  },
  listVariants(productId: string, params?: PaginationFilter) {
    return apiClient
      .get<VariantListOut>(endpoints.products.variants(productId), { params })
      .then((res) => res.data);
  },
  createVariant(productId: string, payload: VariantCreateIn) {
    return apiClient
      .post<VariantCreateOut>(endpoints.products.variants(productId), payload)
      .then((res) => res.data);
  },
  setPublish(productId: string, payload: ProductPublishIn) {
    return apiClient
      .patch<ProductPublishOut>(endpoints.products.publish(productId), payload)
      .then((res) => res.data);
  },
  setVariantPublish(productId: string, variantId: string, payload: VariantPublishIn) {
    return apiClient
      .patch<VariantPublishOut>(endpoints.products.publishVariant(productId, variantId), payload)
      .then((res) => res.data);
  }
};

export const storefrontService = {
  getConfig() {
    return apiClient.get<StorefrontConfigOut>(endpoints.storefront.config).then((res) => res.data);
  },
  upsertConfig(payload: StorefrontConfigUpsertIn) {
    return apiClient
      .put<StorefrontConfigOut>(endpoints.storefront.config, payload)
      .then((res) => res.data);
  },
  getDomainStatus() {
    return apiClient
      .get<StorefrontDomainStatusOut>(endpoints.storefront.domainStatus)
      .then((res) => res.data);
  },
  createDomainChallenge() {
    return apiClient
      .post<StorefrontDomainChallengeOut>(endpoints.storefront.domainChallenge)
      .then((res) => res.data);
  },
  verifyDomain(payload: StorefrontDomainVerifyIn) {
    return apiClient
      .post<StorefrontDomainStatusOut>(endpoints.storefront.domainVerify, payload)
      .then((res) => res.data);
  },
  getPublicStorefront(slug: string) {
    return apiClient
      .get<PublicStorefrontOut>(endpoints.storefront.publicStore(slug))
      .then((res) => res.data);
  },
  listPublicProducts(
    slug: string,
    params?: PaginationFilter & { q?: string; category?: string }
  ) {
    return apiClient
      .get<PublicStorefrontProductListOut>(endpoints.storefront.publicProducts(slug), { params })
      .then((res) => res.data);
  },
  getPublicProductDetail(slug: string, productId: string) {
    return apiClient
      .get<PublicStorefrontProductDetailOut>(endpoints.storefront.publicProductDetail(slug, productId))
      .then((res) => res.data);
  }
};

export const checkoutService = {
  createSession(payload: CheckoutSessionCreateIn) {
    return apiClient
      .post<CheckoutSessionCreateOut>(endpoints.checkout.sessions, payload)
      .then((res) => res.data);
  },
  listSessions(
    params?: PaginationFilter & DateFilter & { status?: string; payment_provider?: string }
  ) {
    return apiClient
      .get<CheckoutSessionListOut>(endpoints.checkout.sessions, { params })
      .then((res) => res.data);
  },
  retryPayment(checkoutSessionId: string) {
    return apiClient
      .post<CheckoutSessionRetryPaymentOut>(endpoints.checkout.sessionRetryPayment(checkoutSessionId))
      .then((res) => res.data);
  },
  paymentsSummary(params?: DateFilter) {
    return apiClient
      .get<CheckoutPaymentsSummaryOut>(endpoints.checkout.paymentsSummary, { params })
      .then((res) => res.data);
  }
};

export const shippingService = {
  getSettings() {
    return apiClient
      .get<ShippingSettingsOut>(endpoints.shipping.settings)
      .then((res) => res.data);
  },
  upsertSettings(payload: ShippingSettingsUpsertIn) {
    return apiClient
      .put<ShippingSettingsOut>(endpoints.shipping.settings, payload)
      .then((res) => res.data);
  },
  quoteCheckoutRate(sessionToken: string, payload: ShippingQuoteIn) {
    return apiClient
      .post<ShippingQuoteOut>(endpoints.shipping.quoteCheckoutRate(sessionToken), payload)
      .then((res) => res.data);
  },
  selectCheckoutRate(sessionToken: string, payload: ShippingRateSelectIn) {
    return apiClient
      .post<ShippingRateSelectionOut>(endpoints.shipping.selectCheckoutRate(sessionToken), payload)
      .then((res) => res.data);
  },
  getSelectedCheckoutRate(sessionToken: string) {
    return apiClient
      .get<ShippingRateSelectionOut>(endpoints.shipping.selectedCheckoutRate(sessionToken))
      .then((res) => res.data);
  },
  createShipment(payload: ShipmentCreateIn) {
    return apiClient
      .post<ShipmentOut>(endpoints.shipping.shipments, payload)
      .then((res) => res.data);
  },
  listShipments(params?: ShipmentListFilter) {
    return apiClient
      .get<ShipmentListOut>(endpoints.shipping.shipments, { params })
      .then((res) => res.data);
  },
  syncTracking(shipmentId: string) {
    return apiClient
      .post<ShipmentTrackingSyncOut>(endpoints.shipping.syncTracking(shipmentId))
      .then((res) => res.data);
  }
};

export const locationService = {
  create(payload: LocationCreateIn) {
    return apiClient
      .post<LocationOut>(endpoints.locations.base, payload)
      .then((res) => res.data);
  },
  list(params?: LocationListFilter) {
    return apiClient
      .get<LocationListOut>(endpoints.locations.base, { params })
      .then((res) => res.data);
  },
  update(locationId: string, payload: LocationUpdateIn) {
    return apiClient
      .patch<LocationOut>(endpoints.locations.location(locationId), payload)
      .then((res) => res.data);
  },
  upsertMembershipScope(
    locationId: string,
    membershipId: string,
    payload: LocationMembershipScopeUpsertIn
  ) {
    return apiClient
      .put<LocationMembershipScopeOut>(
        endpoints.locations.membershipScope(locationId, membershipId),
        payload
      )
      .then((res) => res.data);
  },
  listMembershipScopes(locationId: string) {
    return apiClient
      .get<LocationMembershipScopeListOut>(endpoints.locations.membershipScopes(locationId))
      .then((res) => res.data);
  },
  stockIn(locationId: string, payload: LocationStockInIn) {
    return apiClient
      .post<LocationVariantStockOut>(endpoints.locations.stockIn(locationId), payload)
      .then((res) => res.data);
  },
  adjust(locationId: string, payload: LocationStockAdjustIn) {
    return apiClient
      .post<LocationVariantStockOut>(endpoints.locations.adjust(locationId), payload)
      .then((res) => res.data);
  },
  stock(locationId: string, variantId: string) {
    return apiClient
      .get<LocationVariantStockOut>(endpoints.locations.stock(locationId, variantId))
      .then((res) => res.data);
  },
  stockOverview(variantId: string) {
    return apiClient
      .get<LocationStockOverviewOut>(endpoints.locations.stockOverview(variantId))
      .then((res) => res.data);
  },
  createTransfer(payload: StockTransferCreateIn) {
    return apiClient
      .post<StockTransferOut>(endpoints.locations.transfers, payload)
      .then((res) => res.data);
  },
  listTransfers(params?: PaginationFilter) {
    return apiClient
      .get<StockTransferListOut>(endpoints.locations.transfers, { params })
      .then((res) => res.data);
  },
  lowStock(params?: LocationLowStockFilter) {
    return apiClient
      .get<LocationLowStockListOut>(endpoints.locations.lowStock, { params })
      .then((res) => res.data);
  },
  allocateOrder(payload: OrderLocationAllocationIn) {
    return apiClient
      .post<OrderLocationAllocationOut>(endpoints.locations.orderAllocations, payload)
      .then((res) => res.data);
  }
};

export const integrationService = {
  upsertSecret(payload: IntegrationSecretUpsertIn) {
    return apiClient
      .put<IntegrationSecretOut>(endpoints.integrations.secrets, payload)
      .then((res) => res.data);
  },
  listSecrets() {
    return apiClient
      .get<IntegrationSecretListOut>(endpoints.integrations.secrets)
      .then((res) => res.data);
  },
  installApp(payload: AppInstallationIn) {
    return apiClient
      .post<AppInstallationOut>(endpoints.integrations.installApp, payload)
      .then((res) => res.data);
  },
  listApps() {
    return apiClient
      .get<AppInstallationListOut>(endpoints.integrations.apps)
      .then((res) => res.data);
  },
  disconnectApp(installationId: string) {
    return apiClient
      .post<AppInstallationOut>(endpoints.integrations.disconnectApp(installationId))
      .then((res) => res.data);
  },
  emitOutboxEvent(payload: IntegrationEventEmitIn) {
    return apiClient
      .post<IntegrationEmitOut>(endpoints.integrations.emitOutbox, payload)
      .then((res) => res.data);
  },
  listOutboxEvents(params?: IntegrationOutboxFilter) {
    return apiClient
      .get<IntegrationOutboxEventListOut>(endpoints.integrations.outboxEvents, { params })
      .then((res) => res.data);
  },
  dispatchOutbox(limit?: number) {
    return apiClient
      .post<IntegrationDispatchOut>(endpoints.integrations.dispatchOutbox, undefined, {
        params: { limit }
      })
      .then((res) => res.data);
  },
  sendMessage(payload: IntegrationMessageSendIn) {
    return apiClient
      .post<IntegrationMessageOut>(endpoints.integrations.sendMessage, payload)
      .then((res) => res.data);
  },
  listMessages(params?: PaginationFilter) {
    return apiClient
      .get<IntegrationMessageListOut>(endpoints.integrations.messages, { params })
      .then((res) => res.data);
  }
};

export const campaignService = {
  createSegment(payload: CustomerSegmentCreateIn) {
    return apiClient
      .post<CustomerSegmentOut>(endpoints.campaigns.segments, payload)
      .then((res) => res.data);
  },
  listSegments(params?: CampaignSegmentListFilter) {
    return apiClient
      .get<CustomerSegmentListOut>(endpoints.campaigns.segments, { params })
      .then((res) => res.data);
  },
  updateSegment(segmentId: string, payload: CustomerSegmentUpdateIn) {
    return apiClient
      .patch<CustomerSegmentOut>(endpoints.campaigns.segment(segmentId), payload)
      .then((res) => res.data);
  },
  previewSegment(segmentId: string) {
    return apiClient
      .post<SegmentPreviewOut>(endpoints.campaigns.previewSegment(segmentId))
      .then((res) => res.data);
  },
  createTemplate(payload: CampaignTemplateCreateIn) {
    return apiClient
      .post<CampaignTemplateOut>(endpoints.campaigns.templates, payload)
      .then((res) => res.data);
  },
  listTemplates(params?: CampaignTemplateListFilter) {
    return apiClient
      .get<CampaignTemplateListOut>(endpoints.campaigns.templates, { params })
      .then((res) => res.data);
  },
  updateTemplate(templateId: string, payload: CampaignTemplateUpdateIn) {
    return apiClient
      .patch<CampaignTemplateOut>(endpoints.campaigns.template(templateId), payload)
      .then((res) => res.data);
  },
  upsertConsent(payload: CustomerConsentUpsertIn) {
    return apiClient
      .put<CustomerConsentOut>(endpoints.campaigns.consent, payload)
      .then((res) => res.data);
  },
  listConsents(params?: CampaignConsentListFilter) {
    return apiClient
      .get<CustomerConsentListOut>(endpoints.campaigns.consent, { params })
      .then((res) => res.data);
  },
  createCampaign(payload: CampaignCreateIn) {
    return apiClient
      .post<CampaignOut>(endpoints.campaigns.base, payload)
      .then((res) => res.data);
  },
  listCampaigns(params?: CampaignListFilter) {
    return apiClient
      .get<CampaignListOut>(endpoints.campaigns.base, { params })
      .then((res) => res.data);
  },
  dispatchCampaign(campaignId: string, payload?: CampaignDispatchIn) {
    return apiClient
      .post<CampaignDispatchOut>(endpoints.campaigns.campaignDispatch(campaignId), payload ?? {})
      .then((res) => res.data);
  },
  listRecipients(campaignId: string, params?: CampaignRecipientListFilter) {
    return apiClient
      .get<CampaignRecipientListOut>(endpoints.campaigns.campaignRecipients(campaignId), { params })
      .then((res) => res.data);
  },
  metrics() {
    return apiClient
      .get<CampaignMetricsOut>(endpoints.campaigns.metrics)
      .then((res) => res.data);
  },
  campaignMetrics(campaignId: string) {
    return apiClient
      .get<CampaignMetricsOut>(endpoints.campaigns.campaignMetrics(campaignId))
      .then((res) => res.data);
  },
  createRetentionTrigger(payload: RetentionTriggerCreateIn) {
    return apiClient
      .post<RetentionTriggerOut>(endpoints.campaigns.retentionTriggers, payload)
      .then((res) => res.data);
  },
  listRetentionTriggers(params?: PaginationFilter) {
    return apiClient
      .get<RetentionTriggerListOut>(endpoints.campaigns.retentionTriggers, { params })
      .then((res) => res.data);
  },
  runRetentionTrigger(triggerId: string, payload?: RetentionTriggerRunRequestIn) {
    return apiClient
      .post<RetentionTriggerRunOut>(endpoints.campaigns.runRetentionTrigger(triggerId), payload ?? {})
      .then((res) => res.data);
  }
};

export const automationService = {
  listTemplates() {
    return apiClient
      .get<AutomationTemplateCatalogOut>(endpoints.automation.templates)
      .then((res) => res.data);
  },
  installTemplate(payload: AutomationTemplateInstallIn) {
    return apiClient
      .post<AutomationTemplateInstallOut>(endpoints.automation.installTemplate, payload)
      .then((res) => res.data);
  },
  createRule(payload: AutomationRuleCreateIn) {
    return apiClient
      .post<AutomationRuleOut>(endpoints.automation.rules, payload)
      .then((res) => res.data);
  },
  listRules(params?: AutomationRuleFilter) {
    return apiClient
      .get<AutomationRuleListOut>(endpoints.automation.rules, { params })
      .then((res) => res.data);
  },
  updateRule(ruleId: string, payload: AutomationRuleUpdateIn) {
    return apiClient
      .patch<AutomationRuleOut>(endpoints.automation.rule(ruleId), payload)
      .then((res) => res.data);
  },
  testRule(ruleId: string, payload: AutomationRuleTestIn) {
    return apiClient
      .post<AutomationRuleRunOut>(endpoints.automation.testRule(ruleId), payload)
      .then((res) => res.data);
  },
  runOutbox(limit?: number) {
    return apiClient
      .post<AutomationOutboxRunOut>(endpoints.automation.runOutbox, undefined, {
        params: { limit }
      })
      .then((res) => res.data);
  },
  listRuns(params?: AutomationRunFilter) {
    return apiClient
      .get<AutomationRuleRunListOut>(endpoints.automation.runs, { params })
      .then((res) => res.data);
  },
  getRun(runId: string) {
    return apiClient
      .get<AutomationRuleRunOut>(endpoints.automation.run(runId))
      .then((res) => res.data);
  }
};

export const analyticsService = {
  refreshMart(params?: AnalyticsDateFilter) {
    return apiClient
      .post<AnalyticsMartRefreshOut>(endpoints.analytics.refreshMart, undefined, { params })
      .then((res) => res.data);
  },
  channelProfitability(params?: AnalyticsDateFilter) {
    return apiClient
      .get<ChannelProfitabilityOut>(endpoints.analytics.channelProfitability, { params })
      .then((res) => res.data);
  },
  cohorts(params?: CohortFilter) {
    return apiClient
      .get<CohortRetentionOut>(endpoints.analytics.cohorts, { params })
      .then((res) => res.data);
  },
  inventoryAging(params?: InventoryAgingFilter) {
    return apiClient
      .get<InventoryAgingOut>(endpoints.analytics.inventoryAging, { params })
      .then((res) => res.data);
  },
  ingestAttributionEvent(payload: MarketingAttributionEventIn) {
    return apiClient
      .post<MarketingAttributionEventOut>(endpoints.analytics.attributionEvents, payload)
      .then((res) => res.data);
  },
  exportReport(params: ReportExportFilter) {
    return apiClient
      .get<ReportExportOut>(endpoints.analytics.exportReport, { params })
      .then((res) => res.data);
  },
  createReportSchedule(payload: ReportScheduleCreateIn) {
    return apiClient
      .post<ReportScheduleOut>(endpoints.analytics.reportSchedules, payload)
      .then((res) => res.data);
  },
  listReportSchedules(params?: { status?: string }) {
    return apiClient
      .get<ReportScheduleListOut>(endpoints.analytics.reportSchedules, { params })
      .then((res) => res.data);
  }
};

export const posService = {
  openShift(payload: PosShiftOpenIn) {
    return apiClient.post<PosShiftOut>(endpoints.pos.openShift, payload).then((res) => res.data);
  },
  currentShift() {
    return apiClient.get<PosShiftCurrentOut>(endpoints.pos.currentShift).then((res) => res.data);
  },
  closeShift(shiftId: string, payload: PosShiftCloseIn) {
    return apiClient
      .post<PosShiftOut>(endpoints.pos.closeShift(shiftId), payload)
      .then((res) => res.data);
  },
  syncOfflineOrders(payload: PosOfflineSyncIn) {
    return apiClient
      .post<PosOfflineSyncOut>(endpoints.pos.syncOfflineOrders, payload)
      .then((res) => res.data);
  }
};

export const privacyService = {
  rbacMatrix() {
    return apiClient
      .get<PermissionMatrixOut>(endpoints.privacy.rbacMatrix)
      .then((res) => res.data);
  },
  exportCustomer(customerId: string) {
    return apiClient
      .get<CustomerPiiExportOut>(endpoints.privacy.exportCustomer(customerId))
      .then((res) => res.data);
  },
  deleteCustomer(customerId: string) {
    return apiClient
      .delete<CustomerPiiDeleteOut>(endpoints.privacy.deleteCustomer(customerId))
      .then((res) => res.data);
  },
  archiveAuditLogs(params: { cutoff_date: string; delete_archived?: boolean }) {
    return apiClient
      .post<AuditArchiveOut>(endpoints.privacy.archiveAuditLogs, undefined, { params })
      .then((res) => res.data);
  }
};

export const inventoryService = {
  stockIn(payload: StockIn) {
    return apiClient.post<StockOut>(endpoints.inventory.stockIn, payload).then((res) => res.data);
  },
  adjust(payload: StockAdjustIn) {
    return apiClient.post<StockOut>(endpoints.inventory.adjust, payload).then((res) => res.data);
  },
  stock(variantId: string) {
    return apiClient
      .get<StockLevelOut>(endpoints.inventory.stock(variantId))
      .then((res) => res.data);
  },
  ledger(params?: PaginationFilter & { variant_id?: string }) {
    return apiClient
      .get<InventoryLedgerListOut>(endpoints.inventory.ledger, { params })
      .then((res) => res.data);
  },
  lowStock(params?: PaginationFilter & { threshold?: number }) {
    return apiClient
      .get<LowStockListOut>(endpoints.inventory.lowStock, { params })
      .then((res) => res.data);
  }
};

export const salesService = {
  list(params?: SalesFilter) {
    return apiClient.get<SaleListOut>(endpoints.sales.base, { params }).then((res) => res.data);
  },
  create(payload: SaleCreateIn) {
    return apiClient.post<SaleCreateOut>(endpoints.sales.base, payload).then((res) => res.data);
  },
  refund(saleId: string, payload: RefundCreateIn) {
    return apiClient
      .post<SaleCreateOut>(endpoints.sales.refund(saleId), payload)
      .then((res) => res.data);
  },
  refundOptions(saleId: string) {
    return apiClient
      .get<SaleRefundOptionsOut>(endpoints.sales.refundOptions(saleId))
      .then((res) => res.data);
  }
};

export const orderService = {
  list(params?: OrderFilter) {
    return apiClient.get<OrderListOut>(endpoints.orders.base, { params }).then((res) => res.data);
  },
  create(payload: OrderCreateIn) {
    return apiClient.post<OrderCreateOut>(endpoints.orders.base, payload).then((res) => res.data);
  },
  updateStatus(orderId: string, payload: OrderStatusUpdateIn) {
    return apiClient
      .patch<OrderOut>(endpoints.orders.status(orderId), payload)
      .then((res) => res.data);
  }
};

export const invoiceService = {
  list(params?: InvoiceFilter) {
    return apiClient.get<InvoiceListOut>(endpoints.invoices.base, { params }).then((res) => res.data);
  },
  create(payload: InvoiceCreateIn) {
    return apiClient.post<InvoiceCreateOut>(endpoints.invoices.base, payload).then((res) => res.data);
  },
  fxQuote(params: { from_currency: string; to_currency: string }) {
    return apiClient
      .get<InvoiceFxQuoteOut>(endpoints.invoices.fxQuote, { params })
      .then((res) => res.data);
  },
  listTemplates(params?: InvoiceTemplateFilter) {
    return apiClient
      .get<InvoiceTemplateListOut>(endpoints.invoices.templates, { params })
      .then((res) => res.data);
  },
  upsertTemplate(payload: InvoiceTemplateUpsertIn) {
    return apiClient
      .put<InvoiceTemplateOut>(endpoints.invoices.templates, payload)
      .then((res) => res.data);
  },
  send(invoiceId: string) {
    return apiClient.post<InvoiceOut>(endpoints.invoices.send(invoiceId)).then((res) => res.data);
  },
  markPaid(invoiceId: string, payload: InvoiceMarkPaidIn) {
    return apiClient
      .patch<InvoiceOut>(endpoints.invoices.markPaid(invoiceId), payload)
      .then((res) => res.data);
  },
  recordPayment(invoiceId: string, payload: InvoicePaymentCreateIn) {
    return apiClient
      .post<InvoicePaymentOut>(endpoints.invoices.payments(invoiceId), payload)
      .then((res) => res.data);
  },
  listPayments(invoiceId: string, params?: PaginationFilter) {
    return apiClient
      .get<InvoicePaymentListOut>(endpoints.invoices.payments(invoiceId), { params })
      .then((res) => res.data);
  },
  remind(invoiceId: string, payload?: InvoiceReminderIn) {
    return apiClient
      .post<InvoiceOut>(endpoints.invoices.reminders(invoiceId), payload ?? {})
      .then((res) => res.data);
  },
  runDueReminders() {
    return apiClient
      .post<InvoiceReminderRunOut>(endpoints.invoices.runDueReminders)
      .then((res) => res.data);
  },
  listInstallments(invoiceId: string) {
    return apiClient
      .get<InvoiceInstallmentListOut>(endpoints.invoices.installments(invoiceId))
      .then((res) => res.data);
  },
  upsertInstallments(invoiceId: string, payload: InvoiceInstallmentUpsertIn) {
    return apiClient
      .put<InvoiceInstallmentListOut>(endpoints.invoices.installments(invoiceId), payload)
      .then((res) => res.data);
  },
  getReminderPolicy(invoiceId: string) {
    return apiClient
      .get<InvoiceReminderPolicyOut>(endpoints.invoices.reminderPolicy(invoiceId))
      .then((res) => res.data);
  },
  upsertReminderPolicy(invoiceId: string, payload: InvoiceReminderPolicyIn) {
    return apiClient
      .put<InvoiceReminderPolicyOut>(endpoints.invoices.reminderPolicy(invoiceId), payload)
      .then((res) => res.data);
  },
  agingDashboard(params?: { as_of_date?: string }) {
    return apiClient
      .get<InvoiceAgingDashboardOut>(endpoints.invoices.aging, { params })
      .then((res) => res.data);
  },
  listStatements(params: InvoiceStatementFilter) {
    return apiClient
      .get<InvoiceStatementListOut>(endpoints.invoices.statements, { params })
      .then((res) => res.data);
  },
  exportStatements(params: InvoiceStatementFilter) {
    return apiClient
      .get<InvoiceStatementExportOut>(endpoints.invoices.statementsExport, { params })
      .then((res) => res.data);
  }
};

export const customerService = {
  list(params?: CustomerFilter) {
    return apiClient.get<CustomerListOut>(endpoints.customers.base, { params }).then((res) => res.data);
  },
  create(payload: CustomerCreateIn) {
    return apiClient.post<CustomerCreateOut>(endpoints.customers.base, payload).then((res) => res.data);
  },
  update(customerId: string, payload: CustomerUpdateIn) {
    return apiClient
      .patch<CustomerOut>(endpoints.customers.customer(customerId), payload)
      .then((res) => res.data);
  },
  remove(customerId: string) {
    return apiClient.delete<void>(endpoints.customers.customer(customerId)).then(() => undefined);
  },
  listTags() {
    return apiClient.get<CustomerTagListOut>(endpoints.customers.tags).then((res) => res.data);
  },
  createTag(payload: CustomerTagCreateIn) {
    return apiClient.post<CustomerTagOut>(endpoints.customers.tags, payload).then((res) => res.data);
  },
  attachTag(customerId: string, tagId: string) {
    return apiClient
      .post<CustomerOut>(endpoints.customers.customerTag(customerId, tagId))
      .then((res) => res.data);
  },
  detachTag(customerId: string, tagId: string) {
    return apiClient
      .delete<CustomerOut>(endpoints.customers.customerTag(customerId, tagId))
      .then((res) => res.data);
  }
};

export const expenseService = {
  list(params?: DateFilter & PaginationFilter) {
    return apiClient
      .get<ExpenseListOut>(endpoints.expenses.base, { params })
      .then((res) => res.data);
  },
  create(payload: ExpenseCreateIn) {
    return apiClient
      .post<ExpenseCreateOut>(endpoints.expenses.base, payload)
      .then((res) => res.data);
  }
};

export const aiService = {
  ask(payload: AIAskIn) {
    return apiClient.post<AIResponseOut>(endpoints.ai.ask, payload).then((res) => res.data);
  },
  dailyInsight() {
    return apiClient.get<AIResponseOut>(endpoints.ai.daily).then((res) => res.data);
  },
  refreshFeatureStore(params?: AIFeatureStoreFilter) {
    return apiClient
      .post<AIFeatureSnapshotOut>(endpoints.ai.refreshFeatureStore, undefined, { params })
      .then((res) => res.data);
  },
  latestFeatureStore() {
    return apiClient
      .get<AIFeatureSnapshotOut>(endpoints.ai.latestFeatureStore)
      .then((res) => res.data);
  },
  generateInsightsV2(params?: AIFeatureStoreFilter) {
    return apiClient
      .post<AIInsightsGenerateOut>(endpoints.ai.generateInsightsV2, undefined, { params })
      .then((res) => res.data);
  },
  listInsightsV2(params?: AIInsightV2Filter) {
    return apiClient
      .get<AIInsightV2ListOut>(endpoints.ai.insightsV2, { params })
      .then((res) => res.data);
  },
  listActions(params?: AIPrescriptiveActionFilter) {
    return apiClient
      .get<AIPrescriptiveActionListOut>(endpoints.ai.actions, { params })
      .then((res) => res.data);
  },
  decideAction(actionId: string, payload: AIPrescriptiveDecisionIn) {
    return apiClient
      .post<AIPrescriptiveActionOut>(endpoints.ai.actionDecision(actionId), payload)
      .then((res) => res.data);
  }
};

export const teamService = {
  list(params?: TeamListFilter) {
    return apiClient
      .get<TeamMemberListOut>(endpoints.team.members, { params })
      .then((res) => res.data);
  },
  add(payload: TeamMemberCreateIn) {
    return apiClient
      .post<TeamMemberOut>(endpoints.team.members, payload)
      .then((res) => res.data);
  },
  update(membershipId: string, payload: TeamMemberUpdateIn) {
    return apiClient
      .patch<TeamMemberOut>(endpoints.team.member(membershipId), payload)
      .then((res) => res.data);
  },
  deactivate(membershipId: string) {
    return apiClient.delete<void>(endpoints.team.member(membershipId)).then(() => undefined);
  },
  listInvitations(params?: TeamInvitationListFilter) {
    return apiClient
      .get<TeamInvitationListOut>(endpoints.team.invitations, { params })
      .then((res) => res.data);
  },
  createInvitation(payload: TeamInvitationCreateIn) {
    return apiClient
      .post<TeamInvitationCreateOut>(endpoints.team.invitations, payload)
      .then((res) => res.data);
  },
  revokeInvitation(invitationId: string) {
    return apiClient
      .delete<void>(endpoints.team.invitation(invitationId))
      .then(() => undefined);
  },
  acceptInvitation(payload: TeamInvitationAcceptIn) {
    return apiClient
      .post<TeamMemberOut>(endpoints.team.acceptInvitation, payload)
      .then((res) => res.data);
  }
};

export const auditService = {
  list(params?: AuditLogFilter) {
    return apiClient
      .get<AuditLogListOut>(endpoints.audit.base, { params })
      .then((res) => res.data);
  }
};

export const developerService = {
  listScopeCatalog() {
    return apiClient
      .get<PublicApiScopeCatalogOut>(endpoints.developer.scopeCatalog)
      .then((res) => res.data);
  },
  createApiKey(payload: PublicApiKeyCreateIn) {
    return apiClient
      .post<PublicApiKeyCreateOut>(endpoints.developer.apiKeys, payload)
      .then((res) => res.data);
  },
  listApiKeys() {
    return apiClient
      .get<PublicApiKeyListOut>(endpoints.developer.apiKeys)
      .then((res) => res.data);
  },
  rotateApiKey(apiKeyId: string) {
    return apiClient
      .post<PublicApiKeyRotateOut>(endpoints.developer.rotateApiKey(apiKeyId))
      .then((res) => res.data);
  },
  revokeApiKey(apiKeyId: string) {
    return apiClient
      .post<PublicApiKeyOut>(endpoints.developer.revokeApiKey(apiKeyId))
      .then((res) => res.data);
  },
  createWebhookSubscription(payload: WebhookSubscriptionCreateIn) {
    return apiClient
      .post<WebhookSubscriptionCreateOut>(endpoints.developer.webhookSubscriptions, payload)
      .then((res) => res.data);
  },
  listWebhookSubscriptions() {
    return apiClient
      .get<WebhookSubscriptionListOut>(endpoints.developer.webhookSubscriptions)
      .then((res) => res.data);
  },
  updateWebhookSubscription(subscriptionId: string, payload: WebhookSubscriptionUpdateIn) {
    return apiClient
      .patch<WebhookSubscriptionOut>(endpoints.developer.webhookSubscription(subscriptionId), payload)
      .then((res) => res.data);
  },
  rotateWebhookSecret(subscriptionId: string) {
    return apiClient
      .post<WebhookSubscriptionRotateSecretOut>(endpoints.developer.rotateWebhookSecret(subscriptionId))
      .then((res) => res.data);
  },
  listWebhookDeliveries(params?: WebhookDeliveryFilter) {
    return apiClient
      .get<WebhookDeliveryListOut>(endpoints.developer.webhookDeliveries, { params })
      .then((res) => res.data);
  },
  dispatchWebhookDeliveries(limit?: number, subscriptionId?: string) {
    return apiClient
      .post<WebhookDispatchOut>(endpoints.developer.dispatchWebhookDeliveries, undefined, {
        params: { limit, subscription_id: subscriptionId }
      })
      .then((res) => res.data);
  },
  listPortalDocs() {
    return apiClient
      .get<DeveloperPortalDocsOut>(endpoints.developer.portalDocs)
      .then((res) => res.data);
  },
  createMarketplaceListing(payload: MarketplaceListingCreateIn) {
    return apiClient
      .post<MarketplaceListingOut>(endpoints.developer.marketplaceApps, payload)
      .then((res) => res.data);
  },
  listMarketplaceListings(params?: MarketplaceListingFilter) {
    return apiClient
      .get<MarketplaceListingListOut>(endpoints.developer.marketplaceApps, { params })
      .then((res) => res.data);
  },
  submitMarketplaceListing(listingId: string) {
    return apiClient
      .post<MarketplaceListingOut>(endpoints.developer.submitMarketplaceApp(listingId))
      .then((res) => res.data);
  },
  reviewMarketplaceListing(listingId: string, payload: MarketplaceListingReviewIn) {
    return apiClient
      .post<MarketplaceListingOut>(endpoints.developer.reviewMarketplaceApp(listingId), payload)
      .then((res) => res.data);
  },
  publishMarketplaceListing(listingId: string, payload: MarketplaceListingPublishIn) {
    return apiClient
      .post<MarketplaceListingOut>(endpoints.developer.publishMarketplaceApp(listingId), payload)
      .then((res) => res.data);
  }
};

export const publicApiService = {
  me(apiKey: string) {
    return apiClient
      .get<PublicApiBusinessOut>(endpoints.publicApi.me, {
        headers: { "X-Monidesk-Api-Key": apiKey }
      })
      .then((res) => res.data);
  },
  products(apiKey: string, params?: PaginationFilter & { q?: string; category?: string; is_published?: boolean }) {
    return apiClient
      .get<PublicApiProductListOut>(endpoints.publicApi.products, {
        headers: { "X-Monidesk-Api-Key": apiKey },
        params
      })
      .then((res) => res.data);
  },
  orders(apiKey: string, params?: PaginationFilter & { status?: string }) {
    return apiClient
      .get<PublicApiOrderListOut>(endpoints.publicApi.orders, {
        headers: { "X-Monidesk-Api-Key": apiKey },
        params
      })
      .then((res) => res.data);
  },
  customers(apiKey: string, params?: PaginationFilter & { q?: string }) {
    return apiClient
      .get<PublicApiCustomerListOut>(endpoints.publicApi.customers, {
        headers: { "X-Monidesk-Api-Key": apiKey },
        params
      })
      .then((res) => res.data);
  }
};
