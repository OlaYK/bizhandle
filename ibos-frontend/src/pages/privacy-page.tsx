import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, LockKeyhole, Trash2 } from "lucide-react";
import { useState } from "react";
import { privacyService } from "../api/services";
import type { CustomerPiiExportOut } from "../api/types";
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

function csvCell(value: string | number | null | undefined) {
  const text = value === null || value === undefined ? "" : String(value);
  return `"${text.replace(/"/g, "\"\"")}"`;
}

function buildPiiExportCsv(payload: CustomerPiiExportOut) {
  const lines: string[] = ["section,field,value,context"];
  const pushRow = (
    section: string,
    field: string,
    value: string | number | null | undefined,
    context?: string | null
  ) => {
    lines.push(
      [csvCell(section), csvCell(field), csvCell(value), csvCell(context ?? "")].join(",")
    );
  };

  pushRow("summary", "customer_id", payload.customer_id);
  pushRow("summary", "exported_at", payload.exported_at);

  for (const [key, value] of Object.entries(payload.customer ?? {})) {
    pushRow("customer", key, typeof value === "object" ? JSON.stringify(value) : String(value ?? ""));
  }

  for (const order of payload.orders ?? []) {
    pushRow("order", "id", order.id, `status=${order.status}, channel=${order.channel}`);
    pushRow("order", "total_amount", order.total_amount, order.created_at);
  }

  for (const invoice of payload.invoices ?? []) {
    pushRow("invoice", "id", invoice.id, `status=${invoice.status}, currency=${invoice.currency}`);
    pushRow(
      "invoice",
      "amounts",
      `${invoice.total_amount} / paid ${invoice.amount_paid}`,
      invoice.created_at
    );
  }

  return lines.join("\n");
}

function buildPiiExportPreview(payload: CustomerPiiExportOut) {
  const customerKeys = Object.keys(payload.customer ?? {});
  return [
    `Customer ID: ${payload.customer_id}`,
    `Exported At: ${payload.exported_at}`,
    `Customer fields: ${customerKeys.join(", ") || "-"}`,
    `Orders: ${payload.orders?.length ?? 0}`,
    `Invoices: ${payload.invoices?.length ?? 0}`
  ].join("\n");
}

export function PrivacyPage() {
  const { showToast } = useToast();
  const [customerId, setCustomerId] = useState("");
  const [exportPayload, setExportPayload] = useState("");
  const [exportCsv, setExportCsv] = useState("");
  const [exportFilename, setExportFilename] = useState("customer-pii-export.csv");
  const [cutoffDate, setCutoffDate] = useState(toDateInputValue(new Date()));

  const matrixQuery = useQuery({
    queryKey: ["privacy", "rbac-matrix"],
    queryFn: () => privacyService.rbacMatrix()
  });

  const exportMutation = useMutation({
    mutationFn: (id: string) => privacyService.exportCustomer(id),
    onSuccess: (result) => {
      setExportPayload(buildPiiExportPreview(result));
      setExportCsv(buildPiiExportCsv(result));
      setExportFilename(`customer-pii-export-${result.customer_id.slice(0, 8)}.csv`);
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

  function downloadExportCsv() {
    if (!exportCsv) {
      return;
    }
    const blob = new Blob([exportCsv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFilename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

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
        <div className="mt-4 grid gap-3 md:grid-cols-4">
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
              variant="ghost"
              onClick={downloadExportCsv}
              disabled={!exportCsv}
            >
              <Download className="h-4 w-4" />
              Download CSV
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
        <Textarea
          label="PII Export Preview"
          rows={12}
          value={exportPayload}
          onChange={(event) => setExportPayload(event.target.value)}
        />
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
