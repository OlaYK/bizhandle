import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, ScanLine, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { z } from "zod";
import { orderService, productService } from "../api/services";
import type { OrderStatus } from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDateTime } from "../lib/format";

const orderItemSchema = z.object({
  variant_id: z.string().min(1, "Variant is required"),
  qty: z.coerce.number().int().min(1, "Qty must be at least 1"),
  unit_price: z.coerce.number().positive("Unit price must be > 0")
});

const orderCreateSchema = z.object({
  customer_id: z.string().optional(),
  payment_method: z.enum(["cash", "transfer", "pos"]),
  channel: z.enum(["whatsapp", "instagram", "walk-in"]),
  note: z.string().optional(),
  items: z.array(orderItemSchema).min(1, "Add at least one item")
});

type OrderCreateFormData = z.infer<typeof orderCreateSchema>;

const statusOptions: OrderStatus[] = [
  "pending",
  "paid",
  "processing",
  "fulfilled",
  "cancelled",
  "refunded"
];

const orderTransitions: Record<OrderStatus, OrderStatus[]> = {
  pending: ["paid", "cancelled"],
  paid: ["processing", "fulfilled", "cancelled", "refunded"],
  processing: ["fulfilled", "cancelled", "refunded"],
  fulfilled: ["refunded"],
  cancelled: [],
  refunded: []
};

function getAllowedStatusOptions(status: OrderStatus) {
  return [status, ...(orderTransitions[status] ?? [])];
}

function badgeVariantForStatus(status: OrderStatus): "neutral" | "positive" | "negative" | "info" {
  if (status === "paid" || status === "fulfilled") return "positive";
  if (status === "cancelled" || status === "refunded") return "negative";
  if (status === "processing") return "info";
  return "neutral";
}

function defaultUnitPrice(price: number | null | undefined) {
  if (typeof price !== "number" || Number.isNaN(price) || price <= 0) {
    return 1;
  }
  return price;
}

