import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  useFieldArray,
  useForm,
  useWatch,
  type UseFormReturn,
} from "react-hook-form";
import { z } from "zod";
import { authService, productService, salesService } from "../api/services";
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
import { formatCurrency, formatDateTime } from "../lib/format";
import type { ProductOut, SaleQuoteLineOut } from "../api/types";

const saleItemSchema = z.object({
  variant_id: z.string().min(1, "Variant is required"),
  qty: z.coerce.number().int().min(1, "Qty must be at least 1"),
  unit_price: z.coerce.number().positive("Unit price must be > 0"),
});

const saleSchema = z.object({
  payment_method: z.enum(["cash", "transfer", "pos"]),
  channel: z.enum(["whatsapp", "instagram", "walk-in"]),
  note: z.string().optional(),
  items: z.array(saleItemSchema).min(1, "Add at least one item"),
});

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

const refundSchema = z.object({
  variant_id: z.string().min(1, "Variant is required"),
  qty: z.coerce.number().int().min(1, "Qty must be at least 1"),
  unit_price: optionalPositiveNumber,
  payment_method: z.enum(["cash", "transfer", "pos"]).optional(),
  channel: z.enum(["whatsapp", "instagram", "walk-in"]).optional(),
  note: z.string().optional(),
});

type SaleFormData = z.infer<typeof saleSchema>;
type RefundFormData = z.infer<typeof refundSchema>;

function defaultUnitPrice(price: number | null | undefined) {
  if (typeof price !== "number" || Number.isNaN(price) || price <= 0) {
    return 1;
  }
  return price;
}

/* ── Per-row line item with its own product + variant selection ── */
function SaleLineItem({
  index,
  saleForm,
  products,
  defaultProductId,
  quoteLine,
  canRemove,
  onRemove,
}: {
  index: number;
  saleForm: UseFormReturn<SaleFormData>;
  products: ProductOut[];
  defaultProductId: string;
  quoteLine?: SaleQuoteLineOut;
  canRemove: boolean;
  onRemove: () => void;
}) {
  const [productId, setProductId] = useState(defaultProductId);

  const variantsQuery = useQuery({
    queryKey: ["sales", "variants", productId],
    queryFn: () =>
      productService.listVariants(productId, { limit: 100, offset: 0 }),
    enabled: Boolean(productId),
  });

  /* When the product changes, reset the variant & price for this row */
  useEffect(() => {
    const firstVariant = variantsQuery.data?.items[0];
    if (firstVariant) {
      saleForm.setValue(`items.${index}.variant_id`, firstVariant.id, {
        shouldValidate: true,
      });
      saleForm.setValue(
        `items.${index}.unit_price`,
        defaultUnitPrice(firstVariant.selling_price),
        { shouldValidate: true },
      );
    } else {
      saleForm.setValue(`items.${index}.variant_id`, "");
    }
    // only run when product variants change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variantsQuery.data]);

  const variantField = saleForm.register(`items.${index}.variant_id`);

  return (
    <div className="grid gap-3 rounded-xl border border-surface-100 p-3 md:grid-cols-12">
      <div className="md:col-span-3">
        <Select
          label="Product"
          value={productId}
          onChange={(e) => setProductId(e.target.value)}
        >
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name}
            </option>
          ))}
        </Select>
      </div>

      <div className="md:col-span-3">
        <Select
          label="Variant"
          {...variantField}
          onChange={(event) => {
            variantField.onChange(event);
            const selectedVariant = variantsQuery.data?.items.find(
              (variant) => variant.id === event.target.value,
            );
            if (!selectedVariant) return;
            saleForm.setValue(
              `items.${index}.unit_price`,
              defaultUnitPrice(selectedVariant.selling_price),
              { shouldDirty: true, shouldValidate: true },
            );
          }}
          error={
            saleForm.formState.errors.items?.[index]?.variant_id?.message
          }
        >
          <option value="">Select variant</option>
          {(variantsQuery.data?.items ?? []).map((variant) => (
            <option key={variant.id} value={variant.id}>
              {variant.size}{" "}
              {variant.label ? `- ${variant.label}` : ""} (
              {variant.stock} in stock)
            </option>
          ))}
        </Select>
      </div>

      <div className="md:col-span-2">
        <Input
          label="Qty"
          type="number"
          {...saleForm.register(`items.${index}.qty`)}
          error={saleForm.formState.errors.items?.[index]?.qty?.message}
        />
      </div>
      <div className="md:col-span-2">
        <Input
          label="Unit Price"
          type="number"
          step="0.01"
          {...saleForm.register(`items.${index}.unit_price`)}
          error={
            saleForm.formState.errors.items?.[index]?.unit_price?.message
          }
        />
      </div>
      <div className="md:col-span-1 md:self-end">
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="w-full"
          onClick={onRemove}
          disabled={!canRemove}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
      <div className="md:col-span-12 flex flex-wrap items-center gap-3 text-xs">
        <span className="font-semibold text-surface-600">
          Line Total: {formatCurrency(quoteLine?.line_total ?? 0)}
        </span>
        {quoteLine?.available_stock !== undefined ? (
          <span className="text-surface-500">
            Available Stock: {quoteLine.available_stock ?? "-"}
          </span>
        ) : null}
        {quoteLine?.errors?.length ? (
          <span className="text-red-600">{quoteLine.errors[0]}</span>
        ) : null}
      </div>
    </div>
  );
}

