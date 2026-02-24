import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, FileDown, Send, Wallet } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { invoiceService, orderService } from "../api/services";
import type { InvoiceOut, InvoiceStatus } from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Modal } from "../components/ui/modal";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDate, formatDateTime } from "../lib/format";

const optionalPositiveNumber = z.preprocess((value) => {
  if (value === "" || value === null || value === undefined) {
    return undefined;
  }
  const parsed = Number(value);
  if (Number.isNaN(parsed)) {
    return undefined;
  }
  return parsed;
}, z.number().positive("Must be > 0").optional());

const createInvoiceSchema = z
  .object({
    customer_id: z.string().optional(),
    order_id: z.string().optional(),
    currency: z.string().min(3, "Currency is required").max(3, "Use 3-letter code"),
    total_amount: optionalPositiveNumber,
    issue_date: z.string().optional(),
    due_date: z.string().optional(),
    note: z.string().optional(),
    send_now: z.boolean().default(false)
  })
  .refine(
    (values) => Boolean(values.order_id?.trim()) || values.total_amount !== undefined,
    {
      path: ["total_amount"],
      message: "Provide total amount or choose an order."
    }
  );

const markPaidSchema = z.object({
  amount: optionalPositiveNumber,
  payment_method: z.enum(["cash", "transfer", "pos"]).optional(),
  payment_reference: z.string().optional(),
  idempotency_key: z.string().optional(),
  note: z.string().optional()
});

type CreateInvoiceFormData = z.infer<typeof createInvoiceSchema>;
type MarkPaidFormData = z.infer<typeof markPaidSchema>;

const invoiceStatuses: Array<InvoiceStatus | ""> = [
  "",
  "draft",
  "sent",
  "partially_paid",
  "overdue",
  "paid",
  "cancelled"
];

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function badgeVariantForInvoiceStatus(status: InvoiceStatus): "neutral" | "positive" | "negative" | "info" {
  if (status === "paid") return "positive";
  if (status === "overdue" || status === "cancelled") return "negative";
  if (status === "sent" || status === "partially_paid") return "info";
  return "neutral";
}

