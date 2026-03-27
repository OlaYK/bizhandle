import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BellRing,
  Eye,
  FileDown,
  Send,
  Trash2,
  Wallet,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import {
  authService,
  invoiceService,
  orderService,
  customerService,
} from "../api/services";
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
    customer_name: z.string().min(2, "Customer name is required"),
    customer_id: z.string().optional(),
    order_id: z.string().min(1, "Order is required"),
    currency: z
      .string()
      .min(3, "Currency is required")
      .max(3, "Use 3-letter code"),
    total_amount: optionalPositiveNumber,
    issue_date: z.string().optional(),
    due_date: z.string().optional(),
    note: z.string().optional(),
    send_now: z.boolean().default(false),
  })
  .refine(
    (values) =>
      !values.issue_date ||
      !values.due_date ||
      values.due_date >= values.issue_date,
    {
      path: ["due_date"],
      message: "Due date cannot be before issue date.",
    },
  );

const markPaidSchema = z.object({
  amount: optionalPositiveNumber,
  payment_method: z.enum(["cash", "transfer", "pos"]).optional(),
  payment_reference: z.string().optional(),
  idempotency_key: z.string().optional(),
  note: z.string().optional(),
});

const optionalReminderChannel = z.preprocess(
  (value) => {
    if (value === "" || value === null || value === undefined) {
      return undefined;
    }
    return value;
  },
  z.enum(["email", "sms", "whatsapp"]).optional(),
);

const sendInvoiceSchema = z.object({
  channel: optionalReminderChannel,
  recipient_override: z.string().optional(),
  note: z.string().optional(),
});

type CreateInvoiceFormData = z.infer<typeof createInvoiceSchema>;
type MarkPaidFormData = z.infer<typeof markPaidSchema>;
type SendInvoiceFormData = z.infer<typeof sendInvoiceSchema>;

const invoiceStatuses: Array<InvoiceStatus | ""> = [
  "",
  "draft",
  "sent",
  "partially_paid",
  "overdue",
  "paid",
  "cancelled",
];

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function badgeVariantForInvoiceStatus(
  status: InvoiceStatus,
): "neutral" | "positive" | "negative" | "info" {
  if (status === "paid") return "positive";
  if (status === "overdue" || status === "cancelled") return "negative";
  if (status === "sent" || status === "partially_paid") return "info";
  return "neutral";
}

function canCancelInvoice(invoice: InvoiceOut) {
  return invoice.status !== "paid" && invoice.status !== "cancelled" && invoice.amount_paid === 0;
}

function canDeleteInvoice(invoice: InvoiceOut) {
  return invoice.amount_paid === 0;
}

function channelLabel(channel: string) {
  return channel.charAt(0).toUpperCase() + channel.slice(1).replaceAll("_", " ");
}

function isReminderChannel(
  value?: string | null,
): value is "email" | "sms" | "whatsapp" {
  return value === "email" || value === "sms" || value === "whatsapp";
}

