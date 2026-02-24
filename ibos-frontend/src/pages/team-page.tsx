import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { teamService } from "../api/services";
import type { TeamInvitationCreateIn, TeamMemberCreateIn, TeamRole } from "../api/types";
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
import { formatDateTime } from "../lib/format";

export function TeamPage() {
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<TeamRole>("staff");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<TeamRole>("staff");
  const [inviteExpiryDays, setInviteExpiryDays] = useState(7);
  const [latestInviteLink, setLatestInviteLink] = useState<string | null>(null);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [busyMembershipId, setBusyMembershipId] = useState<string | null>(null);

  const offset = (page - 1) * pageSize;

  useEffect(() => {
    setPage(1);
  }, [includeInactive]);

  const listQuery = useQuery({
    queryKey: ["team", "members", includeInactive, page, pageSize],
    queryFn: () =>
      teamService.list({
        include_inactive: includeInactive,
        limit: pageSize,
        offset
      })
  });

  const invitationsQuery = useQuery({
    queryKey: ["team", "invitations"],
    queryFn: () => teamService.listInvitations({ status: "pending", limit: 100, offset: 0 })
  });

  const addMutation = useMutation({
    mutationFn: (payload: TeamMemberCreateIn) => teamService.add(payload),
    onSuccess: () => {
      showToast({ title: "Team member added", variant: "success" });
      setEmail("");
      setRole("staff");
      queryClient.invalidateQueries({ queryKey: ["team"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not add member",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const inviteMutation = useMutation({
    mutationFn: (payload: TeamInvitationCreateIn) => teamService.createInvitation(payload),
    onSuccess: (response) => {
      setInviteEmail("");
      setInviteRole("staff");
      setInviteExpiryDays(7);
      const inviteLink = `${window.location.origin}/register?invite=${encodeURIComponent(response.invitation_token)}`;
      setLatestInviteLink(inviteLink);
      showToast({ title: "Invitation created", description: "Share the invite link with the team member.", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["team", "invitations"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not create invitation",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const revokeInvitationMutation = useMutation({
    mutationFn: (invitationId: string) => teamService.revokeInvitation(invitationId),
    onSuccess: () => {
      showToast({ title: "Invitation revoked", variant: "success" });
      queryClient.invalidateQueries({ queryKey: ["team", "invitations"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    },
    onError: (error) => {
      showToast({
        title: "Could not revoke invitation",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  const updateMutation = useMutation({
    mutationFn: ({ membershipId, payload }: { membershipId: string; payload: { role?: TeamRole; is_active?: boolean } }) =>
      teamService.update(membershipId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    }
  });

  const deactivateMutation = useMutation({
    mutationFn: (membershipId: string) => teamService.deactivate(membershipId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team"] });
      queryClient.invalidateQueries({ queryKey: ["audit-logs"] });
    }
  });

  async function copyInviteLink(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      showToast({ title: "Invite link copied", variant: "success" });
    } catch {
      showToast({
        title: "Copy failed",
        description: "Copy the invite link manually.",
        variant: "error"
      });
    }
  }

  function updateMemberRole(membershipId: string, nextRole: TeamRole) {
    setBusyMembershipId(membershipId);
    updateMutation.mutate(
      { membershipId, payload: { role: nextRole } },
      {
        onSuccess: () => {
          showToast({ title: "Role updated", variant: "success" });
        },
        onError: (error) => {
          showToast({
            title: "Role update failed",
            description: getApiErrorMessage(error),
            variant: "error"
          });
        },
        onSettled: () => {
          setBusyMembershipId(null);
        }
      }
    );
  }

  function setMemberActiveState(membershipId: string, isActive: boolean) {
    setBusyMembershipId(membershipId);
    if (!isActive) {
      deactivateMutation.mutate(membershipId, {
        onSuccess: () => {
          showToast({ title: "Member deactivated", variant: "success" });
        },
        onError: (error) => {
          showToast({
            title: "Could not deactivate member",
            description: getApiErrorMessage(error),
            variant: "error"
          });
        },
        onSettled: () => {
          setBusyMembershipId(null);
        }
      });
      return;
    }

    updateMutation.mutate(
      { membershipId, payload: { is_active: true } },
      {
        onSuccess: () => {
          showToast({ title: "Member activated", variant: "success" });
        },
        onError: (error) => {
          showToast({
            title: "Could not activate member",
            description: getApiErrorMessage(error),
            variant: "error"
          });
        },
        onSettled: () => {
          setBusyMembershipId(null);
        }
      }
    );
  }

  if (listQuery.isLoading) {
    return <LoadingState label="Loading team members..." />;
  }

  if (listQuery.isError) {
    return (
      <ErrorState
        message="Failed to load team members."
        onRetry={() => listQuery.refetch()}
      />
    );
  }

  const members = listQuery.data?.items ?? [];

  return (
    <div className="space-y-6">
      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Add Team Member</h3>
        <form
          className="mt-4 grid gap-3 md:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            if (!email.trim()) {
              showToast({
                title: "Email is required",
                variant: "error"
              });
              return;
            }
            addMutation.mutate({ email: email.trim(), role });
          }}
        >
          <Input
            label="Member Email"
            placeholder="staff@example.com"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Select
            label="Role"
            value={role}
            onChange={(event) => setRole(event.target.value as TeamRole)}
          >
            <option value="staff">Staff</option>
            <option value="admin">Admin</option>
            <option value="owner">Owner</option>
          </Select>
          <div className="md:pt-7">
            <Button type="submit" loading={addMutation.isPending} className="w-full md:w-auto">
              Add Member
            </Button>
          </div>
        </form>
      </Card>

      <Card>
        <h3 className="font-heading text-lg font-bold text-surface-800">Invite Team Member</h3>
        <p className="mt-1 text-sm text-surface-600">
          Invite by email before account signup. Share generated link with the invitee.
        </p>
        <form
          className="mt-4 grid gap-3 md:grid-cols-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (!inviteEmail.trim()) {
              showToast({ title: "Invite email is required", variant: "error" });
              return;
            }
            inviteMutation.mutate({
              email: inviteEmail.trim(),
              role: inviteRole,
              expires_in_days: inviteExpiryDays
            });
          }}
        >
          <Input
            label="Invite Email"
            type="email"
            placeholder="new.staff@example.com"
            value={inviteEmail}
            onChange={(event) => setInviteEmail(event.target.value)}
          />
          <Select
            label="Role"
            value={inviteRole}
            onChange={(event) => setInviteRole(event.target.value as TeamRole)}
          >
            <option value="staff">Staff</option>
            <option value="admin">Admin</option>
            <option value="owner">Owner</option>
          </Select>
          <Input
            label="Expiry (days)"
            type="number"
            min={1}
            max={30}
            value={inviteExpiryDays}
            onChange={(event) => setInviteExpiryDays(Number(event.target.value || "7"))}
          />
          <div className="md:pt-7">
            <Button type="submit" loading={inviteMutation.isPending} className="w-full md:w-auto">
              Create Invite
            </Button>
          </div>
        </form>

        {latestInviteLink ? (
          <div className="mt-4 rounded-lg border border-surface-200 bg-surface-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-surface-500">Latest Invite Link</p>
            <p className="mt-1 break-all text-sm text-surface-700">{latestInviteLink}</p>
            <div className="mt-2">
              <Button type="button" size="sm" variant="ghost" onClick={() => copyInviteLink(latestInviteLink)}>
                Copy Link
              </Button>
            </div>
          </div>
        ) : null}

        <div className="mt-4">
          <h4 className="text-sm font-semibold text-surface-700">Pending Invitations</h4>
          <p className="mt-1 text-xs text-surface-500">
            Invite links are only shown once at creation time for security.
          </p>
          {invitationsQuery.isLoading ? (
            <p className="mt-2 text-sm text-surface-500">Loading invitations...</p>
          ) : invitationsQuery.isError ? (
            <p className="mt-2 text-sm text-red-600">Could not load invitations.</p>
          ) : (invitationsQuery.data?.items.length ?? 0) === 0 ? (
            <p className="mt-2 text-sm text-surface-500">No active invitations.</p>
          ) : (
            <div className="mt-2 space-y-2">
              {invitationsQuery.data!.items.map((invitation) => {
                return (
                  <div key={invitation.invitation_id} className="rounded-lg border border-surface-100 bg-surface-50 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-surface-700">{invitation.email}</p>
                        <p className="text-xs text-surface-500">
                          {invitation.role} • expires {formatDateTime(invitation.expires_at)}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="danger"
                          loading={revokeInvitationMutation.isPending}
                          onClick={() => revokeInvitationMutation.mutate(invitation.invitation_id)}
                        >
                          Revoke
                        </Button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Card>

      <Card>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h3 className="font-heading text-lg font-bold text-surface-800">Team Members</h3>
          <label className="inline-flex items-center gap-2 text-sm font-medium text-surface-700">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
            />
            Include inactive
          </label>
        </div>

        {members.length === 0 ? (
          <EmptyState title="No team members" description="Add members to collaborate on operations." />
        ) : (
          <div className="space-y-2">
            <div className="space-y-2 sm:hidden">
              {members.map((member) => {
                const busy = busyMembershipId === member.membership_id;
                return (
                  <article key={member.membership_id} className="rounded-xl border border-surface-100 bg-surface-50 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-surface-700">{member.email}</p>
                      <Badge variant={member.is_active ? "positive" : "negative"}>
                        {member.is_active ? "active" : "inactive"}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-surface-500">
                      {member.full_name || member.username} - {member.role}
                    </p>
                    <p className="mt-1 text-xs text-surface-500">{formatDateTime(member.created_at)}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {member.role !== "admin" ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          loading={busy}
                          onClick={() => updateMemberRole(member.membership_id, "admin")}
                        >
                          Make Admin
                        </Button>
                      ) : null}
                      {member.role !== "staff" ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          loading={busy}
                          onClick={() => updateMemberRole(member.membership_id, "staff")}
                        >
                          Make Staff
                        </Button>
                      ) : null}
                      {member.is_active ? (
                        <Button
                          type="button"
                          size="sm"
                          variant="danger"
                          loading={busy}
                          onClick={() => setMemberActiveState(member.membership_id, false)}
                        >
                          Deactivate
                        </Button>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          loading={busy}
                          onClick={() => setMemberActiveState(member.membership_id, true)}
                        >
                          Activate
                        </Button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>

            <div className="hidden overflow-x-auto sm:block">
              <table className="min-w-full divide-y divide-surface-100 text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase tracking-wide text-surface-500">
                    <th className="px-2 py-2">Member</th>
                    <th className="px-2 py-2">Role</th>
                    <th className="px-2 py-2">Status</th>
                    <th className="px-2 py-2">Created</th>
                    <th className="px-2 py-2">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-50">
                  {members.map((member) => {
                    const busy = busyMembershipId === member.membership_id;
                    return (
                      <tr key={member.membership_id}>
                        <td className="px-2 py-2">
                          <p className="font-semibold text-surface-700">{member.email}</p>
                          <p className="text-xs text-surface-500">{member.full_name || member.username}</p>
                        </td>
                        <td className="px-2 py-2 capitalize text-surface-700">{member.role}</td>
                        <td className="px-2 py-2">
                          <Badge variant={member.is_active ? "positive" : "negative"}>
                            {member.is_active ? "active" : "inactive"}
                          </Badge>
                        </td>
                        <td className="px-2 py-2 text-surface-500">{formatDateTime(member.created_at)}</td>
                        <td className="px-2 py-2">
                          <div className="flex flex-wrap gap-2">
                            {member.role !== "admin" ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                loading={busy}
                                onClick={() => updateMemberRole(member.membership_id, "admin")}
                              >
                                Admin
                              </Button>
                            ) : null}
                            {member.role !== "staff" ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="ghost"
                                loading={busy}
                                onClick={() => updateMemberRole(member.membership_id, "staff")}
                              >
                                Staff
                              </Button>
                            ) : null}
                            {member.is_active ? (
                              <Button
                                type="button"
                                size="sm"
                                variant="danger"
                                loading={busy}
                                onClick={() => setMemberActiveState(member.membership_id, false)}
                              >
                                Deactivate
                              </Button>
                            ) : (
                              <Button
                                type="button"
                                size="sm"
                                variant="secondary"
                                loading={busy}
                                onClick={() => setMemberActiveState(member.membership_id, true)}
                              >
                                Activate
                              </Button>
                            )}
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
    </div>
  );
}
