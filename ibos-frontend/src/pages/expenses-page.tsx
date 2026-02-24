import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { useEffect, useState } from "react";
import { z } from "zod";
import { expenseService } from "../api/services";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatCurrency, formatDateTime } from "../lib/format";

const expenseSchema = z.object({
  category: z.string().min(1, "Category is required"),
  amount: z.coerce.number().positive("Amount must be > 0"),
  note: z.string().optional()
});

type ExpenseFormData = z.infer<typeof expenseSchema>;

export function ExpensesPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [startDate, endDate]);

  const form = useForm<ExpenseFormData>({
    resolver: zodResolver(expenseSchema),
    defaultValues: {
      category: "",
      amount: 0,
      note: ""
    }
  });

  const listQuery = useQuery({
    queryKey: ["expenses", "list", startDate, endDate, page, pageSize],
    queryFn: () =>
      expenseService.list({
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: pageSize,
        offset
      })
  });

  const createMutation = useMutation({
    mutationFn: expenseService.create,
    onSuccess: () => {
      showToast({ title: "Expense saved", variant: "success" });
      form.reset({ category: "", amount: 0, note: "" });
      queryClient.invalidateQueries({ queryKey: ["expenses"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      queryClient.invalidateQueries({ queryKey: ["credit"] });
    },
    onError: (error) => {
      showToast({
        title: "Expense failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  if (listQuery.isLoading) {
    return <LoadingState label="Loading expenses..." />;
  }

  if (listQuery.isError) {
    return <ErrorState message="Failed to load expenses." onRetry={() => listQuery.refetch()} />;
  }

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold">Add Expense</h3>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={form.handleSubmit((values) =>
            createMutation.mutate({
              category: values.category,
              amount: values.amount,
              note: values.note?.trim() || undefined
            })
          )}
        >
          <Input
            label="Category"
            placeholder="Logistics"
            {...form.register("category")}
            error={form.formState.errors.category?.message}
          />
          <Input
            label="Amount"
            type="number"
            step="0.01"
            {...form.register("amount")}
            error={form.formState.errors.amount?.message}
          />
          <div className="md:col-span-2">
            <Textarea label="Note" rows={3} {...form.register("note")} />
          </div>
          <div className="md:col-span-2">
            <Button type="submit" loading={createMutation.isPending}>
              Save Expense
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
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

        {!listQuery.data?.items.length ? (
          <EmptyState title="No expenses found" description="Add your first expense entry." />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {listQuery.data.items.map((expense) => (
                <article key={expense.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-surface-700">{expense.category}</p>
                    <p className="text-sm font-semibold text-red-600">{formatCurrency(expense.amount)}</p>
                  </div>
                  <p className="mt-1 text-xs text-surface-500">{expense.note || "-"}</p>
                  <p className="mt-1 text-xs text-surface-500">{formatDateTime(expense.created_at)}</p>
                </article>
              ))}
            </div>
            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Category</th>
                    <th className="px-2 py-2">Amount</th>
                    <th className="px-2 py-2">Note</th>
                    <th className="px-2 py-2">Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {listQuery.data.items.map((expense) => (
                    <tr key={expense.id}>
                      <td className="px-2 py-2 font-semibold text-surface-700">{expense.category}</td>
                      <td className="px-2 py-2 font-semibold text-red-600">{formatCurrency(expense.amount)}</td>
                      <td className="px-2 py-2 text-surface-500">{expense.note || "-"}</td>
                      <td className="px-2 py-2 text-surface-500">{formatDateTime(expense.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PaginationControls
              pagination={listQuery.data.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (listQuery.data.pagination.has_next) {
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
