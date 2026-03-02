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
import { Select } from "../components/ui/select";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDateTime } from "../lib/format";

function normalizeOptional(value: string) {
  const cleaned = value.trim();
  return cleaned || undefined;
}

interface ShippingZoneDraft {
  id: string;
  zone_name: string;
  country: string;
  state: string;
  city: string;
  postal_code_prefix: string;
  is_active: boolean;
}

interface ShippingServiceRuleDraft {
  id: string;
  provider: string;
  service_code: string;
  service_name: string;
  zone_name: string;
  base_rate: number;
  per_kg_rate: number;
  min_eta_days: number;
  max_eta_days: number;
  is_active: boolean;
}

function createZoneDraft(overrides?: Partial<ShippingZoneDraft>): ShippingZoneDraft {
  return {
    id: crypto.randomUUID(),
    zone_name: "Domestic",
    country: "NG",
    state: "",
    city: "",
    postal_code_prefix: "",
    is_active: true,
    ...overrides
  };
}

function createRuleDraft(overrides?: Partial<ShippingServiceRuleDraft>): ShippingServiceRuleDraft {
  return {
    id: crypto.randomUUID(),
    provider: "stub_carrier",
    service_code: "standard",
    service_name: "Standard Shipping",
    zone_name: "",
    base_rate: 0,
    per_kg_rate: 0,
    min_eta_days: 2,
    max_eta_days: 5,
    is_active: true,
    ...overrides
  };
}

function toZonePayload(zone: ShippingZoneDraft) {
  return {
    zone_name: zone.zone_name.trim(),
    country: zone.country.trim().toUpperCase(),
    state: normalizeOptional(zone.state),
    city: normalizeOptional(zone.city),
    postal_code_prefix: normalizeOptional(zone.postal_code_prefix),
    is_active: zone.is_active
  };
}