export function SalesPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
  });
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [includeRefunds, setIncludeRefunds] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [refundSaleId, setRefundSaleId] = useState<string | null>(null);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [startDate, endDate, includeRefunds]);

  const productsQuery = useQuery({
    queryKey: ["sales", "products"],
    queryFn: () => productService.list({ limit: 100, offset: 0 }),
  });

  const firstProductId = productsQuery.data?.items[0]?.id ?? "";

  const saleForm = useForm<SaleFormData>({
    resolver: zodResolver(saleSchema),
    defaultValues: {
      payment_method: "cash",
      channel: "walk-in",
      note: "",
      items: [{ variant_id: "", qty: 1, unit_price: 1 }],
    },
  });

  const { fields, append, remove } = useFieldArray({
    control: saleForm.control,
    name: "items",
  });
  const watchedItems = useWatch({
    control: saleForm.control,
    name: "items",
  }) ?? [];

  const normalizedQuoteItems = useMemo(
    () =>
      watchedItems.map((item) => ({
        variant_id: item?.variant_id || "",
        qty: Number(item?.qty || 0),
        unit_price: Number(item?.unit_price || 0),
      })),
    [watchedItems],
  );
  const [debouncedQuoteItems, setDebouncedQuoteItems] = useState(
    normalizedQuoteItems,
  );

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuoteItems(normalizedQuoteItems);
    }, 350);
    return () => window.clearTimeout(timeout);
  }, [normalizedQuoteItems]);

  const hasQuoteReadyItems =
    debouncedQuoteItems.length > 0 &&
    debouncedQuoteItems.every(
      (item) => item.variant_id && item.qty > 0 && item.unit_price > 0,
    );

  const quoteQuery = useQuery({
    queryKey: ["sales", "quote", debouncedQuoteItems],
    enabled: hasQuoteReadyItems,
    retry: false,
    queryFn: () =>
      salesService.quote({
        items: debouncedQuoteItems,
      }),
  });

  const listQuery = useQuery({
    queryKey: [
      "sales",
      "list",
      startDate,
      endDate,
      includeRefunds,
      page,
      pageSize,
    ],
    queryFn: () =>
      salesService.list({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        include_refunds: includeRefunds,
        limit: pageSize,
        offset,
      }),
  });

  const summaryQuery = useQuery({
    queryKey: ["sales", "summary", startDate, endDate],
    queryFn: () =>
      salesService.summary({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
  });

  const quoteLines = quoteQuery.data?.items ?? [];
  const draftTotal = quoteQuery.data?.total ?? watchedItems.reduce((sum, item) => {
    const qty = Number(item?.qty || 0);
    const unitPrice = Number(item?.unit_price || 0);
    return sum + qty * unitPrice;
  }, 0);
  const quoteHasBlockingErrors = Boolean(
    hasQuoteReadyItems && quoteQuery.data && !quoteQuery.data.is_valid,
  );

  const createSaleMutation = useMutation({
    mutationFn: salesService.create,
    onSuccess: () => {
      showToast({ title: "Sale recorded", variant: "success" });
      saleForm.reset({
        payment_method: "cash",
        channel: "walk-in",
        note: "",
        items: [{ variant_id: "", qty: 1, unit_price: 1 }],
      });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Sale failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const refundForm = useForm<RefundFormData>({
    resolver: zodResolver(refundSchema),
    defaultValues: {
      variant_id: "",
      qty: 1,
      unit_price: undefined,
      payment_method: undefined,
      channel: undefined,
      note: "",
    },
  });

  const refundOptionsQuery = useQuery({
    queryKey: ["sales", "refund-options", refundSaleId],
    queryFn: () => salesService.refundOptions(refundSaleId as string),
    enabled: Boolean(refundSaleId),
  });

  const selectedRefundVariantId = refundForm.watch("variant_id");
  const selectedRefundOption = useMemo(() => {
    if (!selectedRefundVariantId) return null;
    return (
      refundOptionsQuery.data?.items.find(
        (item) => item.variant_id === selectedRefundVariantId,
      ) ?? null
    );
  }, [selectedRefundVariantId, refundOptionsQuery.data]);

  useEffect(() => {
    const firstOption = refundOptionsQuery.data?.items[0];
    if (!firstOption) {
      return;
    }

    const currentVariantId = refundForm.getValues("variant_id");
    const hasCurrentVariant = refundOptionsQuery.data?.items.some(
      (item) => item.variant_id === currentVariantId,
    );
    if (!currentVariantId || !hasCurrentVariant) {
      refundForm.setValue("variant_id", firstOption.variant_id);
      refundForm.setValue("qty", 1);
      refundForm.setValue(
        "unit_price",
        firstOption.default_unit_price ?? undefined,
      );
    }
  }, [refundOptionsQuery.data, refundForm]);

  useEffect(() => {
    if (!selectedRefundOption) return;
    const currentPrice = refundForm.getValues("unit_price");
    if (currentPrice === undefined || Number.isNaN(currentPrice)) {
      refundForm.setValue(
        "unit_price",
        selectedRefundOption.default_unit_price ?? undefined,
      );
    }
  }, [selectedRefundOption, refundForm]);

  const refundMutation = useMutation({
    mutationFn: (values: RefundFormData) => {
      if (!refundSaleId) {
        throw new Error("No sale selected for refund");
      }
      if (!selectedRefundOption) {
        throw new Error("Select a refundable sale item");
      }
      if (values.qty > selectedRefundOption.refundable_qty) {
        throw new Error(
          `Maximum refundable quantity is ${selectedRefundOption.refundable_qty}`,
        );
      }

      return salesService.refund(refundSaleId, {
        payment_method: values.payment_method,
        channel: values.channel,
        note: values.note?.trim() || undefined,
        items: [
          {
            variant_id: values.variant_id,
            qty: values.qty,
            unit_price:
              values.unit_price !== undefined &&
              !Number.isNaN(values.unit_price)
                ? values.unit_price
                : undefined,
          },
        ],
      });
    },
    onSuccess: () => {
      showToast({ title: "Refund recorded", variant: "success" });
      setRefundSaleId(null);
      refundForm.reset({
        variant_id: "",
        qty: 1,
        unit_price: undefined,
        payment_method: undefined,
        channel: undefined,
        note: "",
      });
      queryClient.invalidateQueries({ queryKey: ["sales"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Refund failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  if (productsQuery.isLoading || listQuery.isLoading || summaryQuery.isLoading) {
    return <LoadingState label="Loading sales workspace..." />;
  }

  if (productsQuery.isError || listQuery.isError || summaryQuery.isError) {
    return (
      <ErrorState
        message="Failed to load sales data."
        onRetry={() => {
          productsQuery.refetch();
          listQuery.refetch();
          summaryQuery.refetch();
        }}
      />
    );
  }

  const products = productsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold">Record Sale</h3>
        <form
          className="mt-4 space-y-4"
          onSubmit={saleForm.handleSubmit((values) =>
            createSaleMutation.mutate({
              payment_method: values.payment_method,
              channel: values.channel,
              note: values.note?.trim() || undefined,
              items: values.items,
            }),
          )}
        >
          <div className="grid gap-3 md:grid-cols-3">
            <Select
              label="Payment Method"
              {...saleForm.register("payment_method")}
              error={saleForm.formState.errors.payment_method?.message}
            >
              <option value="cash">Cash</option>
              <option value="transfer">Transfer</option>
              <option value="pos">POS</option>
            </Select>
            <Select
              label="Channel"
              {...saleForm.register("channel")}
              error={saleForm.formState.errors.channel?.message}
            >
              <option value="walk-in">Walk-in</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
            </Select>
          </div>

          <div className="space-y-3 rounded-2xl border border-surface-100 p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-surface-700">
                Sale Items
              </p>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  append({ variant_id: "", qty: 1, unit_price: 1 })
                }
              >
                <Plus className="h-4 w-4" /> Add Item
              </Button>
            </div>

            {fields.map((field, index) => (
              <SaleLineItem
                key={field.id}
                index={index}
                saleForm={saleForm}
                products={products}
                defaultProductId={firstProductId}
                quoteLine={quoteLines[index]}
                canRemove={fields.length > 1}
                onRemove={() => remove(index)}
              />
            ))}
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Draft Total
              </p>
              <p className="mt-1 text-lg font-semibold text-mint-700">
                {formatCurrency(draftTotal, profileQuery.data?.base_currency)}
              </p>
            </div>
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Quote Status
              </p>
              <p className="mt-1 text-sm font-semibold text-surface-700">
                {quoteQuery.isFetching
                  ? "Refreshing totals..."
                  : quoteHasBlockingErrors
                    ? "Fix stock or variant issues"
                    : "Ready to save"}
              </p>
            </div>
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <p className="text-xs uppercase tracking-wide text-surface-500">
                Validation
              </p>
              <p className="mt-1 text-sm text-surface-600">
                {quoteQuery.data?.errors?.[0] ||
                  "Line totals and stock checks update automatically."}
              </p>
            </div>
          </div>

          <Textarea label="Note" rows={3} {...saleForm.register("note")} />
          <Button
            type="submit"
            loading={createSaleMutation.isPending}
            disabled={quoteHasBlockingErrors}
          >
            Save Sale
          </Button>
        </form>
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-4">
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
          <label className="mt-7 inline-flex items-center gap-2 text-sm font-semibold text-surface-700">
            <input
              type="checkbox"
              checked={includeRefunds}
              onChange={(event) => setIncludeRefunds(event.target.checked)}
            />
            Include refunds
          </label>
          <div className="mt-7">
            <Badge variant="info">
              {listQuery.data?.pagination.total ?? 0} records
            </Badge>
          </div>
        </div>
        <div className="mb-4 grid gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Paid Sales Total
            </p>
            <p className="mt-1 text-lg font-semibold text-mint-700">
              {formatCurrency(
                summaryQuery.data?.total_amount ?? 0,
                summaryQuery.data?.base_currency ?? profileQuery.data?.base_currency,
              )}
            </p>
          </div>
          <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
            <p className="text-xs uppercase tracking-wide text-surface-500">
              Paid Sales Count
            </p>
            <p className="mt-1 text-lg font-semibold text-surface-700">
              {summaryQuery.data?.sales_count ?? 0}
            </p>
          </div>
        </div>

        {!listQuery.data?.items.length ? (
          <EmptyState
            title="No sales found"
            description="Change filters or record a new sale."
          />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {listQuery.data.items.map((sale) => (
                <article
                  key={sale.id}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3"
                >
                  <div className="flex items-center justify-between">
                    <Badge
                      variant={sale.kind === "refund" ? "negative" : "positive"}
                    >
                      {sale.kind}
                    </Badge>
                    <p
                      className={`text-sm font-semibold ${
                        sale.total_amount >= 0
                          ? "text-mint-700"
                          : "text-red-600"
                      }`}
                    >
                      {formatCurrency(
                        sale.total_amount,
                        profileQuery.data?.base_currency,
                      )}
                    </p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">
                    {sale.channel} / {sale.payment_method}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    {formatDateTime(sale.created_at)}
                  </p>
                  {sale.kind === "sale" ? (
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="mt-2"
                      onClick={() => setRefundSaleId(sale.id)}
                    >
                      <RefreshCw className="h-4 w-4" />
                      Refund
                    </Button>
                  ) : null}
                </article>
              ))}
            </div>
            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Kind</th>
                    <th className="px-2 py-2">Amount</th>
                    <th className="px-2 py-2">Channel</th>
                    <th className="px-2 py-2">Payment</th>
                    <th className="px-2 py-2">Date</th>
                    <th className="px-2 py-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {listQuery.data.items.map((sale) => (
                    <tr key={sale.id}>
                      <td className="px-2 py-2">
                        <Badge
                          variant={
                            sale.kind === "refund" ? "negative" : "positive"
                          }
                        >
                          {sale.kind}
                        </Badge>
                      </td>
                      <td
                        className={`px-2 py-2 font-semibold ${
                          sale.total_amount >= 0
                            ? "text-mint-700"
                            : "text-red-600"
                        }`}
                      >
                        {formatCurrency(
                          sale.total_amount,
                          profileQuery.data?.base_currency,
                        )}
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        {sale.channel}
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        {sale.payment_method}
                      </td>
                      <td className="px-2 py-2 text-surface-500">
                        {formatDateTime(sale.created_at)}
                      </td>
                      <td className="px-2 py-2">
                        {sale.kind === "sale" ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() => setRefundSaleId(sale.id)}
                          >
                            <RefreshCw className="h-4 w-4" />
                          </Button>
                        ) : (
                          "-"
                        )}
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
        open={Boolean(refundSaleId)}
        title="Create Refund"
        onClose={() => setRefundSaleId(null)}
      >
        {refundOptionsQuery.isLoading ? (
          <LoadingState label="Loading refundable items..." />
        ) : refundOptionsQuery.isError ? (
          <ErrorState
            message="Failed to load refund options."
            onRetry={() => refundOptionsQuery.refetch()}
          />
        ) : !refundOptionsQuery.data?.items.length ? (
          <EmptyState
            title="No refundable items left"
            description="All sale items have already been fully refunded."
          />
        ) : (
          <form
            className="grid gap-3"
            onSubmit={refundForm.handleSubmit((values) =>
              refundMutation.mutate(values),
            )}
          >
            <Select
              label="Sale Item"
              {...refundForm.register("variant_id")}
              error={refundForm.formState.errors.variant_id?.message}
            >
              {refundOptionsQuery.data.items.map((item) => (
                <option key={item.variant_id} value={item.variant_id}>
                  {item.product_name} - {item.size}{" "}
                  {item.label ? `(${item.label})` : ""}
                </option>
              ))}
            </Select>
            {selectedRefundOption ? (
              <p className="text-xs text-surface-500">
                Sold: {selectedRefundOption.sold_qty} | Refunded:{" "}
                {selectedRefundOption.refunded_qty} | Remaining:{" "}
                {selectedRefundOption.refundable_qty}
              </p>
            ) : null}
            <Input
              label="Quantity"
              type="number"
              max={selectedRefundOption?.refundable_qty ?? undefined}
              {...refundForm.register("qty")}
              error={refundForm.formState.errors.qty?.message}
            />
            <Input
              label="Unit Price (optional)"
              type="number"
              step="0.01"
              {...refundForm.register("unit_price")}
              error={refundForm.formState.errors.unit_price?.message}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Select
                label="Payment Method"
                {...refundForm.register("payment_method")}
              >
                <option value="">
                  Use original ({refundOptionsQuery.data.payment_method})
                </option>
                <option value="cash">Cash</option>
                <option value="transfer">Transfer</option>
                <option value="pos">POS</option>
              </Select>
              <Select label="Channel" {...refundForm.register("channel")}>
                <option value="">
                  Use original ({refundOptionsQuery.data.channel})
                </option>
                <option value="walk-in">Walk-in</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="instagram">Instagram</option>
              </Select>
            </div>
            <Textarea label="Note" rows={3} {...refundForm.register("note")} />
            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                onClick={() => setRefundSaleId(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="secondary"
                loading={refundMutation.isPending}
              >
                Save Refund
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
