import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { locationService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

function normalizeOptional(value: string) {
  const cleaned = value.trim();
  return cleaned || undefined;
}

export function LocationsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [includeInactive, setIncludeInactive] = useState(false);
  const [locationName, setLocationName] = useState("");
  const [locationCode, setLocationCode] = useState("");
  const [selectedLocationId, setSelectedLocationId] = useState("");
  const [stockVariantId, setStockVariantId] = useState("");
  const [stockInQty, setStockInQty] = useState(1);
  const [stockInNote, setStockInNote] = useState("");
  const [adjustQtyDelta, setAdjustQtyDelta] = useState(-1);
  const [adjustReason, setAdjustReason] = useState("correction");
  const [adjustNote, setAdjustNote] = useState("");
  const [stockResult, setStockResult] = useState<number | null>(null);
  const [overviewVariantId, setOverviewVariantId] = useState("");
  const [overviewRows, setOverviewRows] = useState<Array<{ location_id: string; stock: number }>>([]);
  const [transferFromLocationId, setTransferFromLocationId] = useState("");
  const [transferToLocationId, setTransferToLocationId] = useState("");
  const [transferVariantId, setTransferVariantId] = useState("");
  const [transferQty, setTransferQty] = useState(1);
  const [transferNote, setTransferNote] = useState("");
  const [allocationOrderId, setAllocationOrderId] = useState("");
  const [allocationLocationId, setAllocationLocationId] = useState("");
  const [lowStockLocationFilter, setLowStockLocationFilter] = useState("");
  const [lowStockThreshold, setLowStockThreshold] = useState(0);
  const [transferPage, setTransferPage] = useState(1);
  const [transferPageSize, setTransferPageSize] = useState(20);
  const [lowStockPage, setLowStockPage] = useState(1);
  const [lowStockPageSize, setLowStockPageSize] = useState(20);

  const transferOffset = (transferPage - 1) * transferPageSize;
  const lowStockOffset = (lowStockPage - 1) * lowStockPageSize;

  useEffect(() => {
    setTransferPage(1);
  }, []);

  useEffect(() => {
    setLowStockPage(1);
  }, [lowStockLocationFilter, lowStockThreshold]);

  const locationsQuery = useQuery({
    queryKey: ["locations", "list", includeInactive],
    queryFn: () =>
      locationService.list({
        include_inactive: includeInactive,
        limit: 200,
        offset: 0
      })
  });

  useEffect(() => {
    if (!locationsQuery.data?.items.length) return;
    const firstLocationId = locationsQuery.data.items[0].id;
    if (!selectedLocationId) setSelectedLocationId(firstLocationId);
    if (!transferFromLocationId) setTransferFromLocationId(firstLocationId);
    if (!allocationLocationId) setAllocationLocationId(firstLocationId);
    if (!transferToLocationId && locationsQuery.data.items[1]) {
      setTransferToLocationId(locationsQuery.data.items[1].id);
    }
  }, [
    allocationLocationId,
    locationsQuery.data,
    selectedLocationId,
    transferFromLocationId,
    transferToLocationId
  ]);

  const transfersQuery = useQuery({
    queryKey: ["locations", "transfers", transferPage, transferPageSize],
    queryFn: () =>
      locationService.listTransfers({
        limit: transferPageSize,
        offset: transferOffset
      })
  });

  const lowStockQuery = useQuery({
    queryKey: [
      "locations",
      "low-stock",
      lowStockLocationFilter,
      lowStockThreshold,
      lowStockPage,
      lowStockPageSize
    ],
    queryFn: () =>
      locationService.lowStock({
        location_id: lowStockLocationFilter || undefined,
        threshold: lowStockThreshold,
        limit: lowStockPageSize,
        offset: lowStockOffset
      })
  });

  const createLocationMutation = useMutation({
    mutationFn: () =>
      locationService.create({
        name: locationName.trim(),
        code: locationCode.trim()
      }),
    onSuccess: () => {
      showToast({ title: "Location created", variant: "success" });
      setLocationName("");
      setLocationCode("");
      queryClient.invalidateQueries({ queryKey: ["locations"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create location",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const updateLocationMutation = useMutation({
    mutationFn: ({ locationId, isActive }: { locationId: string; isActive: boolean }) =>
      locationService.update(locationId, { is_active: isActive }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["locations"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    }
  });

  const stockInMutation = useMutation({
    mutationFn: () =>
      locationService.stockIn(selectedLocationId, {
        variant_id: stockVariantId.trim(),
        qty: Number(stockInQty || 0),
        note: normalizeOptional(stockInNote)
      }),
    onSuccess: (result) => {
      setStockResult(result.stock);
      showToast({ title: "Stock added", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["locations", "low-stock"] });
    },
    onError: (error) => {
      showToast({
        title: "Stock-in failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const adjustMutation = useMutation({
    mutationFn: () =>
      locationService.adjust(selectedLocationId, {
        variant_id: stockVariantId.trim(),
        qty_delta: Number(adjustQtyDelta || 0),
        reason: adjustReason.trim(),
        note: normalizeOptional(adjustNote)
      }),
    onSuccess: (result) => {
      setStockResult(result.stock);
      showToast({ title: "Stock adjusted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["locations", "low-stock"] });
    },
    onError: (error) => {
      showToast({
        title: "Stock adjustment failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const readStockMutation = useMutation({
    mutationFn: () => locationService.stock(selectedLocationId, stockVariantId.trim()),
    onSuccess: (result) => {
      setStockResult(result.stock);
    },
    onError: (error) => {
      showToast({
        title: "Could not fetch stock",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const stockOverviewMutation = useMutation({
    mutationFn: () => locationService.stockOverview(overviewVariantId.trim()),
    onSuccess: (result) => {
      setOverviewRows(result.by_location.map((row) => ({ location_id: row.location_id, stock: row.stock })));
    },
    onError: (error) => {
      showToast({
        title: "Could not load stock overview",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createTransferMutation = useMutation({
    mutationFn: () =>
      locationService.createTransfer({
        from_location_id: transferFromLocationId,
        to_location_id: transferToLocationId,
        note: normalizeOptional(transferNote),
        items: [
          {
            variant_id: transferVariantId.trim(),
            qty: Number(transferQty || 0)
          }
        ]
      }),
    onSuccess: () => {
      showToast({
        title: "Transfer completed",
        description: "Source and destination ledgers were updated.",
        variant: "success"
      });
      setTransferVariantId("");
      setTransferQty(1);
      setTransferNote("");
      queryClient.invalidateQueries({ queryKey: ["locations", "transfers"] });
      queryClient.invalidateQueries({ queryKey: ["locations", "low-stock"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Transfer failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const allocateMutation = useMutation({
    mutationFn: () =>
      locationService.allocateOrder({
        order_id: allocationOrderId.trim(),
        location_id: allocationLocationId
      }),
    onSuccess: () => {
      showToast({
        title: "Order allocated",
        description: "Order items have been reserved at the selected location.",
        variant: "success"
      });
      setAllocationOrderId("");
      queryClient.invalidateQueries({ queryKey: ["locations", "low-stock"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Order allocation failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (locationsQuery.isLoading || transfersQuery.isLoading || lowStockQuery.isLoading) {
    return <LoadingState label="Loading location operations..." />;
  }

  if (
    locationsQuery.isError ||
    transfersQuery.isError ||
    lowStockQuery.isError ||
    !locationsQuery.data ||
    !transfersQuery.data ||
    !lowStockQuery.data
  ) {
    return (
      <ErrorState
        message="Unable to load location operations."
        onRetry={() => {
          locationsQuery.refetch();
          transfersQuery.refetch();
          lowStockQuery.refetch();
        }}
      />
    );
  }

  const locations = locationsQuery.data.items;

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#132f45_0%,#1f4b66_50%,#2a5b73_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Multi-Location Inventory Operations</h3>
        <p className="mt-1 text-sm text-white/80">
          Manage locations, move stock across branches, and allocate orders from explicit locations.
        </p>
      </Card>

      <Card>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-heading text-lg font-bold text-surface-800">Location Setup</h3>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-surface-700">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            Include inactive
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <Input label="Location Name" value={locationName} onChange={(event) => setLocationName(event.target.value)} />
          <Input label="Location Code" value={locationCode} onChange={(event) => setLocationCode(event.target.value)} />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={createLocationMutation.isPending}
              onClick={() => createLocationMutation.mutate()}
              disabled={!locationName.trim() || !locationCode.trim()}
            >
              Create Location
            </Button>
          </div>
        </div>

        {!locations.length ? (
          <div className="mt-4">
            <EmptyState title="No locations yet" description="Create your first location to start allocating stock." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {locations.map((location) => (
              <article key={location.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">
                      {location.name} <span className="text-surface-400">({location.code})</span>
                    </p>
                    <p className="text-xs text-surface-500">Created: {formatDateTime(location.created_at)}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={location.is_active ? "positive" : "negative"}>
                      {location.is_active ? "active" : "inactive"}
                    </Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={
                        updateLocationMutation.isPending &&
                        updateLocationMutation.variables?.locationId === location.id
                      }
                      onClick={() =>
                        updateLocationMutation.mutate({
                          locationId: location.id,
                          isActive: !location.is_active
                        })
                      }
                    >
                      {location.is_active ? "Deactivate" : "Activate"}
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Stock by Location</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Select
            label="Location"
            value={selectedLocationId}
            onChange={(event) => setSelectedLocationId(event.target.value)}
          >
            <option value="">Select location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </Select>
          <Input
            label="Variant ID"
            value={stockVariantId}
            onChange={(event) => setStockVariantId(event.target.value)}
            placeholder="variant-id"
          />
          <Input
            label="Stock In Qty"
            type="number"
            value={stockInQty}
            onChange={(event) => setStockInQty(Number(event.target.value || 0))}
          />
          <Input label="Stock In Note" value={stockInNote} onChange={(event) => setStockInNote(event.target.value)} />
          <Input
            label="Adjust Qty Delta"
            type="number"
            value={adjustQtyDelta}
            onChange={(event) => setAdjustQtyDelta(Number(event.target.value || 0))}
          />
          <Input label="Adjust Reason" value={adjustReason} onChange={(event) => setAdjustReason(event.target.value)} />
          <Input label="Adjust Note" value={adjustNote} onChange={(event) => setAdjustNote(event.target.value)} />
          <div className="mt-7">
            <Badge variant={stockResult === null ? "neutral" : stockResult > 0 ? "positive" : "negative"}>
              Current stock: {stockResult ?? "-"}
            </Badge>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            loading={readStockMutation.isPending}
            disabled={!selectedLocationId || !stockVariantId.trim()}
            onClick={() => readStockMutation.mutate()}
          >
            Get Stock
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={stockInMutation.isPending}
            disabled={!selectedLocationId || !stockVariantId.trim() || stockInQty <= 0}
            onClick={() => stockInMutation.mutate()}
          >
            Stock In
          </Button>
          <Button
            type="button"
            loading={adjustMutation.isPending}
            disabled={!selectedLocationId || !stockVariantId.trim() || adjustQtyDelta === 0}
            onClick={() => adjustMutation.mutate()}
          >
            Adjust Stock
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Variant Stock Overview</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Input
            label="Variant ID"
            value={overviewVariantId}
            onChange={(event) => setOverviewVariantId(event.target.value)}
          />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={stockOverviewMutation.isPending}
              disabled={!overviewVariantId.trim()}
              onClick={() => stockOverviewMutation.mutate()}
            >
              Load Overview
            </Button>
          </div>
        </div>
        {overviewRows.length ? (
          <div className="mt-4 space-y-2">
            {overviewRows.map((row) => (
              <div key={row.location_id} className="rounded-xl border border-surface-100 bg-surface-50 p-3 text-sm">
                <p className="font-semibold text-surface-700">Location: {row.location_id}</p>
                <p className="text-surface-500">Stock: {row.stock}</p>
              </div>
            ))}
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Inter-Location Transfer</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Select
            label="From Location"
            value={transferFromLocationId}
            onChange={(event) => setTransferFromLocationId(event.target.value)}
          >
            <option value="">Select</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </Select>
          <Select
            label="To Location"
            value={transferToLocationId}
            onChange={(event) => setTransferToLocationId(event.target.value)}
          >
            <option value="">Select</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </Select>
          <Input
            label="Variant ID"
            value={transferVariantId}
            onChange={(event) => setTransferVariantId(event.target.value)}
          />
          <Input
            label="Qty"
            type="number"
            value={transferQty}
            onChange={(event) => setTransferQty(Number(event.target.value || 0))}
          />
          <div className="md:col-span-3">
            <Input label="Note" value={transferNote} onChange={(event) => setTransferNote(event.target.value)} />
          </div>
          <div className="md:pt-7">
            <Button
              type="button"
              loading={createTransferMutation.isPending}
              disabled={
                !transferFromLocationId ||
                !transferToLocationId ||
                !transferVariantId.trim() ||
                transferQty <= 0
              }
              onClick={() => createTransferMutation.mutate()}
            >
              Transfer Stock
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Order Allocation</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Input
            label="Order ID"
            value={allocationOrderId}
            onChange={(event) => setAllocationOrderId(event.target.value)}
          />
          <Select
            label="Location"
            value={allocationLocationId}
            onChange={(event) => setAllocationLocationId(event.target.value)}
          >
            <option value="">Select location</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </Select>
          <div className="md:pt-7">
            <Button
              type="button"
              loading={allocateMutation.isPending}
              disabled={!allocationOrderId.trim() || !allocationLocationId}
              onClick={() => allocateMutation.mutate()}
            >
              Allocate Order
            </Button>
          </div>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Transfers Log</h3>
        {!transfersQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No transfers yet" description="Stock transfers will appear here after execution." />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {transfersQuery.data.items.map((transfer) => (
              <article key={transfer.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">
                      {transfer.from_location_id} {"->"} {transfer.to_location_id}
                    </p>
                    <p className="text-xs text-surface-500">
                      {transfer.items.map((item) => `${item.variant_id} x${item.qty}`).join(", ")}
                    </p>
                  </div>
                  <Badge variant={transfer.status === "completed" ? "positive" : "neutral"}>
                    {transfer.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">{formatDateTime(transfer.created_at)}</p>
              </article>
            ))}
            <PaginationControls
              pagination={transfersQuery.data.pagination}
              pageSize={transferPageSize}
              onPageSizeChange={(size) => {
                setTransferPageSize(size);
                setTransferPage(1);
              }}
              onPrev={() => setTransferPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (transfersQuery.data.pagination.has_next) {
                  setTransferPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Low Stock by Location</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Select
            label="Location Filter"
            value={lowStockLocationFilter}
            onChange={(event) => setLowStockLocationFilter(event.target.value)}
          >
            <option value="">All locations</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </Select>
          <Input
            label="Default Threshold"
            type="number"
            value={lowStockThreshold}
            onChange={(event) => setLowStockThreshold(Number(event.target.value || 0))}
          />
          <div className="mt-7">
            <Badge variant="info">{lowStockQuery.data.pagination.total} records</Badge>
          </div>
        </div>

        {!lowStockQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No low stock records" description="Inventory levels are above reorder thresholds." />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {lowStockQuery.data.items.map((item) => (
              <article
                key={`${item.location_id}-${item.variant_id}`}
                className="rounded-xl border border-surface-100 bg-surface-50 p-3"
              >
                <p className="font-semibold text-surface-700">
                  Location {item.location_id} | Variant {item.variant_id}
                </p>
                <p className="text-sm text-surface-500">
                  Stock: {item.stock} | Reorder Level: {item.reorder_level}
                </p>
              </article>
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
    </div>
  );
}
