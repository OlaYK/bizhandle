import { lazy, Suspense } from "react";
import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "./components/layout/app-shell";
import { PageLoading } from "./components/state/page-loading";
import { ProtectedRoute } from "./routes/protected-route";

const LoginPage = lazy(() => import("./pages/login-page").then((module) => ({ default: module.LoginPage })));
const RegisterPage = lazy(() => import("./pages/register-page").then((module) => ({ default: module.RegisterPage })));
const DashboardPage = lazy(() => import("./pages/dashboard-page").then((module) => ({ default: module.DashboardPage })));
const InventoryPage = lazy(() => import("./pages/inventory-page").then((module) => ({ default: module.InventoryPage })));
const SalesPage = lazy(() => import("./pages/sales-page").then((module) => ({ default: module.SalesPage })));
const OrdersPage = lazy(() => import("./pages/orders-page").then((module) => ({ default: module.OrdersPage })));
const InvoicesPage = lazy(() => import("./pages/invoices-page").then((module) => ({ default: module.InvoicesPage })));
const CustomersPage = lazy(() => import("./pages/customers-page").then((module) => ({ default: module.CustomersPage })));
const ExpensesPage = lazy(() => import("./pages/expenses-page").then((module) => ({ default: module.ExpensesPage })));
const InsightsPage = lazy(() => import("./pages/insights-page").then((module) => ({ default: module.InsightsPage })));
const CreditProfilePage = lazy(() =>
  import("./pages/credit-profile-page").then((module) => ({ default: module.CreditProfilePage }))
);
const TeamPage = lazy(() => import("./pages/team-page").then((module) => ({ default: module.TeamPage })));
const AuditLogsPage = lazy(() =>
  import("./pages/audit-logs-page").then((module) => ({ default: module.AuditLogsPage }))
);
const SettingsPage = lazy(() => import("./pages/settings-page").then((module) => ({ default: module.SettingsPage })));
const StorefrontSettingsPage = lazy(() =>
  import("./pages/storefront-settings-page").then((module) => ({ default: module.StorefrontSettingsPage }))
);
const StorefrontPage = lazy(() =>
  import("./pages/storefront-page").then((module) => ({ default: module.StorefrontPage }))
);
const StorefrontProductPage = lazy(() =>
  import("./pages/storefront-product-page").then((module) => ({ default: module.StorefrontProductPage }))
);
const PaymentsPage = lazy(() =>
  import("./pages/payments-page").then((module) => ({ default: module.PaymentsPage }))
);
const ShippingPage = lazy(() =>
  import("./pages/shipping-page").then((module) => ({ default: module.ShippingPage }))
);
const LocationsPage = lazy(() =>
  import("./pages/locations-page").then((module) => ({ default: module.LocationsPage }))
);
const IntegrationsPage = lazy(() =>
  import("./pages/integrations-page").then((module) => ({ default: module.IntegrationsPage }))
);
const DeveloperPortalPage = lazy(() =>
  import("./pages/developer-portal-page").then((module) => ({ default: module.DeveloperPortalPage }))
);
const CampaignsPage = lazy(() =>
  import("./pages/campaigns-page").then((module) => ({ default: module.CampaignsPage }))
);
const AutomationPage = lazy(() =>
  import("./pages/automation-page").then((module) => ({ default: module.AutomationPage }))
);
const AnalyticsPage = lazy(() =>
  import("./pages/analytics-page").then((module) => ({ default: module.AnalyticsPage }))
);
const PosPage = lazy(() =>
  import("./pages/pos-page").then((module) => ({ default: module.PosPage }))
);
const PrivacyPage = lazy(() =>
  import("./pages/privacy-page").then((module) => ({ default: module.PrivacyPage }))
);
const NotFoundPage = lazy(() => import("./pages/not-found-page").then((module) => ({ default: module.NotFoundPage })));

function withSuspense(element: JSX.Element) {
  return <Suspense fallback={<PageLoading />}>{element}</Suspense>;
}

export const router = createBrowserRouter([
  { path: "/login", element: withSuspense(<LoginPage />) },
  { path: "/register", element: withSuspense(<RegisterPage />) },
  { path: "/store/:slug", element: withSuspense(<StorefrontPage />) },
  { path: "/store/:slug/products/:productId", element: withSuspense(<StorefrontProductPage />) },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: withSuspense(<DashboardPage />) },
          { path: "/inventory", element: withSuspense(<InventoryPage />) },
          { path: "/sales", element: withSuspense(<SalesPage />) },
          { path: "/orders", element: withSuspense(<OrdersPage />) },
          { path: "/payments", element: withSuspense(<PaymentsPage />) },
          { path: "/shipping", element: withSuspense(<ShippingPage />) },
          { path: "/locations", element: withSuspense(<LocationsPage />) },
          { path: "/integrations", element: withSuspense(<IntegrationsPage />) },
          { path: "/developers", element: withSuspense(<DeveloperPortalPage />) },
          { path: "/campaigns", element: withSuspense(<CampaignsPage />) },
          { path: "/automation", element: withSuspense(<AutomationPage />) },
          { path: "/analytics", element: withSuspense(<AnalyticsPage />) },
          { path: "/pos", element: withSuspense(<PosPage />) },
          { path: "/invoices", element: withSuspense(<InvoicesPage />) },
          { path: "/customers", element: withSuspense(<CustomersPage />) },
          { path: "/expenses", element: withSuspense(<ExpensesPage />) },
          { path: "/insights", element: withSuspense(<InsightsPage />) },
          { path: "/credit-profile", element: withSuspense(<CreditProfilePage />) },
          { path: "/team", element: withSuspense(<TeamPage />) },
          { path: "/audit-logs", element: withSuspense(<AuditLogsPage />) },
          { path: "/privacy", element: withSuspense(<PrivacyPage />) },
          { path: "/settings", element: withSuspense(<SettingsPage />) },
          { path: "/storefront-settings", element: withSuspense(<StorefrontSettingsPage />) }
        ]
      }
    ]
  },
  { path: "/404", element: withSuspense(<NotFoundPage />) },
  { path: "*", element: <Navigate to="/404" replace /> }
]);
