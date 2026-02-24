import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { dashboardService, expenseService, salesService } from "../api/services";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { EmptyState } from "../components/state/empty-state";
import { useTheme } from "../hooks/use-theme";
import { formatCurrency, formatDateTime, formatNumber } from "../lib/format";

export function DashboardPage() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const { resolvedTheme } = useTheme();

  const chartGridColor = resolvedTheme === "dark" ? "#2f4d6e" : "#d2dde7";
  const chartAxisColor = resolvedTheme === "dark" ? "#b9d0e6" : "#456885";

  const summaryQuery = useQuery({
    queryKey: ["dashboard", "summary", startDate, endDate],
    queryFn: () =>
      dashboardService.summary({
        start_date: startDate || undefined,
        end_date: endDate || undefined
      })
  });

  const customerInsightsQuery = useQuery({
    queryKey: ["dashboard", "customer-insights", startDate, endDate],
    queryFn: () =>
      dashboardService.customerInsights({
        start_date: startDate || undefined,
        end_date: endDate || undefined
      })
  });

  const salesQuery = useQuery({
    queryKey: ["dashboard", "sales", startDate, endDate],
    queryFn: () =>
      salesService.list({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        include_refunds: true,
        limit: 100,
        offset: 0
      })
  });

  const expensesQuery = useQuery({
    queryKey: ["dashboard", "expenses", startDate, endDate],
    queryFn: () =>
      expenseService.list({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: 100,
        offset: 0
      })
  });

  const loading =
    summaryQuery.isLoading ||
    customerInsightsQuery.isLoading ||
    salesQuery.isLoading ||
    expensesQuery.isLoading;
  const errored =
    summaryQuery.isError ||
    customerInsightsQuery.isError ||
    salesQuery.isError ||
    expensesQuery.isError;

  const chartData = useMemo(() => {
    if (!salesQuery.data || !expensesQuery.data) return [];
    const byDay = new Map<string, { day: string; sales: number; expenses: number }>();

    for (const sale of salesQuery.data.items) {
      const day = sale.created_at.slice(0, 10);
      const previous = byDay.get(day) ?? { day, sales: 0, expenses: 0 };
      previous.sales += sale.total_amount;
      byDay.set(day, previous);
    }

    for (const expense of expensesQuery.data.items) {
      const day = expense.created_at.slice(0, 10);
      const previous = byDay.get(day) ?? { day, sales: 0, expenses: 0 };
      previous.expenses += expense.amount;
      byDay.set(day, previous);
    }

    return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
  }, [salesQuery.data, expensesQuery.data]);

  const recentActivity = useMemo(() => {
    if (!salesQuery.data || !expensesQuery.data) return [];

    const salesItems = salesQuery.data.items.map((sale) => ({
      id: sale.id,
      type: sale.kind === "refund" ? "Refund" : "Sale",
      amount: sale.total_amount,
      created_at: sale.created_at,
      note: sale.note ?? `${sale.channel} / ${sale.payment_method}`
    }));

    const expenseItems = expensesQuery.data.items.map((expense) => ({
      id: expense.id,
      type: "Expense",
      amount: -expense.amount,
      created_at: expense.created_at,
      note: expense.note ?? expense.category
    }));

    return [...salesItems, ...expenseItems]
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 8);
  }, [salesQuery.data, expensesQuery.data]);

  if (loading) {
    return <LoadingState label="Loading business dashboard..." />;
  }

  if (errored) {
    return (
      <ErrorState
        message="Failed to load dashboard data."
        onRetry={() => {
          summaryQuery.refetch();
          customerInsightsQuery.refetch();
          salesQuery.refetch();
          expensesQuery.refetch();
        }}
      />
    );
  }

  if (!summaryQuery.data || !customerInsightsQuery.data) {
    return <EmptyState title="No dashboard data" description="Start recording sales and expenses." />;
  }

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#ffffff_0,#ecfff3_55%,#eef4ff_100%)] dark:bg-[linear-gradient(135deg,#1b3858_0,#14304d_55%,#102742_100%)]">
        <div className="grid gap-3 sm:grid-cols-3">
          <Input
            label="Start Date"
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
          />
          <Input
            label="End Date"
            type="date"
            value={endDate}
            onChange={(event) => setEndDate(event.target.value)}
          />
          <div className="flex items-end text-xs text-surface-500 dark:text-surface-200">
            Filters affect KPIs, chart, and recent activity.
          </div>
        </div>
      </Card>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="animate-fade-up [animation-delay:60ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Sales Total</p>
          <p className="mt-2 font-heading text-2xl font-black text-surface-800">
            {formatCurrency(summaryQuery.data.sales_total)}
          </p>
          <p className="mt-1 text-xs text-surface-500">{formatNumber(summaryQuery.data.sales_count)} sales</p>
        </Card>
        <Card className="animate-fade-up [animation-delay:90ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Expenses</p>
          <p className="mt-2 font-heading text-2xl font-black text-surface-800">
            {formatCurrency(summaryQuery.data.expense_total)}
          </p>
          <p className="mt-1 text-xs text-surface-500">
            {formatNumber(summaryQuery.data.expense_count)} records
          </p>
        </Card>
        <Card className="animate-fade-up [animation-delay:120ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Profit (Simple)</p>
          <p className="mt-2 font-heading text-2xl font-black text-surface-800">
            {formatCurrency(summaryQuery.data.profit_simple)}
          </p>
          <p className="mt-1 text-xs text-surface-500">
            Margin{" "}
            {summaryQuery.data.sales_total > 0
              ? `${((summaryQuery.data.profit_simple / summaryQuery.data.sales_total) * 100).toFixed(1)}%`
              : "0%"}
          </p>
        </Card>
        <Card className="animate-fade-up [animation-delay:150ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Average Sale</p>
          <p className="mt-2 font-heading text-2xl font-black text-surface-800">
            {formatCurrency(summaryQuery.data.average_sale_value)}
          </p>
          <p className="mt-1 text-xs text-surface-500">Per order average</p>
        </Card>
      </div>

      <Card className="animate-fade-up [animation-delay:165ms]">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-heading text-lg font-bold text-surface-800">Customer Insights</h3>
          <p className="text-xs text-surface-500">
            {formatNumber(customerInsightsQuery.data.total_customers)} total customers
          </p>
        </div>

        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 dark:border-surface-700 dark:bg-surface-800/60">
            <p className="text-xs uppercase tracking-wide text-surface-500">Active Customers</p>
            <p className="mt-1 font-heading text-xl font-black text-surface-800">
              {formatNumber(customerInsightsQuery.data.active_customers)}
            </p>
          </div>
          <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 dark:border-surface-700 dark:bg-surface-800/60">
            <p className="text-xs uppercase tracking-wide text-surface-500">Repeat Buyers</p>
            <p className="mt-1 font-heading text-xl font-black text-surface-800">
              {formatNumber(customerInsightsQuery.data.repeat_buyers)}
            </p>
          </div>
          <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 dark:border-surface-700 dark:bg-surface-800/60">
            <p className="text-xs uppercase tracking-wide text-surface-500">Repeat Rate</p>
            <p className="mt-1 font-heading text-xl font-black text-surface-800">
              {customerInsightsQuery.data.active_customers > 0
                ? `${(
                    (customerInsightsQuery.data.repeat_buyers /
                      customerInsightsQuery.data.active_customers) *
                    100
                  ).toFixed(1)}%`
                : "0%"}
            </p>
          </div>
        </div>

        <h4 className="mb-2 text-sm font-semibold text-surface-700">Top Customers</h4>
        {customerInsightsQuery.data.top_customers.length === 0 ? (
          <EmptyState
            title="No customer transactions yet"
            description="Orders and paid invoices will populate top customers."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-surface-100 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                  <th className="px-2 py-2">Customer</th>
                  <th className="px-2 py-2">Total Spent</th>
                  <th className="px-2 py-2">Transactions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-50">
                {customerInsightsQuery.data.top_customers.map((customer) => (
                  <tr key={customer.customer_id}>
                    <td className="px-2 py-2 font-semibold text-surface-700">
                      {customer.customer_name}
                    </td>
                    <td className="px-2 py-2 text-surface-700">
                      {formatCurrency(customer.total_spent)}
                    </td>
                    <td className="px-2 py-2 text-surface-500">
                      {formatNumber(customer.transactions)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card className="animate-fade-up [animation-delay:180ms]">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-heading text-lg font-bold text-surface-800">Sales vs Expenses Trend</h3>
          <p className="text-xs text-surface-500">Last {chartData.length} active days</p>
        </div>
        {chartData.length === 0 ? (
          <EmptyState title="No trend data yet" description="Create transactions to view chart analytics." />
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="salesFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#27c25c" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#27c25c" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="expenseFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#497cf2" stopOpacity={0.28} />
                    <stop offset="95%" stopColor="#497cf2" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis dataKey="day" tick={{ fill: chartAxisColor, fontSize: 12 }} />
                <YAxis tick={{ fill: chartAxisColor, fontSize: 12 }} />
                <Tooltip />
                <Area
                  type="monotone"
                  dataKey="sales"
                  name="Sales"
                  stroke="#27c25c"
                  fillOpacity={1}
                  fill="url(#salesFill)"
                />
                <Area
                  type="monotone"
                  dataKey="expenses"
                  name="Expenses"
                  stroke="#497cf2"
                  fillOpacity={1}
                  fill="url(#expenseFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <Card className="animate-fade-up [animation-delay:210ms]">
        <h3 className="mb-4 font-heading text-lg font-bold text-surface-800">Recent Activity</h3>
        {recentActivity.length === 0 ? (
          <EmptyState title="No activity yet" description="Sales and expenses will appear here." />
        ) : (
          <div className="space-y-3">
            <div className="space-y-2 sm:hidden">
              {recentActivity.map((entry) => (
                <article
                  key={`${entry.type}-${entry.id}`}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3 dark:border-surface-700 dark:bg-surface-800/60"
                >
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-surface-700">{entry.type}</p>
                    <p
                      className={`text-sm font-semibold ${
                        entry.amount >= 0 ? "text-mint-700" : "text-red-600"
                      }`}
                    >
                      {formatCurrency(entry.amount)}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">{entry.note ?? "-"}</p>
                  <p className="mt-1 text-xs text-surface-500">{formatDateTime(entry.created_at)}</p>
                </article>
              ))}
            </div>
            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Type</th>
                    <th className="px-2 py-2">Amount</th>
                    <th className="px-2 py-2">Note</th>
                    <th className="px-2 py-2">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {recentActivity.map((entry) => (
                    <tr key={`${entry.type}-${entry.id}`}>
                      <td className="px-2 py-2 font-semibold text-surface-700">{entry.type}</td>
                      <td
                        className={`px-2 py-2 font-semibold ${
                          entry.amount >= 0 ? "text-mint-700" : "text-red-600"
                        }`}
                      >
                        {formatCurrency(entry.amount)}
                      </td>
                      <td className="px-2 py-2 text-surface-500">{entry.note ?? "-"}</td>
                      <td className="px-2 py-2 text-surface-500">{formatDateTime(entry.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
