import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { inventoryService, productService } from "../api/services";
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

const productSchema = z.object({
  name: z.string().min(1, "Product name is required"),
  category: z.string().optional()
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

const variantSchema = z.object({
  size: z.string().min(1, "Size is required"),
  label: z.string().optional(),
  sku: z.string().optional(),
  reorder_level: z.coerce.number().min(0, "Must be >= 0"),
  cost_price: optionalPositiveNumber,
  selling_price: optionalPositiveNumber
});

const stockInSchema = z.object({
  qty: z.coerce.number().int().min(1, "Quantity must be at least 1"),
  unit_cost: optionalPositiveNumber
});

const adjustSchema = z.object({
  qty_delta: z.coerce.number().int().refine((value) => value !== 0, "Cannot be zero"),
  reason: z.string().min(3, "Reason is required"),
  note: z.string().optional(),
  unit_cost: optionalPositiveNumber
});

type ProductForm = z.infer<typeof productSchema>;
type VariantForm = z.infer<typeof variantSchema>;
type StockInForm = z.infer<typeof stockInSchema>;
type AdjustForm = z.infer<typeof adjustSchema>;

function normalizeOptionalNumber(value: number | undefined) {
  if (value === undefined || Number.isNaN(value)) {
    return undefined;
  }
  return value;
}

export function InventoryPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [selectedProductId, setSelectedProductId] = useState<string>("");
  const [selectedVariantId, setSelectedVariantId] = useState<string>("");
  const [ledgerVariantFilter, setLedgerVariantFilter] = useState<string>("");
  const [ledgerPage, setLedgerPage] = useState(1);
  const [ledgerPageSize, setLedgerPageSize] = useState(20);
  const [lowStockPage, setLowStockPage] = useState(1);
  const [lowStockPageSize, setLowStockPageSize] = useState(20);

  const ledgerOffset = (ledgerPage - 1) * ledgerPageSize;
  const lowStockOffset = (lowStockPage - 1) * lowStockPageSize;

  const productsQuery = useQuery({
    queryKey: ["products", "list"],
    queryFn: () => productService.list({ limit: 200, offset: 0 })
  });

  useEffect(() => {
    if (!productsQuery.data?.items.length) return;
    if (!selectedProductId) {
      setSelectedProductId(productsQuery.data.items[0].id);
    }
  }, [productsQuery.data, selectedProductId]);

  const variantsQuery = useQuery({
    queryKey: ["products", "variants", selectedProductId],
    queryFn: () => productService.listVariants(selectedProductId, { limit: 200, offset: 0 }),
    enabled: Boolean(selectedProductId)
  });

  useEffect(() => {
    const firstVariant = variantsQuery.data?.items[0];
    if (firstVariant && !selectedVariantId) {
      setSelectedVariantId(firstVariant.id);
      setLedgerVariantFilter(firstVariant.id);
    }
    if (!variantsQuery.data?.items.length) {
      setSelectedVariantId("");
      setLedgerVariantFilter("");
    }
  }, [variantsQuery.data, selectedVariantId]);

  useEffect(() => {
    setLedgerPage(1);
  }, [ledgerVariantFilter]);

  const ledgerQuery = useQuery({
    queryKey: ["inventory", "ledger", ledgerVariantFilter, ledgerPage, ledgerPageSize],
    queryFn: () =>
      inventoryService.ledger({
        variant_id: ledgerVariantFilter || undefined,
        limit: ledgerPageSize,
        offset: ledgerOffset
      })
  });

  const lowStockQuery = useQuery({
    queryKey: ["inventory", "low-stock", lowStockPage, lowStockPageSize],
    queryFn: () =>
      inventoryService.lowStock({
        limit: lowStockPageSize,
        offset: lowStockOffset
      })
  });

  const productForm = useForm<ProductForm>({
    resolver: zodResolver(productSchema),
    defaultValues: { name: "", category: "" }
  });

  const variantForm = useForm<VariantForm>({
    resolver: zodResolver(variantSchema),
    defaultValues: {
      size: "",
      label: "",
      sku: "",
      reorder_level: 0,
      cost_price: undefined,
      selling_price: undefined
    }
  });

  const stockInForm = useForm<StockInForm>({
    resolver: zodResolver(stockInSchema),
    defaultValues: { qty: 1, unit_cost: undefined }
  });

  const adjustForm = useForm<AdjustForm>({
    resolver: zodResolver(adjustSchema),
    defaultValues: { qty_delta: 1, reason: "", note: "", unit_cost: undefined }
  });

  const createProductMutation = useMutation({
    mutationFn: productService.create,
    onSuccess: () => {
      showToast({ title: "Product added", variant: "success" });
      productForm.reset({ name: "", category: "" });
      queryClient.invalidateQueries({ queryKey: ["products"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not add product",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createVariantMutation = useMutation({
    mutationFn: (values: VariantForm) => {
      if (!selectedProductId) {
        throw new Error("Select a product first");
      }
      return productService.createVariant(selectedProductId, {
        size: values.size,
        label: values.label?.trim() || undefined,
        sku: values.sku?.trim() || undefined,
        reorder_level: values.reorder_level,
        cost_price: normalizeOptionalNumber(values.cost_price),
        selling_price: normalizeOptionalNumber(values.selling_price)
      });
    },
    onSuccess: () => {
      showToast({ title: "Variant added", variant: "success" });
      variantForm.reset({
        size: "",
        label: "",
        sku: "",
        reorder_level: 0,
        cost_price: undefined,
        selling_price: undefined
      });
      queryClient.invalidateQueries({ queryKey: ["products", "variants", selectedProductId] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not add variant",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const stockInMutation = useMutation({
    mutationFn: (values: StockInForm) => {
      if (!selectedVariantId) {
        throw new Error("Select a variant first");
      }
      return inventoryService.stockIn({
        variant_id: selectedVariantId,
        qty: values.qty,
        unit_cost: normalizeOptionalNumber(values.unit_cost)
      });
    },
    onSuccess: () => {
      showToast({ title: "Stock updated", variant: "success" });
      stockInForm.reset({ qty: 1, unit_cost: undefined });
      queryClient.invalidateQueries({ queryKey: ["products", "variants", selectedProductId] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Stock update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const adjustMutation = useMutation({
    mutationFn: (values: AdjustForm) => {
      if (!selectedVariantId) {
        throw new Error("Select a variant first");
      }
      return inventoryService.adjust({
        variant_id: selectedVariantId,
        qty_delta: values.qty_delta,
        reason: values.reason,
        note: values.note?.trim() || undefined,
        unit_cost: normalizeOptionalNumber(values.unit_cost)
      });
    },
    onSuccess: () => {
      showToast({ title: "Adjustment saved", variant: "success" });
      adjustForm.reset({ qty_delta: 1, reason: "", note: "", unit_cost: undefined });
      queryClient.invalidateQueries({ queryKey: ["products", "variants", selectedProductId] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Adjustment failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const selectedProductName = useMemo(() => {
    return productsQuery.data?.items.find((item) => item.id === selectedProductId)?.name ?? "-";
  }, [productsQuery.data, selectedProductId]);

  if (productsQuery.isLoading) {
    return <LoadingState label="Loading inventory workspace..." />;
  }

  if (productsQuery.isError || variantsQuery.isError || ledgerQuery.isError || lowStockQuery.isError) {
    return (
      <ErrorState
        message="Failed to load inventory data."
        onRetry={() => {
          productsQuery.refetch();
          variantsQuery.refetch();
          ledgerQuery.refetch();
          lowStockQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Create Product</h3>
          <form
            className="mt-4 grid gap-3"
            onSubmit={productForm.handleSubmit((values) =>
              createProductMutation.mutate({
                name: values.name,
                category: values.category?.trim() || undefined
              })
            )}
          >
            <Input
              label="Name"
              placeholder="Ankara Fabric"
              {...productForm.register("name")}
              error={productForm.formState.errors.name?.message}
            />
            <Input label="Category" placeholder="Fabrics" {...productForm.register("category")} />
            <Button type="submit" loading={createProductMutation.isPending}>
              Add Product
            </Button>
          </form>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Products</h3>
          {!productsQuery.data?.items.length ? (
            <EmptyState title="No products yet" description="Create your first product to proceed." />
          ) : (
            <div className="mt-4 space-y-2">
              {productsQuery.data.items.map((product) => (
                <button
                  type="button"
                  key={product.id}
                  className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                    selectedProductId === product.id
                      ? "border-surface-600 bg-surface-100"
                      : "border-surface-100 hover:border-surface-300"
                  }`}
                  onClick={() => {
                    setSelectedProductId(product.id);
                    setSelectedVariantId("");
                    setLedgerVariantFilter("");
                  }}
                >
                  <p className="font-semibold text-surface-700">{product.name}</p>
                  <p className="text-xs text-surface-500">{product.category || "Uncategorized"}</p>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Create Variant</h3>
          <p className="mt-1 text-sm text-surface-500">Current product: {selectedProductName}</p>
          <form
            className="mt-4 grid gap-3"
            onSubmit={variantForm.handleSubmit((values) => createVariantMutation.mutate(values))}
          >
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Size"
                placeholder="6x6"
                {...variantForm.register("size")}
                error={variantForm.formState.errors.size?.message}
              />
              <Input label="Label" placeholder="Plain" {...variantForm.register("label")} />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="SKU" placeholder="ANK-6X6-PLN" {...variantForm.register("sku")} />
              <Input
                label="Reorder Level"
                type="number"
                {...variantForm.register("reorder_level")}
                error={variantForm.formState.errors.reorder_level?.message}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Cost Price" type="number" step="0.01" {...variantForm.register("cost_price")} />
              <Input
                label="Selling Price"
                type="number"
                step="0.01"
                {...variantForm.register("selling_price")}
              />
            </div>
            <Button
              type="submit"
              loading={createVariantMutation.isPending}
              disabled={!selectedProductId}
            >
              Add Variant
            </Button>
          </form>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Variants</h3>
          {!variantsQuery.data?.items.length ? (
            <EmptyState title="No variants yet" description="Create a variant for this product." />
          ) : (
            <div className="mt-4 space-y-2">
              <div className="space-y-2 sm:hidden">
                {variantsQuery.data.items.map((variant) => (
                  <button
                    type="button"
                    key={variant.id}
                    className={`w-full rounded-xl border p-3 text-left transition ${
                      selectedVariantId === variant.id
                        ? "border-surface-500 bg-surface-50"
                        : "border-surface-100"
                    }`}
                    onClick={() => {
                      setSelectedVariantId(variant.id);
                      setLedgerVariantFilter(variant.id);
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-surface-700">
                        {variant.size} {variant.label ? `- ${variant.label}` : ""}
                      </p>
                      {variant.stock <= variant.reorder_level ? (
                        <Badge variant="negative">{variant.stock}</Badge>
                      ) : (
                        <Badge variant="positive">{variant.stock}</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-surface-500">SKU: {variant.sku || "-"}</p>
                    <p className="mt-1 text-xs text-surface-500">
                      Price: {variant.selling_price ? formatCurrency(variant.selling_price) : "-"}
                    </p>
                  </button>
                ))}
              </div>
              <div className="hidden overflow-x-auto sm:block">
                <table className="min-w-full divide-y divide-surface-100 text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                      <th className="px-2 py-2">Variant</th>
                      <th className="px-2 py-2">SKU</th>
                      <th className="px-2 py-2">Stock</th>
                      <th className="px-2 py-2">Price</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {variantsQuery.data.items.map((variant) => (
                      <tr
                        key={variant.id}
                        className={`cursor-pointer transition ${
                          selectedVariantId === variant.id ? "bg-surface-50" : ""
                        }`}
                        onClick={() => {
                          setSelectedVariantId(variant.id);
                          setLedgerVariantFilter(variant.id);
                        }}
                      >
                        <td className="px-2 py-2">
                          <p className="font-semibold text-surface-700">{variant.size}</p>
                          <p className="text-xs text-surface-500">{variant.label || "-"}</p>
                        </td>
                        <td className="px-2 py-2 text-surface-600">{variant.sku || "-"}</td>
                        <td className="px-2 py-2">
                          {variant.stock <= variant.reorder_level ? (
                            <Badge variant="negative">{variant.stock}</Badge>
                          ) : (
                            <Badge variant="positive">{variant.stock}</Badge>
                          )}
                        </td>
                        <td className="px-2 py-2 text-surface-600">
                          {variant.selling_price ? formatCurrency(variant.selling_price) : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Stock-In</h3>
          <p className="mt-1 text-sm text-surface-500">Selected variant: {selectedVariantId || "-"}</p>
          <form
            className="mt-4 grid gap-3"
            onSubmit={stockInForm.handleSubmit((values) => stockInMutation.mutate(values))}
          >
            <Input
              label="Quantity"
              type="number"
              {...stockInForm.register("qty")}
              error={stockInForm.formState.errors.qty?.message}
            />
            <Input label="Unit Cost (optional)" type="number" step="0.01" {...stockInForm.register("unit_cost")} />
            <Button type="submit" loading={stockInMutation.isPending} disabled={!selectedVariantId}>
              Add Stock
            </Button>
          </form>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Manual Adjustment</h3>
          <p className="mt-1 text-sm text-surface-500">
            Use positive value to add, negative to remove.
          </p>
          <form
            className="mt-4 grid gap-3"
            onSubmit={adjustForm.handleSubmit((values) => adjustMutation.mutate(values))}
          >
            <Input
              label="Quantity Delta"
              type="number"
              {...adjustForm.register("qty_delta")}
              error={adjustForm.formState.errors.qty_delta?.message}
            />
            <Input
              label="Reason"
              placeholder="damaged_stock"
              {...adjustForm.register("reason")}
              error={adjustForm.formState.errors.reason?.message}
            />
            <Textarea label="Note (optional)" rows={3} {...adjustForm.register("note")} />
            <Input label="Unit Cost (optional)" type="number" step="0.01" {...adjustForm.register("unit_cost")} />
            <Button type="submit" loading={adjustMutation.isPending} disabled={!selectedVariantId}>
              Save Adjustment
            </Button>
          </form>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="font-heading text-lg font-bold">Low Stock Alerts</h3>
            <Badge variant="negative">{lowStockQuery.data?.pagination.total ?? 0}</Badge>
          </div>
          {!lowStockQuery.data?.items.length ? (
            <EmptyState title="No low stock alerts" description="All variants are above threshold." />
        ) : (
            <div className="space-y-2">
              {lowStockQuery.data.items.map((item) => (
                <div key={item.variant_id} className="rounded-xl border border-red-200 bg-red-50 p-3">
                  <div className="flex items-center justify-between">
                    <p className="font-semibold text-red-700">{item.product_name}</p>
                    <Badge variant="negative">Stock: {item.stock}</Badge>
                  </div>
                  <p className="text-sm text-red-600">
                    {item.size} {item.label ? `- ${item.label}` : ""} | Reorder at {item.reorder_level}
                  </p>
                </div>
              ))}
              <PaginationControls
                pagination={lowStockQuery.data.pagination}
                pageSize={lowStockPageSize}
                onPageSizeChange={(size) => {
                  setLowStockPageSize(size);
                  setLowStockPage(1);
                }}
                onPrev={() => setLowStockPage((value) => Math.max(1, value - 1))}
                onNext={() => {
                  if (lowStockQuery.data.pagination.has_next) {
                    setLowStockPage((value) => value + 1);
                  }
                }}
              />
            </div>
          )}
        </Card>

        <Card>
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <h3 className="font-heading text-lg font-bold">Inventory Ledger</h3>
            <Select
              label="Filter Variant"
              value={ledgerVariantFilter}
              onChange={(event) => setLedgerVariantFilter(event.target.value)}
            >
              <option value="">All variants</option>
              {(variantsQuery.data?.items ?? []).map((variant) => (
                <option key={variant.id} value={variant.id}>
                  {variant.size} {variant.label ? `- ${variant.label}` : ""}
                </option>
              ))}
            </Select>
          </div>
          {!ledgerQuery.data?.items.length ? (
            <EmptyState title="No ledger entries" />
          ) : (
            <div className="space-y-2">
              <div className="space-y-2 sm:hidden">
                {ledgerQuery.data.items.map((entry) => (
                  <article key={entry.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold capitalize text-surface-700">
                        {entry.reason.replace("_", " ")}
                      </p>
                      <p className={`text-sm font-semibold ${entry.qty_delta >= 0 ? "text-mint-700" : "text-red-600"}`}>
                        {entry.qty_delta > 0 ? `+${entry.qty_delta}` : entry.qty_delta}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">{entry.note || "-"}</p>
                    <div className="mt-1 flex items-center justify-between text-xs text-surface-500">
                      <span>{entry.unit_cost ? formatCurrency(entry.unit_cost) : "-"}</span>
                      <span>{formatDateTime(entry.created_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
              <div className="hidden max-h-[350px] overflow-y-auto sm:block">
                <table className="min-w-full divide-y divide-surface-100 text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                      <th className="px-2 py-2">Reason</th>
                      <th className="px-2 py-2">Qty</th>
                      <th className="px-2 py-2">Cost</th>
                      <th className="px-2 py-2">Date</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-surface-50">
                    {ledgerQuery.data.items.map((entry) => (
                      <tr key={entry.id}>
                        <td className="px-2 py-2 text-surface-700">
                          <p className="font-semibold capitalize">{entry.reason.replace("_", " ")}</p>
                          <p className="text-xs text-surface-500">{entry.note || "-"}</p>
                        </td>
                        <td className={`px-2 py-2 font-semibold ${entry.qty_delta >= 0 ? "text-mint-700" : "text-red-600"}`}>
                          {entry.qty_delta > 0 ? `+${entry.qty_delta}` : entry.qty_delta}
                        </td>
                        <td className="px-2 py-2 text-surface-500">
                          {entry.unit_cost ? formatCurrency(entry.unit_cost) : "-"}
                        </td>
                        <td className="px-2 py-2 text-surface-500">{formatDateTime(entry.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <PaginationControls
                pagination={ledgerQuery.data.pagination}
                pageSize={ledgerPageSize}
                onPageSizeChange={(size) => {
                  setLedgerPageSize(size);
                  setLedgerPage(1);
                }}
                onPrev={() => setLedgerPage((value) => Math.max(1, value - 1))}
                onNext={() => {
                  if (ledgerQuery.data.pagination.has_next) {
                    setLedgerPage((value) => value + 1);
                  }
                }}
              />
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
