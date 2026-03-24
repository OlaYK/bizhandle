import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Download, RefreshCcw } from "lucide-react";
import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { analyticsService, authService } from "../api/services";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { useTheme } from "../hooks/use-theme";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency } from "../lib/format";

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function AnalyticsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [startDate, setStartDate] = useState(
    toDateInputValue(
      new Date(new Date().getFullYear(), new Date().getMonth(), 1),
    ),
  );
  const [endDate, setEndDate] = useState(toDateInputValue(new Date()));
  const [reportType, setReportType] = useState<
    "channel_profitability" | "cohorts" | "inventory_aging"
  >("channel_profitability");
  const [recipientEmail, setRecipientEmail] = useState("");
  const { resolvedTheme } = useTheme();

  const chartGridColor = resolvedTheme === "dark" ? "#2f4d6e" : "#d2dde7";
  const chartAxisColor = resolvedTheme === "dark" ? "#b9d0e6" : "#456885";

  const channelQuery = useQuery({
    queryKey: ["analytics", "channel-profitability", startDate, endDate],
    queryFn: () =>
      analyticsService.channelProfitability({
        start_date: startDate,
        end_date: endDate,
      }),
  });

  const cohortQuery = useQuery({
    queryKey: ["analytics", "cohorts"],
    queryFn: () => analyticsService.cohorts({ months_after: 1 }),
  });

  const inventoryAgingQuery = useQuery({
    queryKey: ["analytics", "inventory-aging", endDate],
    queryFn: () => analyticsService.inventoryAging({ as_of_date: endDate }),
  });

  const schedulesQuery = useQuery({
    queryKey: ["analytics", "schedules"],
    queryFn: () => analyticsService.listReportSchedules(),
  });

  const refreshMutation = useMutation({
    mutationFn: () =>
      analyticsService.refreshMart({
        start_date: startDate,
        end_date: endDate,
      }),
    onSuccess: (result) => {
      showToast({
        title: "Analytics mart refreshed",
        description: `${result.rows_refreshed} rows rebuilt.`,
        variant: "success",
      });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: (error) => {
      showToast({
        title: "Refresh failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
  });

  const exportMutation = useMutation({
    mutationFn: () =>
      analyticsService.exportReport({
        report_type: reportType,
        start_date: startDate,
        end_date: endDate,
      }),
    onSuccess: (result) => {
      const blob = new Blob([result.csv_content], {
        type: result.content_type || "text/csv",
      });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename || "analytics-export.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast({
        title: "Export ready",
        description: `${result.row_count} rows downloaded.`,
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Export failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const scheduleMutation = useMutation({
    mutationFn: () =>
      analyticsService.createReportSchedule({
        name: `${reportType} schedule`,
        report_type: reportType,
        recipient_email: recipientEmail.trim(),
        frequency: "weekly",
        status: "active",
      }),
    onSuccess: () => {
      showToast({ title: "Schedule created", variant: "success" });
      setRecipientEmail("");
      queryClient.invalidateQueries({ queryKey: ["analytics", "schedules"] });
    },
    onError: (error) => {
      showToast({
        title: "Schedule failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const totals = useMemo(() => {
    const items = channelQuery.data?.items ?? [];
    return items.reduce(
      (acc, row) => {
        acc.revenue += row.revenue;
        acc.net += row.net_profit;
        acc.orders += row.orders_count;
        return acc;
      },
      { revenue: 0, net: 0, orders: 0 },
    );
  }, [channelQuery.data]);

  if (
    channelQuery.isLoading ||
    cohortQuery.isLoading ||
    inventoryAgingQuery.isLoading ||
    schedulesQuery.isLoading
  ) {
    return <LoadingState label="Loading analytics workspace..." />;
  }

  if (
    channelQuery.isError ||
    cohortQuery.isError ||
    inventoryAgingQuery.isError ||
    schedulesQuery.isError
  ) {
    return (
      <ErrorState
        message="Failed to load analytics data."
        onRetry={() => {
          channelQuery.refetch();
          cohortQuery.refetch();
          inventoryAgingQuery.refetch();
          schedulesQuery.refetch();
        }}
      />
    );
  }

  console.log(inventoryAgingQuery.data?.items);

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
              <BarChart3 className="h-4 w-4" />
              Analytics Intelligence
            </p>
            <h3 className="font-heading text-lg font-bold">
              Profitability, Cohorts, and Inventory Impact
            </h3>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => refreshMutation.mutate()}
            loading={refreshMutation.isPending}
          >
            <RefreshCcw className="h-4 w-4" />
            Refresh Mart
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
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
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Revenue</p>
            <p className="mt-1 font-semibold text-mint-700">
              {formatCurrency(totals.revenue, profileQuery.data?.base_currency)}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Net Profit</p>
            <p className="mt-1 font-semibold text-mint-700">
              {formatCurrency(totals.net, profileQuery.data?.base_currency)}
            </p>
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold">
          Channel Profitability
        </h3>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full divide-y divide-surface-100 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                <th className="px-2 py-2">Channel</th>
                <th className="px-2 py-2">Revenue</th>
                <th className="px-2 py-2">Net Profit</th>
                <th className="px-2 py-2">Margin</th>
                <th className="px-2 py-2">Orders</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-50">
              {(channelQuery.data?.items ?? []).map((row) => (
                <tr key={row.channel}>
                  <td className="px-2 py-2">{row.channel}</td>
                  <td className="px-2 py-2">
                    {formatCurrency(
                      row.revenue,
                      profileQuery.data?.base_currency,
                    )}
                  </td>
                  <td className="px-2 py-2">
                    {formatCurrency(
                      row.net_profit,
                      profileQuery.data?.base_currency,
                    )}
                  </td>
                  <td className="px-2 py-2">{row.margin_pct.toFixed(2)}%</td>
                  <td className="px-2 py-2">{row.orders_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-heading text-lg font-bold">
            Channel Revenue vs Net Profit
          </h3>
          <p className="text-xs text-surface-500">
            {channelQuery.data?.items.length ?? 0} channels
          </p>
        </div>
        {(channelQuery.data?.items ?? []).length === 0 ? (
          <p className="py-8 text-center text-sm text-surface-500">
            No channel data for the selected period.
          </p>
        ) : (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={channelQuery.data?.items ?? []}>
                <defs>
                  <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#27c25c" stopOpacity={0.85} />
                    <stop offset="95%" stopColor="#27c25c" stopOpacity={0.35} />
                  </linearGradient>
                  <linearGradient id="profitFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#497cf2" stopOpacity={0.85} />
                    <stop offset="95%" stopColor="#497cf2" stopOpacity={0.35} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chartGridColor} />
                <XAxis
                  dataKey="channel"
                  tick={{ fill: chartAxisColor, fontSize: 12 }}
                />
                <YAxis tick={{ fill: chartAxisColor, fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar
                  dataKey="revenue"
                  name="Revenue"
                  fill="url(#revenueFill)"
                  radius={[4, 4, 0, 0]}
                />
                <Bar
                  dataKey="net_profit"
                  name="Net Profit"
                  fill="url(#profitFill)"
                  radius={[4, 4, 0, 0]}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Cohort Retention</h3>
          <div className="mt-3 space-y-2">
            {(cohortQuery.data?.items ?? []).map((row) => (
              <div
                key={row.cohort_month}
                className="rounded-lg border border-surface-100 bg-surface-50 p-3"
              >
                <div className="flex items-center justify-between">
                  <Badge variant="info">{row.cohort_month}</Badge>
                  <p className="text-sm font-semibold">
                    {row.retention_rate.toFixed(2)}%
                  </p>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  {row.retained_customers} retained of {row.total_customers}
                </p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Inventory Aging</h3>
          <p className="text-sm text-surface-500">
            Stockout variants: {inventoryAgingQuery.data?.stockout_count ?? 0}
          </p>
          <div className="mt-3 space-y-2">
            {(inventoryAgingQuery.data?.items ?? []).slice(0, 6).map((row) => (
              <div
                key={row.variant_id}
                className="rounded-lg border border-surface-100 bg-surface-50 p-3"
              >
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-surface-700">
                    {/* {row.variant_id.slice(0, 8)}... */}
                    {row.product_name}- {row.sku}
                  </p>
                  <Badge variant="neutral">{row.bucket}</Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  Stock: {row.stock} | Value:{" "}
                  {formatCurrency(
                    row.estimated_value,
                    profileQuery.data?.base_currency,
                  )}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="font-heading text-lg font-bold">
          Report Export & Scheduling
        </h3>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Select
            label="Report Type"
            value={reportType}
            onChange={(event) =>
              setReportType(
                event.target.value as
                  | "channel_profitability"
                  | "cohorts"
                  | "inventory_aging",
              )
            }
          >
            <option value="channel_profitability">Channel Profitability</option>
            <option value="cohorts">Cohorts</option>
            <option value="inventory_aging">Inventory Aging</option>
          </Select>
          <Input
            label="Recipient Email"
            value={recipientEmail}
            onChange={(event) => setRecipientEmail(event.target.value)}
          />
          <div className="mt-7">
            <Button
              type="button"
              variant="ghost"
              onClick={() => exportMutation.mutate()}
              loading={exportMutation.isPending}
            >
              <Download className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
          <div className="mt-7">
            <Button
              type="button"
              variant="secondary"
              onClick={() => scheduleMutation.mutate()}
              disabled={!recipientEmail.trim()}
              loading={scheduleMutation.isPending}
            >
              Save Weekly Schedule
            </Button>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          {(schedulesQuery.data?.items ?? []).map((item) => (
            <Badge
              key={item.id}
              variant={item.status === "active" ? "positive" : "neutral"}
            >
              {item.report_type}
              {" -> "}
              {item.recipient_email}
            </Badge>
          ))}
        </div>
      </Card>
    </div>
  );
}
