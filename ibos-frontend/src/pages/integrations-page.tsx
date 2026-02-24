import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { integrationService } from "../api/services";
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
import { formatDateTime } from "../lib/format";

function safeJsonParse(raw: string): Record<string, unknown> | null {
  const cleaned = raw.trim();
  if (!cleaned) return null;
  const parsed = JSON.parse(cleaned) as unknown;
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    return parsed as Record<string, unknown>;
  }
  return null;
}

export function IntegrationsPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [secretProvider, setSecretProvider] = useState("meta_pixel");
  const [secretKeyName, setSecretKeyName] = useState("access_token");
  const [secretValue, setSecretValue] = useState("");

  const [appKey, setAppKey] = useState("meta_pixel");
  const [appDisplayName, setAppDisplayName] = useState("Meta Pixel");
  const [appPermissions, setAppPermissions] = useState("events:write");
  const [appConfigJson, setAppConfigJson] = useState("{}");

  const [eventType, setEventType] = useState("storefront.page_view");
  const [eventTargetApp, setEventTargetApp] = useState("meta_pixel");
  const [eventPayloadJson, setEventPayloadJson] = useState(
    JSON.stringify({ path: "/store/sample", slug: "sample" }, null, 2)
  );

  const [messageProvider, setMessageProvider] = useState("whatsapp_stub");
  const [messageRecipient, setMessageRecipient] = useState("");
  const [messageContent, setMessageContent] = useState("");

  const [outboxStatusFilter, setOutboxStatusFilter] = useState("");
  const [outboxAppFilter, setOutboxAppFilter] = useState("");
  const [outboxPage, setOutboxPage] = useState(1);
  const [outboxPageSize, setOutboxPageSize] = useState(20);
  const [messagesPage, setMessagesPage] = useState(1);
  const [messagesPageSize, setMessagesPageSize] = useState(20);

  useEffect(() => {
    setOutboxPage(1);
  }, [outboxStatusFilter, outboxAppFilter]);

  const outboxOffset = (outboxPage - 1) * outboxPageSize;
  const messagesOffset = (messagesPage - 1) * messagesPageSize;

  const secretsQuery = useQuery({
    queryKey: ["integrations", "secrets"],
    queryFn: integrationService.listSecrets
  });

  const appsQuery = useQuery({
    queryKey: ["integrations", "apps"],
    queryFn: integrationService.listApps
  });

  const outboxQuery = useQuery({
    queryKey: [
      "integrations",
      "outbox",
      outboxStatusFilter,
      outboxAppFilter,
      outboxPage,
      outboxPageSize
    ],
    queryFn: () =>
      integrationService.listOutboxEvents({
        status: outboxStatusFilter || undefined,
        target_app_key: outboxAppFilter || undefined,
        limit: outboxPageSize,
        offset: outboxOffset
      })
  });

  const messagesQuery = useQuery({
    queryKey: ["integrations", "messages", messagesPage, messagesPageSize],
    queryFn: () =>
      integrationService.listMessages({
        limit: messagesPageSize,
        offset: messagesOffset
      })
  });

  const upsertSecretMutation = useMutation({
    mutationFn: () =>
      integrationService.upsertSecret({
        provider: secretProvider.trim(),
        key_name: secretKeyName.trim(),
        secret_value: secretValue
      }),
    onSuccess: () => {
      showToast({ title: "Secret saved", variant: "success" });
      setSecretValue("");
      queryClient.invalidateQueries({ queryKey: ["integrations", "secrets"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not save secret",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const installAppMutation = useMutation({
    mutationFn: () =>
      integrationService.installApp({
        app_key: appKey.trim(),
        display_name: appDisplayName.trim(),
        permissions: appPermissions
          .split(",")
          .map((value) => value.trim())
          .filter(Boolean),
        config_json: safeJsonParse(appConfigJson)
      }),
    onSuccess: () => {
      showToast({ title: "App connected", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["integrations", "apps"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not connect app",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const disconnectAppMutation = useMutation({
    mutationFn: (installationId: string) => integrationService.disconnectApp(installationId),
    onSuccess: () => {
      showToast({ title: "App disconnected", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["integrations", "apps"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not disconnect app",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const emitEventMutation = useMutation({
    mutationFn: () =>
      integrationService.emitOutboxEvent({
        event_type: eventType.trim(),
        target_app_key: eventTargetApp.trim(),
        payload_json: safeJsonParse(eventPayloadJson)
      }),
    onSuccess: () => {
      showToast({
        title: "Event emitted",
        description: "Event added to outbox queue.",
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["integrations", "outbox"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not emit event",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const dispatchOutboxMutation = useMutation({
    mutationFn: () => integrationService.dispatchOutbox(100),
    onSuccess: (result) => {
      showToast({
        title: "Outbox dispatch complete",
        description: `Processed ${result.processed}, delivered ${result.delivered}, failed ${result.failed}.`,
        variant: "success"
      });
      queryClient.invalidateQueries({ queryKey: ["integrations", "outbox"] });
    },
    onError: (error) => {
      showToast({
        title: "Dispatch failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const sendMessageMutation = useMutation({
    mutationFn: () =>
      integrationService.sendMessage({
        provider: messageProvider.trim(),
        recipient: messageRecipient.trim(),
        content: messageContent.trim()
      }),
    onSuccess: () => {
      showToast({ title: "Message sent", variant: "success" });
      setMessageContent("");
      queryClient.invalidateQueries({ queryKey: ["integrations", "messages"] });
      queryClient.invalidateQueries({ queryKey: ["integrations", "outbox"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Message send failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (
    secretsQuery.isLoading ||
    appsQuery.isLoading ||
    outboxQuery.isLoading ||
    messagesQuery.isLoading
  ) {
    return <LoadingState label="Loading integration operations..." />;
  }

  if (
    secretsQuery.isError ||
    appsQuery.isError ||
    outboxQuery.isError ||
    messagesQuery.isError ||
    !secretsQuery.data ||
    !appsQuery.data ||
    !outboxQuery.data ||
    !messagesQuery.data
  ) {
    return (
      <ErrorState
        message="Unable to load integration operations."
        onRetry={() => {
          secretsQuery.refetch();
          appsQuery.refetch();
          outboxQuery.refetch();
          messagesQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up bg-[linear-gradient(135deg,#123044_0%,#1f4c64_55%,#2a5b73_100%)] text-white">
        <h3 className="font-heading text-xl font-black">Integrations Center</h3>
        <p className="mt-1 text-sm text-white/80">
          Manage app installations, secrets, event delivery, and messaging connectors.
        </p>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Credential Vault</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Input label="Provider" value={secretProvider} onChange={(e) => setSecretProvider(e.target.value)} />
          <Input label="Key Name" value={secretKeyName} onChange={(e) => setSecretKeyName(e.target.value)} />
          <Input
            label="Secret Value"
            type="password"
            value={secretValue}
            onChange={(e) => setSecretValue(e.target.value)}
          />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={upsertSecretMutation.isPending}
              onClick={() => upsertSecretMutation.mutate()}
              disabled={!secretProvider.trim() || !secretKeyName.trim() || !secretValue.trim()}
            >
              Save Secret
            </Button>
          </div>
        </div>

        {!secretsQuery.data.items.length ? (
          <div className="mt-4">
            <EmptyState title="No secrets yet" description="Secrets metadata appears here after first save." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {secretsQuery.data.items.map((secret) => (
              <article key={secret.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-semibold text-surface-700">
                    {secret.provider} / {secret.key_name}
                  </p>
                  <Badge variant="info">v{secret.version}</Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">Status: {secret.status}</p>
                <p className="mt-1 text-xs text-surface-500">Updated: {formatDateTime(secret.updated_at)}</p>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">App Installations</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Input label="App Key" value={appKey} onChange={(e) => setAppKey(e.target.value)} />
          <Input label="Display Name" value={appDisplayName} onChange={(e) => setAppDisplayName(e.target.value)} />
          <Input
            label="Permissions (comma separated)"
            value={appPermissions}
            onChange={(e) => setAppPermissions(e.target.value)}
          />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={installAppMutation.isPending}
              onClick={() => {
                try {
                  safeJsonParse(appConfigJson);
                } catch (error) {
                  showToast({
                    title: "Invalid app config JSON",
                    description: getApiErrorMessage(error),
                    variant: "error"
                  });
                  return;
                }
                installAppMutation.mutate();
              }}
              disabled={!appKey.trim() || !appDisplayName.trim()}
            >
              Connect App
            </Button>
          </div>
          <div className="md:col-span-4">
            <Textarea
              label="App Config JSON"
              rows={4}
              value={appConfigJson}
              onChange={(event) => setAppConfigJson(event.target.value)}
            />
          </div>
          <div className="md:col-span-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setAppKey("meta_pixel");
                setAppDisplayName("Meta Pixel");
                setAppPermissions("events:write");
              }}
            >
              Meta Pixel Preset
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setAppKey("google_analytics");
                setAppDisplayName("Google Analytics");
                setAppPermissions("events:write");
              }}
            >
              Google Analytics Preset
            </Button>
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setAppKey("whatsapp");
                setAppDisplayName("WhatsApp");
                setAppPermissions("messages:send");
              }}
            >
              WhatsApp Preset
            </Button>
          </div>
        </div>

        {!appsQuery.data.items.length ? (
          <div className="mt-4">
            <EmptyState title="No apps connected" description="Connect apps to start receiving storefront events." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {appsQuery.data.items.map((installation) => (
              <article key={installation.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">
                      {installation.display_name} ({installation.app_key})
                    </p>
                    <p className="text-xs text-surface-500">
                      Permissions: {installation.permissions.length ? installation.permissions.join(", ") : "none"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={installation.status === "connected" ? "positive" : "negative"}>
                      {installation.status}
                    </Badge>
                    {installation.status === "connected" ? (
                      <Button
                        type="button"
                        size="sm"
                        variant="danger"
                        loading={
                          disconnectAppMutation.isPending &&
                          disconnectAppMutation.variables === installation.id
                        }
                        onClick={() => disconnectAppMutation.mutate(installation.id)}
                      >
                        Disconnect
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="mt-1 text-xs text-surface-500">Updated: {formatDateTime(installation.updated_at)}</p>
              </article>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Outbox Events</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Input label="Event Type" value={eventType} onChange={(e) => setEventType(e.target.value)} />
          <Input label="Target App Key" value={eventTargetApp} onChange={(e) => setEventTargetApp(e.target.value)} />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={emitEventMutation.isPending}
              onClick={() => {
                try {
                  safeJsonParse(eventPayloadJson);
                } catch (error) {
                  showToast({
                    title: "Invalid event payload JSON",
                    description: getApiErrorMessage(error),
                    variant: "error"
                  });
                  return;
                }
                emitEventMutation.mutate();
              }}
              disabled={!eventType.trim() || !eventTargetApp.trim()}
            >
              Emit Event
            </Button>
          </div>
          <div className="md:pt-7">
            <Button
              type="button"
              variant="secondary"
              loading={dispatchOutboxMutation.isPending}
              onClick={() => dispatchOutboxMutation.mutate()}
            >
              Dispatch Due Events
            </Button>
          </div>
          <div className="md:col-span-4">
            <Textarea
              label="Event Payload JSON"
              rows={4}
              value={eventPayloadJson}
              onChange={(event) => setEventPayloadJson(event.target.value)}
            />
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Input
            label="Filter Status"
            value={outboxStatusFilter}
            onChange={(event) => setOutboxStatusFilter(event.target.value)}
          />
          <Input
            label="Filter App Key"
            value={outboxAppFilter}
            onChange={(event) => setOutboxAppFilter(event.target.value)}
          />
          <div className="mt-7">
            <Badge variant="info">{outboxQuery.data.pagination.total} events</Badge>
          </div>
        </div>

        {!outboxQuery.data.items.length ? (
          <div className="mt-3">
            <EmptyState title="No outbox events" description="Emit events to test delivery and retry flow." />
          </div>
        ) : (
          <div className="mt-3 space-y-2">
            {outboxQuery.data.items.map((event) => (
              <article key={event.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">
                      {event.event_type} {"->"} {event.target_app_key}
                    </p>
                    <p className="text-xs text-surface-500">
                      Attempts: {event.attempt_count}/{event.max_attempts}
                    </p>
                  </div>
                  <Badge
                    variant={
                      event.status === "delivered"
                        ? "positive"
                        : event.status === "dead_letter"
                          ? "negative"
                          : "info"
                    }
                  >
                    {event.status}
                  </Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">Updated: {formatDateTime(event.updated_at)}</p>
                {event.last_error ? (
                  <p className="mt-1 text-xs text-red-600">Last error: {event.last_error}</p>
                ) : null}
              </article>
            ))}
            <PaginationControls
              pagination={outboxQuery.data.pagination}
              pageSize={outboxPageSize}
              onPageSizeChange={(size) => {
                setOutboxPageSize(size);
                setOutboxPage(1);
              }}
              onPrev={() => setOutboxPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (outboxQuery.data.pagination.has_next) {
                  setOutboxPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Messaging Connector</h3>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <Input
            label="Provider"
            value={messageProvider}
            onChange={(event) => setMessageProvider(event.target.value)}
          />
          <Input
            label="Recipient"
            value={messageRecipient}
            onChange={(event) => setMessageRecipient(event.target.value)}
            placeholder="+2348012345678"
          />
          <Input
            label="Message Content"
            value={messageContent}
            onChange={(event) => setMessageContent(event.target.value)}
          />
          <div className="md:pt-7">
            <Button
              type="button"
              loading={sendMessageMutation.isPending}
              onClick={() => sendMessageMutation.mutate()}
              disabled={!messageRecipient.trim() || !messageContent.trim()}
            >
              Send Message
            </Button>
          </div>
        </div>

        {!messagesQuery.data.items.length ? (
          <div className="mt-4">
            <EmptyState title="No outbound messages" description="Send messages through a connected provider." />
          </div>
        ) : (
          <div className="mt-4 space-y-2">
            {messagesQuery.data.items.map((message) => (
              <article key={message.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="font-semibold text-surface-700">{message.recipient}</p>
                    <p className="text-xs text-surface-500">{message.content}</p>
                  </div>
                  <Badge variant={message.status === "sent" ? "positive" : "info"}>{message.status}</Badge>
                </div>
                <p className="mt-1 text-xs text-surface-500">
                  Provider: {message.provider} | Created: {formatDateTime(message.created_at)}
                </p>
                {message.error_message ? (
                  <p className="mt-1 text-xs text-red-600">Error: {message.error_message}</p>
                ) : null}
              </article>
            ))}
            <PaginationControls
              pagination={messagesQuery.data.pagination}
              pageSize={messagesPageSize}
              onPageSizeChange={(size) => {
                setMessagesPageSize(size);
                setMessagesPage(1);
              }}
              onPrev={() => setMessagesPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (messagesQuery.data.pagination.has_next) {
                  setMessagesPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>
    </div>
  );
}
