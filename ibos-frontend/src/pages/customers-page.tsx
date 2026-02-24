import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Tag, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { customerService } from "../api/services";
import type { CustomerOut } from "../api/types";
import { EmptyState } from "../components/state/empty-state";
import { ErrorState } from "../components/state/error-state";
import { LoadingState } from "../components/state/loading-state";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Modal } from "../components/ui/modal";
import { PaginationControls } from "../components/ui/pagination-controls";
import { Select } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

const createCustomerSchema = z.object({
  name: z.string().min(2, "Name is required"),
  phone: z.string().optional(),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  note: z.string().optional(),
  tag_ids: z.array(z.string()).default([])
});

const editCustomerSchema = z.object({
  name: z.string().min(2, "Name is required"),
  phone: z.string().optional(),
  email: z.string().email("Invalid email").optional().or(z.literal("")),
  note: z.string().optional()
});

type CreateCustomerFormData = z.infer<typeof createCustomerSchema>;
type EditCustomerFormData = z.infer<typeof editCustomerSchema>;

export function CustomersPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [search, setSearch] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const [newTagName, setNewTagName] = useState("");
  const [newTagColor, setNewTagColor] = useState("");
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [attachTagSelection, setAttachTagSelection] = useState<Record<string, string>>({});
  const [editingCustomer, setEditingCustomer] = useState<CustomerOut | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [search, tagFilter]);

  const tagsQuery = useQuery({
    queryKey: ["customers", "tags"],
    queryFn: () => customerService.listTags()
  });

  const listQuery = useQuery({
    queryKey: ["customers", "list", search, tagFilter, page, pageSize],
    queryFn: () =>
      customerService.list({
        q: search.trim() || undefined,
        tag_id: tagFilter || undefined,
        limit: pageSize,
        offset
      })
  });

  const createForm = useForm<CreateCustomerFormData>({
    resolver: zodResolver(createCustomerSchema),
    defaultValues: {
      name: "",
      phone: "",
      email: "",
      note: "",
      tag_ids: []
    }
  });

  const editForm = useForm<EditCustomerFormData>({
    resolver: zodResolver(editCustomerSchema),
    defaultValues: {
      name: "",
      phone: "",
      email: "",
      note: ""
    }
  });

  useEffect(() => {
    if (!editingCustomer) return;
    editForm.reset({
      name: editingCustomer.name,
      phone: editingCustomer.phone ?? "",
      email: editingCustomer.email ?? "",
      note: editingCustomer.note ?? ""
    });
  }, [editingCustomer, editForm]);

  const createCustomerMutation = useMutation({
    mutationFn: customerService.create,
    onSuccess: () => {
      showToast({ title: "Customer created", variant: "success" });
      createForm.reset({ name: "", phone: "", email: "", note: "", tag_ids: [] });
      setSelectedTagIds([]);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create customer",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const updateCustomerMutation = useMutation({
    mutationFn: ({ customerId, payload }: { customerId: string; payload: EditCustomerFormData }) =>
      customerService.update(customerId, {
        name: payload.name.trim(),
        phone: payload.phone?.trim() || undefined,
        email: payload.email?.trim() || undefined,
        note: payload.note?.trim() || undefined
      }),
    onSuccess: () => {
      showToast({ title: "Customer updated", variant: "success" });
      setEditingCustomer(null);
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Update failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const deleteCustomerMutation = useMutation({
    mutationFn: (customerId: string) => customerService.remove(customerId),
    onSuccess: () => {
      showToast({ title: "Customer deleted", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Delete failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const createTagMutation = useMutation({
    mutationFn: customerService.createTag,
    onSuccess: () => {
      showToast({ title: "Tag created", variant: "success" });
      setNewTagName("");
      setNewTagColor("");
      queryClient.invalidateQueries({ queryKey: ["customers", "tags"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Tag creation failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const attachTagMutation = useMutation({
    mutationFn: ({ customerId, tagId }: { customerId: string; tagId: string }) =>
      customerService.attachTag(customerId, tagId),
    onSuccess: () => {
      showToast({ title: "Tag attached", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Tag attach failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const detachTagMutation = useMutation({
    mutationFn: ({ customerId, tagId }: { customerId: string; tagId: string }) =>
      customerService.detachTag(customerId, tagId),
    onSuccess: () => {
      showToast({ title: "Tag detached", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Tag detach failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const tags = tagsQuery.data?.items ?? [];
  const customers = listQuery.data?.items ?? [];

  const tagOptionsByCustomer = useMemo(() => {
    const map: Record<string, typeof tags> = {};
    for (const customer of customers) {
      const currentTagIds = new Set(customer.tags.map((tag) => tag.id));
      map[customer.id] = tags.filter((tag) => !currentTagIds.has(tag.id));
    }
    return map;
  }, [customers, tags]);

  if (tagsQuery.isLoading || listQuery.isLoading) {
    return <LoadingState label="Loading CRM workspace..." />;
  }

  if (tagsQuery.isError || listQuery.isError) {
    return (
      <ErrorState
        message="Failed to load customer workspace."
        onRetry={() => {
          tagsQuery.refetch();
          listQuery.refetch();
        }}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <h3 className="font-heading text-lg font-bold">Create Customer</h3>
          <form
            className="mt-4 grid gap-3"
            onSubmit={createForm.handleSubmit((values) =>
              createCustomerMutation.mutate({
                name: values.name.trim(),
                phone: values.phone?.trim() || undefined,
                email: values.email?.trim() || undefined,
                note: values.note?.trim() || undefined,
                tag_ids: selectedTagIds
              })
            )}
          >
            <Input
              label="Name"
              placeholder="Aisha Bello"
              {...createForm.register("name")}
              error={createForm.formState.errors.name?.message}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Phone" placeholder="+2348012345678" {...createForm.register("phone")} />
              <Input
                label="Email"
                type="email"
                placeholder="customer@example.com"
                {...createForm.register("email")}
                error={createForm.formState.errors.email?.message}
              />
            </div>
            <Textarea label="Note" rows={3} {...createForm.register("note")} />
            <div className="space-y-2">
              <p className="text-sm font-semibold text-surface-700">Initial Tags</p>
              <div className="flex flex-wrap gap-2">
                {tags.map((tag) => {
                  const selected = selectedTagIds.includes(tag.id);
                  return (
                    <button
                      key={tag.id}
                      type="button"
                      className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                        selected
                          ? "border-cobalt-500 bg-cobalt-100 text-cobalt-700"
                          : "border-surface-200 text-surface-600 hover:border-surface-400"
                      }`}
                      onClick={() =>
                        setSelectedTagIds((current) =>
                          selected ? current.filter((id) => id !== tag.id) : [...current, tag.id]
                        )
                      }
                    >
                      {tag.name}
                    </button>
                  );
                })}
              </div>
            </div>
            <Button type="submit" loading={createCustomerMutation.isPending}>
              Add Customer
            </Button>
          </form>
        </Card>

        <Card>
          <h3 className="font-heading text-lg font-bold">Tag Manager</h3>
          <div className="mt-4 grid gap-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Input
                label="Tag Name"
                placeholder="VIP"
                value={newTagName}
                onChange={(event) => setNewTagName(event.target.value)}
              />
              <Input
                label="Color (optional)"
                placeholder="#16a34a"
                value={newTagColor}
                onChange={(event) => setNewTagColor(event.target.value)}
              />
            </div>
            <Button
              type="button"
              variant="secondary"
              loading={createTagMutation.isPending}
              onClick={() => {
                const normalizedName = newTagName.trim();
                if (!normalizedName) {
                  showToast({ title: "Tag name is required", variant: "error" });
                  return;
                }
                createTagMutation.mutate({
                  name: normalizedName,
                  color: newTagColor.trim() || undefined
                });
              }}
            >
              <Plus className="h-4 w-4" />
              Create Tag
            </Button>
            <div className="rounded-xl border border-surface-100 bg-surface-50 p-3">
              <p className="mb-2 text-sm font-semibold text-surface-700">Existing Tags</p>
              {!tags.length ? (
                <p className="text-sm text-surface-500">No tags yet.</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {tags.map((tag) => (
                    <Badge key={tag.id} variant="info">
                      {tag.name}
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>
        </Card>
      </div>

      <Card>
        <div className="mb-4 grid gap-3 md:grid-cols-4">
          <Input
            label="Search"
            placeholder="Name, phone, email"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <Select label="Filter Tag" value={tagFilter} onChange={(event) => setTagFilter(event.target.value)}>
            <option value="">All tags</option>
            {tags.map((tag) => (
              <option key={tag.id} value={tag.id}>
                {tag.name}
              </option>
            ))}
          </Select>
          <div className="mt-7">
            <Badge variant="info">{listQuery.data?.pagination.total ?? 0} customers</Badge>
          </div>
        </div>

        {!customers.length ? (
          <EmptyState title="No customers found" description="Add customers or adjust your filters." />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {customers.map((customer) => {
                const attachOptions = tagOptionsByCustomer[customer.id] ?? [];
                const selectedAttachTagId = attachTagSelection[customer.id] ?? attachOptions[0]?.id ?? "";
                return (
                  <article key={customer.id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-surface-700">{customer.name}</p>
                        <p className="text-xs text-surface-500">{customer.email || customer.phone || "-"}</p>
                      </div>
                      <div className="flex gap-1">
                        <Button type="button" size="sm" variant="ghost" onClick={() => setEditingCustomer(customer)}>
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="danger"
                          onClick={() => deleteCustomerMutation.mutate(customer.id)}
                          loading={deleteCustomerMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">{customer.note || "-"}</p>
                    <p className="mt-1 text-xs text-surface-500">{formatDateTime(customer.created_at)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {customer.tags.map((tag) => (
                        <button
                          key={tag.id}
                          type="button"
                          className="inline-flex items-center gap-1 rounded-full border border-surface-200 bg-white px-2 py-1 text-xs font-semibold text-surface-700"
                          onClick={() => detachTagMutation.mutate({ customerId: customer.id, tagId: tag.id })}
                        >
                          {tag.name}
                          <Trash2 className="h-3 w-3" />
                        </button>
                      ))}
                    </div>
                    <div className="mt-3 grid grid-cols-[1fr_auto] gap-2">
                      <select
                        className="h-9 rounded border border-surface-200 bg-white px-2 text-sm"
                        value={selectedAttachTagId}
                        onChange={(event) =>
                          setAttachTagSelection((state) => ({
                            ...state,
                            [customer.id]: event.target.value
                          }))
                        }
                        disabled={!attachOptions.length}
                      >
                        {attachOptions.length ? null : <option value="">No more tags</option>}
                        {attachOptions.map((tag) => (
                          <option key={tag.id} value={tag.id}>
                            {tag.name}
                          </option>
                        ))}
                      </select>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        disabled={!selectedAttachTagId}
                        onClick={() =>
                          attachTagMutation.mutate({
                            customerId: customer.id,
                            tagId: selectedAttachTagId
                          })
                        }
                      >
                        <Tag className="h-4 w-4" />
                        Add
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Customer</th>
                    <th className="px-2 py-2">Contact</th>
                    <th className="px-2 py-2">Tags</th>
                    <th className="px-2 py-2">Created</th>
                    <th className="px-2 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {customers.map((customer) => {
                    const attachOptions = tagOptionsByCustomer[customer.id] ?? [];
                    const selectedAttachTagId = attachTagSelection[customer.id] ?? attachOptions[0]?.id ?? "";
                    return (
                      <tr key={customer.id}>
                        <td className="px-2 py-2">
                          <p className="font-semibold text-surface-700">{customer.name}</p>
                          <p className="text-xs text-surface-500">{customer.note || "-"}</p>
                        </td>
                        <td className="px-2 py-2 text-surface-600">
                          <p>{customer.email || "-"}</p>
                          <p className="text-xs text-surface-500">{customer.phone || "-"}</p>
                        </td>
                        <td className="px-2 py-2">
                          <div className="flex flex-wrap gap-1">
                            {customer.tags.map((tag) => (
                              <button
                                key={tag.id}
                                type="button"
                                className="inline-flex items-center gap-1 rounded-full border border-surface-200 bg-white px-2 py-1 text-xs font-semibold text-surface-700"
                                onClick={() =>
                                  detachTagMutation.mutate({ customerId: customer.id, tagId: tag.id })
                                }
                              >
                                {tag.name}
                                <Trash2 className="h-3 w-3" />
                              </button>
                            ))}
                            {!customer.tags.length ? <span className="text-xs text-surface-500">-</span> : null}
                          </div>
                        </td>
                        <td className="px-2 py-2 text-surface-500">{formatDateTime(customer.created_at)}</td>
                        <td className="px-2 py-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <select
                              className="h-9 rounded border border-surface-200 bg-white px-2 text-sm"
                              value={selectedAttachTagId}
                              onChange={(event) =>
                                setAttachTagSelection((state) => ({
                                  ...state,
                                  [customer.id]: event.target.value
                                }))
                              }
                              disabled={!attachOptions.length}
                            >
                              {attachOptions.length ? null : <option value="">No more tags</option>}
                              {attachOptions.map((tag) => (
                                <option key={tag.id} value={tag.id}>
                                  {tag.name}
                                </option>
                              ))}
                            </select>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled={!selectedAttachTagId}
                              onClick={() =>
                                attachTagMutation.mutate({
                                  customerId: customer.id,
                                  tagId: selectedAttachTagId
                                })
                              }
                            >
                              Add Tag
                            </Button>
                            <Button type="button" size="sm" variant="ghost" onClick={() => setEditingCustomer(customer)}>
                              Edit
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="danger"
                              onClick={() => deleteCustomerMutation.mutate(customer.id)}
                              loading={deleteCustomerMutation.isPending}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <PaginationControls
              pagination={listQuery.data!.pagination}
              pageSize={pageSize}
              onPageSizeChange={(size) => {
                setPageSize(size);
                setPage(1);
              }}
              onPrev={() => setPage((value) => Math.max(1, value - 1))}
              onNext={() => {
                if (listQuery.data?.pagination.has_next) {
                  setPage((value) => value + 1);
                }
              }}
            />
          </div>
        )}
      </Card>

      <Modal open={Boolean(editingCustomer)} title="Edit Customer" onClose={() => setEditingCustomer(null)}>
        {!editingCustomer ? null : (
          <form
            className="grid gap-3"
            onSubmit={editForm.handleSubmit((values) =>
              updateCustomerMutation.mutate({
                customerId: editingCustomer.id,
                payload: values
              })
            )}
          >
            <Input
              label="Name"
              {...editForm.register("name")}
              error={editForm.formState.errors.name?.message}
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <Input label="Phone" {...editForm.register("phone")} />
              <Input
                label="Email"
                type="email"
                {...editForm.register("email")}
                error={editForm.formState.errors.email?.message}
              />
            </div>
            <Textarea label="Note" rows={3} {...editForm.register("note")} />
            <div className="flex justify-end gap-2">
              <Button type="button" variant="ghost" onClick={() => setEditingCustomer(null)}>
                Cancel
              </Button>
              <Button type="submit" variant="secondary" loading={updateCustomerMutation.isPending}>
                Save
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
}