function toRulePayload(rule: ShippingServiceRuleDraft) {
  return {
    provider: rule.provider.trim().toLowerCase(),
    service_code: rule.service_code.trim(),
    service_name: rule.service_name.trim(),
    zone_name: normalizeOptional(rule.zone_name),
    base_rate: Number(rule.base_rate || 0),
    per_kg_rate: Number(rule.per_kg_rate || 0),
    min_eta_days: Number(rule.min_eta_days || 1),
    max_eta_days: Number(rule.max_eta_days || 1),
    is_active: rule.is_active
  };
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
  const [zones, setZones] = useState<ShippingZoneDraft[]>([createZoneDraft()]);
  const [serviceRules, setServiceRules] = useState<ShippingServiceRuleDraft[]>([
    createRuleDraft({ zone_name: "Domestic" })
  ]);

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
    setZones(
      settingsQuery.data.zones.length
        ? settingsQuery.data.zones.map((zone) =>
            createZoneDraft({
              zone_name: zone.zone_name,
              country: zone.country,
              state: zone.state ?? "",
              city: zone.city ?? "",
              postal_code_prefix: zone.postal_code_prefix ?? "",
              is_active: zone.is_active
            })
          )
        : [createZoneDraft()]
    );
    setServiceRules(
      settingsQuery.data.service_rules.length
        ? settingsQuery.data.service_rules.map((rule) =>
            createRuleDraft({
              provider: rule.provider,
              service_code: rule.service_code,
              service_name: rule.service_name,
              zone_name: rule.zone_name ?? "",
              base_rate: rule.base_rate,
              per_kg_rate: rule.per_kg_rate,
              min_eta_days: rule.min_eta_days,
              max_eta_days: rule.max_eta_days,
              is_active: rule.is_active
            })
          )
        : [createRuleDraft()]
    );
  }, [settingsQuery.data]);

  const updateZoneDraft = (id: string, patch: Partial<ShippingZoneDraft>) => {
    setZones((prev) => prev.map((zone) => (zone.id === id ? { ...zone, ...patch } : zone)));
  };

  const removeZoneDraft = (id: string) => {
    const removedZone = zones.find((zone) => zone.id === id);
    setZones((prev) => {
      const next = prev.filter((zone) => zone.id !== id);
      return next.length ? next : [createZoneDraft()];
    });
    if (!removedZone) {
      return;
    }
    const removedZoneName = removedZone.zone_name.trim().toLowerCase();
    setServiceRules((prev) =>
      prev.map((rule) =>
        rule.zone_name.trim().toLowerCase() === removedZoneName
          ? { ...rule, zone_name: "" }
          : rule
      )
    );
  };

  const updateRuleDraft = (id: string, patch: Partial<ShippingServiceRuleDraft>) => {
    setServiceRules((prev) => prev.map((rule) => (rule.id === id ? { ...rule, ...patch } : rule)));
  };

  const removeRuleDraft = (id: string) => {
    setServiceRules((prev) => {
      const next = prev.filter((rule) => rule.id !== id);
      return next.length ? next : [createRuleDraft()];
    });
  };

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
        zones: zones.map(toZonePayload),
        service_rules: serviceRules.map(toRulePayload)
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

  const zoneNameOptions = Array.from(
    new Set(zones.map((zone) => zone.zone_name.trim()).filter((name) => name.length > 0))
  );

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
          <div className="space-y-3 rounded-xl border border-surface-100 bg-surface-50 p-3 md:col-span-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-semibold text-surface-700">Delivery Zones</h4>
                <p className="text-xs text-surface-500">
                  Define where you ship. Service rules can target a specific zone.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() => setZones((prev) => [...prev, createZoneDraft()])}
              >
                Add Zone
              </Button>
            </div>
            {zones.map((zone, index) => (
              <article key={zone.id} className="rounded-xl border border-surface-200 bg-white p-3 dark:bg-surface-900">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-surface-700">Zone {index + 1}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="danger"
                    disabled={zones.length === 1}
                    onClick={() => removeZoneDraft(zone.id)}
                  >
                    Remove
                  </Button>
                </div>
                <div className="grid gap-3 lg:grid-cols-3">
                  <Input
                    label="Zone Name"
                    value={zone.zone_name}
                    onChange={(event) => updateZoneDraft(zone.id, { zone_name: event.target.value })}
                  />
                  <Input
                    label="Country Code"
                    value={zone.country}
                    onChange={(event) => updateZoneDraft(zone.id, { country: event.target.value })}
                    placeholder="NG"
                  />
                  <Select
                    label="Status"
                    value={zone.is_active ? "active" : "inactive"}
                    onChange={(event) =>
                      updateZoneDraft(zone.id, { is_active: event.target.value === "active" })
                    }
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </Select>
                  <Input
                    label="State (optional)"
                    value={zone.state}
                    onChange={(event) => updateZoneDraft(zone.id, { state: event.target.value })}
                  />
                  <Input
                    label="City (optional)"
                    value={zone.city}
                    onChange={(event) => updateZoneDraft(zone.id, { city: event.target.value })}
                  />
                  <Input
                    label="Postal Prefix (optional)"
                    value={zone.postal_code_prefix}
                    onChange={(event) =>
                      updateZoneDraft(zone.id, { postal_code_prefix: event.target.value })
                    }
                  />
                </div>
              </article>
            ))}
          </div>
          <div className="space-y-3 rounded-xl border border-surface-100 bg-surface-50 p-3 md:col-span-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h4 className="font-semibold text-surface-700">Service Rules</h4>
                <p className="text-xs text-surface-500">
                  Configure provider pricing and delivery windows. Zone is optional for fallback rules.
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={() =>
                  setServiceRules((prev) => [
                    ...prev,
                    createRuleDraft({ zone_name: zoneNameOptions[0] ?? "" })
                  ])
                }
              >
                Add Rule
              </Button>
            </div>
            {serviceRules.map((rule, index) => (
              <article key={rule.id} className="rounded-xl border border-surface-200 bg-white p-3 dark:bg-surface-900">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-surface-700">Rule {index + 1}</p>
                  <Button
                    type="button"
                    size="sm"
                    variant="danger"
                    disabled={serviceRules.length === 1}
                    onClick={() => removeRuleDraft(rule.id)}
                  >
                    Remove
                  </Button>
                </div>
                <div className="grid gap-3 lg:grid-cols-4">
                  <Input
                    label="Provider"
                    value={rule.provider}
                    onChange={(event) => updateRuleDraft(rule.id, { provider: event.target.value })}
                  />
                  <Input
                    label="Service Code"
                    value={rule.service_code}
                    onChange={(event) => updateRuleDraft(rule.id, { service_code: event.target.value })}
                  />
                  <Input
                    label="Service Name"
                    value={rule.service_name}
                    onChange={(event) => updateRuleDraft(rule.id, { service_name: event.target.value })}
                  />
                  <Select
                    label="Zone"
                    value={rule.zone_name}
                    onChange={(event) => updateRuleDraft(rule.id, { zone_name: event.target.value })}
                  >
                    <option value="">All destinations (fallback)</option>
                    {zoneNameOptions.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </Select>
                  <Input
                    label="Base Rate"
                    type="number"
                    step="0.01"
                    value={rule.base_rate}
                    onChange={(event) =>
                      updateRuleDraft(rule.id, { base_rate: Number(event.target.value || 0) })
                    }
                  />
                  <Input
                    label="Per KG Rate"
                    type="number"
                    step="0.01"
                    value={rule.per_kg_rate}
                    onChange={(event) =>
                      updateRuleDraft(rule.id, { per_kg_rate: Number(event.target.value || 0) })
                    }
                  />
                  <Input
                    label="Min ETA Days"
                    type="number"
                    min={1}
                    value={rule.min_eta_days}
                    onChange={(event) =>
                      updateRuleDraft(rule.id, { min_eta_days: Number(event.target.value || 1) })
                    }
                  />
                  <Input
                    label="Max ETA Days"
                    type="number"
                    min={1}
                    value={rule.max_eta_days}
                    onChange={(event) =>
                      updateRuleDraft(rule.id, { max_eta_days: Number(event.target.value || 1) })
                    }
                  />
                  <Select
                    label="Status"
                    value={rule.is_active ? "active" : "inactive"}
                    onChange={(event) =>
                      updateRuleDraft(rule.id, { is_active: event.target.value === "active" })
                    }
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </Select>
                </div>
              </article>
            ))}
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            type="button"
            loading={saveSettingsMutation.isPending}
            onClick={() => {
              if (originCountry.trim().length < 2) {
                showToast({
                  title: "Invalid origin country",
                  description: "Origin country must be at least 2 characters.",
                  variant: "error"
                });
                return;
              }
              if (currency.trim().length !== 3) {
                showToast({
                  title: "Invalid currency",
                  description: "Currency must be a 3-letter ISO code (for example NGN, USD, EUR).",
                  variant: "error"
                });
                return;
              }
              if (Number(handlingFee || 0) < 0) {
                showToast({
                  title: "Invalid handling fee",
                  description: "Handling fee cannot be negative.",
                  variant: "error"
                });
                return;
              }
              if (!zones.length) {
                showToast({
                  title: "At least one zone is required",
                  description: "Add a delivery zone before saving shipping settings.",
                  variant: "error"
                });
                return;
              }
              if (!serviceRules.length) {
                showToast({
                  title: "At least one service rule is required",
                  description: "Add a service rule before saving shipping settings.",
                  variant: "error"
                });
                return;
              }
              const invalidZone = zones.find(
                (zone) => zone.zone_name.trim().length < 2 || zone.country.trim().length < 2
              );
              if (invalidZone) {
                showToast({
                  title: "Invalid zone details",
                  description: "Zone name and country code must be at least 2 characters.",
                  variant: "error"
                });
                return;
              }
              const invalidRule = serviceRules.find(
                (rule) =>
                  rule.provider.trim().length < 2 ||
                  rule.service_code.trim().length < 2 ||
                  rule.service_name.trim().length < 2
              );
              if (invalidRule) {
                showToast({
                  title: "Invalid service rule",
                  description: "Provider, service code, and service name must be at least 2 characters.",
                  variant: "error"
                });
                return;
              }
              const invalidEtaRule = serviceRules.find(
                (rule) =>
                  Number(rule.min_eta_days || 0) < 1 ||
                  Number(rule.max_eta_days || 0) < 1 ||
                  Number(rule.min_eta_days || 1) > Number(rule.max_eta_days || 1)
              );
              if (invalidEtaRule) {
                showToast({
                  title: "Invalid ETA window",
                  description: "ETA values must be at least 1 day, and min ETA cannot exceed max ETA.",
                  variant: "error"
                });
                return;
              }
              const invalidRateRule = serviceRules.find(
                (rule) => Number(rule.base_rate || 0) < 0 || Number(rule.per_kg_rate || 0) < 0
              );
              if (invalidRateRule) {
                showToast({
                  title: "Invalid shipping rates",
                  description: "Base rate and per KG rate cannot be negative.",
                  variant: "error"
                });
                return;
              }
              const knownZoneNames = new Set(
                zones.map((zone) => zone.zone_name.trim().toLowerCase()).filter((name) => name.length > 0)
              );
              const unknownZoneRule = serviceRules.find(
                (rule) => rule.zone_name.trim() && !knownZoneNames.has(rule.zone_name.trim().toLowerCase())
              );
              if (unknownZoneRule) {
                showToast({
                  title: "Rule zone not found",
                  description: `The rule "${unknownZoneRule.service_name}" references a zone that does not exist.`,
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
