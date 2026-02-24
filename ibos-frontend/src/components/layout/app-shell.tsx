import {
  ClipboardCheck,
  Bot,
  ChartNoAxesCombined,
  ClipboardList,
  CreditCard,
  FileText,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  Megaphone,
  Moon,
  Package,
  Radio,
  Settings,
  ShoppingCart,
  Sun,
  User,
  Users,
  Workflow,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { authService } from "../../api/services";
import { MoniDeskLogo } from "../brand/monidesk-logo";
import { cn } from "../../lib/cn";
import { useAuth } from "../../hooks/use-auth";
import { useTheme } from "../../hooks/use-theme";

const navItems = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/inventory", label: "Inventory", icon: Package },
  { to: "/sales", label: "Sales", icon: ChartNoAxesCombined },
  { to: "/orders", label: "Orders", icon: ShoppingCart },
  { to: "/payments", label: "Payments", icon: CreditCard },
  { to: "/shipping", label: "Shipping", icon: ShoppingCart },
  { to: "/locations", label: "Locations", icon: Package },
  { to: "/integrations", label: "Integrations", icon: Settings },
  { to: "/developers", label: "Developers", icon: Settings },
  { to: "/campaigns", label: "Campaigns", icon: Megaphone },
  { to: "/automation", label: "Automation", icon: Workflow },
  { to: "/analytics", label: "Analytics", icon: ChartNoAxesCombined },
  { to: "/pos", label: "POS", icon: Radio },
  { to: "/invoices", label: "Invoices", icon: FileText },
  { to: "/customers", label: "Customers", icon: User },
  { to: "/expenses", label: "Expenses", icon: ClipboardList },
  { to: "/insights", label: "AI", icon: Bot },
  { to: "/credit-profile", label: "Credit", icon: CreditCard },
  { to: "/team", label: "Team", icon: Users },
  { to: "/audit-logs", label: "Audit", icon: ClipboardCheck },
  { to: "/privacy", label: "Privacy", icon: LockKeyhole },
  { to: "/settings", label: "Settings", icon: Settings }
];

