import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { formatDateTime } from "../lib/format";

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
            placeholder="user-id"
            value={actorUserId}
            onChange={(event) => setActorUserId(event.target.value)}
          />
          <Input
            label="Action"
            placeholder="team.member.updated"
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
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {logs.map((entry) => (
                <article key={entry.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <p className="text-sm font-semibold text-surface-700">{entry.action}</p>
                  <p className="mt-1 text-xs text-surface-500">
                    {entry.target_type}
                    {entry.target_id ? ` • ${entry.target_id}` : ""}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">Actor: {entry.actor_user_id}</p>
                  <p className="mt-1 text-xs text-surface-500">{formatDateTime(entry.created_at)}</p>
                </article>
              ))}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Action</th>
                    <th className="px-2 py-2">Target</th>
                    <th className="px-2 py-2">Actor</th>
                    <th className="px-2 py-2">Metadata</th>
                    <th className="px-2 py-2">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {logs.map((entry) => (
                    <tr key={entry.id}>
                      <td className="px-2 py-2 font-semibold text-surface-700">{entry.action}</td>
                      <td className="px-2 py-2 text-surface-600">
                        <p>{entry.target_type}</p>
                        <p className="text-xs text-surface-500">{entry.target_id || "-"}</p>
                      </td>
                      <td className="px-2 py-2 text-surface-600">{entry.actor_user_id}</td>
                      <td className="px-2 py-2 text-xs text-surface-500">
                        {entry.metadata_json
                          ? JSON.stringify(entry.metadata_json).slice(0, 120)
                          : "-"}
                      </td>
                      <td className="px-2 py-2 text-surface-500">{formatDateTime(entry.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

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
