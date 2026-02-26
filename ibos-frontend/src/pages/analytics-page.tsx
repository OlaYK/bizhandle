import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BarChart3, Download, RefreshCcw } from "lucide-react";
import { useMemo, useState } from "react";
import { analyticsService, expenseService, inventoryService } from "../api/services";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
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
    toDateInputValue(new Date(new Date().getFullYear(), new Date().getMonth(), 1))
  );
  const [endDate, setEndDate] = useState(toDateInputValue(new Date()));
  const [reportType, setReportType] = useState<"channel_profitability" | "cohorts" | "inventory_aging">(
    "channel_profitability"
  );
  const [recipientEmail, setRecipientEmail] = useState("");

  const channelQuery = useQuery({
    queryKey: ["analytics", "channel-profitability", startDate, endDate],
    queryFn: () => analyticsService.channelProfitability({ start_date: startDate, end_date: endDate })
  });

  const cohortQuery = useQuery({
    queryKey: ["analytics", "cohorts"],
    queryFn: () => analyticsService.cohorts({ months_after: 1 })
  });

  const inventoryAgingQuery = useQuery({
    queryKey: ["analytics", "inventory-aging", endDate],
    queryFn: () => analyticsService.inventoryAging({ as_of_date: endDate })
  });

  const schedulesQuery = useQuery({
    queryKey: ["analytics", "schedules"],
    queryFn: () => analyticsService.listReportSchedules()
  });

  const expensesQuery = useQuery({
    queryKey: ["analytics", "expenses", startDate, endDate],
    queryFn: () =>
      expenseService.list({
        start_date: startDate,
        end_date: endDate,
        limit: 500,
        offset: 0
      })
  });

  const inventoryLedgerQuery = useQuery({
    queryKey: ["analytics", "inventory-ledger"],
    queryFn: () => inventoryService.ledger({ limit: 500, offset: 0 })
  });

  const refreshMutation = useMutation({
    mutationFn: () => analyticsService.refreshMart({ start_date: startDate, end_date: endDate }),
    onSuccess: (result) => {
      showToast({
        title: "Analytics mart refreshed",
        description: `${result.rows_refreshed} rows rebuilt.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["analytics"] });
    },
    onError: (error) => {
      showToast({
        title: "Refresh failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const exportMutation = useMutation({
    mutationFn: () =>
      analyticsService.exportReport({
        report_type: reportType,
        start_date: startDate,
        end_date: endDate
      }),
    onSuccess: (result) => {
      const blob = new Blob([result.csv_content], { type: result.content_type || "text/csv" });
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
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Export failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const scheduleMutation = useMutation({
    mutationFn: () =>
      analyticsService.createReportSchedule({
        name: `${reportType} schedule`,
        report_type: reportType,
        recipient_email: recipientEmail.trim(),
        frequency: "weekly",
        status: "active"
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
        variant: "error"
      });
    }
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
      { revenue: 0, net: 0, orders: 0 }
    );
  }, [channelQuery.data]);

  const expenseByCategory = useMemo(() => {
    const bucket = new Map<string, number>();
    for (const expense of expensesQuery.data?.items ?? []) {
      const current = bucket.get(expense.category) ?? 0;
      bucket.set(expense.category, current + expense.amount);
    }
    return Array.from(bucket.entries())
      .map(([category, total]) => ({ category, total }))
      .sort((a, b) => b.total - a.total);
  }, [expensesQuery.data]);

  const inventoryEntrySummary = useMemo(() => {
    const rows = (inventoryLedgerQuery.data?.items ?? []).filter((entry) => {
      const day = entry.created_at.slice(0, 10);
      if (startDate && day < startDate) {
        return false;
      }
      if (endDate && day > endDate) {
        return false;
      }
      return true;
    });
    const inbound = rows.filter((entry) => entry.qty_delta > 0);
    const outbound = rows.filter((entry) => entry.qty_delta < 0);
    const reasonMap = new Map<string, number>();
    for (const row of rows) {
      reasonMap.set(row.reason, (reasonMap.get(row.reason) ?? 0) + 1);
    }
    const topReasons = Array.from(reasonMap.entries())
      .map(([reason, count]) => ({ reason, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 5);

    return {
      totalEntries: rows.length,
      inboundCount: inbound.length,
      inboundQty: inbound.reduce((sum, row) => sum + row.qty_delta, 0),
      outboundCount: outbound.length,
      outboundQty: outbound.reduce((sum, row) => sum + Math.abs(row.qty_delta), 0),
      topReasons
    };
  }, [inventoryLedgerQuery.data, startDate, endDate]);

  if (
    channelQuery.isLoading ||
    cohortQuery.isLoading ||
    inventoryAgingQuery.isLoading ||
    schedulesQuery.isLoading ||
    expensesQuery.isLoading ||
    inventoryLedgerQuery.isLoading
  ) {
    return <LoadingState label="Loading analytics workspace..." />;
  }

  if (
    channelQuery.isError ||
    cohortQuery.isError ||
    inventoryAgingQuery.isError ||
    schedulesQuery.isError ||
    expensesQuery.isError ||
    inventoryLedgerQuery.isError
  ) {
    return (
      <ErrorState
        message="Failed to load analytics data."
        onRetry={() => {
          channelQuery.refetch();
          cohortQuery.refetch();
          inventoryAgingQuery.refetch();
          schedulesQuery.refetch();
          expensesQuery.refetch();
          inventoryLedgerQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
              <BarChart3 className="h-4 w-4" />
              Analytics Intelligence
            </p>
            <h3 className="font-heading text-lg font-bold">Profitability, Cohorts, and Inventory Impact</h3>
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
        <div className="mt-4 grid gap-3 md:grid-cols-6">
          <Input label="Start Date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Revenue</p>
            <p className="mt-1 font-semibold text-mint-700">{formatCurrency(totals.revenue)}</p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Net Profit</p>
            <p className="mt-1 font-semibold text-mint-700">{formatCurrency(totals.net)}</p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Expenses</p>
            <p className="mt-1 font-semibold text-red-600">
              {formatCurrency((expensesQuery.data?.items ?? []).reduce((sum, row) => sum + row.amount, 0))}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase text-surface-500">Inventory Entries</p>
            <p className="mt-1 font-semibold text-surface-700">{inventoryEntrySummary.totalEntries}</p>
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold">Channel Profitability</h3>
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
                  <td className="px-2 py-2">{formatCurrency(row.revenue)}</td>
                  <td className="px-2 py-2">{formatCurrency(row.net_profit)}</td>
                  <td className="px-2 py-2">{row.margin_pct.toFixed(2)}%</td>
                  <td className="px-2 py-2">{row.orders_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Cohort Retention</h3>
          <div className="mt-3 space-y-2">
            {(cohortQuery.data?.items ?? []).map((row) => (
              <div key={row.cohort_month} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
                <div className="flex items-center justify-between">
                  <Badge variant="info">{row.cohort_month}</Badge>
                  <p className="text-sm font-semibold">{row.retention_rate.toFixed(2)}%</p>
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
              <div key={row.variant_id} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
                <div className="flex items-center justify-between">
                  <p className="text-xs font-semibold text-surface-700">{row.variant_id.slice(0, 8)}...</p>
                  <Badge variant="neutral">{row.bucket}</Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  Stock: {row.stock} | Value: {formatCurrency(row.estimated_value)}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Expense Breakdown</h3>
          {expenseByCategory.length === 0 ? (
            <p className="mt-3 text-sm text-surface-500">No expenses recorded in this date range.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {expenseByCategory.map((row) => {
                const max = expenseByCategory[0]?.total ?? 1;
                const widthPct = Math.max(8, Math.round((row.total / max) * 100));
                return (
                  <div key={row.category} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
                    <div className="flex items-center justify-between text-sm">
                      <p className="font-semibold text-surface-700">{row.category}</p>
                      <p className="font-semibold text-red-600">{formatCurrency(row.total)}</p>
                    </div>
                    <div className="mt-2 h-2 rounded-full bg-surface-200">
                      <div className="h-2 rounded-full bg-red-500" style={{ width: `${widthPct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Inventory Entry Activity</h3>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
              <p className="text-xs uppercase text-surface-500">Inbound Entries</p>
              <p className="mt-1 text-lg font-bold text-mint-700">{inventoryEntrySummary.inboundCount}</p>
              <p className="text-xs text-surface-500">Qty added: {inventoryEntrySummary.inboundQty}</p>
            </div>
            <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
              <p className="text-xs uppercase text-surface-500">Outbound Entries</p>
              <p className="mt-1 text-lg font-bold text-red-600">{inventoryEntrySummary.outboundCount}</p>
              <p className="text-xs text-surface-500">Qty removed: {inventoryEntrySummary.outboundQty}</p>
            </div>
          </div>
          <div className="mt-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">Top Entry Reasons</p>
            {inventoryEntrySummary.topReasons.length === 0 ? (
              <p className="mt-2 text-sm text-surface-500">No inventory ledger activity in this range.</p>
            ) : (
              <div className="mt-2 flex flex-wrap gap-2">
                {inventoryEntrySummary.topReasons.map((row) => (
                  <Badge key={row.reason} variant="info">
                    {row.reason}: {row.count}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      <Card>
        <h3 className="font-heading text-lg font-bold">Report Export & Scheduling</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Select label="Report Type" value={reportType} onChange={(event) => setReportType(event.target.value as "channel_profitability" | "cohorts" | "inventory_aging")}>
            <option value="channel_profitability">Channel Profitability</option>
            <option value="cohorts">Cohorts</option>
            <option value="inventory_aging">Inventory Aging</option>
          </Select>
          <Input label="Recipient Email" value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)} />
          <div className="mt-7">
            <Button type="button" variant="ghost" onClick={() => exportMutation.mutate()} loading={exportMutation.isPending}>
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
            <Badge key={item.id} variant={item.status === "active" ? "positive" : "neutral"}>
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
