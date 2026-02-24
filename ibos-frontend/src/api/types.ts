export type PaymentMethod = "cash" | "transfer" | "pos";
export type SalesChannel = "whatsapp" | "instagram" | "walk-in";
export type SaleKind = "sale" | "refund";

export interface PaginationMeta {
  total: number;
  limit: number;
  offset: number;
  count: number;
  has_next: boolean;
}

export interface ValidationIssueOut {
  field: string;
  message: string;
  type?: string | null;
}

export interface ErrorDetailOut {
  code: string;
  message: string;
  request_id: string;
  path: string;
  details?: ValidationIssueOut[] | null;
}

export interface ApiErrorOut {
  error: ErrorDetailOut;
}

export interface TokenOut {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RegisterIn {
  email: string;
  full_name: string;
  password: string;
  business_name?: string;
  username?: string;
}

export interface RegisterWithInviteIn {
  invitation_token: string;
  email: string;
  full_name: string;
  password: string;
  username?: string;
}

export interface LoginIn {
  identifier: string;
  password: string;
}

export interface RefreshIn {
  refresh_token: string;
}

export interface LogoutIn {
  refresh_token: string;
}

export interface ChangePasswordIn {
  current_password: string;
  new_password: string;
}

export interface UserProfileOut {
  id: string;
  email: string;
  username: string;
  full_name?: string | null;
  business_name?: string | null;
  pending_order_timeout_minutes: number;
  created_at: string;
  updated_at: string;
}

export interface UpdateProfileIn {
  full_name?: string;
  username?: string;
  business_name?: string;
  pending_order_timeout_minutes?: number;
}

export interface OkOut {
  ok: boolean;
}

export interface DashboardSummaryOut {
  sales_total: number;
  sales_count: number;
  average_sale_value: number;
  expense_total: number;
  expense_count: number;
  profit_simple: number;
  start_date: string | null;
  end_date: string | null;
}

export interface DashboardTopCustomerOut {
  customer_id: string;
  customer_name: string;
  total_spent: number;
  transactions: number;
}

export interface DashboardCustomerInsightsOut {
  repeat_buyers: number;
  active_customers: number;
  total_customers: number;
  top_customers: DashboardTopCustomerOut[];
  start_date: string | null;
  end_date: string | null;
}

export interface CreditMetricOut {
  name: string;
  score: number;
}

export interface CreditProfileOut {
  overall_score: number;
  grade: "excellent" | "good" | "fair" | "weak";
  metrics: CreditMetricOut[];
  recommendations: string[];
  sales_total: number;
  expense_total: number;
  profit_simple: number;
  sales_count: number;
  expense_count: number;
  low_stock_count: number;
  payment_methods_count: number;
  start_date: string | null;
  end_date: string | null;
}

export interface CreditScoreFactorOut {
  key: string;
  label: string;
  score: number;
  weight: number;
  current_value: number;
  previous_value: number;
  delta_pct: number;
  trend: "up" | "down" | "flat" | string;
  rationale: string;
}

export interface CreditProfileV2Out {
  overall_score: number;
  grade: "excellent" | "good" | "fair" | "weak";
  factors: CreditScoreFactorOut[];
  recommendations: string[];
  current_window_start_date: string;
  current_window_end_date: string;
  previous_window_start_date: string;
  previous_window_end_date: string;
  current_net_sales: number;
  current_expenses_total: number;
  current_net_cashflow: number;
  generated_at: string;
}

export interface CashflowForecastIntervalOut {
  interval_index: number;
  interval_start_date: string;
  interval_end_date: string;
  projected_inflow: number;
  projected_outflow: number;
  projected_net_cashflow: number;
  net_lower_bound: number;
  net_upper_bound: number;
}

export interface CashflowForecastOut {
  horizon_days: number;
  history_days: number;
  interval_days: number;
  error_bound_pct: number;
  baseline_daily_net: number;
  intervals: CashflowForecastIntervalOut[];
  generated_at: string;
}

export interface CreditScenarioSimulateIn {
  horizon_days?: number;
  history_days?: number;
  interval_days?: number;
  price_change_pct?: number;
  expense_change_pct?: number;
  restock_investment?: number;
  restock_return_multiplier?: number;
}

export interface CreditScenarioOutcomeOut {
  label: string;
  projected_revenue: number;
  projected_expenses: number;
  projected_net_cashflow: number;
  projected_margin_pct: number;
  intervals: CashflowForecastIntervalOut[];
}

export interface CreditScenarioDeltaOut {
  revenue_delta: number;
  expenses_delta: number;
  net_cashflow_delta: number;
  margin_delta_pct: number;
}

export interface CreditScenarioSimulationOut {
  baseline: CreditScenarioOutcomeOut;
  scenario: CreditScenarioOutcomeOut;
  delta: CreditScenarioDeltaOut;
  assumptions_json: Record<string, number>;
  generated_at: string;
}

export interface LenderPackStatementPeriodOut {
  period_label: string;
  period_start_date: string;
  period_end_date: string;
  net_sales: number;
  expenses_total: number;
  net_cashflow: number;
}

export interface LenderExportPackOut {
  pack_id: string;
  generated_at: string;
  window_days: number;
  horizon_days: number;
  profile: CreditProfileV2Out;
  forecast: CashflowForecastOut;
  statement_periods: LenderPackStatementPeriodOut[];
  score_explanation: string[];
  recommendations: string[];
  bundle_sections: string[];
}

export interface FinanceGuardrailPolicyIn {
  enabled?: boolean;
  margin_floor_ratio?: number;
  margin_drop_threshold?: number;
  expense_growth_threshold?: number;
  minimum_cash_buffer?: number;
}

export interface FinanceGuardrailPolicyOut {
  id: string;
  enabled: boolean;
  margin_floor_ratio: number;
  margin_drop_threshold: number;
  expense_growth_threshold: number;
  minimum_cash_buffer: number;
  updated_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FinanceGuardrailAlertOut {
  alert_type: string;
  severity: string;
  message: string;
  current_value: number;
  threshold_value: number;
  delta_value: number;
  window_start_date: string;
  window_end_date: string;
}

export interface FinanceGuardrailEvaluationOut {
  policy: FinanceGuardrailPolicyOut;
  alerts: FinanceGuardrailAlertOut[];
  generated_at: string;
}

export interface CreditImprovementActionOut {
  priority: number;
  factor_key: string;
  factor_label: string;
  title: string;
  description: string;
  current_score: number;
  target_score: number;
  estimated_score_impact: number;
  measurable_target: string;
}

export interface CreditImprovementPlanOut {
  overall_score: number;
  target_score: number;
  actions: CreditImprovementActionOut[];
  generated_at: string;
}

export interface ProductCreateIn {
  name: string;
  category?: string | null;
}

export interface ProductCreateOut {
  id: string;
}

export interface ProductOut {
  id: string;
  name: string;
  category?: string | null;
  active: boolean;
  is_published: boolean;
}

export interface ProductListOut {
  items: ProductOut[];
  pagination: PaginationMeta;
}

export interface VariantCreateIn {
  size: string;
  label?: string | null;
  sku?: string | null;
  reorder_level?: number;
  cost_price?: number | null;
  selling_price?: number | null;
}

export interface VariantCreateOut {
  id: string;
}

export interface VariantOut {
  id: string;
  product_id: string;
  business_id: string;
  size: string;
  label?: string | null;
  sku?: string | null;
  reorder_level: number;
  cost_price?: number | null;
  selling_price?: number | null;
  is_published: boolean;
  stock: number;
  created_at: string;
}

export interface VariantListOut {
  items: VariantOut[];
  pagination: PaginationMeta;
}

export interface ProductPublishIn {
  is_published: boolean;
}

export interface ProductPublishOut {
  id: string;
  is_published: boolean;
}

export interface VariantPublishIn {
  is_published: boolean;
}

export interface VariantPublishOut {
  id: string;
  product_id: string;
  is_published: boolean;
}

export interface StorefrontConfigUpsertIn {
  slug: string;
  display_name: string;
  tagline?: string | null;
  description?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  seo_og_image_url?: string | null;
  logo_url?: string | null;
  accent_color?: string | null;
  hero_image_url?: string | null;
  support_email?: string | null;
  support_phone?: string | null;
  policy_shipping?: string | null;
  policy_returns?: string | null;
  policy_privacy?: string | null;
  custom_domain?: string | null;
  is_published?: boolean;
}

export interface StorefrontConfigOut {
  id: string;
  business_id: string;
  slug: string;
  display_name: string;
  tagline?: string | null;
  description?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  seo_og_image_url?: string | null;
  logo_url?: string | null;
  accent_color?: string | null;
  hero_image_url?: string | null;
  support_email?: string | null;
  support_phone?: string | null;
  policy_shipping?: string | null;
  policy_returns?: string | null;
  policy_privacy?: string | null;
  custom_domain?: string | null;
  domain_verification_status: "not_configured" | "pending" | "verified";
  domain_verification_token?: string | null;
  domain_last_checked_at?: string | null;
  domain_verified_at?: string | null;
  is_published: boolean;
  created_at: string;
  updated_at: string;
}

export interface StorefrontDomainChallengeOut {
  custom_domain: string;
  verification_status: "pending" | "verified" | "not_configured";
  txt_record_name: string;
  txt_record_value: string;
  domain_last_checked_at?: string | null;
}

export interface StorefrontDomainVerifyIn {
  verification_token: string;
}

export interface StorefrontDomainStatusOut {
  custom_domain?: string | null;
  verification_status: "not_configured" | "pending" | "verified";
  txt_record_name?: string | null;
  txt_record_value?: string | null;
  domain_last_checked_at?: string | null;
  domain_verified_at?: string | null;
}

export interface PublicStorefrontOut {
  slug: string;
  display_name: string;
  tagline?: string | null;
  description?: string | null;
  seo_title?: string | null;
  seo_description?: string | null;
  seo_og_image_url?: string | null;
  logo_url?: string | null;
  accent_color?: string | null;
  hero_image_url?: string | null;
  support_email?: string | null;
  support_phone?: string | null;
  policy_shipping?: string | null;
  policy_returns?: string | null;
  policy_privacy?: string | null;
}

export interface PublicStorefrontProductOut {
  id: string;
  name: string;
  category?: string | null;
  starting_price?: number | null;
  published_variant_count: number;
}

export interface PublicStorefrontProductListOut {
  items: PublicStorefrontProductOut[];
  pagination: PaginationMeta;
  q?: string | null;
  category?: string | null;
}

export interface PublicStorefrontVariantOut {
  id: string;
  size: string;
  label?: string | null;
  sku?: string | null;
  selling_price?: number | null;
}

export interface PublicStorefrontProductDetailOut {
  id: string;
  name: string;
  category?: string | null;
  description?: string | null;
  variants: PublicStorefrontVariantOut[];
}

export type CheckoutSessionStatus =
  | "open"
  | "pending_payment"
  | "payment_failed"
  | "paid"
  | "expired";

export interface CheckoutSessionItemIn {
  variant_id: string;
  qty: number;
  unit_price: number;
}

export interface CheckoutSessionCreateIn {
  currency?: string;
  customer_id?: string;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  note?: string;
  success_redirect_url?: string;
  cancel_redirect_url?: string;
  expires_in_minutes?: number;
  items: CheckoutSessionItemIn[];
}

export interface CheckoutSessionCreateOut {
  id: string;
  session_token: string;
  checkout_url: string;
  status: CheckoutSessionStatus;
  payment_provider: string;
  payment_reference?: string | null;
  payment_checkout_url?: string | null;
  total_amount: number;
  expires_at: string;
}

export interface CheckoutSessionOut {
  id: string;
  session_token: string;
  status: CheckoutSessionStatus;
  currency: string;
  customer_id?: string | null;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  total_amount: number;
  payment_provider: string;
  payment_reference?: string | null;
  payment_checkout_url?: string | null;
  order_id?: string | null;
  order_status?: OrderStatus | null;
  sale_id?: string | null;
  has_sale: boolean;
  created_at: string;
  updated_at: string;
  expires_at: string;
}

export interface CheckoutSessionListOut {
  items: CheckoutSessionOut[];
  pagination: PaginationMeta;
  status?: CheckoutSessionStatus | null;
  payment_provider?: string | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface CheckoutSessionRetryPaymentOut {
  checkout_session_id: string;
  checkout_session_token: string;
  checkout_status: CheckoutSessionStatus;
  payment_provider: string;
  payment_reference: string;
  payment_checkout_url?: string | null;
  expires_at: string;
}

export interface CheckoutPaymentsSummaryOut {
  total_sessions: number;
  open_count: number;
  pending_payment_count: number;
  failed_count: number;
  paid_count: number;
  expired_count: number;
  paid_amount_total: number;
  reconciled_count: number;
  unreconciled_count: number;
  start_date?: string | null;
  end_date?: string | null;
}

export interface ShippingZoneIn {
  zone_name: string;
  country: string;
  state?: string | null;
  city?: string | null;
  postal_code_prefix?: string | null;
  is_active?: boolean;
}

export interface ShippingServiceRuleIn {
  provider: string;
  service_code: string;
  service_name: string;
  zone_name?: string | null;
  base_rate: number;
  per_kg_rate: number;
  min_eta_days?: number;
  max_eta_days?: number;
  is_active?: boolean;
}

export interface ShippingSettingsUpsertIn {
  default_origin_country: string;
  default_origin_state?: string | null;
  default_origin_city?: string | null;
  default_origin_postal_code?: string | null;
  handling_fee?: number;
  currency?: string;
  zones: ShippingZoneIn[];
  service_rules: ShippingServiceRuleIn[];
}

export interface ShippingZoneOut {
  id: string;
  zone_name: string;
  country: string;
  state?: string | null;
  city?: string | null;
  postal_code_prefix?: string | null;
  is_active: boolean;
}

export interface ShippingServiceRuleOut {
  id: string;
  provider: string;
  service_code: string;
  service_name: string;
  zone_name?: string | null;
  base_rate: number;
  per_kg_rate: number;
  min_eta_days: number;
  max_eta_days: number;
  is_active: boolean;
}

export interface ShippingSettingsOut {
  profile_id: string;
  default_origin_country: string;
  default_origin_state?: string | null;
  default_origin_city?: string | null;
  default_origin_postal_code?: string | null;
  handling_fee: number;
  currency: string;
  zones: ShippingZoneOut[];
  service_rules: ShippingServiceRuleOut[];
  updated_at: string;
}

export interface ShippingQuoteIn {
  destination_country: string;
  destination_state?: string | null;
  destination_city?: string | null;
  destination_postal_code?: string | null;
  total_weight_kg: number;
}

export interface ShippingQuoteOptionOut {
  provider: string;
  service_code: string;
  service_name: string;
  zone_name?: string | null;
  amount: number;
  currency: string;
  eta_min_days: number;
  eta_max_days: number;
}

export interface ShippingQuoteOut {
  checkout_session_token: string;
  currency: string;
  options: ShippingQuoteOptionOut[];
}

export interface ShippingRateSelectIn {
  provider: string;
  service_code: string;
  service_name: string;
  zone_name?: string | null;
  amount: number;
  currency?: string;
  eta_min_days?: number;
  eta_max_days?: number;
}

export interface ShippingRateSelectionOut {
  checkout_session_id: string;
  provider: string;
  service_code: string;
  service_name: string;
  zone_name?: string | null;
  amount: number;
  currency: string;
  eta_min_days: number;
  eta_max_days: number;
  updated_at: string;
}

export interface ShipmentCreateIn {
  order_id: string;
  checkout_session_id?: string | null;
  provider: string;
  service_code: string;
  service_name: string;
  shipping_cost?: number;
  currency?: string;
  recipient_name: string;
  recipient_phone?: string | null;
  address_line1: string;
  address_line2?: string | null;
  city: string;
  state?: string | null;
  country: string;
  postal_code?: string | null;
}

export interface ShipmentTrackingEventOut {
  id: string;
  status: string;
  description?: string | null;
  event_time: string;
  created_at: string;
}

export interface ShipmentOut {
  id: string;
  order_id: string;
  checkout_session_id?: string | null;
  provider: string;
  service_code: string;
  service_name: string;
  status: string;
  shipping_cost: number;
  currency: string;
  tracking_number?: string | null;
  label_url?: string | null;
  recipient_name: string;
  recipient_phone?: string | null;
  address_line1: string;
  address_line2?: string | null;
  city: string;
  state?: string | null;
  country: string;
  postal_code?: string | null;
  shipped_at?: string | null;
  delivered_at?: string | null;
  created_at: string;
  updated_at: string;
  tracking_events: ShipmentTrackingEventOut[];
}

export interface ShipmentListOut {
  items: ShipmentOut[];
  pagination: PaginationMeta;
  order_id?: string | null;
  status?: string | null;
}

export interface ShipmentTrackingSyncOut {
  shipment_id: string;
  shipment_status: string;
  order_id: string;
  order_status: string;
  tracking_events_added: number;
}

export interface LocationCreateIn {
  name: string;
  code: string;
}

export interface LocationUpdateIn {
  name?: string;
  is_active?: boolean;
}

export interface LocationOut {
  id: string;
  name: string;
  code: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LocationListOut {
  items: LocationOut[];
  pagination: PaginationMeta;
}

export interface LocationMembershipScopeUpsertIn {
  can_manage_inventory: boolean;
}

export interface LocationMembershipScopeOut {
  id: string;
  membership_id: string;
  location_id: string;
  can_manage_inventory: boolean;
  created_at: string;
}

export interface LocationMembershipScopeListOut {
  items: LocationMembershipScopeOut[];
}

export interface LocationStockInIn {
  variant_id: string;
  qty: number;
  note?: string | null;
}

export interface LocationStockAdjustIn {
  variant_id: string;
  qty_delta: number;
  reason: string;
  note?: string | null;
}

export interface LocationVariantStockOut {
  location_id: string;
  variant_id: string;
  stock: number;
}

export interface LocationStockOverviewOut {
  variant_id: string;
  by_location: LocationVariantStockOut[];
}

export interface LocationTransferItemIn {
  variant_id: string;
  qty: number;
}

export interface StockTransferCreateIn {
  from_location_id: string;
  to_location_id: string;
  note?: string | null;
  items: LocationTransferItemIn[];
}

export interface StockTransferItemOut {
  variant_id: string;
  qty: number;
}

export interface StockTransferOut {
  id: string;
  from_location_id: string;
  to_location_id: string;
  status: string;
  note?: string | null;
  created_at: string;
  items: StockTransferItemOut[];
}

export interface StockTransferListOut {
  items: StockTransferOut[];
  pagination: PaginationMeta;
}

export interface LocationLowStockItemOut {
  location_id: string;
  variant_id: string;
  reorder_level: number;
  stock: number;
}

export interface LocationLowStockListOut {
  items: LocationLowStockItemOut[];
  pagination: PaginationMeta;
}

export interface OrderLocationAllocationIn {
  order_id: string;
  location_id: string;
}

export interface OrderLocationAllocationOut {
  id: string;
  order_id: string;
  location_id: string;
  allocated_at: string;
}

export interface IntegrationSecretUpsertIn {
  provider: string;
  key_name: string;
  secret_value: string;
}

export interface IntegrationSecretOut {
  id: string;
  provider: string;
  key_name: string;
  version: number;
  status: string;
  rotated_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationSecretListOut {
  items: IntegrationSecretOut[];
}

export interface AppInstallationIn {
  app_key: string;
  display_name: string;
  permissions?: string[];
  config_json?: Record<string, unknown> | null;
}

export interface AppInstallationOut {
  id: string;
  app_key: string;
  display_name: string;
  status: string;
  permissions: string[];
  config_json?: Record<string, unknown> | null;
  installed_at: string;
  disconnected_at?: string | null;
  updated_at: string;
}

export interface AppInstallationListOut {
  items: AppInstallationOut[];
}

export interface IntegrationOutboxEventOut {
  id: string;
  event_type: string;
  target_app_key: string;
  status: string;
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationOutboxEventListOut {
  items: IntegrationOutboxEventOut[];
  pagination: PaginationMeta;
  status?: string | null;
  target_app_key?: string | null;
}

export interface IntegrationDispatchOut {
  processed: number;
  delivered: number;
  failed: number;
  dead_lettered: number;
}

export interface IntegrationMessageSendIn {
  provider?: string;
  recipient: string;
  content: string;
}

export interface IntegrationMessageOut {
  id: string;
  provider: string;
  recipient: string;
  content: string;
  status: string;
  external_message_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface IntegrationMessageListOut {
  items: IntegrationMessageOut[];
  pagination: PaginationMeta;
}

export interface IntegrationEventEmitIn {
  event_type: string;
  target_app_key: string;
  payload_json?: Record<string, unknown> | null;
}

export interface IntegrationEmitOut {
  event_id: string;
}

export type CampaignChannel = "whatsapp" | "sms" | "email";
export type CampaignTemplateStatus = "draft" | "approved" | "archived";
export type CampaignStatus =
  | "draft"
  | "queued"
  | "sending"
  | "completed"
  | "failed"
  | "cancelled";
export type CampaignRecipientStatus =
  | "queued"
  | "sent"
  | "delivered"
  | "opened"
  | "replied"
  | "failed"
  | "suppressed"
  | "skipped";
export type ConsentStatus = "subscribed" | "unsubscribed";
export type RetentionTriggerStatus = "active" | "inactive";

export interface SegmentFiltersIn {
  q?: string;
  tag_ids_any?: string[];
  min_total_spent?: number;
  min_order_count?: number;
  channels_any?: string[];
  has_email?: boolean;
  has_phone?: boolean;
  last_order_before_days?: number;
  last_order_within_days?: number;
}

export interface CustomerSegmentCreateIn {
  name: string;
  description?: string;
  filters?: SegmentFiltersIn;
}

export interface CustomerSegmentUpdateIn {
  name?: string;
  description?: string;
  filters?: SegmentFiltersIn;
  is_active?: boolean;
}

export interface CustomerSegmentOut {
  id: string;
  name: string;
  description?: string | null;
  filters: SegmentFiltersIn;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomerSegmentListOut {
  items: CustomerSegmentOut[];
  pagination: PaginationMeta;
}

export interface SegmentPreviewOut {
  segment_id: string;
  total_customers: number;
  customer_ids: string[];
}

export interface CampaignTemplateCreateIn {
  name: string;
  channel?: CampaignChannel;
  content: string;
  status?: CampaignTemplateStatus;
}

export interface CampaignTemplateUpdateIn {
  name?: string;
  channel?: CampaignChannel;
  content?: string;
  status?: CampaignTemplateStatus;
}

export interface CampaignTemplateOut {
  id: string;
  name: string;
  channel: CampaignChannel;
  content: string;
  status: CampaignTemplateStatus;
  created_by_user_id: string;
  approved_by_user_id?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignTemplateListOut {
  items: CampaignTemplateOut[];
  pagination: PaginationMeta;
}

export interface CustomerConsentUpsertIn {
  customer_id: string;
  channel?: CampaignChannel;
  status: ConsentStatus;
  source?: string;
  note?: string;
}

export interface CustomerConsentOut {
  id: string;
  customer_id: string;
  channel: CampaignChannel;
  status: ConsentStatus;
  source?: string | null;
  note?: string | null;
  opted_at: string;
  updated_at: string;
}

export interface CustomerConsentListOut {
  items: CustomerConsentOut[];
  pagination: PaginationMeta;
  channel?: CampaignChannel | null;
  status?: ConsentStatus | null;
}

export interface CampaignCreateIn {
  name: string;
  segment_id?: string;
  template_id?: string;
  explicit_customer_ids?: string[];
  channel?: CampaignChannel;
  provider?: string;
  content_override?: string;
  scheduled_at?: string;
  send_now?: boolean;
}

export interface CampaignOut {
  id: string;
  name: string;
  segment_id?: string | null;
  template_id?: string | null;
  channel: CampaignChannel;
  provider: string;
  message_content: string;
  status: CampaignStatus;
  scheduled_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  opened_count: number;
  replied_count: number;
  failed_count: number;
  suppressed_count: number;
  skipped_count: number;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
}

export interface CampaignListOut {
  items: CampaignOut[];
  pagination: PaginationMeta;
  status?: CampaignStatus | null;
}

export interface CampaignDispatchIn {
  provider?: string;
}

export interface CampaignDispatchOut {
  campaign_id: string;
  campaign_status: CampaignStatus;
  processed: number;
  sent: number;
  failed: number;
  suppressed: number;
  skipped: number;
}

export interface CampaignRecipientOut {
  id: string;
  campaign_id: string;
  customer_id: string;
  recipient: string;
  status: CampaignRecipientStatus;
  outbound_message_id?: string | null;
  error_message?: string | null;
  sent_at?: string | null;
  delivered_at?: string | null;
  opened_at?: string | null;
  replied_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignRecipientListOut {
  items: CampaignRecipientOut[];
  pagination: PaginationMeta;
  status?: CampaignRecipientStatus | null;
}

export interface CampaignMetricsOut {
  campaigns_total: number;
  recipients_total: number;
  queued_count: number;
  sent_count: number;
  delivered_count: number;
  opened_count: number;
  replied_count: number;
  failed_count: number;
  suppressed_count: number;
  skipped_count: number;
  response_rate: number;
}

export interface RetentionTriggerCreateIn {
  name: string;
  trigger_type?: string;
  status?: RetentionTriggerStatus;
  segment_id?: string;
  template_id?: string;
  channel?: CampaignChannel;
  provider?: string;
  config_json?: Record<string, unknown>;
}

export interface RetentionTriggerOut {
  id: string;
  name: string;
  trigger_type: string;
  status: RetentionTriggerStatus;
  segment_id?: string | null;
  template_id?: string | null;
  channel: CampaignChannel;
  provider: string;
  config_json?: Record<string, unknown> | null;
  created_by_user_id: string;
  last_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RetentionTriggerListOut {
  items: RetentionTriggerOut[];
  pagination: PaginationMeta;
}

export interface RetentionTriggerRunRequestIn {
  auto_dispatch?: boolean;
}

export interface RetentionTriggerRunOut {
  id: string;
  retention_trigger_id: string;
  campaign_id?: string | null;
  status: string;
  processed_count: number;
  queued_count: number;
  skipped_count: number;
  error_count: number;
  created_at: string;
}

export type AutomationRuleStatus = "active" | "inactive";
export type AutomationTriggerSource = "outbox_event";
export type AutomationActionType =
  | "send_message"
  | "tag_customer"
  | "create_task"
  | "apply_discount";
export type AutomationRunStatus = "success" | "failed" | "skipped" | "blocked" | "dry_run";
export type AutomationStepStatus =
  | "success"
  | "failed"
  | "skipped"
  | "rolled_back"
  | "dry_run";
export type AutomationConditionOperator =
  | "eq"
  | "neq"
  | "gt"
  | "gte"
  | "lt"
  | "lte"
  | "contains"
  | "in"
  | "exists"
  | "not_exists";
export type AutomationTemplateKey = "abandoned_cart" | "overdue_invoice" | "low_stock";

export interface AutomationConditionIn {
  field: string;
  operator?: AutomationConditionOperator;
  value?: unknown;
  case_sensitive?: boolean;
}

export interface AutomationActionIn {
  type: AutomationActionType;
  config_json?: Record<string, unknown>;
}

export interface AutomationRuleCreateIn {
  name: string;
  description?: string;
  status?: AutomationRuleStatus;
  trigger_source?: AutomationTriggerSource;
  trigger_event_type?: string;
  conditions?: AutomationConditionIn[];
  actions: AutomationActionIn[];
  template_key?: string;
  run_limit_per_hour?: number;
  reentry_cooldown_seconds?: number;
  rollback_on_failure?: boolean;
}

export interface AutomationRuleUpdateIn {
  name?: string;
  description?: string;
  status?: AutomationRuleStatus;
  trigger_event_type?: string;
  conditions?: AutomationConditionIn[];
  actions?: AutomationActionIn[];
  run_limit_per_hour?: number;
  reentry_cooldown_seconds?: number;
  rollback_on_failure?: boolean;
}

export interface AutomationConditionOut {
  field: string;
  operator: AutomationConditionOperator;
  value?: unknown;
  case_sensitive: boolean;
}

export interface AutomationActionOut {
  type: AutomationActionType;
  config_json: Record<string, unknown>;
}

export interface AutomationRuleOut {
  id: string;
  name: string;
  description?: string | null;
  status: AutomationRuleStatus;
  trigger_source: AutomationTriggerSource;
  trigger_event_type: string;
  conditions: AutomationConditionOut[];
  actions: AutomationActionOut[];
  template_key?: string | null;
  version: number;
  run_limit_per_hour: number;
  reentry_cooldown_seconds: number;
  rollback_on_failure: boolean;
  created_by_user_id: string;
  updated_by_user_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AutomationRuleListOut {
  items: AutomationRuleOut[];
  pagination: PaginationMeta;
  status?: AutomationRuleStatus | null;
  trigger_event_type?: string | null;
}

export interface AutomationRuleTestIn {
  event_type?: string;
  target_app_key?: string;
  payload_json?: Record<string, unknown>;
}

export interface AutomationRuleStepOut {
  id?: string | null;
  step_index: number;
  action_type: AutomationActionType;
  status: AutomationStepStatus;
  input_json?: Record<string, unknown> | null;
  output_json?: Record<string, unknown> | null;
  error_message?: string | null;
  created_at?: string | null;
}

export interface AutomationRuleRunOut {
  id: string;
  rule_id: string;
  trigger_event_id?: string | null;
  trigger_event_type: string;
  status: AutomationRunStatus;
  blocked_reason?: string | null;
  error_message?: string | null;
  steps_total: number;
  steps_succeeded: number;
  steps_failed: number;
  started_at: string;
  completed_at?: string | null;
  created_at: string;
  steps: AutomationRuleStepOut[];
}

export interface AutomationRuleRunListOut {
  items: AutomationRuleRunOut[];
  pagination: PaginationMeta;
  rule_id?: string | null;
  status?: AutomationRunStatus | null;
}

export interface AutomationOutboxRunOut {
  processed_events: number;
  matched_rules: number;
  triggered_runs: number;
  successful_runs: number;
  failed_runs: number;
  blocked_runs: number;
  skipped_runs: number;
}

export interface AutomationTemplateOut {
  template_key: AutomationTemplateKey;
  name: string;
  description: string;
  trigger_event_type: string;
  default_conditions: AutomationConditionOut[];
  default_actions: AutomationActionOut[];
}

export interface AutomationTemplateCatalogOut {
  items: AutomationTemplateOut[];
}

export interface AutomationTemplateInstallIn {
  template_key: AutomationTemplateKey;
  activate?: boolean;
}

export interface AutomationTemplateInstallOut {
  template: AutomationTemplateOut;
  rule: AutomationRuleOut;
}

export interface StockIn {
  variant_id: string;
  qty: number;
  unit_cost?: number | null;
}

export interface StockAdjustIn {
  variant_id: string;
  qty_delta: number;
  reason: string;
  note?: string | null;
  unit_cost?: number | null;
}

export interface StockOut {
  ok: boolean;
}

export interface StockLevelOut {
  variant_id: string;
  stock: number;
}

export interface InventoryLedgerEntryOut {
  id: string;
  variant_id: string;
  qty_delta: number;
  reason: string;
  reference_id?: string | null;
  note?: string | null;
  unit_cost?: number | null;
  created_at: string;
}

export interface InventoryLedgerListOut {
  items: InventoryLedgerEntryOut[];
  pagination: PaginationMeta;
}

export interface LowStockVariantOut {
  variant_id: string;
  product_id: string;
  product_name: string;
  size: string;
  label?: string | null;
  sku?: string | null;
  reorder_level: number;
  stock: number;
}

export interface LowStockListOut {
  items: LowStockVariantOut[];
  pagination: PaginationMeta;
}

export interface SaleItemIn {
  variant_id: string;
  qty: number;
  unit_price: number;
}

export interface SaleCreateIn {
  payment_method: PaymentMethod;
  channel: SalesChannel;
  note?: string | null;
  items: SaleItemIn[];
}

export interface SaleCreateOut {
  id: string;
  total: number;
}

export interface SaleOut {
  id: string;
  kind: SaleKind;
  parent_sale_id?: string | null;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  note?: string | null;
  total_amount: number;
  created_at: string;
}

export interface SaleListOut {
  pagination: PaginationMeta;
  start_date: string | null;
  end_date: string | null;
  items: SaleOut[];
}

export interface SaleRefundOptionOut {
  variant_id: string;
  product_id: string;
  product_name: string;
  size: string;
  label?: string | null;
  sku?: string | null;
  sold_qty: number;
  refunded_qty: number;
  refundable_qty: number;
  default_unit_price?: number | null;
}

export interface SaleRefundOptionsOut {
  sale_id: string;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  items: SaleRefundOptionOut[];
}

export type OrderStatus =
  | "pending"
  | "paid"
  | "processing"
  | "fulfilled"
  | "cancelled"
  | "refunded";

export interface OrderItemIn {
  variant_id: string;
  qty: number;
  unit_price: number;
}

export interface OrderCreateIn {
  customer_id?: string;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  note?: string | null;
  items: OrderItemIn[];
}

export interface OrderCreateOut {
  id: string;
  total: number;
  status: OrderStatus;
  sale_id?: string | null;
}

export interface OrderOut {
  id: string;
  customer_id?: string | null;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  status: OrderStatus;
  total_amount: number;
  sale_id?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrderStatusUpdateIn {
  status: OrderStatus;
  note?: string | null;
}

export interface OrderListOut {
  pagination: PaginationMeta;
  start_date: string | null;
  end_date: string | null;
  status?: OrderStatus | null;
  channel?: SalesChannel | null;
  customer_id?: string | null;
  items: OrderOut[];
}

export type InvoiceStatus =
  | "draft"
  | "sent"
  | "partially_paid"
  | "paid"
  | "overdue"
  | "cancelled";

export type ReminderChannel = "email" | "sms" | "whatsapp";
export type InvoiceTemplateStatus = "active" | "archived";

export interface InvoiceInstallmentCreateIn {
  due_date: string;
  amount: number;
  note?: string;
}

export interface InvoiceReminderPolicyIn {
  enabled?: boolean;
  first_delay_days?: number;
  cadence_days?: number;
  max_reminders?: number;
  escalation_after_days?: number;
  channels?: ReminderChannel[];
}

export interface InvoiceCreateIn {
  customer_id?: string;
  order_id?: string;
  currency?: string;
  fx_rate_to_base?: number;
  total_amount?: number;
  issue_date?: string;
  due_date?: string;
  template_id?: string;
  reminder_policy?: InvoiceReminderPolicyIn;
  installments?: InvoiceInstallmentCreateIn[];
  note?: string | null;
  send_now?: boolean;
}

export interface InvoiceCreateOut {
  id: string;
  status: InvoiceStatus;
  total_amount: number;
  total_amount_base: number;
  currency: string;
  base_currency: string;
}

export interface InvoiceOut {
  id: string;
  customer_id?: string | null;
  order_id?: string | null;
  status: InvoiceStatus;
  currency: string;
  base_currency: string;
  fx_rate_to_base: number;
  total_amount: number;
  total_amount_base: number;
  amount_paid: number;
  amount_paid_base: number;
  outstanding_amount: number;
  outstanding_amount_base: number;
  template_id?: string | null;
  payment_reference?: string | null;
  payment_method?: PaymentMethod | null;
  issue_date: string;
  due_date?: string | null;
  last_sent_at?: string | null;
  paid_at?: string | null;
  reminder_count: number;
  escalation_level: number;
  next_reminder_at?: string | null;
  note?: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceListOut {
  pagination: PaginationMeta;
  start_date: string | null;
  end_date: string | null;
  status?: InvoiceStatus | null;
  customer_id?: string | null;
  order_id?: string | null;
  items: InvoiceOut[];
}

export interface InvoiceMarkPaidIn {
  amount?: number;
  payment_method?: PaymentMethod;
  payment_reference?: string;
  idempotency_key?: string;
  note?: string;
}

export interface InvoiceReminderIn {
  channel?: ReminderChannel;
  note?: string;
}

export interface InvoicePaymentCreateIn {
  amount: number;
  payment_method?: PaymentMethod;
  payment_reference?: string;
  idempotency_key?: string;
  paid_at?: string;
  note?: string;
}

export interface InvoicePaymentOut {
  id: string;
  invoice_id: string;
  amount: number;
  amount_base: number;
  currency: string;
  fx_rate_to_base: number;
  payment_method?: PaymentMethod | null;
  payment_reference?: string | null;
  idempotency_key?: string | null;
  note?: string | null;
  paid_at: string;
  created_at: string;
}

export interface InvoicePaymentListOut {
  items: InvoicePaymentOut[];
  pagination: PaginationMeta;
}

export interface InvoiceInstallmentOut {
  id: string;
  due_date: string;
  amount: number;
  paid_amount: number;
  remaining_amount: number;
  status: string;
  note?: string | null;
}

export interface InvoiceInstallmentListOut {
  items: InvoiceInstallmentOut[];
  total_scheduled: number;
  total_paid: number;
  total_remaining: number;
}

export interface InvoiceInstallmentUpsertIn {
  items: InvoiceInstallmentCreateIn[];
}

export interface InvoiceReminderPolicyOut {
  enabled: boolean;
  first_delay_days: number;
  cadence_days: number;
  max_reminders: number;
  escalation_after_days: number;
  channels: ReminderChannel[];
  reminder_count: number;
  escalation_level: number;
  next_reminder_at?: string | null;
}

export interface InvoiceReminderRunOut {
  processed_count: number;
  reminders_created: number;
  escalated_count: number;
  next_due_count: number;
}

export interface InvoiceTemplateUpsertIn {
  template_id?: string;
  name: string;
  status?: InvoiceTemplateStatus;
  is_default?: boolean;
  brand_name?: string;
  logo_url?: string;
  primary_color?: string;
  footer_text?: string;
  config_json?: Record<string, unknown>;
}

export interface InvoiceTemplateOut {
  id: string;
  name: string;
  status: InvoiceTemplateStatus;
  is_default: boolean;
  brand_name?: string | null;
  logo_url?: string | null;
  primary_color?: string | null;
  footer_text?: string | null;
  config_json?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface InvoiceTemplateListOut {
  items: InvoiceTemplateOut[];
}

export interface InvoiceFxQuoteOut {
  from_currency: string;
  to_currency: string;
  rate: number;
  as_of: string;
}

export interface InvoiceAgingBucketOut {
  bucket: string;
  amount: number;
  count: number;
}

export interface InvoiceAgingCustomerOut {
  customer_id?: string | null;
  amount: number;
  count: number;
}

export interface InvoiceAgingDashboardOut {
  as_of_date: string;
  base_currency: string;
  total_outstanding: number;
  overdue_count: number;
  partially_paid_count: number;
  buckets: InvoiceAgingBucketOut[];
  by_currency: Record<string, number>;
  top_customers: InvoiceAgingCustomerOut[];
}

export interface InvoiceStatementItemOut {
  customer_id?: string | null;
  invoices_count: number;
  total_invoiced: number;
  total_paid: number;
  total_outstanding: number;
  by_currency: Record<string, number>;
}

export interface InvoiceStatementListOut {
  items: InvoiceStatementItemOut[];
  start_date: string;
  end_date: string;
}

export interface InvoiceStatementExportOut {
  filename: string;
  content_type: string;
  row_count: number;
  csv_content: string;
}

export interface CustomerTagCreateIn {
  name: string;
  color?: string;
}

export interface CustomerTagOut {
  id: string;
  name: string;
  color?: string | null;
  created_at: string;
}

export interface CustomerTagListOut {
  items: CustomerTagOut[];
}

export interface CustomerCreateIn {
  name: string;
  phone?: string;
  email?: string;
  note?: string;
  tag_ids?: string[];
}

export interface CustomerUpdateIn {
  name?: string;
  phone?: string;
  email?: string;
  note?: string;
}

export interface CustomerCreateOut {
  id: string;
}

export interface CustomerOut {
  id: string;
  name: string;
  phone?: string | null;
  email?: string | null;
  note?: string | null;
  tags: CustomerTagOut[];
  created_at: string;
  updated_at: string;
}

export interface CustomerListOut {
  items: CustomerOut[];
  pagination: PaginationMeta;
  q?: string | null;
  tag_id?: string | null;
}

export interface RefundItemIn {
  variant_id: string;
  qty: number;
  unit_price?: number | null;
}

export interface RefundCreateIn {
  payment_method?: PaymentMethod | null;
  channel?: SalesChannel | null;
  note?: string | null;
  items: RefundItemIn[];
}

export interface ExpenseCreateIn {
  category: string;
  amount: number;
  note?: string | null;
}

export interface ExpenseCreateOut {
  id: string;
}

export interface ExpenseOut {
  id: string;
  category: string;
  amount: number;
  note?: string | null;
  created_at: string;
}

export interface ExpenseListOut {
  pagination: PaginationMeta;
  start_date: string | null;
  end_date: string | null;
  items: ExpenseOut[];
}

export interface AIAskIn {
  question: string;
}

export interface AITokenUsageOut {
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
}

export interface AIResponseOut {
  id: string;
  insight_type: string;
  response: string;
  provider: string;
  model: string;
  token_usage?: AITokenUsageOut | null;
  estimated_cost_usd?: number | null;
}

export interface AIFeatureSnapshotOut {
  id: string;
  window_start_date: string;
  window_end_date: string;
  orders_count: number;
  paid_orders_count: number;
  gross_revenue: number;
  refunds_count: number;
  refunds_amount: number;
  net_revenue: number;
  expenses_total: number;
  refund_rate: number;
  stockout_events_count: number;
  campaigns_sent_count: number;
  campaigns_failed_count: number;
  repeat_customers_count: number;
  created_at: string;
}

export interface AIInsightV2Out {
  id: string;
  feature_snapshot_id?: string | null;
  insight_type: string;
  severity: string;
  title: string;
  summary: string;
  confidence_score: number;
  status: string;
  context_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface AIInsightV2ListOut {
  items: AIInsightV2Out[];
  status?: string | null;
  insight_type?: string | null;
}

export interface AIPrescriptiveActionOut {
  id: string;
  insight_id: string;
  action_type: string;
  title: string;
  description: string;
  payload_json?: Record<string, unknown> | null;
  status: string;
  decision_note?: string | null;
  decided_by_user_id?: string | null;
  decided_at?: string | null;
  executed_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIPrescriptiveActionListOut {
  items: AIPrescriptiveActionOut[];
  status?: string | null;
}

export interface AIPrescriptiveDecisionIn {
  decision: "approve" | "reject";
  note?: string | null;
}

export interface AIInsightsGenerateOut {
  snapshot: AIFeatureSnapshotOut;
  insights: AIInsightV2Out[];
  actions_created: number;
}

export type TeamRole = "owner" | "admin" | "staff";

export interface TeamMemberCreateIn {
  email: string;
  role: TeamRole;
}

export interface TeamMemberUpdateIn {
  role?: TeamRole;
  is_active?: boolean;
}

export interface TeamMemberOut {
  membership_id: string;
  user_id: string;
  email: string;
  username: string;
  full_name?: string | null;
  role: TeamRole;
  is_active: boolean;
  created_at: string;
}

export interface TeamMemberListOut {
  items: TeamMemberOut[];
  pagination: PaginationMeta;
}

export interface TeamListFilter extends PaginationFilter {
  include_inactive?: boolean;
}

export interface TeamInvitationCreateIn {
  email: string;
  role: TeamRole;
  expires_in_days?: number;
}

export interface TeamInvitationOut {
  invitation_id: string;
  business_id: string;
  invited_by_user_id: string;
  accepted_by_user_id?: string | null;
  email: string;
  role: TeamRole;
  status: string;
  expires_at: string;
  invited_at: string;
  accepted_at?: string | null;
  revoked_at?: string | null;
}

export interface TeamInvitationCreateOut extends TeamInvitationOut {
  invitation_token: string;
}

export interface TeamInvitationListOut {
  items: TeamInvitationOut[];
  pagination: PaginationMeta;
}

export interface TeamInvitationListFilter extends PaginationFilter {
  status?: string;
}

export interface TeamInvitationAcceptIn {
  invitation_token: string;
}

export interface AIFeatureStoreFilter {
  window_days?: number;
}

export interface AIInsightV2Filter {
  status?: string;
  insight_type?: string;
}

export interface AIPrescriptiveActionFilter {
  status?: string;
}

export interface ShipmentListFilter extends PaginationFilter {
  order_id?: string;
  status?: string;
}

export interface LocationListFilter extends PaginationFilter {
  include_inactive?: boolean;
}

export interface LocationLowStockFilter extends PaginationFilter {
  location_id?: string;
  threshold?: number;
}

export interface IntegrationOutboxFilter extends PaginationFilter {
  status?: string;
  target_app_key?: string;
}

export interface CampaignSegmentListFilter extends PaginationFilter {
  q?: string;
  is_active?: boolean;
}

export interface CampaignTemplateListFilter extends PaginationFilter {
  status?: CampaignTemplateStatus;
  channel?: CampaignChannel;
}

export interface CampaignConsentListFilter extends PaginationFilter {
  channel?: CampaignChannel;
  status?: ConsentStatus;
}

export interface CampaignListFilter extends PaginationFilter {
  status?: CampaignStatus;
  channel?: CampaignChannel;
}

export interface CampaignRecipientListFilter extends PaginationFilter {
  status?: CampaignRecipientStatus;
}

export interface AutomationRuleFilter extends PaginationFilter {
  status?: AutomationRuleStatus;
  trigger_event_type?: string;
}

export interface AutomationRunFilter extends PaginationFilter {
  rule_id?: string;
  status?: AutomationRunStatus;
}

export interface AuditLogOut {
  id: string;
  actor_user_id: string;
  action: string;
  target_type: string;
  target_id?: string | null;
  metadata_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListOut {
  items: AuditLogOut[];
  pagination: PaginationMeta;
}

export interface AnalyticsMartRefreshOut {
  start_date: string;
  end_date: string;
  rows_refreshed: number;
}

export interface ChannelProfitabilityItemOut {
  channel: string;
  revenue: number;
  cogs: number;
  expenses: number;
  gross_profit: number;
  net_profit: number;
  orders_count: number;
  margin_pct: number;
}

export interface ChannelProfitabilityOut {
  start_date: string;
  end_date: string;
  items: ChannelProfitabilityItemOut[];
}

export interface CohortRetentionItemOut {
  cohort_month: string;
  total_customers: number;
  retained_customers: number;
  retention_rate: number;
}

export interface CohortRetentionOut {
  months_after: number;
  items: CohortRetentionItemOut[];
}

export interface InventoryAgingItemOut {
  variant_id: string;
  bucket: string;
  stock: number;
  estimated_value: number;
  days_since_last_movement?: number | null;
}

export interface InventoryAgingOut {
  as_of_date: string;
  stockout_count: number;
  total_estimated_inventory_value: number;
  items: InventoryAgingItemOut[];
}

export interface MarketingAttributionEventIn {
  event_type: string;
  channel: string;
  source?: string;
  medium?: string;
  campaign_name?: string;
  order_id?: string;
  revenue_amount?: number;
  metadata_json?: Record<string, unknown>;
  event_time?: string;
}

export interface MarketingAttributionEventOut {
  id: string;
  event_type: string;
  channel: string;
  source?: string | null;
  medium?: string | null;
  campaign_name?: string | null;
  order_id?: string | null;
  revenue_amount: number;
  metadata_json?: Record<string, unknown> | null;
  event_time: string;
  created_at: string;
}

export interface ReportExportOut {
  filename: string;
  content_type: string;
  row_count: number;
  csv_content: string;
}

export interface ReportScheduleCreateIn {
  name: string;
  report_type: "channel_profitability" | "cohorts" | "inventory_aging";
  frequency?: string;
  recipient_email: string;
  status?: string;
  config_json?: Record<string, unknown>;
  next_run_at?: string;
}

export interface ReportScheduleOut {
  id: string;
  name: string;
  report_type: string;
  frequency: string;
  recipient_email: string;
  status: string;
  config_json?: Record<string, unknown> | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ReportScheduleListOut {
  items: ReportScheduleOut[];
}

export interface PosOfflineOrderItemIn {
  variant_id: string;
  qty: number;
  unit_price: number;
}

export interface PosOfflineOrderIn {
  client_event_id: string;
  customer_id?: string;
  payment_method: PaymentMethod;
  channel: SalesChannel;
  note?: string;
  created_at?: string;
  items: PosOfflineOrderItemIn[];
}

export interface PosOfflineSyncIn {
  conflict_policy?: "reject_conflict" | "adjust_to_available";
  orders: PosOfflineOrderIn[];
}

export interface PosOfflineSyncResultOut {
  client_event_id: string;
  status: string;
  order_id?: string | null;
  conflict_code?: string | null;
  note?: string | null;
}

export interface PosOfflineSyncOut {
  processed: number;
  created: number;
  conflicted: number;
  duplicate: number;
  results: PosOfflineSyncResultOut[];
}

export interface PosShiftOpenIn {
  opening_cash: number;
  note?: string;
}

export interface PosShiftCloseIn {
  closing_cash: number;
  note?: string;
}

export interface PosShiftOut {
  id: string;
  status: string;
  opening_cash: number;
  closing_cash?: number | null;
  expected_cash?: number | null;
  cash_difference?: number | null;
  opened_by_user_id: string;
  closed_by_user_id?: string | null;
  note?: string | null;
  opened_at: string;
  closed_at?: string | null;
}

export interface PosShiftCurrentOut {
  shift?: PosShiftOut | null;
}

export interface CustomerPiiOrderOut {
  id: string;
  status: string;
  channel: string;
  total_amount: number;
  created_at: string;
}

export interface CustomerPiiInvoiceOut {
  id: string;
  status: string;
  currency: string;
  total_amount: number;
  amount_paid: number;
  issue_date?: string | null;
  created_at: string;
}

export interface CustomerPiiExportOut {
  customer_id: string;
  exported_at: string;
  customer: Record<string, unknown>;
  orders: CustomerPiiOrderOut[];
  invoices: CustomerPiiInvoiceOut[];
}

export interface CustomerPiiDeleteOut {
  customer_id: string;
  anonymized: boolean;
  deleted_fields: string[];
  processed_at: string;
}

export interface AuditArchiveOut {
  archive_id: string;
  cutoff_date: string;
  records_count: number;
  archived_at: string;
}

export interface RolePermissionOut {
  role: string;
  permissions: string[];
}

export interface PermissionMatrixOut {
  items: RolePermissionOut[];
}

export interface DateFilter {
  start_date?: string;
  end_date?: string;
}

export interface PaginationFilter {
  limit?: number;
  offset?: number;
}

export interface SalesFilter extends DateFilter, PaginationFilter {
  include_refunds?: boolean;
}

export interface OrderFilter extends DateFilter, PaginationFilter {
  status?: OrderStatus;
  channel?: SalesChannel;
  customer_id?: string;
}

export interface InvoiceFilter extends DateFilter, PaginationFilter {
  status?: InvoiceStatus;
  customer_id?: string;
  order_id?: string;
}

export interface InvoiceTemplateFilter {
  status?: InvoiceTemplateStatus;
}

export interface InvoiceStatementFilter extends DateFilter {
  start_date: string;
  end_date: string;
}

export interface CustomerFilter extends PaginationFilter {
  q?: string;
  tag_id?: string;
}

export interface AuditLogFilter extends DateFilter, PaginationFilter {
  actor_user_id?: string;
  action?: string;
}

export interface AnalyticsDateFilter extends DateFilter {
  start_date?: string;
  end_date?: string;
}

export interface CreditProfileV2Filter {
  window_days?: number;
}

export interface CreditForecastFilter {
  horizon_days?: number;
  history_days?: number;
  interval_days?: number;
}

export interface CreditExportPackFilter {
  window_days?: number;
  history_days?: number;
  horizon_days?: number;
}

export interface FinanceGuardrailEvaluateFilter {
  window_days?: number;
  history_days?: number;
  horizon_days?: number;
  interval_days?: number;
}

export interface CreditImprovementPlanFilter {
  window_days?: number;
  target_score?: number;
}

export interface CohortFilter {
  months_after?: number;
}

export interface InventoryAgingFilter {
  as_of_date?: string;
}

export interface ReportExportFilter extends DateFilter {
  report_type: "channel_profitability" | "cohorts" | "inventory_aging";
  months_after?: number;
}

export interface PublicApiScopeOut {
  scope: string;
  description: string;
}

export interface PublicApiScopeCatalogOut {
  items: PublicApiScopeOut[];
}

export interface PublicApiBusinessOut {
  business_id: string;
  business_name: string;
  base_currency: string;
}

export interface PublicApiProductOut {
  id: string;
  name: string;
  category?: string;
  is_published: boolean;
  created_at: string;
}

export interface PublicApiProductListOut {
  items: PublicApiProductOut[];
  pagination: PaginationMeta;
  q?: string;
  category?: string;
  is_published?: boolean;
}

export interface PublicApiOrderOut {
  id: string;
  customer_id?: string;
  payment_method: string;
  channel: string;
  status: string;
  total_amount: number;
  created_at: string;
  updated_at: string;
}

export interface PublicApiOrderListOut {
  items: PublicApiOrderOut[];
  pagination: PaginationMeta;
  status?: string;
}

export interface PublicApiCustomerOut {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  created_at: string;
  updated_at: string;
}

export interface PublicApiCustomerListOut {
  items: PublicApiCustomerOut[];
  pagination: PaginationMeta;
  q?: string;
}

export interface PublicApiKeyCreateIn {
  name: string;
  scopes: string[];
  expires_at?: string;
}

export interface PublicApiKeyOut {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  status: "active" | "revoked";
  version: number;
  last_used_at?: string;
  expires_at?: string;
  rotated_at?: string;
  revoked_at?: string;
  created_at: string;
  updated_at: string;
}

export interface PublicApiKeyCreateOut extends PublicApiKeyOut {
  api_key: string;
}

export interface PublicApiKeyRotateOut extends PublicApiKeyOut {
  api_key: string;
}

export interface PublicApiKeyListOut {
  items: PublicApiKeyOut[];
}

export interface WebhookSubscriptionCreateIn {
  name: string;
  endpoint_url: string;
  description?: string;
  events: string[];
  max_attempts?: number;
  retry_seconds?: number;
}

export interface WebhookSubscriptionUpdateIn {
  endpoint_url?: string;
  description?: string;
  events?: string[];
  status?: "active" | "paused";
  max_attempts?: number;
  retry_seconds?: number;
}

export interface WebhookSubscriptionOut {
  id: string;
  name: string;
  endpoint_url: string;
  description?: string;
  events: string[];
  status: "active" | "paused";
  max_attempts: number;
  retry_seconds: number;
  secret_hint: string;
  last_delivery_at?: string;
  created_at: string;
  updated_at: string;
}

export interface WebhookSubscriptionCreateOut extends WebhookSubscriptionOut {
  signing_secret: string;
}

export interface WebhookSubscriptionRotateSecretOut {
  subscription_id: string;
  signing_secret: string;
  rotated_at: string;
}

export interface WebhookSubscriptionListOut {
  items: WebhookSubscriptionOut[];
}

export interface WebhookDeliveryOut {
  id: string;
  subscription_id: string;
  outbox_event_id: string;
  event_type: string;
  status: "pending" | "delivered" | "failed" | "dead_letter";
  attempt_count: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error?: string;
  last_response_code?: number;
  delivered_at?: string;
  created_at: string;
  updated_at: string;
}

export interface WebhookDeliveryListOut {
  items: WebhookDeliveryOut[];
  pagination: PaginationMeta;
  subscription_id?: string;
  status?: "pending" | "delivered" | "failed" | "dead_letter";
}

export interface WebhookDispatchOut {
  enqueued: number;
  processed: number;
  delivered: number;
  failed: number;
  dead_lettered: number;
}

export interface DeveloperPortalDocOut {
  section: string;
  title: string;
  summary: string;
  relative_path: string;
}

export interface DeveloperPortalDocsOut {
  items: DeveloperPortalDocOut[];
  generated_at: string;
}

export interface MarketplaceListingCreateIn {
  app_key: string;
  display_name: string;
  description: string;
  category: string;
  requested_scopes: string[];
}

export interface MarketplaceListingReviewIn {
  decision: "under_review" | "approved" | "rejected";
  review_notes?: string;
}

export interface MarketplaceListingPublishIn {
  publish: boolean;
}

export interface MarketplaceListingOut {
  id: string;
  app_key: string;
  display_name: string;
  description: string;
  category: string;
  requested_scopes: string[];
  status: "draft" | "submitted" | "under_review" | "approved" | "rejected" | "published";
  review_notes?: string;
  submitted_at?: string;
  reviewed_at?: string;
  published_at?: string;
  created_at: string;
  updated_at: string;
}

export interface MarketplaceListingListOut {
  items: MarketplaceListingOut[];
  pagination: PaginationMeta;
  status?: "draft" | "submitted" | "under_review" | "approved" | "rejected" | "published";
}

export interface WebhookDeliveryFilter extends PaginationFilter {
  subscription_id?: string;
  status?: "pending" | "delivered" | "failed" | "dead_letter";
}

export interface MarketplaceListingFilter extends PaginationFilter {
  status?: "draft" | "submitted" | "under_review" | "approved" | "rejected" | "published";
}
