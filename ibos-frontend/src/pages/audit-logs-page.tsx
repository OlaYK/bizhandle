import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { auditService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

export function AuditLogsPage() {
  const { showToast } = useToast();
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
    queryKey: [
      "audit-logs",
      actorUserId,
      action,
      startDate,
      endDate,
      page,
      pageSize,
    ],
    queryFn: () =>
      auditService.list({
        actor_user_id: actorUserId || undefined,
        action: action || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset,
      }),
  });

  const exportMutation = useMutation({
    mutationFn: (format: "csv" | "pdf") =>
      auditService.export({
        format,
        actor_user_id: actorUserId || undefined,
        action: action || undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
      }),
    onSuccess: (result) => {
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      showToast({
        title: "Audit export ready",
        description: "Audit log export downloaded successfully.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Audit export failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
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
        <h3 className="font-heading text-lg font-bold text-surface-800">
          Audit Filters
        </h3>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Input
            label="Actor User ID"
            placeholder="user-id"
            value={actorUserId}
            onChange={(event) => setActorUserId(event.target.value)}
          />
          <Input
            label="Action"
            placeholder="invoice.create"
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
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            type="button"
            variant="ghost"
            loading={
              exportMutation.isPending && exportMutation.variables === "csv"
            }
            onClick={() => exportMutation.mutate("csv")}
          >
            <Download className="h-4 w-4" />
            Export CSV
          </Button>
          <Button
            type="button"
            variant="secondary"
            loading={
              exportMutation.isPending && exportMutation.variables === "pdf"
            }
            onClick={() => exportMutation.mutate("pdf")}
          >
            <Download className="h-4 w-4" />
            Export PDF
          </Button>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 font-heading text-lg font-bold text-surface-800">
          Audit Timeline
        </h3>
        {logs.length === 0 ? (
          <EmptyState
            title="No audit logs found"
            description="Try changing your filters."
          />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {logs.map((entry) => (
                <article
                  key={entry.id}
                  className="rounded-xl border border-surface-100 bg-surface-50 p-3"
                >
                  <p className="text-sm font-semibold text-surface-700">
                    {entry.summary}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    {entry.target_label || entry.target_type}
                  </p>
                  <p className="mt-1 text-xs text-surface-500">
                    Actor:{" "}
                    {entry.actor_name ||
                      entry.actor_username ||
                      entry.actor_user_id}
                  </p>
                  {entry.metadata_preview.length ? (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {entry.metadata_preview.map((item) => (
                        <Badge key={`${entry.id}-${item}`} variant="neutral">
                          {item}
                        </Badge>
                      ))}
                    </div>
                  ) : null}
                  <p className="mt-2 text-xs text-surface-500">
                    {formatDateTime(entry.created_at)}
                  </p>
                </article>
              ))}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Summary</th>
                    <th className="px-2 py-2">Target</th>
                    <th className="px-2 py-2">Actor</th>
                    <th className="px-2 py-2">Metadata</th>
                    <th className="px-2 py-2">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {logs.map((entry) => (
                    <tr key={entry.id}>
                      <td className="px-2 py-2 font-semibold text-surface-700">
                        {entry.summary}
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        <p>{entry.target_label || entry.target_type}</p>
                        <p className="text-xs text-surface-500">
                          {entry.target_id || "-"}
                        </p>
                      </td>
                      <td className="px-2 py-2 text-surface-600">
                        <p>{entry.actor_name || entry.actor_username || "-"}</p>
                        <p className="text-xs text-surface-500">
                          {entry.actor_role || "-"}
                          {entry.actor_email ? ` · ${entry.actor_email}` : ""}
                        </p>
                      </td>
                      <td className="px-2 py-2 text-xs text-surface-500">
                        {entry.metadata_preview.length
                          ? entry.metadata_preview.join(" • ")
                          : "-"}
                      </td>
                      <td className="px-2 py-2 text-surface-500">
                        {formatDateTime(entry.created_at)}
                      </td>
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
