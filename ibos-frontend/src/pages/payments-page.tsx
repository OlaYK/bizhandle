import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { checkoutService } from "../api/services";
import type { CheckoutSessionOut, CheckoutSessionStatus } from "../api/types";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { EmptyState } from "../components/state/empty-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDateTime } from "../lib/format";

const statusOptions: Array<CheckoutSessionStatus | ""> = [
  "",
  "open",
  "pending_payment",
  "payment_failed",
  "paid",
  "expired"
];

function statusVariant(status: CheckoutSessionStatus): "neutral" | "positive" | "negative" | "info" {
  if (status === "paid") return "positive";
  if (status === "payment_failed" || status === "expired") return "negative";
  if (status === "pending_payment") return "info";
  return "neutral";
}

function reconciliationLabel(session: CheckoutSessionOut): { label: string; variant: "neutral" | "positive" | "negative" } {
  if (session.status !== "paid") {
    return { label: "N/A", variant: "neutral" };
  }
  if (session.has_sale && session.order_status === "paid") {
    return { label: "Reconciled", variant: "positive" };
  }
  return { label: "Unreconciled", variant: "negative" };
}

export function PaymentsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [statusFilter, setStatusFilter] = useState<CheckoutSessionStatus | "">("");
  const [paymentProviderFilter, setPaymentProviderFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  useEffect(() => {
    setPage(1);
  }, [statusFilter, paymentProviderFilter, startDate, endDate]);

  const offset = (page - 1) * pageSize;

  const summaryQuery = useQuery({
    queryKey: ["checkout", "payments-summary", startDate, endDate],
    queryFn: () =>
      checkoutService.paymentsSummary({
        start_date: startDate || undefined,
        end_date: endDate || undefined
      })
  });

  const sessionsQuery = useQuery({
    queryKey: [
      "checkout",
      "sessions",
      statusFilter,
      paymentProviderFilter,
      startDate,
      endDate,
      pageSize,
      page
    ],
    queryFn: () =>
      checkoutService.listSessions({
        status: statusFilter || undefined,
        payment_provider: paymentProviderFilter.trim() || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset
      })
  });

  const retryMutation = useMutation({
    mutationFn: (checkoutSessionId: string) => checkoutService.retryPayment(checkoutSessionId),
    onSuccess: () => {
      showToast({
        title: "Payment retry initialized",
        description: "Checkout session was re-opened for payment.",
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["checkout"] });
    },
    onError: (error) => {
      showToast({
        title: "Retry failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (summaryQuery.isLoading || sessionsQuery.isLoading) {
    return <LoadingState label="Loading payments operations..." />;
  }

  if (summaryQuery.isError || sessionsQuery.isError || !summaryQuery.data || !sessionsQuery.data) {
    return (
      <ErrorState
        message="Unable to load payments operations."
        onRetry={() => {
          summaryQuery.refetch();
          sessionsQuery.refetch();
        }}
      />
    );
  }

  const summary = summaryQuery.data;
  const sessions = sessionsQuery.data;

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#132a42_0%,#1a3a59_45%,#254e70_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Payments Operations</h3>
        <p className="mt-1 text-sm text-white/80">
          Reconcile paid checkouts, retry failed or pending sessions, and monitor payment health.
        </p>
      </Card>

      <Card className="animate-fade-up [animation-delay:40ms]">
        <div className="grid gap-3 md:grid-cols-5">
          <Input label="Start Date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          <Select
            label="Session Status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as CheckoutSessionStatus | "")}
          >
            {statusOptions.map((status) => (
              <option key={status || "all"} value={status}>
                {status || "all"}
              </option>
            ))}
          </Select>
          <Input
            label="Payment Provider"
            value={paymentProviderFilter}
            onChange={(event) => setPaymentProviderFilter(event.target.value)}
            placeholder="stub"
          />
          <div className="mt-7">
            <Badge variant="info">{sessions.pagination.total} sessions</Badge>
          </div>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="animate-fade-up [animation-delay:60ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Paid Amount</p>
          <p className="mt-1 font-heading text-2xl font-black text-mint-700">
            {formatCurrency(summary.paid_amount_total)}
          </p>
        </Card>
        <Card className="animate-fade-up [animation-delay:80ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Paid Sessions</p>
          <p className="mt-1 font-heading text-2xl font-black text-surface-800">{summary.paid_count}</p>
          <p className="mt-1 text-xs text-surface-500">
            Reconciled {summary.reconciled_count} / Unreconciled {summary.unreconciled_count}
          </p>
        </Card>
        <Card className="animate-fade-up [animation-delay:100ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Pending + Open</p>
          <p className="mt-1 font-heading text-2xl font-black text-accent-700">
            {summary.pending_payment_count + summary.open_count}
          </p>
          <p className="mt-1 text-xs text-surface-500">
            Open {summary.open_count} / Pending {summary.pending_payment_count}
          </p>
        </Card>
        <Card className="animate-fade-up [animation-delay:120ms]">
          <p className="text-xs uppercase tracking-wide text-surface-500">Failed + Expired</p>
          <p className="mt-1 font-heading text-2xl font-black text-red-700">
            {summary.failed_count + summary.expired_count}
          </p>
          <p className="mt-1 text-xs text-surface-500">
            Failed {summary.failed_count} / Expired {summary.expired_count}
          </p>
        </Card>
      </div>

      <Card className="animate-fade-up [animation-delay:140ms]">
        {!sessions.items.length ? (
          <EmptyState
            title="No checkout sessions"
            description="Create checkout sessions from order workflow to start tracking payment operations."
          />
        ) : (
          <div className="space-y-3">
            <div className="space-y-2 sm:hidden">
              {sessions.items.map((session) => {
                const reconciliation = reconciliationLabel(session);
                const canRetry = ["open", "pending_payment", "payment_failed"].includes(session.status);
                return (
                  <article key={session.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <Badge variant={statusVariant(session.status)}>{session.status}</Badge>
                      <p className="font-semibold text-mint-700">{formatCurrency(session.total_amount)}</p>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">Provider: {session.payment_provider}</p>
                    <p className="mt-1 text-xs text-surface-500">Order: {session.order_id ?? "-"}</p>
                    <p className="mt-1 text-xs text-surface-500">Created: {formatDateTime(session.created_at)}</p>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <Badge variant={reconciliation.variant}>{reconciliation.label}</Badge>
                      {canRetry ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => retryMutation.mutate(session.id)}
                          loading={retryMutation.isPending && retryMutation.variables === session.id}
                        >
                          Retry
                        </Button>
                      ) : null}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Amount</th>
                    <th className="px-2 py-2">Provider</th>
                    <th className="px-2 py-2">Order</th>
                    <th className="px-2 py-2">Reconciliation</th>
                    <th className="px-2 py-2">Created</th>
                    <th className="px-2 py-2">Retry</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {sessions.items.map((session) => {
                    const reconciliation = reconciliationLabel(session);
                    const canRetry = ["open", "pending_payment", "payment_failed"].includes(session.status);
                    return (
                      <tr key={session.id}>
                        <td className="px-2 py-2">
                          <Badge variant={statusVariant(session.status)}>{session.status}</Badge>
                        </td>
                        <td className="px-2 py-2 font-semibold text-mint-700">
                          {formatCurrency(session.total_amount)}
                        </td>
                        <td className="px-2 py-2 text-surface-600">{session.payment_provider}</td>
                        <td className="px-2 py-2 text-surface-600">{session.order_id ?? "-"}</td>
                        <td className="px-2 py-2">
                          <Badge variant={reconciliation.variant}>{reconciliation.label}</Badge>
                        </td>
                        <td className="px-2 py-2 text-surface-500">{formatDateTime(session.created_at)}</td>
                        <td className="px-2 py-2">
                          {canRetry ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => retryMutation.mutate(session.id)}
                              loading={retryMutation.isPending && retryMutation.variables === session.id}
                            >
                              Retry
                            </Button>
                          ) : (
                            <span className="text-xs text-surface-400">N/A</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <PaginationControls
              pagination={sessions.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (sessions.pagination.has_next) {
                  setPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
