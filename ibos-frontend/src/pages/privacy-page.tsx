import { useMutation, useQuery } from "@tanstack/react-query";
import { LockKeyhole, Trash2 } from "lucide-react";
import { useState } from "react";
import { privacyService } from "../api/services";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";

function toDateInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function PrivacyPage() {
  const { showToast } = useToast();
  const [customerId, setCustomerId] = useState("");
  const [exportPayload, setExportPayload] = useState("");
  const [cutoffDate, setCutoffDate] = useState(toDateInputValue(new Date()));

  const matrixQuery = useQuery({
    queryKey: ["privacy", "rbac-matrix"],
    queryFn: () => privacyService.rbacMatrix()
  });

  const exportMutation = useMutation({
    mutationFn: (id: string) => privacyService.exportCustomer(id),
    onSuccess: (result) => {
      setExportPayload(JSON.stringify(result, null, 2));
      showToast({ title: "Customer export ready", variant: "success" });
    },
    onError: (error) => {
      showToast({
        title: "Export failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => privacyService.deleteCustomer(id),
    onSuccess: () => {
      showToast({
        title: "PII anonymized",
        description: "Customer personal fields were removed.",
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Delete failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const archiveMutation = useMutation({
    mutationFn: () =>
      privacyService.archiveAuditLogs({
        cutoff_date: cutoffDate,
        delete_archived: true
      }),
    onSuccess: (result) => {
      showToast({
        title: "Audit archive complete",
        description: `${result.records_count} records archived.`,
        variant: "success"
      });
    },
    onError: (error) => {
      showToast({
        title: "Archive failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (matrixQuery.isLoading) {
    return <LoadingState label="Loading privacy controls..." />;
  }

  if (matrixQuery.isError) {
    return <ErrorState message="Failed to load privacy controls." onRetry={() => matrixQuery.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <Card>
        <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
          <LockKeyhole className="h-4 w-4" />
          Security and Privacy
        </p>
        <h3 className="font-heading text-lg font-bold">RBAC v2 and Data Privacy Controls</h3>
        <div className="mt-4 flex flex-wrap gap-2">
          {(matrixQuery.data?.items ?? []).map((item) => (
            <Badge key={item.role} variant="info">
              {item.role}: {item.permissions.length} permissions
            </Badge>
          ))}
        </div>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold">Customer PII Export / Delete</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <Input label="Customer ID" value={customerId} onChange={(event) => setCustomerId(event.target.value)} />
          <div className="mt-7">
            <Button
              type="button"
              variant="ghost"
              onClick={() => exportMutation.mutate(customerId.trim())}
              disabled={!customerId.trim()}
              loading={exportMutation.isPending}
            >
              Export PII
            </Button>
          </div>
          <div className="mt-7">
            <Button
              type="button"
              variant="secondary"
              onClick={() => deleteMutation.mutate(customerId.trim())}
              disabled={!customerId.trim()}
              loading={deleteMutation.isPending}
            >
              <Trash2 className="h-4 w-4" />
              Delete PII
            </Button>
          </div>
        </div>
        <Textarea label="PII Export Result" rows={12} value={exportPayload} onChange={(event) => setExportPayload(event.target.value)} />
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold">Immutable Audit Archive</h3>
        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <Input label="Cutoff Date" type="date" value={cutoffDate} onChange={(event) => setCutoffDate(event.target.value)} />
          <div className="mt-7">
            <Button type="button" onClick={() => archiveMutation.mutate()} loading={archiveMutation.isPending}>
              Archive Audit Logs
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