export function InvoicesPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
  });
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "">("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [orderFilter, setOrderFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selectedInvoice, setSelectedInvoice] = useState<InvoiceOut | null>(
    null,
  );
  const [previewInvoice, setPreviewInvoice] = useState<InvoiceOut | null>(null);
  const [sendInvoiceTarget, setSendInvoiceTarget] = useState<InvoiceOut | null>(
    null,
  );
  const todayDate = toDateInputValue(new Date());
  const monthStartDate = toDateInputValue(
    new Date(new Date().getFullYear(), new Date().getMonth(), 1),
  );
  const [statementStartDate, setStatementStartDate] = useState(monthStartDate);
  const [statementEndDate, setStatementEndDate] = useState(todayDate);
  const [templateName, setTemplateName] = useState("");

  const offset = (page - 1) * pageSize;
  const activePreviewInvoiceId = previewInvoice?.id ?? sendInvoiceTarget?.id;

  useEffect(() => {
    setPage(1);
  }, [statusFilter, customerFilter, orderFilter, startDate, endDate]);

  const ordersQuery = useQuery({
    queryKey: ["invoices", "orders", "eligible"],
    queryFn: () =>
      orderService.list({ limit: 200, offset: 0, invoice_eligible: true }),
  });

  const previewQuery = useQuery({
    queryKey: ["invoices", "preview", activePreviewInvoiceId],
    enabled: Boolean(activePreviewInvoiceId),
    queryFn: () => invoiceService.preview(activePreviewInvoiceId as string),
  });

  const customersQuery = useQuery({
    queryKey: ["orders", "customers"],
    queryFn: () => customerService.list({ limit: 200, offset: 0 }),
  });

  const createForm = useForm<CreateInvoiceFormData>({
    resolver: zodResolver(createInvoiceSchema),
    defaultValues: {
      customer_name: "",
      customer_id: "",
      order_id: "",
      currency: profileQuery.data?.base_currency ?? "NGN",
      total_amount: undefined,
      issue_date: "",
      due_date: "",
      note: "",
      send_now: false,
    },
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
      pageSize,
    ],
    queryFn: () =>
      invoiceService.list({
        status: statusFilter || undefined,
        customer_id: customerFilter.trim() || undefined,
        order_id: orderFilter.trim() || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset,
      }),
  });

  const customers = customersQuery.data?.items ?? [];
  const orderOptions = useMemo(
    () => ordersQuery.data?.items ?? [],
    [ordersQuery.data],
  );
  const orderOptionsById = useMemo(
    () => Object.fromEntries(orderOptions.map((order) => [order.id, order])),
    [orderOptions],
  );
  const customersById = useMemo(
    () => Object.fromEntries(customers.map((customer) => [customer.id, customer])),
    [customers],
  );
  const selectedOrderId = createForm.watch("order_id");
  const selectedCustomerId = createForm.watch("customer_id");

  useEffect(() => {
    const selectedOrder = orderOptionsById[selectedOrderId];
    if (!selectedOrder) {
      return;
    }

    if (
      selectedOrder.customer_name &&
      createForm.getValues("customer_name") !== selectedOrder.customer_name
    ) {
      createForm.setValue("customer_name", selectedOrder.customer_name, {
        shouldValidate: true,
      });
    }

    if (
      selectedOrder.customer_id &&
      createForm.getValues("customer_id") !== selectedOrder.customer_id
    ) {
      createForm.setValue("customer_id", selectedOrder.customer_id);
    }
  }, [createForm, orderOptionsById, selectedOrderId]);

  useEffect(() => {
    if (!selectedCustomerId) {
      return;
    }
    const customer = customersById[selectedCustomerId];
    if (!customer) {
      return;
    }
    if (createForm.getValues("customer_name") !== customer.name) {
      createForm.setValue("customer_name", customer.name, {
        shouldValidate: true,
      });
    }
  }, [createForm, customersById, selectedCustomerId]);

  const templatesQuery = useQuery({
    queryKey: ["invoices", "templates"],
    queryFn: () => invoiceService.listTemplates(),
  });

  const agingQuery = useQuery({
    queryKey: ["invoices", "aging"],
    queryFn: () => invoiceService.agingDashboard(),
  });

  const statementsQuery = useQuery({
    queryKey: ["invoices", "statements", statementStartDate, statementEndDate],
    enabled: Boolean(statementStartDate) && Boolean(statementEndDate),
    queryFn: () =>
      invoiceService.listStatements({
        start_date: statementStartDate,
        end_date: statementEndDate,
      }),
  });

  const createMutation = useMutation({
    mutationFn: invoiceService.create,
    onSuccess: () => {
      showToast({ title: "Invoice created", variant: "success" });
      createForm.reset({
        customer_name: "",
        customer_id: "",
        order_id: "",
        currency: profileQuery.data?.base_currency ?? "NGN",
        total_amount: undefined,
        issue_date: "",
        due_date: "",
        note: "",
        send_now: false,
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "orders"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create invoice",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const sendForm = useForm<SendInvoiceFormData>({
    resolver: zodResolver(sendInvoiceSchema),
    defaultValues: {
      channel: undefined,
      recipient_override: "",
      note: "",
    },
  });

  useEffect(() => {
    if (!sendInvoiceTarget) {
      return;
    }
    sendForm.reset({
      channel: undefined,
      recipient_override: "",
      note: "",
    });
  }, [sendForm, sendInvoiceTarget]);

  useEffect(() => {
    if (!sendInvoiceTarget) {
      return;
    }
    if (!isReminderChannel(previewQuery.data?.recommended_channel)) {
      return;
    }
    if (sendForm.getValues("channel")) {
      return;
    }
    sendForm.setValue("channel", previewQuery.data.recommended_channel, {
      shouldValidate: true,
    });
  }, [previewQuery.data?.recommended_channel, sendForm, sendInvoiceTarget]);

  const sendMutation = useMutation({
    mutationFn: ({
      invoiceId,
      values,
    }: {
      invoiceId: string;
      values: SendInvoiceFormData;
    }) =>
      invoiceService.send(invoiceId, {
        channel: values.channel,
        recipient_override: values.recipient_override?.trim() || undefined,
        note: values.note?.trim() || undefined,
      }),
    onSuccess: () => {
      showToast({ title: "Invoice sent", variant: "success" });
      setSendInvoiceTarget(null);
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Send failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const remindMutation = useMutation({
    mutationFn: (invoiceId: string) =>
      invoiceService.remind(invoiceId, { channel: "email" }),
    onSuccess: () => {
      showToast({
        title: "Reminder queued",
        description: "Manual reminder event recorded via email channel.",
        variant: "success",
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Reminder failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const runDueRemindersMutation = useMutation({
    mutationFn: () => invoiceService.runDueReminders(),
    onSuccess: (result) => {
      showToast({
        title: "Automated reminders executed",
        description: `${result.reminders_created} reminders created from ${result.processed_count} due invoices.`,
        variant: "success",
      });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
    },
    onError: (error) => {
      showToast({
        title: "Automation run failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const createTemplateMutation = useMutation({
    mutationFn: (name: string) =>
      invoiceService.upsertTemplate({
        name,
        status: "active",
        is_default: true,
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
        variant: "error",
      });
    },
  });

  const exportStatementsMutation = useMutation({
    mutationFn: () =>
      invoiceService.exportStatements({
        start_date: statementStartDate,
        end_date: statementEndDate,
      }),
    onSuccess: (result) => {
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast({
        title: "Statements exported",
        description: "Invoice statements downloaded successfully.",
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

  const markPaidForm = useForm<MarkPaidFormData>({
    resolver: zodResolver(markPaidSchema),
    defaultValues: {
      amount: undefined,
      payment_method: "transfer",
      payment_reference: "",
      idempotency_key: "",
      note: "",
    },
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
      note: "",
    });
  }, [selectedInvoice, markPaidForm]);

  const markPaidMutation = useMutation({
    mutationFn: ({
      invoiceId,
      values,
    }: {
      invoiceId: string;
      values: MarkPaidFormData;
    }) =>
      invoiceService.markPaid(invoiceId, {
        amount: values.amount,
        payment_method: values.payment_method,
        payment_reference: values.payment_reference?.trim() || undefined,
        idempotency_key: values.idempotency_key?.trim() || undefined,
        note: values.note?.trim() || undefined,
      }),
    onSuccess: () => {
      showToast({ title: "Invoice marked paid", variant: "success" });
      setSelectedInvoice(null);
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      showToast({
        title: "Payment update failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (invoiceId: string) => invoiceService.cancel(invoiceId),
    onSuccess: () => {
      showToast({ title: "Invoice cancelled", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "orders"] });
    },
    onError: (error) => {
      showToast({
        title: "Cancel failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (invoiceId: string) => invoiceService.remove(invoiceId),
    onSuccess: () => {
      showToast({ title: "Invoice deleted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["invoices", "orders"] });
    },
    onError: (error) => {
      showToast({
        title: "Delete failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  if (ordersQuery.isLoading || customersQuery.isLoading || listQuery.isLoading) {
    return <LoadingState label="Loading invoice workspace..." />;
  }

  if (ordersQuery.isError || customersQuery.isError || listQuery.isError) {
    return (
      <ErrorState
        message="Failed to load invoice data."
        onRetry={() => {
          ordersQuery.refetch();
          customersQuery.refetch();
          listQuery.refetch();
        }}
      />
    );
  }

  const previewData = previewQuery.data;

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold">Create Invoice</h3>
        <form
          className="mt-4 grid gap-3"
          onSubmit={createForm.handleSubmit((values) =>
            createMutation.mutate({
              customer_name: values.customer_name.trim(),
              customer_id: values.customer_id?.trim() || undefined,
              order_id: values.order_id.trim(),
              currency: values.currency.toUpperCase(),
              total_amount: values.total_amount,
              issue_date: values.issue_date || undefined,
              due_date: values.due_date || undefined,
              note: values.note?.trim() || undefined,
              send_now: values.send_now,
            }),
          )}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Input
              label="Customer Name"
              placeholder="Aisha Bello"
              {...createForm.register("customer_name")}
              error={createForm.formState.errors.customer_name?.message}
            />
            <Select
              label="Customer Record Match"
              {...createForm.register("customer_id")}
              error={createForm.formState.errors.customer_id?.message}
            >
              <option value="">Match from customers database</option>
              {(customers ?? []).map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name}
                </option>
              ))}
            </Select>
            <Select
              label="Order"
              {...createForm.register("order_id")}
              error={createForm.formState.errors.order_id?.message}
            >
              <option value="">Select eligible order</option>
              {orderOptions.map((order) => (
                <option key={order.id} value={order.id}>
                  {(order.customer_name || "No customer")} -{" "}
                  {formatCurrency(
                    order.total_amount,
                    profileQuery.data?.base_currency,
                  )}
                  {" · "}
                  {order.id.slice(0, 8)}...
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
              label="Total Amount (optional)"
              type="number"
              step="0.01"
              {...createForm.register("total_amount")}
              error={createForm.formState.errors.total_amount?.message}
            />
          </div>
          <p className="text-xs text-surface-500">
            Pick an eligible order first. If the order already has a customer,
            the customer name is auto-filled for you.
          </p>
          <div className="grid gap-3 md:grid-cols-3">
            <Input
              label="Issue Date"
              type="date"
              {...createForm.register("issue_date")}
            />
            <Input
              label="Due Date"
              type="date"
              {...createForm.register("due_date")}
            />
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
            <h3 className="font-heading text-lg font-bold">
              Receivables Intelligence
            </h3>
            <p className="text-sm text-surface-500">
              Aging visibility, reminder automation, and monthly statement
              exports.
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
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Outstanding
            </p>
            <p className="mt-1 text-lg font-semibold text-mint-700">
              {agingQuery.data
                ? formatCurrency(
                    agingQuery.data.total_outstanding,
                    profileQuery.data?.base_currency,
                  )
                : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Overdue Invoices
            </p>
            <p className="mt-1 text-lg font-semibold text-surface-900">
              {agingQuery.data ? agingQuery.data.overdue_count : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Partially Paid
            </p>
            <p className="mt-1 text-lg font-semibold text-surface-900">
              {agingQuery.data ? agingQuery.data.partially_paid_count : "-"}
            </p>
          </div>
          <div className="rounded-lg border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Top Bucket
            </p>
            <p className="mt-1 text-sm font-semibold text-surface-900">
              {agingQuery.data?.buckets?.[0]
                ? `${agingQuery.data.buckets[0].bucket} (${formatCurrency(agingQuery.data.buckets[0].amount, profileQuery.data?.base_currency)})`
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
          {statementsQuery.data
            ? `${statementsQuery.data.items.length} customer statement rows loaded.`
            : "No statement rows loaded yet."}
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
          <p className="mt-3 text-sm text-surface-500">
            No templates created yet.
          </p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-2">
            {templatesQuery.data.items.map((template) => (
              <Badge
                key={template.id}
                variant={template.is_default ? "positive" : "neutral"}
              >
                {template.name}
              </Badge>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-6">
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
          <Select
            label="Status"
            value={statusFilter}
            onChange={(event) =>
              setStatusFilter(event.target.value as InvoiceStatus | "")
            }
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
          <Input
            label="Order ID"
            value={orderFilter}
            onChange={(event) => setOrderFilter(event.target.value)}
          />
          <div className="mt-7">
            <Badge variant="info">
              {listQuery.data?.pagination.total ?? 0} invoices
            </Badge>
          </div>
        </div>

        {!listQuery.data?.items.length ? (
          <EmptyState
            title="No invoices yet"
            description="Create your first invoice to start receivables tracking."
          />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {listQuery.data.items.map((invoice) => (
                <article
                  key={invoice.id}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3"
                >
                  <div className="flex items-center justify-between">
                    <Badge
                      variant={badgeVariantForInvoiceStatus(invoice.status)}
                    >
                      {invoice.status}
                    </Badge>
                    <p className="text-sm font-semibold text-mint-700">
                      {formatCurrency(
                        invoice.outstanding_amount,
                        profileQuery.data?.base_currency,
                      )}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    Total:{" "}
                    {formatCurrency(
                      invoice.total_amount,
                      profileQuery.data?.base_currency,
                    )}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    Due: {invoice.due_date ? formatDate(invoice.due_date) : "-"}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    Customer: {invoice.customer_name || invoice.customer_id || "-"}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    {formatDateTime(invoice.created_at)}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => setPreviewInvoice(invoice)}
                    >
                      <Eye className="h-4 w-4" />
                      Preview
                    </Button>
                    {invoice.status !== "paid" &&
                    invoice.status !== "cancelled" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => setSendInvoiceTarget(invoice)}
                      >
                        <Send className="h-4 w-4" />
                        Send
                      </Button>
                    ) : null}
                    {invoice.status === "sent" ||
                    invoice.status === "overdue" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => remindMutation.mutate(invoice.id)}
                        loading={
                          remindMutation.isPending &&
                          remindMutation.variables === invoice.id
                        }
                      >
                        Remind
                      </Button>
                    ) : null}
                    {invoice.status !== "paid" &&
                    invoice.status !== "cancelled" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        onClick={() => setSelectedInvoice(invoice)}
                      >
                        <Wallet className="h-4 w-4" />
                        Mark Paid
                      </Button>
                    ) : null}
                    {canCancelInvoice(invoice) ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => cancelMutation.mutate(invoice.id)}
                        loading={
                          cancelMutation.isPending &&
                          cancelMutation.variables === invoice.id
                        }
                      >
                        <XCircle className="h-4 w-4" />
                        Cancel
                      </Button>
                    ) : null}
                    {canDeleteInvoice(invoice) ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="danger"
                        onClick={() => {
                          if (window.confirm("Delete this invoice? This cannot be undone.")) {
                            deleteMutation.mutate(invoice.id);
                          }
                        }}
                        loading={
                          deleteMutation.isPending &&
                          deleteMutation.variables === invoice.id
                        }
                      >
                        <Trash2 className="h-4 w-4" />
                        Delete
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
                        <Badge
                          variant={badgeVariantForInvoiceStatus(invoice.status)}
                        >
                          {invoice.status}
                        </Badge>
                      </td>
                      <td className="px-2 py-2 text-surface-700">
                        {formatCurrency(
                          invoice.total_amount,
                          profileQuery.data?.base_currency,
                        )}
                      </td>
                      <td className="px-2 py-2 text-surface-700">
                        {formatCurrency(
                          invoice.amount_paid,
                          profileQuery.data?.base_currency,
                        )}
                      </td>
                      <td className="px-2 py-2 font-semibold text-mint-700">
                        {formatCurrency(
                          invoice.outstanding_amount,
                          profileQuery.data?.base_currency,
                        )}
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        {invoice.customer_name || invoice.customer_id || "-"}
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        {invoice.due_date ? formatDate(invoice.due_date) : "-"}
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1">
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => setPreviewInvoice(invoice)}
                          >
                            Preview
                          </Button>
                          {invoice.status !== "paid" &&
                          invoice.status !== "cancelled" ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => setSendInvoiceTarget(invoice)}
                            >
                              Send
                            </Button>
                          ) : null}
                          {invoice.status === "sent" ||
                          invoice.status === "overdue" ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => remindMutation.mutate(invoice.id)}
                              loading={
                                remindMutation.isPending &&
                                remindMutation.variables === invoice.id
                              }
                            >
                              Remind
                            </Button>
                          ) : null}
                          {invoice.status !== "paid" &&
                          invoice.status !== "cancelled" ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="secondary"
                              onClick={() => setSelectedInvoice(invoice)}
                            >
                              Mark Paid
                            </Button>
                          ) : null}
                          {canCancelInvoice(invoice) ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => cancelMutation.mutate(invoice.id)}
                              loading={
                                cancelMutation.isPending &&
                                cancelMutation.variables === invoice.id
                              }
                            >
                              Cancel
                            </Button>
                          ) : null}
                          {canDeleteInvoice(invoice) ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="danger"
                              onClick={() => {
                                if (window.confirm("Delete this invoice? This cannot be undone.")) {
                                  deleteMutation.mutate(invoice.id);
                                }
                              }}
                              loading={
                                deleteMutation.isPending &&
                                deleteMutation.variables === invoice.id
                              }
                            >
                              Delete
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

      <Modal
        open={Boolean(selectedInvoice)}
        title="Mark Invoice Paid"
        onClose={() => setSelectedInvoice(null)}
      >
        {!selectedInvoice ? null : (
          <form
            className="grid gap-3"
            onSubmit={markPaidForm.handleSubmit((values) =>
              markPaidMutation.mutate({
                invoiceId: selectedInvoice.id,
                values,
              }),
            )}
          >
            <p className="text-sm text-surface-600 dark:text-surface-200">
              Outstanding balance:{" "}
              <span className="font-semibold">
                {formatCurrency(
                  selectedInvoice.outstanding_amount,
                  profileQuery.data?.base_currency,
                )}
              </span>
            </p>
            <Input
              label="Amount (optional)"
              type="number"
              step="0.01"
              {...markPaidForm.register("amount")}
              error={markPaidForm.formState.errors.amount?.message}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Payment Method"
                {...markPaidForm.register("payment_method")}
              >
                <option value="">Not specified</option>
                <option value="cash">Cash</option>
                <option value="transfer">Transfer</option>
                <option value="pos">POS</option>
              </Select>
              <Input
                label="Payment Reference"
                {...markPaidForm.register("payment_reference")}
              />
            </div>
            <Input
              label="Idempotency Key"
              {...markPaidForm.register("idempotency_key")}
            />
            <Textarea
              label="Note"
              rows={3}
              {...markPaidForm.register("note")}
            />
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setSelectedInvoice(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="secondary"
                loading={markPaidMutation.isPending}
              >
                Confirm Paid
              </Button>
            </div>
          </form>
        )}
      </Modal>

      <Modal
        open={Boolean(previewInvoice)}
        title="Invoice Preview"
        onClose={() => setPreviewInvoice(null)}
      >
        {!previewInvoice ? null : previewQuery.isLoading ? (
          <LoadingState label="Loading invoice preview..." />
        ) : previewQuery.isError || !previewData ? (
          <ErrorState
            message="Failed to load invoice preview."
            onRetry={() => previewQuery.refetch()}
          />
        ) : (
          <div className="space-y-4">
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Subject
              </p>
              <p className="mt-1 font-semibold text-surface-900 dark:text-surface-100">
                {previewData.subject}
              </p>
              <p className="mt-2 text-xs text-surface-500">
                Recommended channel:{" "}
                <span className="font-semibold text-surface-700 dark:text-surface-200">
                  {previewData.recommended_channel
                    ? channelLabel(previewData.recommended_channel)
                    : "None"}
                </span>
              </p>
            </div>

            <div className="grid gap-2">
              {previewData.delivery_options.map((option) => (
                <div
                  key={option.channel}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-surface-900 dark:text-surface-100">
                      {channelLabel(option.channel)}
                    </p>
                    <Badge
                      variant={
                        option.ready
                          ? option.suggested
                            ? "positive"
                            : "info"
                          : "negative"
                      }
                    >
                      {option.ready
                        ? option.suggested
                          ? "suggested"
                          : "ready"
                        : "not ready"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    Recipient: {option.recipient || "Not available"}
                  </p>
                  {!option.ready && option.reason ? (
                    <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">
                      {option.reason}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>

            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Message Preview
              </p>
              <p className="mt-2 whitespace-pre-wrap text-surface-700 dark:text-surface-200">
                {previewData.message_preview}
              </p>
            </div>

            <div className="space-y-2">
              <h4 className="font-semibold text-surface-900 dark:text-surface-100">
                Line Items
              </h4>
              {previewData.line_items.length ? (
                previewData.line_items.map((item) => (
                  <div
                    key={`${item.variant_id}-${item.sku || item.label || item.size}`}
                    className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-surface-900 dark:text-surface-100">
                          {item.product_name}
                        </p>
                        <p className="text-xs text-surface-500">
                          {item.size}
                          {item.label ? ` - ${item.label}` : ""}
                          {item.sku ? ` (${item.sku})` : ""}
                        </p>
                      </div>
                      <p className="font-semibold text-mint-700">
                        {formatCurrency(
                          item.line_total,
                          previewData.invoice.currency,
                        )}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">
                      {item.qty} x{" "}
                      {formatCurrency(
                        item.unit_price,
                        previewData.invoice.currency,
                      )}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-surface-500">No line items available.</p>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setPreviewInvoice(null)}
              >
                Close
              </Button>
              {previewInvoice.status !== "paid" &&
              previewInvoice.status !== "cancelled" ? (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => {
                    setSendInvoiceTarget(previewInvoice);
                    setPreviewInvoice(null);
                  }}
                >
                  Open Send Options
                </Button>
              ) : null}
            </div>
          </div>
        )}
      </Modal>

      <Modal
        open={Boolean(sendInvoiceTarget)}
        title="Send Invoice"
        onClose={() => setSendInvoiceTarget(null)}
      >
        {!sendInvoiceTarget ? null : previewQuery.isLoading ? (
          <LoadingState label="Loading delivery options..." />
        ) : previewQuery.isError || !previewData ? (
          <ErrorState
            message="Failed to load invoice delivery options."
            onRetry={() => previewQuery.refetch()}
          />
        ) : (
          <form
            className="grid gap-3"
            onSubmit={sendForm.handleSubmit((values) =>
              sendMutation.mutate({
                invoiceId: sendInvoiceTarget.id,
                values,
              })
            )}
          >
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Delivery Guidance
              </p>
              <p className="mt-1 text-surface-700 dark:text-surface-200">
                Recommended channel:{" "}
                <span className="font-semibold">
                  {previewData.recommended_channel
                    ? channelLabel(previewData.recommended_channel)
                    : "Use any ready channel"}
                </span>
              </p>
            </div>

            <Select
              label="Send Via"
              {...sendForm.register("channel")}
              error={sendForm.formState.errors.channel?.message}
            >
              <option value="">Use recommended channel</option>
              {previewData.delivery_options.map((option) => (
                <option
                  key={option.channel}
                  value={option.channel}
                  disabled={!option.ready}
                >
                  {channelLabel(option.channel)}
                  {option.suggested ? " (recommended)" : ""}
                  {!option.ready && option.reason ? ` - ${option.reason}` : ""}
                </option>
              ))}
            </Select>

            <Input
              label="Recipient Override"
              placeholder="optional@example.com or 080..."
              {...sendForm.register("recipient_override")}
              error={sendForm.formState.errors.recipient_override?.message}
            />

            <Textarea
              label="Send Note"
              rows={3}
              placeholder="Optional note for this delivery"
              {...sendForm.register("note")}
            />

            <div className="grid gap-2">
              {previewData.delivery_options.map((option) => (
                <div
                  key={option.channel}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm dark:border-surface-700 dark:bg-surface-800/60"
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-semibold text-surface-900 dark:text-surface-100">
                      {channelLabel(option.channel)}
                    </p>
                    <Badge variant={option.ready ? "positive" : "negative"}>
                      {option.ready ? "ready" : "unavailable"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    Recipient: {option.recipient || "Not available"}
                  </p>
                  {!option.ready && option.reason ? (
                    <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">
                      {option.reason}
                    </p>
                  ) : null}
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setSendInvoiceTarget(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="secondary"
                loading={sendMutation.isPending}
              >
                Send Invoice
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
