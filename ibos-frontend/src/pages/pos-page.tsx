import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Printer, Radio, RefreshCcw, UploadCloud } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { posService, productService } from "../api/services";
import type { PosOfflineOrderIn } from "../api/types";
import { EmptyState } from "../components/state/empty-state";
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
import { printReceiptText } from "../lib/pos-devices";

const OFFLINE_QUEUE_KEY = "monidesk_pos_offline_queue_v1";

function readQueue(): PosOfflineOrderIn[] {
  try {
    const raw = localStorage.getItem(OFFLINE_QUEUE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as PosOfflineOrderIn[];
  } catch {
    return [];
  }
}

function saveQueue(items: PosOfflineOrderIn[]) {
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(items));
}

export function PosPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [selectedProductId, setSelectedProductId] = useState("");
  const [selectedVariantId, setSelectedVariantId] = useState("");
  const [qty, setQty] = useState(1);
  const [unitPrice, setUnitPrice] = useState(1);
  const [paymentMethod, setPaymentMethod] = useState<"cash" | "transfer" | "pos">("cash");
  const [channel, setChannel] = useState<"walk-in" | "whatsapp" | "instagram">("walk-in");
  const [openingCash, setOpeningCash] = useState("0");
  const [closingCash, setClosingCash] = useState("0");
  const [queue, setQueue] = useState<PosOfflineOrderIn[]>([]);

  useEffect(() => {
    setQueue(readQueue());
  }, []);

  const productsQuery = useQuery({
    queryKey: ["pos", "products"],
    queryFn: () => productService.list({ limit: 200, offset: 0 })
  });

  useEffect(() => {
    if (!productsQuery.data?.items.length) return;
    if (!selectedProductId) {
      setSelectedProductId(productsQuery.data.items[0].id);
    }
  }, [productsQuery.data, selectedProductId]);

  const variantsQuery = useQuery({
    queryKey: ["pos", "variants", selectedProductId],
    queryFn: () => productService.listVariants(selectedProductId, { limit: 300, offset: 0 }),
    enabled: Boolean(selectedProductId)
  });

  useEffect(() => {
    const first = variantsQuery.data?.items[0];
    if (!first) return;
    if (!selectedVariantId) {
      setSelectedVariantId(first.id);
      setUnitPrice(first.selling_price && first.selling_price > 0 ? first.selling_price : 1);
    }
  }, [variantsQuery.data, selectedVariantId]);

  const currentShiftQuery = useQuery({
    queryKey: ["pos", "current-shift"],
    queryFn: () => posService.currentShift()
  });

  const openShiftMutation = useMutation({
    mutationFn: () =>
      posService.openShift({
        opening_cash: Number(openingCash) || 0
      }),
    onSuccess: () => {
      showToast({ title: "Shift opened", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["pos"] });
    },
    onError: (error) => {
      showToast({
        title: "Open shift failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const closeShiftMutation = useMutation({
    mutationFn: () => {
      const shiftId = currentShiftQuery.data?.shift?.id;
      if (!shiftId) throw new Error("No open shift");
      return posService.closeShift(shiftId, {
        closing_cash: Number(closingCash) || 0
      });
    },
    onSuccess: (result) => {
      showToast({
        title: "Shift closed",
        description: `Difference: ${formatCurrency(result.cash_difference ?? 0)}`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["pos"] });
    },
    onError: (error) => {
      showToast({
        title: "Close shift failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const syncMutation = useMutation({
    mutationFn: () =>
      posService.syncOfflineOrders({
        conflict_policy: "adjust_to_available",
        orders: queue
      }),
    onSuccess: (result) => {
      const unresolved = queue.filter((item) => {
        const matched = result.results.find((row) => row.client_event_id === item.client_event_id);
        return !matched || matched.status === "conflict";
      });
      setQueue(unresolved);
      saveQueue(unresolved);
      showToast({
        title: "Offline queue synced",
        description: `${result.created} created, ${result.conflicted} conflicted, ${result.duplicate} duplicate.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["inventory"] });
    },
    onError: (error) => {
      showToast({
        title: "Sync failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const cartTotal = useMemo(() => (Number(qty) || 0) * (Number(unitPrice) || 0), [qty, unitPrice]);

  function queueOrder() {
    if (!selectedVariantId || qty <= 0 || unitPrice <= 0) {
      showToast({
        title: "Invalid order",
        description: "Select variant and enter valid quantity/price.",
        variant: "error"
      });
      return;
    }
    const order: PosOfflineOrderIn = {
      client_event_id: `pos-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
      payment_method: paymentMethod,
      channel,
      items: [{ variant_id: selectedVariantId, qty, unit_price: unitPrice }],
      created_at: new Date().toISOString()
    };
    const nextQueue = [order, ...queue];
    setQueue(nextQueue);
    saveQueue(nextQueue);
    showToast({
      title: "Order queued offline",
      description: "Sync queue when network is available.",
      variant: "success"
    });
  }

  const posPanelLoading =
    productsQuery.isLoading || (Boolean(selectedProductId) && variantsQuery.isLoading);
  const posPanelError = productsQuery.isError || variantsQuery.isError;
  const posPanelErrorMessage = posPanelError
    ? getApiErrorMessage(productsQuery.error ?? variantsQuery.error)
    : "";
  const shiftPanelLoading = currentShiftQuery.isLoading;
  const shiftPanelError = currentShiftQuery.isError;
  const shiftPanelErrorMessage = shiftPanelError ? getApiErrorMessage(currentShiftQuery.error) : "";

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between">
          <h3 className="font-heading text-lg font-bold">Mobile POS Console</h3>
          <Badge variant="info">Offline Ready</Badge>
        </div>
        <p className="mt-1 text-sm text-surface-500">
          Optimized for touch devices with local queueing and one-tap sync.
        </p>
        {posPanelLoading ? (
          <div className="mt-4">
            <LoadingState label="Loading POS catalog..." />
          </div>
        ) : posPanelError ? (
          <div className="mt-4">
            <ErrorState
              message={`Failed to load POS catalog. ${posPanelErrorMessage}`}
              onRetry={() => {
                productsQuery.refetch();
                variantsQuery.refetch();
              }}
            />
          </div>
        ) : (
          <>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Select label="Product" value={selectedProductId} onChange={(event) => setSelectedProductId(event.target.value)}>
                {(productsQuery.data?.items ?? []).map((product) => (
                  <option key={product.id} value={product.id}>
                    {product.name}
                  </option>
                ))}
              </Select>
              <Select
                label="Variant"
                value={selectedVariantId}
                onChange={(event) => {
                  setSelectedVariantId(event.target.value);
                  const found = variantsQuery.data?.items.find((item) => item.id === event.target.value);
                  if (found?.selling_price && found.selling_price > 0) {
                    setUnitPrice(found.selling_price);
                  }
                }}
              >
                {(variantsQuery.data?.items ?? []).map((variant) => (
                  <option key={variant.id} value={variant.id}>
                    {variant.size}
                    {variant.label ? ` - ${variant.label}` : ""}
                  </option>
                ))}
              </Select>
              <Input label="Qty" type="number" value={String(qty)} onChange={(event) => setQty(Number(event.target.value) || 0)} />
              <Input
                label="Unit Price"
                type="number"
                step="0.01"
                value={String(unitPrice)}
                onChange={(event) => setUnitPrice(Number(event.target.value) || 0)}
              />
              <Select label="Payment" value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value as "cash" | "transfer" | "pos")}>
                <option value="cash">Cash</option>
                <option value="transfer">Transfer</option>
                <option value="pos">POS</option>
              </Select>
              <Select label="Channel" value={channel} onChange={(event) => setChannel(event.target.value as "walk-in" | "whatsapp" | "instagram")}>
                <option value="walk-in">Walk-in</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="instagram">Instagram</option>
              </Select>
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <Badge variant="positive">Order Total: {formatCurrency(cartTotal)}</Badge>
              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="ghost" onClick={() => printReceiptText(`MoniDesk POS Receipt\nTotal: ${cartTotal}`)}>
                  <Printer className="h-4 w-4" />
                  Print Hook
                </Button>
                <Button type="button" variant="secondary" onClick={queueOrder}>
                  <Radio className="h-4 w-4" />
                  Queue Offline
                </Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Shift Reconciliation</h3>
          {shiftPanelLoading ? (
            <div className="mt-3">
              <LoadingState label="Loading shift status..." />
            </div>
          ) : shiftPanelError ? (
            <div className="mt-3">
              <ErrorState
                message={`Failed to load shift status. ${shiftPanelErrorMessage}`}
                onRetry={() => currentShiftQuery.refetch()}
              />
            </div>
          ) : !currentShiftQuery.data?.shift ? (
            <div className="mt-3 space-y-3">
              <Input label="Opening Cash" type="number" value={openingCash} onChange={(event) => setOpeningCash(event.target.value)} />
              <Button type="button" onClick={() => openShiftMutation.mutate()} loading={openShiftMutation.isPending}>
                Open Shift
              </Button>
            </div>
          ) : (
            <div className="mt-3 space-y-3">
              <p className="text-sm text-surface-600">
                Opened by {currentShiftQuery.data.shift.opened_by_user_id.slice(0, 8)}...
              </p>
              <Badge variant="info">Opening Cash: {formatCurrency(currentShiftQuery.data.shift.opening_cash)}</Badge>
              <Input label="Closing Cash" type="number" value={closingCash} onChange={(event) => setClosingCash(event.target.value)} />
              <Button type="button" variant="secondary" onClick={() => closeShiftMutation.mutate()} loading={closeShiftMutation.isPending}>
                Close Shift
              </Button>
            </div>
          )}
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <h3 className="font-heading text-lg font-bold">Offline Queue</h3>
            <Badge variant="neutral">{queue.length} queued</Badge>
          </div>
          {queue.length === 0 ? (
            <div className="mt-3">
              <EmptyState title="Queue is empty" description="Add offline orders from the POS panel above." />
            </div>
          ) : (
            <div className="mt-3 space-y-2">
              {queue.slice(0, 8).map((item) => (
                <div key={item.client_event_id} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
                  <p className="text-xs font-semibold text-surface-700">{item.client_event_id}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    {item.channel} / {item.payment_method} / {item.items[0].qty} x {formatCurrency(item.items[0].unit_price)}
                  </p>
                </div>
              ))}
              <div className="flex gap-2">
                <Button type="button" variant="ghost" onClick={() => { setQueue([]); saveQueue([]); }}>
                  <RefreshCcw className="h-4 w-4" />
                  Clear
                </Button>
                <Button type="button" variant="secondary" onClick={() => syncMutation.mutate()} loading={syncMutation.isPending}>
                  <UploadCloud className="h-4 w-4" />
                  Sync Queue
                </Button>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