export function InvoicesPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [orderFilter, setOrderFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceOut | null>(null);
  const todayDate = toDateInputValue(new Date());
  const monthStartDate = toDateInputValue(new Date(new Date().getFullYear(), new Date().getMonth(), 1));
  const [statementStartDate, setStatementStartDate] = useState(monthStartDate);
  const [statementEndDate, setStatementEndDate] = useState(todayDate);
  const [templateName, setTemplateName] = useState("");

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [statusFilter, customerFilter, orderFilter, startDate, endDate]);

  const ordersQuery = useQuery({
    queryKey: ["invoices", "orders"],
    queryFn: () => orderService.list({ limit: 200, offset: 0 })
  });

  const createForm = useForm<CreateInvoiceFormData>({
    resolver: zodResolver(createInvoiceSchema),
    defaultValues: {
      customer_id: "",
      order_id: "",
      currency: "USD",
      total_amount: undefined,
      issue_date: "",
      due_date: "",
      note: "",
      send_now: false
    }
  });

  const listQuery = useQuery({
    queryKey: [
      "invoices",
      "list",
      statusFilter,
      customerFilter,
      orderFilter,
      startDate,
      endDate,
      page,
      pageSize
    ],
    queryFn: () =>
      invoiceService.list({
        status: statusFilter || undefined,
        customer_id: customerFilter.trim() || undefined,
        order_id: orderFilter.trim() || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset
      })
  });

  const templatesQuery = useQuery({
    queryKey: ["invoices", "templates"],
    queryFn: () => invoiceService.listTemplates()
  });

  const agingQuery = useQuery({
    queryKey: ["invoices", "aging"],
    queryFn: () => invoiceService.agingDashboard()
  });

  const statementsQuery = useQuery({
    queryKey: ["invoices", "statements", statementStartDate, statementEndDate],
    enabled: Boolean(statementStartDate) && Boolean(statementEndDate),
    queryFn: () =>
      invoiceService.listStatements({
        start_date: statementStartDate,
        end_date: statementEndDate
      })
  });

  const createMutation = useMutation({
    mutationFn: invoiceService.create,
    onSuccess: () => {
      showToast({ title: "Invoice created", variant: "success" });
      createForm.reset({
        customer_id: "",
        order_id: "",
        currency: "USD",
        total_amount: undefined,
        issue_date: "",
        due_date: "",
        note: "",
        send_now: false
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create invoice",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const sendMutation = useMutation({
    mutationFn: (invoiceId: string) => invoiceService.send(invoiceId),
    onSuccess: () => {
      showToast({ title: "Invoice sent", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Send failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const remindMutation = useMutation({
    mutationFn: (invoiceId: string) => invoiceService.remind(invoiceId, { channel: "email" }),
    onSuccess: () => {
      showToast({
        title: "Reminder queued",
        description: "Manual reminder event recorded via email channel.",
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Reminder failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const runDueRemindersMutation = useMutation({
    mutationFn: () => invoiceService.runDueReminders(),
    onSuccess: (result) => {
      showToast({
        title: "Automated reminders executed",
        description: `${result.reminders_created} reminders created from ${result.processed_count} due invoices.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Automation run failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createTemplateMutation = useMutation({
    mutationFn: (name: string) =>
      invoiceService.upsertTemplate({
        name,
        status: "active",
        is_default: true
      }),
    onSuccess: () => {
      showToast({ title: "Template saved", variant: "success" });
      setTemplateName("");
      queryClient.invalidateQueries({ queryKey: ["invoices", "templates"] });
    },
    onError: (error) => {
      showToast({
        title: "Template save failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const exportStatementsMutation = useMutation({
    mutationFn: () =>
      invoiceService.exportStatements({
        start_date: statementStartDate,
        end_date: statementEndDate
      }),
    onSuccess: (result) => {
      const blob = new Blob([result.csv_content], { type: result.content_type || "text/csv" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename || "invoice-statements.csv";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast({
        title: "Statements exported",
        description: `${result.row_count} customer rows exported.`,
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

  const markPaidForm = useForm<MarkPaidFormData>({
    resolver: zodResolver(markPaidSchema),
    defaultValues: {
      amount: undefined,
      payment_method: "transfer",
      payment_reference: "",
      idempotency_key: "",
      note: ""
    }
  });

  useEffect(() => {
    if (!selectedInvoice) {
      return;
    }
    markPaidForm.reset({
      amount: undefined,
      payment_method: "transfer",
      payment_reference: "",
      idempotency_key: `invpay-${selectedInvoice.id}-${Date.now()}`,
      note: ""
    });
  }, [selectedInvoice, markPaidForm]);

  const markPaidMutation = useMutation({
    mutationFn: ({ invoiceId, values }: { invoiceId: string; values: MarkPaidFormData }) =>
      invoiceService.markPaid(invoiceId, {
        amount: values.amount,
        payment_method: values.payment_method,
        payment_reference: values.payment_reference?.trim() || undefined,
        idempotency_key: values.idempotency_key?.trim() || undefined,
        note: values.note?.trim() || undefined
      }),
    onSuccess: () => {
      showToast({ title: "Invoice marked paid", variant: "success" });
      setSelectedInvoice(null);
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      showToast({
        title: "Payment update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const orderOptions = useMemo(() => ordersQuery.data?.items ?? [], [ordersQuery.data]);

  if (ordersQuery.isLoading || listQuery.isLoading) {
    return <LoadingState label="Loading invoice workspace..." />;
  }

  if (ordersQuery.isError || listQuery.isError) {
    return (
      <ErrorState
        message="Failed to load invoice data."
        onRetry={() => {
          ordersQuery.refetch();
          listQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold">Create Invoice</h3>
        <form
          className="mt-4 grid gap-3"
          onSubmit={createForm.handleSubmit((values) =>
            createMutation.mutate({
              customer_id: values.customer_id?.trim() || undefined,
              order_id: values.order_id?.trim() || undefined,
              currency: values.currency.toUpperCase(),
              total_amount: values.total_amount,
              issue_date: values.issue_date || undefined,
              due_date: values.due_date || undefined,
              note: values.note?.trim() || undefined,
              send_now: values.send_now
            })
          )}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Input label="Customer ID (optional)" {...createForm.register("customer_id")} />
            <Select label="Order (optional)" {...createForm.register("order_id")}>
              <option value="">No linked order</option>
              {orderOptions.map((order) => (
                <option key={order.id} value={order.id}>
                  {order.id.slice(0, 8)}... ({formatCurrency(order.total_amount)})
                </option>
              ))}
            </Select>
            <Input
              label="Currency"
              maxLength={3}
              {...createForm.register("currency")}
              error={createForm.formState.errors.currency?.message}
            />
            <Input
              label="Total Amount"
              type="number"
              step="0.01"
              {...createForm.register("total_amount")}
              error={createForm.formState.errors.total_amount?.message}
            />
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <Input label="Issue Date" type="date" {...createForm.register("issue_date")} />
            <Input label="Due Date" type="date" {...createForm.register("due_date")} />
            <label className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-surface-700">
              <input type="checkbox" {...createForm.register("send_now")} />
              Send immediately
            </label>
          </div>
          <Textarea label="Note" rows={3} {...createForm.register("note")} />
          <Button type="submit" loading={createMutation.isPending}>
            Save Invoice
          </Button>
        </form>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-heading text-lg font-bold">Receivables Intelligence</h3>
            <p className="text-sm text-surface-500">
              Aging visibility, reminder automation, and monthly statement exports.
            </p>
          </div>
          <Button
            type="button"
            variant="secondary"
            onClick={() => runDueRemindersMutation.mutate()}
            loading={runDueRemindersMutation.isPending}
          >
            <BellRing className="h-4 w-4" />
            Run Due Reminders
          </Button>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">Outstanding</p>
            <p className="mt-1 text-lg font-semibold text-mint-700">
              {agingQuery.data ? formatCurrency(agingQuery.data.total_outstanding) : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">Overdue Invoices</p>
            <p className="mt-1 text-lg font-semibold text-surface-900">
              {agingQuery.data ? agingQuery.data.overdue_count : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">Partially Paid</p>
            <p className="mt-1 text-lg font-semibold text-surface-900">
              {agingQuery.data ? agingQuery.data.partially_paid_count : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">Top Bucket</p>
            <p className="mt-1 text-sm font-semibold text-surface-900">
              {agingQuery.data?.buckets?.[0]
                ? `${agingQuery.data.buckets[0].bucket} (${formatCurrency(agingQuery.data.buckets[0].amount)})`
                : "-"}
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Input
            label="Statement Start"
            type="date"
            value={statementStartDate}
            onChange={(event) => setStatementStartDate(event.target.value)}
          />
          <Input
            label="Statement End"
            type="date"
            value={statementEndDate}
            onChange={(event) => setStatementEndDate(event.target.value)}
          />
          <div className="mt-7">
            <Button
              type="button"
              variant="ghost"
              onClick={() => statementsQuery.refetch()}
              loading={statementsQuery.isFetching}
            >
              Refresh Statements
            </Button>
          </div>
          <div className="mt-7">
            <Button
              type="button"
              variant="secondary"
              onClick={() => exportStatementsMutation.mutate()}
              loading={exportStatementsMutation.isPending}
            >
              <FileDown className="h-4 w-4" />
              Export CSV
            </Button>
          </div>
        </div>
        <p className="mt-3 text-xs text-surface-500">
          {statementsQuery.data ? `${statementsQuery.data.items.length} customer statement rows loaded.` : "No statement rows loaded yet."}
        </p>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold">Template Library</h3>
        <form
          className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end"
          onSubmit={(event) => {
            event.preventDefault();
            const normalized = templateName.trim();
            if (!normalized) {
              return;
            }
            createTemplateMutation.mutate(normalized);
          }}
        >
          <Input
            label="Template Name"
            value={templateName}
            onChange={(event) => setTemplateName(event.target.value)}
            placeholder="e.g. MoniDesk Premium"
          />
          <Button type="submit" loading={createTemplateMutation.isPending}>
            Save Default Template
          </Button>
        </form>
        {!templatesQuery.data?.items.length ? (
          <p className="mt-3 text-sm text-surface-500">No templates created yet.</p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-2">
            {templatesQuery.data.items.map((template) => (
              <Badge key={template.id} variant={template.is_default ? "positive" : "neutral"}>
                {template.name}
              </Badge>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-6">
          <Input label="Start Date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          <Select
            label="Status"
            value={statusFilter}
            onChange={(event) => setStatusFilter(event.target.value as InvoiceStatus | "")}
          >
            {invoiceStatuses.map((status) => (
              <option key={status || "all"} value={status}>
                {status || "All statuses"}
              </option>
            ))}
          </Select>
          <Input
            label="Customer ID"
            value={customerFilter}
            onChange={(event) => setCustomerFilter(event.target.value)}
          />
          <Input label="Order ID" value={orderFilter} onChange={(event) => setOrderFilter(event.target.value)} />
          <div className="mt-7">
            <Badge variant="info">{listQuery.data?.pagination.total ?? 0} invoices</Badge>
          </div>
        </div>

        {!listQuery.data?.items.length ? (
          <EmptyState title="No invoices yet" description="Create your first invoice to start receivables tracking." />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {listQuery.data.items.map((invoice) => (
                <article key={invoice.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex items-center justify-between">
                    <Badge variant={badgeVariantForInvoiceStatus(invoice.status)}>{invoice.status}</Badge>
                    <p className="text-sm font-semibold text-mint-700">
                      {formatCurrency(invoice.outstanding_amount)}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">Total: {formatCurrency(invoice.total_amount)}</p>
                  <p className="mt-1 text-xs text-surface-500">Due: {invoice.due_date ? formatDate(invoice.due_date) : "-"}</p>
                  <p className="mt-1 text-xs text-surface-500">{formatDateTime(invoice.created_at)}</p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {invoice.status !== "paid" && invoice.status !== "cancelled" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => sendMutation.mutate(invoice.id)}
                        loading={sendMutation.isPending && sendMutation.variables === invoice.id}
                      >
                        <Send className="h-4 w-4" />
                        Send
                      </Button>
                    ) : null}
                    {(invoice.status === "sent" || invoice.status === "overdue") ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => remindMutation.mutate(invoice.id)}
                        loading={remindMutation.isPending && remindMutation.variables === invoice.id}
                      >
                        Remind
                      </Button>
                    ) : null}
                    {invoice.status !== "paid" && invoice.status !== "cancelled" ? (
                      <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedInvoice(invoice)}>
                        <Wallet className="h-4 w-4" />
                        Mark Paid
                      </Button>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Total</th>
                    <th className="px-2 py-2">Paid</th>
                    <th className="px-2 py-2">Outstanding</th>
                    <th className="px-2 py-2">Customer</th>
                    <th className="px-2 py-2">Due Date</th>
                    <th className="px-2 py-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {listQuery.data.items.map((invoice) => (
                    <tr key={invoice.id}>
                      <td className="px-2 py-2">
                        <Badge variant={badgeVariantForInvoiceStatus(invoice.status)}>{invoice.status}</Badge>
                      </td>
                      <td className="px-2 py-2 text-surface-700">{formatCurrency(invoice.total_amount)}</td>
                      <td className="px-2 py-2 text-surface-700">{formatCurrency(invoice.amount_paid)}</td>
                      <td className="px-2 py-2 font-semibold text-mint-700">
                        {formatCurrency(invoice.outstanding_amount)}
                      </td>
                      <td className="px-2 py-2 text-surface-600">{invoice.customer_id || "-"}</td>
                      <td className="px-2 py-2 text-surface-600">{invoice.due_date ? formatDate(invoice.due_date) : "-"}</td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1">
                          {invoice.status !== "paid" && invoice.status !== "cancelled" ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => sendMutation.mutate(invoice.id)}
                              loading={sendMutation.isPending && sendMutation.variables === invoice.id}
                            >
                              Send
                            </Button>
                          ) : null}
                          {(invoice.status === "sent" || invoice.status === "overdue") ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => remindMutation.mutate(invoice.id)}
                              loading={remindMutation.isPending && remindMutation.variables === invoice.id}
                            >
                              Remind
                            </Button>
                          ) : null}
                          {invoice.status !== "paid" && invoice.status !== "cancelled" ? (
                            <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedInvoice(invoice)}>
                              Mark Paid
                            </Button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationControls
              pagination={listQuery.data.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (listQuery.data.pagination.has_next) {
                  setPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>

      <Modal open={Boolean(selectedInvoice)} title="Mark Invoice Paid" onClose={() => setSelectedInvoice(null)}>
        {!selectedInvoice ? null : (
          <form
            className="grid gap-3"
            onSubmit={markPaidForm.handleSubmit((values) =>
              markPaidMutation.mutate({
                invoiceId: selectedInvoice.id,
                values
              })
            )}
          >
            <p className="text-sm text-surface-600 dark:text-surface-200">
              Outstanding balance: <span className="font-semibold">{formatCurrency(selectedInvoice.outstanding_amount)}</span>
            </p>
            <Input
              label="Amount (optional)"
              type="number"
              step="0.01"
              {...markPaidForm.register("amount")}
              error={markPaidForm.formState.errors.amount?.message}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select label="Payment Method" {...markPaidForm.register("payment_method")}>
                <option value="">Not specified</option>
                <option value="cash">Cash</option>
                <option value="transfer">Transfer</option>
                <option value="pos">POS</option>
              </Select>
              <Input label="Payment Reference" {...markPaidForm.register("payment_reference")} />
            </div>
            <Input label="Idempotency Key" {...markPaidForm.register("idempotency_key")} />
            <Textarea label="Note" rows={3} {...markPaidForm.register("note")} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setSelectedInvoice(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="secondary" loading={markPaidMutation.isPending}>
                Confirm Paid
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