export function OrdersPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const quickInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedProductId, setSelectedProductId] = useState("");
  const [quickCode, setQuickCode] = useState("");
  const [statusFilter, setStatusFilter] = useState<OrderStatus | "">("");
  const [channelFilter, setChannelFilter] = useState<"whatsapp" | "instagram" | "walk-in" | "">("");
  const [customerFilter, setCustomerFilter] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusDraftByOrderId, setStatusDraftByOrderId] = useState<Record<string, OrderStatus>>({});

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [statusFilter, channelFilter, customerFilter, startDate, endDate]);

  const productsQuery = useQuery({
    queryKey: ["orders", "products"],
    queryFn: () => productService.list({ limit: 200, offset: 0 })
  });

  useEffect(() => {
    if (!productsQuery.data?.items.length) return;
    if (!selectedProductId) {
      setSelectedProductId(productsQuery.data.items[0].id);
    }
  }, [productsQuery.data, selectedProductId]);

  const variantsQuery = useQuery({
    queryKey: ["orders", "variants", selectedProductId],
    queryFn: () => productService.listVariants(selectedProductId, { limit: 300, offset: 0 }),
    enabled: Boolean(selectedProductId)
  });

  const orderForm = useForm<OrderCreateFormData>({
    resolver: zodResolver(orderCreateSchema),
    defaultValues: {
      customer_id: "",
      payment_method: "cash",
      channel: "walk-in",
      note: "",
      items: [{ variant_id: "", qty: 1, unit_price: 1 }]
    }
  });

  const { fields, append, remove } = useFieldArray({
    control: orderForm.control,
    name: "items"
  });

  useEffect(() => {
    const firstVariant = variantsQuery.data?.items[0];
    if (!firstVariant) return;
    if (!orderForm.getValues("items.0.variant_id")) {
      orderForm.setValue("items.0.variant_id", firstVariant.id);
      orderForm.setValue("items.0.unit_price", defaultUnitPrice(firstVariant.selling_price));
    }
  }, [variantsQuery.data, orderForm]);

  const orderItems = orderForm.watch("items");
  const orderTotal = useMemo(
    () =>
      (orderItems ?? []).reduce((sum, item) => {
        const qty = Number(item.qty) || 0;
        const unitPrice = Number(item.unit_price) || 0;
        return sum + qty * unitPrice;
      }, 0),
    [orderItems]
  );

  const listQuery = useQuery({
    queryKey: [
      "orders",
      "list",
      statusFilter,
      channelFilter,
      customerFilter,
      startDate,
      endDate,
      page,
      pageSize
    ],
    queryFn: () =>
      orderService.list({
        status: statusFilter || undefined,
        channel: channelFilter || undefined,
        customer_id: customerFilter.trim() || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset
      })
  });

  useEffect(() => {
    if (!listQuery.data?.items) return;
    setStatusDraftByOrderId((previous) => {
      const next: Record<string, OrderStatus> = {};
      for (const order of listQuery.data.items) {
        next[order.id] = previous[order.id] ?? order.status;
      }
      return next;
    });
  }, [listQuery.data]);

  const createOrderMutation = useMutation({
    mutationFn: orderService.create,
    onSuccess: () => {
      showToast({
        title: "Order created",
        description: "Order is now pending and can be tracked in the lifecycle list.",
        variant: "success"
      });
      orderForm.reset({
        customer_id: "",
        payment_method: "cash",
        channel: "walk-in",
        note: "",
        items: [
          {
            variant_id: variantsQuery.data?.items[0]?.id ?? "",
            qty: 1,
            unit_price: defaultUnitPrice(variantsQuery.data?.items[0]?.selling_price)
          }
        ]
      });
      setQuickCode("");
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create order",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ orderId, status }: { orderId: string; status: OrderStatus }) =>
      orderService.updateStatus(orderId, { status }),
    onSuccess: () => {
      showToast({ title: "Order status updated", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => {
      showToast({
        title: "Status update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const variantQuickLookup = useMemo(() => {
    const rows = variantsQuery.data?.items ?? [];
    return rows.map((variant) => ({
      variant,
      sku: variant.sku?.trim().toLowerCase() ?? "",
      label: variant.label?.trim().toLowerCase() ?? "",
      size: variant.size.trim().toLowerCase()
    }));
  }, [variantsQuery.data]);

  function handleQuickAdd() {
    const code = quickCode.trim().toLowerCase();
    if (!code) return;

    const exact = variantQuickLookup.find((entry) => entry.sku && entry.sku === code);
    const fallback = variantQuickLookup.find(
      (entry) => entry.size === code || entry.label === code || `${entry.size} ${entry.label}`.trim() === code
    );
    const partial = variantQuickLookup.find(
      (entry) => entry.sku.includes(code) || entry.size.includes(code) || entry.label.includes(code)
    );
    const match = exact?.variant ?? fallback?.variant ?? partial?.variant ?? null;

    if (!match) {
      showToast({
        title: "Variant not found",
        description: "Scan SKU or enter SKU/size/label for the selected product.",
        variant: "error"
      });
      return;
    }

    const currentItems = orderForm.getValues("items");
    const existingIndex = currentItems.findIndex((item) => item.variant_id === match.id);
    if (existingIndex >= 0) {
      const existingQty = Number(currentItems[existingIndex]?.qty ?? 0);
      orderForm.setValue(`items.${existingIndex}.qty`, Math.max(1, existingQty + 1), {
        shouldDirty: true
      });
    } else {
      append({
        variant_id: match.id,
        qty: 1,
        unit_price: defaultUnitPrice(match.selling_price)
      });
    }

    setQuickCode("");
    quickInputRef.current?.focus();
  }

  if (productsQuery.isLoading || listQuery.isLoading) {
    return <LoadingState label="Loading orders workspace..." />;
  }

  if (productsQuery.isError || variantsQuery.isError || listQuery.isError) {
    return (
      <ErrorState
        message="Failed to load order workspace."
        onRetry={() => {
          productsQuery.refetch();
          variantsQuery.refetch();
          listQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-heading text-lg font-bold">POS Quick Order</h3>
          <Badge variant="info">Scanner-ready</Badge>
        </div>
        <p className="mt-1 text-sm text-surface-500">
          Pick a product, scan or type SKU/size/label, then press Enter to add to cart.
        </p>
        <form
          className="mt-4 space-y-4"
          onSubmit={orderForm.handleSubmit((values) =>
            createOrderMutation.mutate({
              customer_id: values.customer_id?.trim() || undefined,
              payment_method: values.payment_method,
              channel: values.channel,
              note: values.note?.trim() || undefined,
              items: values.items
            })
          )}
        >
          <div className="grid gap-3 md:grid-cols-4">
            <Select label="Product" value={selectedProductId} onChange={(event) => setSelectedProductId(event.target.value)}>
              {(productsQuery.data?.items ?? []).map((product) => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </Select>
            <Input label="Customer ID (optional)" placeholder="customer-001" {...orderForm.register("customer_id")} />
            <Select
              label="Payment Method"
              {...orderForm.register("payment_method")}
              error={orderForm.formState.errors.payment_method?.message}
            >
              <option value="cash">Cash</option>
              <option value="transfer">Transfer</option>
              <option value="pos">POS</option>
            </Select>
            <Select
              label="Channel"
              {...orderForm.register("channel")}
              error={orderForm.formState.errors.channel?.message}
            >
              <option value="walk-in">Walk-in</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
            </Select>
          </div>

          <div className="rounded-2xl border border-surface-100 p-3">
            <div className="grid gap-3 md:grid-cols-[1fr_auto]">
              <Input
                ref={quickInputRef}
                label="Quick Add (SKU / size / label)"
                placeholder="Scan barcode or type code and press Enter"
                value={quickCode}
                onChange={(event) => setQuickCode(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    handleQuickAdd();
                  }
                }}
              />
              <div className="md:self-end">
                <Button type="button" variant="secondary" className="w-full md:w-auto" onClick={handleQuickAdd}>
                  <ScanLine className="h-4 w-4" />
                  Add
                </Button>
              </div>
            </div>
          </div>

          <div className="space-y-3 rounded-2xl border border-surface-100 p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-surface-700">Order Items</p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  append({
                    variant_id: variantsQuery.data?.items[0]?.id ?? "",
                    qty: 1,
                    unit_price: defaultUnitPrice(variantsQuery.data?.items[0]?.selling_price)
                  })
                }
              >
                <Plus className="h-4 w-4" />
                Add Row
              </Button>
            </div>

            {fields.map((field, index) => (
              <div key={field.id} className="grid gap-3 rounded-xl border border-surface-100 p-3 md:grid-cols-12">
                <div className="md:col-span-6">
                  <Select
                    label="Variant"
                    {...orderForm.register(`items.${index}.variant_id`)}
                    error={orderForm.formState.errors.items?.[index]?.variant_id?.message}
                  >
                    <option value="">Select variant</option>
                    {(variantsQuery.data?.items ?? []).map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.size}
                        {variant.label ? ` - ${variant.label}` : ""}
                        {variant.sku ? ` (${variant.sku})` : ""}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="md:col-span-2">
                  <Input
                    label="Qty"
                    type="number"
                    {...orderForm.register(`items.${index}.qty`)}
                    error={orderForm.formState.errors.items?.[index]?.qty?.message}
                  />
                </div>
                <div className="md:col-span-3">
                  <Input
                    label="Unit Price"
                    type="number"
                    step="0.01"
                    {...orderForm.register(`items.${index}.unit_price`)}
                    error={orderForm.formState.errors.items?.[index]?.unit_price?.message}
                  />
                </div>
                <div className="md:col-span-1 md:self-end">
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="w-full"
                    onClick={() => remove(index)}
                    disabled={fields.length <= 1}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>

          <Textarea label="Note" rows={3} {...orderForm.register("note")} />

          <div className="flex flex-wrap items-center justify-between gap-3">
            <Badge variant="positive">Cart Total: {formatCurrency(orderTotal)}</Badge>
            <Button type="submit" loading={createOrderMutation.isPending}>
              Create Order
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-6">
          <Input label="Start Date" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          <Input label="End Date" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          <Select label="Status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as OrderStatus | "")}>
            <option value="">All statuses</option>
            {statusOptions.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </Select>
          <Select
            label="Channel"
            value={channelFilter}
            onChange={(event) =>
              setChannelFilter(event.target.value as "whatsapp" | "instagram" | "walk-in" | "")
            }
          >
            <option value="">All channels</option>
            <option value="walk-in">Walk-in</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="instagram">Instagram</option>
          </Select>
          <Input
            label="Customer ID"
            placeholder="customer-001"
            value={customerFilter}
            onChange={(event) => setCustomerFilter(event.target.value)}
          />
          <div className="mt-7">
            <Badge variant="info">{listQuery.data?.pagination.total ?? 0} orders</Badge>
          </div>
        </div>

        {!listQuery.data?.items.length ? (
          <EmptyState
            title="No orders found"
            description="Try changing filters or create a new order from the POS quick-order panel."
          />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {listQuery.data.items.map((order) => {
                const draftStatus = statusDraftByOrderId[order.id] ?? order.status;
                const allowedStatuses = getAllowedStatusOptions(order.status);
                return (
                  <article key={order.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <Badge variant={badgeVariantForStatus(order.status)}>{order.status}</Badge>
                      <p className="text-sm font-semibold text-mint-700">{formatCurrency(order.total_amount)}</p>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">
                      {order.channel} / {order.payment_method}
                    </p>
                    <p className="mt-1 text-xs text-surface-500">{formatDateTime(order.created_at)}</p>
                    <p className="mt-1 text-xs text-surface-500">Customer: {order.customer_id || "-"}</p>
                    <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                      <select
                        className="h-9 rounded border border-surface-200 bg-white px-2 text-sm text-surface-700 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100"
                        value={draftStatus}
                        onChange={(event) =>
                          setStatusDraftByOrderId((previous) => ({
                            ...previous,
                            [order.id]: event.target.value as OrderStatus
                          }))
                        }
                      >
                        {allowedStatuses.map((status) => (
                          <option key={status} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          updateStatusMutation.mutate({
                            orderId: order.id,
                            status: draftStatus
                          })
                        }
                        disabled={
                          draftStatus === order.status ||
                          (updateStatusMutation.isPending &&
                            updateStatusMutation.variables?.orderId === order.id)
                        }
                      >
                        Update
                      </Button>
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
                    <th className="px-2 py-2">Channel</th>
                    <th className="px-2 py-2">Payment</th>
                    <th className="px-2 py-2">Customer</th>
                    <th className="px-2 py-2">Date</th>
                    <th className="px-2 py-2">Lifecycle</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {listQuery.data.items.map((order) => {
                    const draftStatus = statusDraftByOrderId[order.id] ?? order.status;
                    const allowedStatuses = getAllowedStatusOptions(order.status);
                    return (
                      <tr key={order.id}>
                        <td className="px-2 py-2">
                          <Badge variant={badgeVariantForStatus(order.status)}>{order.status}</Badge>
                        </td>
                        <td className="px-2 py-2 font-semibold text-mint-700">{formatCurrency(order.total_amount)}</td>
                        <td className="px-2 py-2 text-surface-600">{order.channel}</td>
                        <td className="px-2 py-2 text-surface-600">{order.payment_method}</td>
                        <td className="px-2 py-2 text-surface-600">{order.customer_id || "-"}</td>
                        <td className="px-2 py-2 text-surface-500">{formatDateTime(order.created_at)}</td>
                        <td className="px-2 py-2">
                          <div className="flex items-center gap-2">
                            <select
                              className="h-9 rounded border border-surface-200 bg-white px-2 text-sm text-surface-700 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100"
                              value={draftStatus}
                              onChange={(event) =>
                                setStatusDraftByOrderId((previous) => ({
                                  ...previous,
                                  [order.id]: event.target.value as OrderStatus
                                }))
                              }
                            >
                              {allowedStatuses.map((status) => (
                                <option key={status} value={status}>
                                  {status}
                                </option>
                              ))}
                            </select>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                updateStatusMutation.mutate({
                                  orderId: order.id,
                                  status: draftStatus
                                })
                              }
                              disabled={
                                draftStatus === order.status ||
                                (updateStatusMutation.isPending &&
                                  updateStatusMutation.variables?.orderId === order.id)
                              }
                            >
                              Update
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
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
    </div>
  );
}