const titleByPath: Record<string, string> = {
  "/": "Dashboard",
  "/inventory": "Inventory Operations",
  "/sales": "Sales Control",
  "/orders": "Orders Workspace",
  "/payments": "Payments Operations",
  "/shipping": "Shipping Operations",
  "/locations": "Locations Operations",
  "/integrations": "Integrations Center",
  "/developers": "Developer Platform",
  "/campaigns": "Campaigns and Retention",
  "/automation": "Automation Workflows",
  "/analytics": "Analytics Intelligence",
  "/pos": "POS Mobile Console",
  "/invoices": "Invoices Workspace",
  "/customers": "Customers Workspace",
  "/expenses": "Expense Tracking",
  "/insights": "AI Insights",
  "/credit-profile": "Credit Profile",
  "/team": "Team Management",
  "/audit-logs": "Audit Logs",
  "/privacy": "Security and Privacy",
  "/settings": "Settings",
  "/storefront-settings": "Storefront Settings"
};

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const title = titleByPath[location.pathname] ?? "MoniDesk";
  const { resolvedTheme, toggleTheme } = useTheme();
  const { tokens, clearAuth } = useAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);

  async function handleSignOut() {
    if (isSigningOut) return;
    setIsSigningOut(true);
    try {
      if (tokens?.refreshToken) {
        await authService.logout({ refresh_token: tokens.refreshToken });
      }
    } catch {
      // Best effort revoke; local sign-out still executes.
    } finally {
      clearAuth();
      navigate("/login", { replace: true });
      setIsSigningOut(false);
    }
  }

  return (
    <div className="min-h-screen bg-surface-50 text-surface-800 dark:bg-surface-900 dark:text-surface-100">
      <div className="fixed inset-0 -z-10 brand-grid opacity-35" />
      <div className="pointer-events-none fixed inset-0 -z-10 animate-aurora bg-[radial-gradient(circle_at_24%_22%,rgba(39,194,92,0.18),transparent_38%),radial-gradient(circle_at_78%_20%,rgba(73,124,242,0.16),transparent_34%),radial-gradient(circle_at_50%_90%,rgba(248,194,13,0.1),transparent_40%)]" />
      <div className="pointer-events-none fixed -left-14 top-24 -z-10 h-44 w-44 rounded-full bg-mint-300/30 blur-3xl animate-float-slow" />
      <div className="pointer-events-none fixed right-6 top-32 -z-10 h-40 w-40 rounded-full bg-cobalt-300/30 blur-3xl animate-float-mid" />
      <div className="pointer-events-none fixed bottom-16 left-1/3 -z-10 h-28 w-28 rounded-full bg-accent-300/25 blur-2xl animate-pulse-glow" />

      <aside className="fixed inset-y-0 left-0 hidden w-64 overflow-y-auto border-r border-surface-100 bg-white/90 p-5 backdrop-blur dark:border-surface-700 dark:bg-surface-900/85 md:block">
        <div className="mb-8">
          <MoniDeskLogo size="md" />
        </div>
        <nav className="space-y-2">
          {navItems.map((item, index) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "animate-fade-up flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-semibold transition",
                  isActive
                    ? "bg-[linear-gradient(140deg,#203f62,#17314e)] text-white shadow-glow"
                    : "text-surface-600 hover:bg-surface-100 hover:text-surface-800 hover:translate-x-1 dark:text-surface-200 dark:hover:bg-surface-700/40 dark:hover:text-surface-100"
                )
              }
              end={item.to === "/"}
              style={{ animationDelay: `${index * 45}ms` }}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
          <button
            type="button"
            onClick={handleSignOut}
            disabled={isSigningOut}
            className="mt-4 flex w-full items-center gap-3 rounded-xl border border-red-300/60 bg-red-50/70 px-3 py-2 text-sm font-semibold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-70 dark:border-red-500/40 dark:bg-red-900/25 dark:text-red-200 dark:hover:bg-red-900/35"
          >
            <LogOut className="h-4 w-4" />
            {isSigningOut ? "Signing out..." : "Logout"}
          </button>
        </nav>
      </aside>

      <div className="pb-[calc(5.5rem+env(safe-area-inset-bottom))] md:pb-0 md:pl-64">
        <header className="safe-top sticky top-0 z-20 border-b border-surface-100 bg-white/85 backdrop-blur dark:border-surface-700 dark:bg-surface-900/80">
          <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6">
            <p className="text-xs uppercase tracking-wide text-surface-500 dark:text-surface-300">Control Center</p>
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-heading text-xl font-bold text-surface-800 dark:text-surface-100">{title}</h2>
              <div className="flex items-center gap-2">
                <NavLink
                  to="/settings"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-surface-200 bg-white text-xs font-semibold text-surface-700 transition hover:bg-surface-50 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:hover:bg-surface-700"
                  aria-label="Open settings"
                >
                  <Settings className="h-4 w-4" />
                </NavLink>
                <button
                  type="button"
                  onClick={toggleTheme}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-surface-200 bg-white text-xs font-semibold text-surface-700 transition hover:bg-surface-50 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:hover:bg-surface-700"
                  aria-label="Toggle theme"
                >
                  {resolvedTheme === "dark" ? (
                    <Sun className="h-4 w-4" />
                  ) : (
                    <Moon className="h-4 w-4" />
                  )}
                </button>
                <MoniDeskLogo size="sm" showTagline={false} className="md:hidden" />
              </div>
            </div>
          </div>
        </header>

        <AnimatePresence mode="wait">
          <motion.main
            key={location.pathname}
            initial={{ opacity: 0, y: 12, scale: 0.995 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.995 }}
            transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            className="mx-auto max-w-7xl p-4 sm:p-6"
          >
            <Outlet />
          </motion.main>
        </AnimatePresence>
      </div>

      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-40 border-t border-surface-100 bg-white/95 backdrop-blur dark:border-surface-700 dark:bg-surface-900/95 md:hidden">
        <div className="grid grid-cols-12">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  "flex flex-col items-center gap-1 py-2 text-[10px] font-semibold transition",
                  isActive
                    ? "bg-surface-100/80 text-surface-800 dark:bg-surface-700/50 dark:text-surface-100"
                    : "text-surface-400 hover:text-surface-700 dark:text-surface-400 dark:hover:text-surface-200"
                )
              }
              end={item.to === "/"}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
