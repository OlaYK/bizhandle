import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { developerService, publicApiService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { formatDateTime } from "../lib/format";
import { getApiErrorMessage } from "../lib/api-error";

function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function DeveloperPortalPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [apiKeyName, setApiKeyName] = useState("");
  const [apiKeyScopesInput, setApiKeyScopesInput] = useState("business:read,products:read,orders:read,customers:read");
  const [apiKeyExpiresAt, setApiKeyExpiresAt] = useState("");
  const [latestApiKeyValue, setLatestApiKeyValue] = useState<string | null>(null);

  const [subscriptionName, setSubscriptionName] = useState("");
  const [subscriptionEndpoint, setSubscriptionEndpoint] = useState("https://hooks.example.com/receiver");
  const [subscriptionEvents, setSubscriptionEvents] = useState("storefront.page_view,order.created");
  const [subscriptionDescription, setSubscriptionDescription] = useState("");
  const [latestWebhookSecret, setLatestWebhookSecret] = useState<string | null>(null);
  const [deliveryStatusFilter, setDeliveryStatusFilter] = useState("");

  const [listingAppKey, setListingAppKey] = useState("");
  const [listingDisplayName, setListingDisplayName] = useState("");
  const [listingCategory, setListingCategory] = useState("operations");
  const [listingScopesInput, setListingScopesInput] = useState("products:read,orders:read");
  const [listingDescription, setListingDescription] = useState("");

  const [probeApiKey, setProbeApiKey] = useState("");
  const [probeResult, setProbeResult] = useState<string | null>(null);

  const scopeCatalogQuery = useQuery({
    queryKey: ["developer", "scope-catalog"],
    queryFn: developerService.listScopeCatalog
  });

  const apiKeysQuery = useQuery({
    queryKey: ["developer", "api-keys"],
    queryFn: developerService.listApiKeys
  });

  const subscriptionsQuery = useQuery({
    queryKey: ["developer", "webhook-subscriptions"],
    queryFn: developerService.listWebhookSubscriptions
  });

  const deliveriesQuery = useQuery({
    queryKey: ["developer", "webhook-deliveries", deliveryStatusFilter],
    queryFn: () =>
      developerService.listWebhookDeliveries({
        status: (deliveryStatusFilter || undefined) as
          | "pending"
          | "delivered"
          | "failed"
          | "dead_letter"
          | undefined,
        limit: 50,
        offset: 0
      })
  });

  const docsQuery = useQuery({
    queryKey: ["developer", "portal-docs"],
    queryFn: developerService.listPortalDocs
  });

  const marketplaceQuery = useQuery({
    queryKey: ["developer", "marketplace-listings"],
    queryFn: () => developerService.listMarketplaceListings({ limit: 50, offset: 0 })
  });

  const createApiKeyMutation = useMutation({
    mutationFn: () =>
      developerService.createApiKey({
        name: apiKeyName.trim(),
        scopes: parseCsv(apiKeyScopesInput),
        expires_at: apiKeyExpiresAt ? new Date(apiKeyExpiresAt).toISOString() : undefined
      }),
    onSuccess: (payload) => {
      setLatestApiKeyValue(payload.api_key);
      setApiKeyName("");
      setApiKeyExpiresAt("");
      queryClient.invalidateQueries({ queryKey: ["developer", "api-keys"] });
      showToast({
        title: "API key created",
        description: "Copy and store the plaintext key now. It is shown only once.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "API key creation failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const rotateApiKeyMutation = useMutation({
    mutationFn: (apiKeyId: string) => developerService.rotateApiKey(apiKeyId),
    onSuccess: (payload) => {
      setLatestApiKeyValue(payload.api_key);
      queryClient.invalidateQueries({ queryKey: ["developer", "api-keys"] });
      showToast({ title: "API key rotated", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "API key rotation failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const revokeApiKeyMutation = useMutation({
    mutationFn: (apiKeyId: string) => developerService.revokeApiKey(apiKeyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer", "api-keys"] });
      showToast({ title: "API key revoked", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "API key revoke failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const createSubscriptionMutation = useMutation({
    mutationFn: () =>
      developerService.createWebhookSubscription({
        name: subscriptionName.trim(),
        endpoint_url: subscriptionEndpoint.trim(),
        description: subscriptionDescription.trim() || undefined,
        events: parseCsv(subscriptionEvents),
        max_attempts: 5,
        retry_seconds: 120
      }),
    onSuccess: (payload) => {
      setLatestWebhookSecret(payload.signing_secret);
      setSubscriptionName("");
      setSubscriptionDescription("");
      queryClient.invalidateQueries({ queryKey: ["developer", "webhook-subscriptions"] });
      showToast({
        title: "Webhook subscription created",
        description: "Signing secret displayed once. Save it securely.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({ title: "Subscription creation failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const updateSubscriptionMutation = useMutation({
    mutationFn: (params: { subscriptionId: string; status: "active" | "paused" }) =>
      developerService.updateWebhookSubscription(params.subscriptionId, { status: params.status }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer", "webhook-subscriptions"] });
      showToast({ title: "Subscription updated", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Subscription update failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const rotateWebhookSecretMutation = useMutation({
    mutationFn: (subscriptionId: string) => developerService.rotateWebhookSecret(subscriptionId),
    onSuccess: (payload) => {
      setLatestWebhookSecret(payload.signing_secret);
      showToast({ title: "Webhook secret rotated", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Secret rotation failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const dispatchWebhooksMutation = useMutation({
    mutationFn: () => developerService.dispatchWebhookDeliveries(100),
    onSuccess: (payload) => {
      queryClient.invalidateQueries({ queryKey: ["developer", "webhook-deliveries"] });
      showToast({
        title: "Dispatch complete",
        description: `Processed: ${payload.processed}, delivered: ${payload.delivered}, failed: ${payload.failed}.`,
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({ title: "Dispatch failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const createListingMutation = useMutation({
    mutationFn: () =>
      developerService.createMarketplaceListing({
        app_key: listingAppKey.trim(),
        display_name: listingDisplayName.trim(),
        description: listingDescription.trim(),
        category: listingCategory,
        requested_scopes: parseCsv(listingScopesInput)
      }),
    onSuccess: () => {
      setListingAppKey("");
      setListingDisplayName("");
      setListingDescription("");
      queryClient.invalidateQueries({ queryKey: ["developer", "marketplace-listings"] });
      showToast({ title: "Listing draft created", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Listing create failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const submitListingMutation = useMutation({
    mutationFn: (listingId: string) => developerService.submitMarketplaceListing(listingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer", "marketplace-listings"] });
      showToast({ title: "Listing submitted", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Submit failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const reviewListingMutation = useMutation({
    mutationFn: (params: { listingId: string; decision: "under_review" | "approved" | "rejected" }) =>
      developerService.reviewMarketplaceListing(params.listingId, {
        decision: params.decision
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer", "marketplace-listings"] });
      showToast({ title: "Review decision saved", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Review failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const publishListingMutation = useMutation({
    mutationFn: (params: { listingId: string; publish: boolean }) =>
      developerService.publishMarketplaceListing(params.listingId, { publish: params.publish }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["developer", "marketplace-listings"] });
      showToast({ title: "Listing publication updated", variant: "success" });
    },
    onError: (error) => {
      showToast({ title: "Publish action failed", description: getApiErrorMessage(error), variant: "error" });
    }
  });

  const probeMutation = useMutation({
    mutationFn: async () => {
      const key = probeApiKey.trim();
      const profile = await publicApiService.me(key);
      const products = await publicApiService.products(key, { limit: 5, offset: 0 });
      return { profile, productsCount: products.pagination.total };
    },
    onSuccess: (payload) => {
      setProbeResult(`Connected to ${payload.profile.business_name}. Products visible: ${payload.productsCount}.`);
    },
    onError: (error) => {
      setProbeResult(`Probe failed: ${getApiErrorMessage(error)}`);
    }
  });

  const supportedScopes = useMemo(
    () => scopeCatalogQuery.data?.items.map((item) => item.scope).join(", ") ?? "",
    [scopeCatalogQuery.data]
  );

  if (
    scopeCatalogQuery.isLoading ||
    apiKeysQuery.isLoading ||
    subscriptionsQuery.isLoading ||
    deliveriesQuery.isLoading ||
    docsQuery.isLoading ||
    marketplaceQuery.isLoading
  ) {
    return <LoadingState label="Loading developer platform..." />;
  }

  if (
    scopeCatalogQuery.isError ||
    apiKeysQuery.isError ||
    subscriptionsQuery.isError ||
    deliveriesQuery.isError ||
    docsQuery.isError ||
    marketplaceQuery.isError ||
    !scopeCatalogQuery.data ||
    !apiKeysQuery.data ||
    !subscriptionsQuery.data ||
    !deliveriesQuery.data ||
    !docsQuery.data ||
    !marketplaceQuery.data
  ) {
    return (
      <ErrorState
        message="Unable to load developer platform workspace."
        onRetry={() => {
          scopeCatalogQuery.refetch();
          apiKeysQuery.refetch();
          subscriptionsQuery.refetch();
          deliveriesQuery.refetch();
          docsQuery.refetch();
          marketplaceQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#152235_0%,#1f3e61_60%,#2a5f83_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Developer Platform</h3>
        <p className="mt-1 text-sm text-white/80">
          Manage public API keys, webhook subscriptions, and marketplace listing governance from one console.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Badge variant="info">{apiKeysQuery.data.items.length} API keys</Badge>
          <Badge variant="info">{subscriptionsQuery.data.items.length} webhook subscriptions</Badge>
          <Badge variant="info">{marketplaceQuery.data.items.length} marketplace listings</Badge>
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Public API Keys</h3>
        <p className="mt-1 text-xs text-surface-500">Supported scopes: {supportedScopes || "loading..."}</p>
        <div className="mt-3 grid gap-3 lg:grid-cols-3">
          <Input label="Key Name" value={apiKeyName} onChange={(event) => setApiKeyName(event.target.value)} />
          <Input
            label="Scopes CSV"
            value={apiKeyScopesInput}
            onChange={(event) => setApiKeyScopesInput(event.target.value)}
          />
          <Input
            type="datetime-local"
            label="Expires At (optional)"
            value={apiKeyExpiresAt}
            onChange={(event) => setApiKeyExpiresAt(event.target.value)}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            loading={createApiKeyMutation.isPending}
            disabled={!apiKeyName.trim()}
            onClick={() => createApiKeyMutation.mutate()}
          >
            Create API Key
          </Button>
        </div>
        {latestApiKeyValue ? (
          <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-semibold text-amber-800">One-time plaintext key</p>
            <p className="mt-1 break-all font-mono text-xs text-amber-900">{latestApiKeyValue}</p>
          </div>
        ) : null}
        {!apiKeysQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No API keys yet" description="Create your first key for public API access." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {apiKeysQuery.data.items.map((item) => (
              <article key={item.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{item.name}</p>
                    <p className="text-xs text-surface-500">
                      Prefix: <span className="font-mono">{item.key_prefix}</span> | Scopes: {item.scopes.join(", ")}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={item.status === "active" ? "positive" : "negative"}>{item.status}</Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      loading={rotateApiKeyMutation.isPending && rotateApiKeyMutation.variables === item.id}
                      onClick={() => rotateApiKeyMutation.mutate(item.id)}
                    >
                      Rotate
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="danger"
                      loading={revokeApiKeyMutation.isPending && revokeApiKeyMutation.variables === item.id}
                      onClick={() => revokeApiKeyMutation.mutate(item.id)}
                    >
                      Revoke
                    </Button>
                  </div>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  Updated: {formatDateTime(item.updated_at)} | Last used: {item.last_used_at ? formatDateTime(item.last_used_at) : "never"}
                </p>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Webhook Subscriptions</h3>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <Input
            label="Subscription Name"
            value={subscriptionName}
            onChange={(event) => setSubscriptionName(event.target.value)}
          />
          <Input
            label="Endpoint URL"
            value={subscriptionEndpoint}
            onChange={(event) => setSubscriptionEndpoint(event.target.value)}
          />
          <Input
            label="Events CSV"
            value={subscriptionEvents}
            onChange={(event) => setSubscriptionEvents(event.target.value)}
          />
          <Input
            label="Description"
            value={subscriptionDescription}
            onChange={(event) => setSubscriptionDescription(event.target.value)}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            type="button"
            loading={createSubscriptionMutation.isPending}
            disabled={!subscriptionName.trim() || !subscriptionEndpoint.trim()}
            onClick={() => createSubscriptionMutation.mutate()}
          >
            Create Subscription
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={dispatchWebhooksMutation.isPending}
            onClick={() => dispatchWebhooksMutation.mutate()}
          >
            Dispatch Deliveries
          </Button>
        </div>
        {latestWebhookSecret ? (
          <div className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <p className="text-xs font-semibold text-emerald-800">Latest webhook signing secret</p>
            <p className="mt-1 break-all font-mono text-xs text-emerald-900">{latestWebhookSecret}</p>
          </div>
        ) : null}
        {!subscriptionsQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No subscriptions" description="Create at least one webhook receiver." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {subscriptionsQuery.data.items.map((item) => (
              <article key={item.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{item.name}</p>
                    <p className="text-xs text-surface-500">
                      {item.endpoint_url} | Events: {item.events.join(", ")}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Badge variant={item.status === "active" ? "positive" : "neutral"}>{item.status}</Badge>
                    <Button
                      type="button"
                      size="sm"
                      variant="secondary"
                      loading={rotateWebhookSecretMutation.isPending && rotateWebhookSecretMutation.variables === item.id}
                      onClick={() => rotateWebhookSecretMutation.mutate(item.id)}
                    >
                      Rotate Secret
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      loading={
                        updateSubscriptionMutation.isPending &&
                        updateSubscriptionMutation.variables?.subscriptionId === item.id
                      }
                      onClick={() =>
                        updateSubscriptionMutation.mutate({
                          subscriptionId: item.id,
                          status: item.status === "active" ? "paused" : "active"
                        })
                      }
                    >
                      {item.status === "active" ? "Pause" : "Activate"}
                    </Button>
                  </div>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  Last delivery: {item.last_delivery_at ? formatDateTime(item.last_delivery_at) : "n/a"} | Secret hint: {item.secret_hint}
                </p>
              </article>
            ))}
          </div>
        )}

        <div className="mt-5 grid gap-3 md:grid-cols-3">
          <Select
            label="Delivery Status Filter"
            value={deliveryStatusFilter}
            onChange={(event) => setDeliveryStatusFilter(event.target.value)}
          >
            <option value="">all</option>
            <option value="pending">pending</option>
            <option value="delivered">delivered</option>
            <option value="failed">failed</option>
            <option value="dead_letter">dead_letter</option>
          </Select>
          <div className="md:col-span-2 flex items-end">
            <Button type="button" variant="secondary" onClick={() => deliveriesQuery.refetch()}>
              Refresh Delivery Logs
            </Button>
          </div>
        </div>
        {!deliveriesQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No delivery logs" description="Run dispatch after emitting outbox events." />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {deliveriesQuery.data.items.map((item) => (
              <article key={item.id} className="rounded-lg border border-surface-100 bg-white p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-surface-700">{item.event_type}</p>
                  <Badge
                    variant={
                      item.status === "delivered"
                        ? "positive"
                        : item.status === "failed" || item.status === "dead_letter"
                          ? "negative"
                          : "info"
                    }
                  >
                    {item.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  attempts: {item.attempt_count}/{item.max_attempts} | response: {item.last_response_code ?? "n/a"} | created: {formatDateTime(item.created_at)}
                </p>
                {item.last_error ? <p className="mt-1 text-xs text-red-600">{item.last_error}</p> : null}
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Marketplace Governance</h3>
        <div className="mt-3 grid gap-3 lg:grid-cols-2">
          <Input label="App Key" value={listingAppKey} onChange={(event) => setListingAppKey(event.target.value)} />
          <Input
            label="Display Name"
            value={listingDisplayName}
            onChange={(event) => setListingDisplayName(event.target.value)}
          />
          <Input
            label="Category"
            value={listingCategory}
            onChange={(event) => setListingCategory(event.target.value)}
          />
          <Input
            label="Requested Scopes CSV"
            value={listingScopesInput}
            onChange={(event) => setListingScopesInput(event.target.value)}
          />
        </div>
        <div className="mt-3">
          <Textarea
            label="Description"
            rows={3}
            value={listingDescription}
            onChange={(event) => setListingDescription(event.target.value)}
          />
        </div>
        <div className="mt-3">
          <Button
            type="button"
            loading={createListingMutation.isPending}
            disabled={!listingAppKey.trim() || !listingDisplayName.trim() || listingDescription.trim().length < 10}
            onClick={() => createListingMutation.mutate()}
          >
            Create Draft Listing
          </Button>
        </div>
        {!marketplaceQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No marketplace listings" description="Create a draft and move it through review." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {marketplaceQuery.data.items.map((item) => (
              <article key={item.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{item.display_name}</p>
                    <p className="text-xs text-surface-500">
                      {item.app_key} | category: {item.category} | scopes: {item.requested_scopes.join(", ")}
                    </p>
                  </div>
                  <Badge
                    variant={
                      item.status === "approved" || item.status === "published"
                        ? "positive"
                        : item.status === "rejected"
                          ? "negative"
                          : "info"
                    }
                  >
                    {item.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">{item.description}</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={item.status !== "draft" && item.status !== "rejected"}
                    loading={submitListingMutation.isPending && submitListingMutation.variables === item.id}
                    onClick={() => submitListingMutation.mutate(item.id)}
                  >
                    Submit
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    disabled={item.status !== "submitted" && item.status !== "under_review"}
                    loading={
                      reviewListingMutation.isPending &&
                      reviewListingMutation.variables?.listingId === item.id &&
                      reviewListingMutation.variables?.decision === "approved"
                    }
                    onClick={() => reviewListingMutation.mutate({ listingId: item.id, decision: "approved" })}
                  >
                    Approve
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="danger"
                    disabled={item.status !== "submitted" && item.status !== "under_review"}
                    loading={
                      reviewListingMutation.isPending &&
                      reviewListingMutation.variables?.listingId === item.id &&
                      reviewListingMutation.variables?.decision === "rejected"
                    }
                    onClick={() => reviewListingMutation.mutate({ listingId: item.id, decision: "rejected" })}
                  >
                    Reject
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    disabled={item.status !== "approved" && item.status !== "published"}
                    loading={
                      publishListingMutation.isPending &&
                      publishListingMutation.variables?.listingId === item.id
                    }
                    onClick={() =>
                      publishListingMutation.mutate({
                        listingId: item.id,
                        publish: item.status !== "published"
                      })
                    }
                  >
                    {item.status === "published" ? "Unpublish" : "Publish"}
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Developer Docs and SDK Quickstarts</h3>
        <div className="mt-3 space-y-2">
          {docsQuery.data.items.map((doc) => (
            <article key={doc.relative_path} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
              <div className="flex items-center justify-between gap-2">
                <p className="font-semibold text-surface-700">{doc.title}</p>
                <Badge variant="info">{doc.section}</Badge>
              </div>
              <p className="mt-1 text-xs text-surface-500">{doc.summary}</p>
              <p className="mt-1 font-mono text-xs text-surface-600">{doc.relative_path}</p>
            </article>
          ))}
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Public API Smoke Test</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Input
            label="Plaintext API key"
            value={probeApiKey}
            onChange={(event) => setProbeApiKey(event.target.value)}
          />
          <div className="flex items-end">
            <Button
              type="button"
              loading={probeMutation.isPending}
              disabled={!probeApiKey.trim()}
              onClick={() => probeMutation.mutate()}
            >
              Run Probe
            </Button>
          </div>
        </div>
        {probeResult ? <p className="mt-3 text-sm font-semibold text-surface-700">{probeResult}</p> : null}
      </Card>
    </div>
  );
}
