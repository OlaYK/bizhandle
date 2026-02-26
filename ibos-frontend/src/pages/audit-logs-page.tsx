import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditService, teamService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { formatDateTime } from "../lib/format";

const ACTION_LABELS: Record<string, string> = {
  "team.member.added": "Added team member",
  "team.member.updated": "Updated team member",
  "team.member.deactivated": "Deactivated team member",
  "team.invitation.created": "Created team invitation",
  "team.invitation.revoked": "Revoked team invitation",
  "team.invitation.accepted": "Accepted team invitation",
  "customer.create": "Created customer",
  "customer.update": "Updated customer",
  "customer.delete": "Deleted customer",
  "customer.tag.create": "Created customer tag",
  "customer.tag.attach": "Attached customer tag",
  "customer.tag.detach": "Detached customer tag",
  "inventory.stock_in": "Stock added",
  "inventory.adjust": "Adjusted stock",
  "order.create": "Created order",
  "order.status.update": "Updated order status",
  "order.auto_cancel": "Auto-cancelled order",
  "order.convert_to_sale": "Converted order to sale",
  "pos.shift.open": "Opened POS shift",
  "pos.shift.close": "Closed POS shift",
  "pos.offline_orders.sync": "Synced POS offline orders",
  "analytics.mart.refresh": "Refreshed analytics mart"
};

function toHumanLabel(value: string) {
  return value
    .replace(/[._]/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((token, index) =>
      index === 0 ? token.charAt(0).toUpperCase() + token.slice(1) : token.toLowerCase()
    )
    .join(" ");
}

function actionLabel(action: string) {
  return ACTION_LABELS[action] ?? toHumanLabel(action);
}

function targetLabel(targetType: string, targetId: string | null | undefined) {
  const readableType = toHumanLabel(targetType || "record");
  if (!targetId) {
    return readableType;
  }
  return `${readableType} (${targetId.slice(0, 8)}...)`;
}

function stringifyMetadataValue(value: unknown): string {
  if (value === null || value === undefined) {
    return "-";
  }
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return `${value.length} item(s)`;
  }
  if (typeof value === "object") {
    return "object";
  }
  return String(value);
}

function summarizeMetadata(metadata: Record<string, unknown> | null | undefined) {
  if (!metadata) {
    return [];
  }

  const preferredKeys = [
    "email",
    "role",
    "from_status",
    "to_status",
    "payment_method",
    "channel",
    "qty",
    "qty_delta",
    "reason",
    "total",
    "rows_refreshed"
  ];

  const output: Array<{ key: string; value: string }> = [];
  for (const key of preferredKeys) {
    if (!(key in metadata)) {
      continue;
    }
    output.push({ key: toHumanLabel(key), value: stringifyMetadataValue(metadata[key]) });
  }

  if (output.length === 0) {
    const entries = Object.entries(metadata).slice(0, 4);
    for (const [key, value] of entries) {
      output.push({ key: toHumanLabel(key), value: stringifyMetadataValue(value) });
    }
  }
  return output.slice(0, 4);
}

export function AuditLogsPage() {
  const [actorUserId, setActorUserId] = useState("");
  const [action, setAction] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [actorUserId, action, startDate, endDate]);

  const logsQuery = useQuery({
    queryKey: ["audit-logs", actorUserId, action, startDate, endDate, page, pageSize],
    queryFn: () =>
      auditService.list({
        actor_user_id: actorUserId || undefined,
        action: action || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset
      })
  });

  const membersQuery = useQuery({
    queryKey: ["audit-logs", "team-members-lookup"],
    queryFn: () => teamService.list({ include_inactive: true, limit: 200, offset: 0 })
  });

  const actorLookup = useMemo(() => {
    return new Map((membersQuery.data?.items ?? []).map((member) => [member.user_id, member]));
  }, [membersQuery.data]);

  if (logsQuery.isLoading) {
    return <LoadingState label="Loading audit logs..." />;
  }

  if (logsQuery.isError) {
    return (
      <ErrorState
        message="Failed to load audit logs."
        onRetry={() => logsQuery.refetch()}
      />
    );
  }

  const logs = logsQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Audit Filters</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Input
            label="Actor User ID"
            placeholder="Optional actor user ID"
            value={actorUserId}
            onChange={(event) => setActorUserId(event.target.value)}
          />
          <Input
            label="Action"
            placeholder="Optional action key"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />
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
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 font-heading text-lg font-bold text-surface-800">Audit Timeline</h3>
        {logs.length === 0 ? (
          <EmptyState title="No audit logs found" description="Try changing your filters." />
        ) : (
          <div className="space-y-3">
            {logs.map((entry) => {
              const actor = actorLookup.get(entry.actor_user_id);
              const actorName = actor?.full_name || actor?.username || actor?.email || entry.actor_user_id;
              const actorRole = actor?.role || "unknown role";
              const metadataItems = summarizeMetadata(entry.metadata_json);

              return (
                <article key={entry.id} className="rounded-xl border border-surface-100 bg-surface-50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-surface-800">{actionLabel(entry.action)}</p>
                    <Badge variant="info">{formatDateTime(entry.created_at)}</Badge>
                  </div>
                  <p className="mt-1 text-xs text-surface-600">
                    Target: {targetLabel(entry.target_type, entry.target_id)}
                  </p>
                  <p className="mt-1 text-xs text-surface-600">
                    Actor: {actorName} ({actorRole})
                  </p>
                  {metadataItems.length > 0 ? (
                    <div className="mt-2 grid gap-1 sm:grid-cols-2">
                      {metadataItems.map((item) => (
                        <p key={`${entry.id}-${item.key}`} className="text-xs text-surface-500">
                          {item.key}: {item.value}
                        </p>
                      ))}
                    </div>
                  ) : null}
                </article>
              );
            })}

            <PaginationControls
              pagination={logsQuery.data!.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (logsQuery.data?.pagination.has_next) {
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
