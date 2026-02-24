import axios from "axios";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { shippingService } from "../api/services";
import type { ShippingQuoteOptionOut } from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDateTime } from "../lib/format";

function normalizeOptional(value: string) {
  const cleaned = value.trim();
  return cleaned || undefined;
}

function prettyJson(value: unknown) {
  return JSON.stringify(value, null, 2);
}

function parseJsonArray<T>(raw: string, fallback: T[]): T[] {
  const parsed = JSON.parse(raw) as unknown;
  return Array.isArray(parsed) ? (parsed as T[]) : fallback;
}

export function ShippingPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [originCountry, setOriginCountry] = useState("NG");
  const [originState, setOriginState] = useState("");
  const [originCity, setOriginCity] = useState("");
  const [originPostalCode, setOriginPostalCode] = useState("");
  const [handlingFee, setHandlingFee] = useState(0);
  const [currency, setCurrency] = useState("USD");
  const [zonesJson, setZonesJson] = useState(
    prettyJson([
      {
        zone_name: "Domestic",
        country: "NG",
        state: "",
        city: "",
        postal_code_prefix: "",
        is_active: true
      }
    ])
  );
  const [rulesJson, setRulesJson] = useState(
    prettyJson([
      {
        provider: "stub_carrier",
        service_code: "standard",
        service_name: "Standard Shipping",
        zone_name: "Domestic",
        base_rate: 0,
        per_kg_rate: 0,
        min_eta_days: 2,
        max_eta_days: 5,
        is_active: true
      }
    ])
  );

  const [quoteSessionToken, setQuoteSessionToken] = useState("");
  const [destinationCountry, setDestinationCountry] = useState("NG");
  const [destinationState, setDestinationState] = useState("");
  const [destinationCity, setDestinationCity] = useState("");
  const [destinationPostalCode, setDestinationPostalCode] = useState("");
  const [totalWeightKg, setTotalWeightKg] = useState(1);

  const [orderId, setOrderId] = useState("");
  const [checkoutSessionId, setCheckoutSessionId] = useState("");
  const [provider, setProvider] = useState("stub_carrier");
  const [serviceCode, setServiceCode] = useState("standard");
  const [serviceName, setServiceName] = useState("Standard Shipping");
  const [shippingCost, setShippingCost] = useState(0);
  const [shipmentCurrency, setShipmentCurrency] = useState("USD");
  const [recipientName, setRecipientName] = useState("");
  const [recipientPhone, setRecipientPhone] = useState("");
  const [addressLine1, setAddressLine1] = useState("");
  const [addressLine2, setAddressLine2] = useState("");
  const [shipmentCity, setShipmentCity] = useState("");
  const [shipmentState, setShipmentState] = useState("");
  const [shipmentCountry, setShipmentCountry] = useState("NG");
  const [shipmentPostalCode, setShipmentPostalCode] = useState("");

  const [orderFilter, setOrderFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [orderFilter, statusFilter]);

  const settingsQuery = useQuery({
    queryKey: ["shipping", "settings"],
    queryFn: shippingService.getSettings,
    retry: false
  });

  const settingsNotConfigured =
    settingsQuery.isError &&
    axios.isAxiosError(settingsQuery.error) &&
    settingsQuery.error.response?.status === 404;

  useEffect(() => {
    if (!settingsQuery.data) return;
    setOriginCountry(settingsQuery.data.default_origin_country);
    setOriginState(settingsQuery.data.default_origin_state ?? "");
    setOriginCity(settingsQuery.data.default_origin_city ?? "");
    setOriginPostalCode(settingsQuery.data.default_origin_postal_code ?? "");
    setHandlingFee(settingsQuery.data.handling_fee);
    setCurrency(settingsQuery.data.currency);
    setZonesJson(prettyJson(settingsQuery.data.zones));
    setRulesJson(prettyJson(settingsQuery.data.service_rules));
  }, [settingsQuery.data]);

  const shipmentsQuery = useQuery({
    queryKey: ["shipping", "shipments", orderFilter, statusFilter, page, pageSize],
    queryFn: () =>
      shippingService.listShipments({
        order_id: orderFilter.trim() || undefined,
        status: statusFilter.trim() || undefined,
        limit: pageSize,
        offset
      })
  });

  const saveSettingsMutation = useMutation({
    mutationFn: () =>
      shippingService.upsertSettings({
        default_origin_country: originCountry.trim().toUpperCase(),
        default_origin_state: normalizeOptional(originState),
        default_origin_city: normalizeOptional(originCity),
        default_origin_postal_code: normalizeOptional(originPostalCode),
        handling_fee: Number(handlingFee || 0),
        currency: currency.trim().toUpperCase(),
        zones: parseJsonArray(zonesJson, []),
        service_rules: parseJsonArray(rulesJson, [])
      }),
    onSuccess: () => {
      showToast({
        title: "Shipping settings saved",
        description: "Shipping zones and service rules have been updated.",
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["shipping", "settings"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not save shipping settings",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const quoteMutation = useMutation({
    mutationFn: () =>
      shippingService.quoteCheckoutRate(quoteSessionToken.trim(), {
        destination_country: destinationCountry.trim().toUpperCase(),
        destination_state: normalizeOptional(destinationState),
        destination_city: normalizeOptional(destinationCity),
        destination_postal_code: normalizeOptional(destinationPostalCode),
        total_weight_kg: Number(totalWeightKg || 1)
      }),
    onError: (error) => {
      showToast({
        title: "Quote failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const selectRateMutation = useMutation({
    mutationFn: (rate: ShippingQuoteOptionOut) =>
      shippingService.selectCheckoutRate(quoteSessionToken.trim(), {
        provider: rate.provider,
        service_code: rate.service_code,
        service_name: rate.service_name,
        zone_name: rate.zone_name,
        amount: rate.amount,
        currency: rate.currency,
        eta_min_days: rate.eta_min_days,
        eta_max_days: rate.eta_max_days
      }),
    onSuccess: () => {
      showToast({ title: "Shipping rate selected", variant: "success" });
    },
    onError: (error) => {
      showToast({
        title: "Could not select rate",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createShipmentMutation = useMutation({
    mutationFn: () =>
      shippingService.createShipment({
        order_id: orderId.trim(),
        checkout_session_id: normalizeOptional(checkoutSessionId),
        provider: provider.trim(),
        service_code: serviceCode.trim(),
        service_name: serviceName.trim(),
        shipping_cost: Number(shippingCost || 0),
        currency: shipmentCurrency.trim().toUpperCase(),
        recipient_name: recipientName.trim(),
        recipient_phone: normalizeOptional(recipientPhone),
        address_line1: addressLine1.trim(),
        address_line2: normalizeOptional(addressLine2),
        city: shipmentCity.trim(),
        state: normalizeOptional(shipmentState),
        country: shipmentCountry.trim().toUpperCase(),
        postal_code: normalizeOptional(shipmentPostalCode)
      }),
    onSuccess: () => {
      showToast({
        title: "Shipment created",
        description: "Label created and shipment linked to order.",
        variant: "success"
      });
      setOrderId("");
      setCheckoutSessionId("");
      setRecipientName("");
      setRecipientPhone("");
      setAddressLine1("");
      setAddressLine2("");
      setShipmentCity("");
      setShipmentState("");
      setShipmentPostalCode("");
      queryClient.invalidateQueries({ queryKey: ["shipping", "shipments"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create shipment",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const syncTrackingMutation = useMutation({
    mutationFn: (shipmentId: string) => shippingService.syncTracking(shipmentId),
    onSuccess: () => {
      showToast({ title: "Tracking synced", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["shipping", "shipments"] });
      queryClient.invalidateQueries({ queryKey: ["orders"] });
    },
    onError: (error) => {
      showToast({
        title: "Tracking sync failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if ((settingsQuery.isLoading && !settingsNotConfigured) || shipmentsQuery.isLoading) {
    return <LoadingState label="Loading shipping operations..." />;
  }

  if ((settingsQuery.isError && !settingsNotConfigured) || shipmentsQuery.isError || !shipmentsQuery.data) {
    return (
      <ErrorState
        message="Unable to load shipping operations."
        onRetry={() => {
          settingsQuery.refetch();
          shipmentsQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#153149_0%,#1f4966_50%,#2e5d76_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Shipping and Delivery Operations</h3>
        <p className="mt-1 text-sm text-white/80">
          Configure rates, quote checkout shipping, create shipments, and sync tracking.
        </p>
      </Card>

      <Card>
        <div className="mb-4 flex items-center justify-between gap-2">
          <h3 className="font-heading text-lg font-bold text-surface-800">Shipping Settings</h3>
          {settingsNotConfigured ? <Badge variant="info">Not configured</Badge> : null}
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <Input label="Origin Country" value={originCountry} onChange={(e) => setOriginCountry(e.target.value)} />
          <Input label="Origin State" value={originState} onChange={(e) => setOriginState(e.target.value)} />
          <Input label="Origin City" value={originCity} onChange={(e) => setOriginCity(e.target.value)} />
          <Input label="Origin Postal" value={originPostalCode} onChange={(e) => setOriginPostalCode(e.target.value)} />
          <Input
            label="Handling Fee"
            type="number"
            step="0.01"
            value={handlingFee}
            onChange={(e) => setHandlingFee(Number(e.target.value || 0))}
          />
          <Input label="Currency" value={currency} onChange={(e) => setCurrency(e.target.value)} />
          <div className="md:col-span-3">
            <Textarea
              label="Zones (JSON array)"
              rows={8}
              value={zonesJson}
              onChange={(event) => setZonesJson(event.target.value)}
            />
          </div>
          <div className="md:col-span-3">
            <Textarea
              label="Service Rules (JSON array)"
              rows={8}
              value={rulesJson}
              onChange={(event) => setRulesJson(event.target.value)}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            loading={saveSettingsMutation.isPending}
            onClick={() => {
              try {
                parseJsonArray(zonesJson, []);
                parseJsonArray(rulesJson, []);
              } catch (error) {
                showToast({
                  title: "Invalid JSON",
                  description: getApiErrorMessage(error),
                  variant: "error"
                });
                return;
              }
              saveSettingsMutation.mutate();
            }}
          >
            Save Settings
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Checkout Rate Quote</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Input
            label="Checkout Session Token"
            value={quoteSessionToken}
            onChange={(event) => setQuoteSessionToken(event.target.value)}
          />
          <Input
            label="Destination Country"
            value={destinationCountry}
            onChange={(event) => setDestinationCountry(event.target.value)}
          />
          <Input
            label="Total Weight (KG)"
            type="number"
            step="0.1"
            value={totalWeightKg}
            onChange={(event) => setTotalWeightKg(Number(event.target.value || 1))}
          />
          <Input
            label="Destination State"
            value={destinationState}
            onChange={(event) => setDestinationState(event.target.value)}
          />
          <Input
            label="Destination City"
            value={destinationCity}
            onChange={(event) => setDestinationCity(event.target.value)}
          />
          <Input
            label="Destination Postal"
            value={destinationPostalCode}
            onChange={(event) => setDestinationPostalCode(event.target.value)}
          />
        </div>
        <div className="mt-4">
          <Button
            type="button"
            variant="secondary"
            loading={quoteMutation.isPending}
            onClick={() => quoteMutation.mutate()}
            disabled={!quoteSessionToken.trim()}
          >
            Quote Rates
          </Button>
        </div>
        {quoteMutation.data ? (
          <div className="mt-4 space-y-2">
            {quoteMutation.data.options.map((option) => (
              <article key={`${option.provider}-${option.service_code}`} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">
                      {option.service_name} ({option.provider})
                    </p>
                    <p className="text-xs text-surface-500">
                      ETA {option.eta_min_days}-{option.eta_max_days} days
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="info">{formatCurrency(option.amount)}</Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={
                        selectRateMutation.isPending &&
                        selectRateMutation.variables?.service_code === option.service_code
                      }
                      onClick={() => selectRateMutation.mutate(option)}
                    >
                      Select
                    </Button>
                  </div>
                </div>
              </article>
            ))}
            {!quoteMutation.data.options.length ? (
              <EmptyState title="No rates returned" description="Check shipping settings and destination details." />
            ) : null}
          </div>
        ) : null}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Create Shipment</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-3">
          <Input label="Order ID" value={orderId} onChange={(event) => setOrderId(event.target.value)} />
          <Input
            label="Checkout Session ID"
            value={checkoutSessionId}
            onChange={(event) => setCheckoutSessionId(event.target.value)}
          />
          <Input label="Provider" value={provider} onChange={(event) => setProvider(event.target.value)} />
          <Input label="Service Code" value={serviceCode} onChange={(event) => setServiceCode(event.target.value)} />
          <Input label="Service Name" value={serviceName} onChange={(event) => setServiceName(event.target.value)} />
          <Input
            label="Shipping Cost"
            type="number"
            step="0.01"
            value={shippingCost}
            onChange={(event) => setShippingCost(Number(event.target.value || 0))}
          />
          <Input label="Currency" value={shipmentCurrency} onChange={(event) => setShipmentCurrency(event.target.value)} />
          <Input label="Recipient Name" value={recipientName} onChange={(event) => setRecipientName(event.target.value)} />
          <Input label="Recipient Phone" value={recipientPhone} onChange={(event) => setRecipientPhone(event.target.value)} />
          <Input label="Address Line 1" value={addressLine1} onChange={(event) => setAddressLine1(event.target.value)} />
          <Input label="Address Line 2" value={addressLine2} onChange={(event) => setAddressLine2(event.target.value)} />
          <Input label="City" value={shipmentCity} onChange={(event) => setShipmentCity(event.target.value)} />
          <Input label="State" value={shipmentState} onChange={(event) => setShipmentState(event.target.value)} />
          <Input label="Country" value={shipmentCountry} onChange={(event) => setShipmentCountry(event.target.value)} />
          <Input label="Postal Code" value={shipmentPostalCode} onChange={(event) => setShipmentPostalCode(event.target.value)} />
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            loading={createShipmentMutation.isPending}
            onClick={() => createShipmentMutation.mutate()}
            disabled={!orderId.trim() || !recipientName.trim() || !addressLine1.trim() || !shipmentCity.trim()}
          >
            Create Shipment
          </Button>
        </div>
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-4">
          <Input label="Order Filter" value={orderFilter} onChange={(event) => setOrderFilter(event.target.value)} />
          <Input label="Status Filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} />
          <div className="mt-7">
            <Badge variant="info">{shipmentsQuery.data.pagination.total} shipments</Badge>
          </div>
        </div>
        {!shipmentsQuery.data.items.length ? (
          <EmptyState title="No shipments yet" description="Create and sync shipments from this page." />
        ) : (
          <div className="space-y-3">
            <div className="space-y-2 sm:hidden">
              {shipmentsQuery.data.items.map((shipment) => (
                <article key={shipment.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant={shipment.status === "delivered" ? "positive" : "info"}>
                      {shipment.status}
                    </Badge>
                    <p className="font-semibold text-mint-700">{formatCurrency(shipment.shipping_cost)}</p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">Order: {shipment.order_id}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    Tracking: {shipment.tracking_number ?? "-"} | Events: {shipment.tracking_events.length}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">{formatDateTime(shipment.created_at)}</p>
                  <div className="mt-3">
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={syncTrackingMutation.isPending && syncTrackingMutation.variables === shipment.id}
                      onClick={() => syncTrackingMutation.mutate(shipment.id)}
                    >
                      Sync Tracking
                    </Button>
                  </div>
                </article>
              ))}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Service</th>
                    <th className="px-2 py-2">Order</th>
                    <th className="px-2 py-2">Tracking</th>
                    <th className="px-2 py-2">Cost</th>
                    <th className="px-2 py-2">Created</th>
                    <th className="px-2 py-2">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {shipmentsQuery.data.items.map((shipment) => (
                    <tr key={shipment.id}>
                      <td className="px-2 py-2">
                        <Badge variant={shipment.status === "delivered" ? "positive" : "info"}>
                          {shipment.status}
                        </Badge>
                      </td>
                      <td className="px-2 py-2 text-surface-700">
                        {shipment.service_name}
                        <p className="text-xs text-surface-500">{shipment.provider}</p>
                      </td>
                      <td className="px-2 py-2 text-surface-600">{shipment.order_id}</td>
                      <td className="px-2 py-2 text-surface-600">{shipment.tracking_number ?? "-"}</td>
                      <td className="px-2 py-2 font-semibold text-mint-700">
                        {formatCurrency(shipment.shipping_cost)}
                      </td>
                      <td className="px-2 py-2 text-surface-500">{formatDateTime(shipment.created_at)}</td>
                      <td className="px-2 py-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          loading={syncTrackingMutation.isPending && syncTrackingMutation.variables === shipment.id}
                          onClick={() => syncTrackingMutation.mutate(shipment.id)}
                        >
                          Sync
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <PaginationControls
              pagination={shipmentsQuery.data.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (shipmentsQuery.data.pagination.has_next) {
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
