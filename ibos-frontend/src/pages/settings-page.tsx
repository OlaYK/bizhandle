import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Moon, Sun, SunMoon } from "lucide-react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { authService, teamService } from "../api/services";
import { LoadingState } from "../components/state/loading-state";
import { ErrorState } from "../components/state/error-state";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Modal } from "../components/ui/modal";
import { Select } from "../components/ui/select";
import { useAuth } from "../hooks/use-auth";
import { useTheme, type ThemeMode } from "../hooks/use-theme";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { formatDateTime } from "../lib/format";

const profileSchema = z.object({
  full_name: z.string().min(2, "Full name must be at least 2 characters"),
  username: z
    .string()
    .min(3, "Username must be at least 3 characters")
    .regex(/^[a-zA-Z0-9_]+$/, "Use letters, numbers, or underscores"),
  business_name: z
    .string()
    .min(2, "Business name must be at least 2 characters"),
  pending_order_timeout_minutes: z.coerce
    .number()
    .int("Use a whole number")
    .min(1, "Minimum is 1 minute")
    .max(10080, "Maximum is 10080 minutes"),
});

const passwordSchema = z
  .object({
    current_password: z.string().min(1, "Current password is required"),
    new_password: z
      .string()
      .min(8, "New password must be at least 8 characters"),
    confirm_password: z.string().min(8, "Confirm the new password"),
  })
  .refine((value) => value.new_password === value.confirm_password, {
    path: ["confirm_password"],
    message: "Passwords do not match",
  });

type ProfileFormData = z.infer<typeof profileSchema>;
type PasswordFormData = z.infer<typeof passwordSchema>;

export function SettingsPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { tokens, clearAuth } = useAuth();
  const { showToast } = useToast();
  const { theme, resolvedTheme, setTheme } = useTheme();
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [inviteTokenInput, setInviteTokenInput] = useState("");

  const profileForm = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      full_name: "",
      username: "",
      business_name: "",
      pending_order_timeout_minutes: 60,
    },
  });

  const passwordForm = useForm<PasswordFormData>({
    resolver: zodResolver(passwordSchema),
    defaultValues: {
      current_password: "",
      new_password: "",
      confirm_password: "",
    },
  });

  const profileQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: authService.me,
  });

  useEffect(() => {
    if (!profileQuery.data) return;
    profileForm.reset({
      full_name: profileQuery.data.full_name ?? "",
      username: profileQuery.data.username ?? "",
      business_name: profileQuery.data.business_name ?? "",
      pending_order_timeout_minutes:
        profileQuery.data.pending_order_timeout_minutes,
    });
  }, [profileQuery.data, profileForm]);

  const updateProfileMutation = useMutation({
    mutationFn: authService.updateProfile,
    onSuccess: (profile) => {
      profileForm.reset({
        full_name: profile.full_name ?? "",
        username: profile.username ?? "",
        business_name: profile.business_name ?? "",
        pending_order_timeout_minutes: profile.pending_order_timeout_minutes,
      });
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      showToast({
        title: "Profile updated",
        description: "Your account details were saved.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Profile update failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const changePasswordMutation = useMutation({
    mutationFn: authService.changePassword,
    onSuccess: () => {
      passwordForm.reset();
      showToast({
        title: "Password updated",
        description: "All active refresh sessions are revoked.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Password change failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: async () => {
      if (tokens?.refreshToken) {
        await authService.logout({ refresh_token: tokens.refreshToken });
      }
    },
    onSettled: () => {
      clearAuth();
      navigate("/login", { replace: true });
    },
  });

  const acceptInvitationMutation = useMutation({
    mutationFn: (invitationToken: string) =>
      teamService.acceptInvitation({ invitation_token: invitationToken }),
    onSuccess: () => {
      setInviteTokenInput("");
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({ queryKey: ["team"] });
      showToast({
        title: "Invitation accepted",
        description: "You now have access to the invited workspace.",
        variant: "success",
      });
    },
    onError: (error) => {
      showToast({
        title: "Could not accept invitation",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  if (profileQuery.isLoading) {
    return <LoadingState label="Loading settings..." />;
  }

  if (profileQuery.isError || !profileQuery.data) {
    return (
      <ErrorState
        message="Failed to load your account settings."
        onRetry={() => profileQuery.refetch()}
      />
    );
  }

  const profile = profileQuery.data;
  const saveDisabled =
    !profileForm.formState.isDirty || updateProfileMutation.isPending;

  return (
    <div className="space-y-6">
      <Card className="animate-fade-up">
        <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
          Profile
        </h3>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-300">
          Update your account identity and workspace name.
        </p>
        <form
          className="mt-4 grid gap-3 md:grid-cols-2"
          onSubmit={profileForm.handleSubmit((values) =>
            updateProfileMutation.mutate({
              full_name: values.full_name.trim(),
              username: values.username.trim(),
              business_name: values.business_name.trim(),
              pending_order_timeout_minutes:
                values.pending_order_timeout_minutes,
            }),
          )}
        >
          <Input
            label="Full Name"
            {...profileForm.register("full_name")}
            error={profileForm.formState.errors.full_name?.message}
          />
          <Input
            label="Email"
            value={profile.email}
            disabled
            className="opacity-80"
          />
          <Input
            label="Username"
            {...profileForm.register("username")}
            error={profileForm.formState.errors.username?.message}
          />
          <Input
            label="Business Name"
            {...profileForm.register("business_name")}
            error={profileForm.formState.errors.business_name?.message}
          />
          <Input
            label="Pending Order Timeout (mins)"
            type="number"
            {...profileForm.register("pending_order_timeout_minutes")}
            error={
              profileForm.formState.errors.pending_order_timeout_minutes
                ?.message
            }
          />
          <div className="md:col-span-2">
            <Button
              type="submit"
              loading={updateProfileMutation.isPending}
              disabled={saveDisabled}
            >
              Save Profile
            </Button>
          </div>
        </form>
      </Card>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card className="animate-fade-up [animation-delay:70ms]">
          <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
            Appearance
          </h3>
          <p className="mt-1 text-sm text-surface-600 dark:text-surface-300">
            Choose how MoniDesk looks on this device.
          </p>
          <div className="mt-4 grid gap-3">
            <Select
              label="Theme Mode"
              value={theme}
              onChange={(event) => setTheme(event.target.value as ThemeMode)}
            >
              <option value="system">System</option>
              <option value="light">Light</option>
              <option value="dark">Dark</option>
            </Select>
            <div className="grid grid-cols-3 gap-2">
              <button
                type="button"
                onClick={() => setTheme("light")}
                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  theme === "light"
                    ? "border-cobalt-500 bg-cobalt-100 text-cobalt-700"
                    : "border-surface-200 text-surface-600 hover:bg-surface-50 dark:border-surface-600 dark:text-surface-200 dark:hover:bg-surface-700/50"
                }`}
              >
                <Sun className="h-4 w-4" /> Light
              </button>
              <button
                type="button"
                onClick={() => setTheme("dark")}
                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  theme === "dark"
                    ? "border-cobalt-500 bg-cobalt-100 text-cobalt-700"
                    : "border-surface-200 text-surface-600 hover:bg-surface-50 dark:border-surface-600 dark:text-surface-200 dark:hover:bg-surface-700/50"
                }`}
              >
                <Moon className="h-4 w-4" /> Dark
              </button>
              <button
                type="button"
                onClick={() => setTheme("system")}
                className={`flex items-center justify-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                  theme === "system"
                    ? "border-cobalt-500 bg-cobalt-100 text-cobalt-700"
                    : "border-surface-200 text-surface-600 hover:bg-surface-50 dark:border-surface-600 dark:text-surface-200 dark:hover:bg-surface-700/50"
                }`}
              >
                <SunMoon className="h-4 w-4" /> System
              </button>
            </div>
            <p className="text-xs text-surface-500 dark:text-surface-300">
              Active theme:{" "}
              <span className="font-semibold capitalize">{resolvedTheme}</span>
            </p>
          </div>
        </Card>

        <Card className="animate-fade-up [animation-delay:100ms]">
          <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
            Workspace Info
          </h3>
          <div className="mt-4 space-y-2 text-sm text-surface-600 dark:text-surface-200">
            <p>
              <span className="font-semibold text-surface-700 dark:text-surface-100">
                Account ID:
              </span>{" "}
              {profile.id}
            </p>
            <p>
              <span className="font-semibold text-surface-700 dark:text-surface-100">
                Created:
              </span>{" "}
              {formatDateTime(profile.created_at)}
            </p>
            <p>
              <span className="font-semibold text-surface-700 dark:text-surface-100">
                Last Updated:
              </span>{" "}
              {formatDateTime(profile.updated_at)}
            </p>
            <p>
              <span className="font-semibold text-surface-700 dark:text-surface-100">
                API Base URL:
              </span>{" "}
              <code className="rounded bg-surface-100 px-2 py-1 text-xs dark:bg-surface-800 dark:text-surface-100">
                {import.meta.env.VITE_API_BASE_URL}
              </code>
            </p>
            <p className="pt-2">
              <Link
                to="/storefront-settings"
                className="inline-flex rounded-lg bg-surface-100 px-3 py-2 text-xs font-semibold text-surface-800 transition hover:bg-surface-200 dark:bg-surface-800 dark:text-surface-100 dark:hover:bg-surface-700"
              >
                Manage Storefront Settings
              </Link>
            </p>
          </div>
        </Card>
      </div>

      <Card className="animate-fade-up [animation-delay:130ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
          Security
        </h3>
        <p className="mt-1 text-sm text-surface-600 dark:text-surface-300">
          Rotate your password regularly for better account protection.
        </p>
        <form
          className="mt-4 grid gap-3 md:max-w-lg"
          onSubmit={passwordForm.handleSubmit((values) =>
            changePasswordMutation.mutate({
              current_password: values.current_password,
              new_password: values.new_password,
            }),
          )}
        >
          <Input
            label="Current Password"
            type="password"
            {...passwordForm.register("current_password")}
            error={passwordForm.formState.errors.current_password?.message}
          />
          <Input
            label="New Password"
            type="password"
            {...passwordForm.register("new_password")}
            error={passwordForm.formState.errors.new_password?.message}
          />
          <Input
            label="Confirm New Password"
            type="password"
            {...passwordForm.register("confirm_password")}
            error={passwordForm.formState.errors.confirm_password?.message}
          />
          <Button type="submit" loading={changePasswordMutation.isPending}>
            Update Password
          </Button>
        </form>
      </Card>

      <Card className="animate-fade-up [animation-delay:145ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
          Access and Team Roles
        </h3>
        <p className="mt-2 text-sm text-surface-600 dark:text-surface-300">
          Owner signup creates the business workspace. Team membership and roles
          are managed in Team Management.
        </p>
        <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm text-surface-600 dark:text-surface-200">
          <li>Create owner account on the Register page.</li>
          <li>
            Update owner details and business profile in this Settings page.
          </li>
          <li>Open Team Management and add members by email.</li>
          <li>Assign roles: owner, admin, or staff.</li>
          <li>
            Deactivate or reactivate access from Team Management when needed.
          </li>
        </ol>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link
            to="/team"
            className="inline-flex rounded-lg bg-surface-100 px-3 py-2 text-xs font-semibold text-surface-800 transition hover:bg-surface-200 dark:bg-surface-800 dark:text-surface-100 dark:hover:bg-surface-700"
          >
            Open Team Management
          </Link>
          <Link
            to="/login"
            className="inline-flex rounded-lg bg-surface-100 px-3 py-2 text-xs font-semibold text-surface-800 transition hover:bg-surface-200 dark:bg-surface-800 dark:text-surface-100 dark:hover:bg-surface-700"
          >
            Open Login Page
          </Link>
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:152ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
          Accept Team Invitation
        </h3>
        <p className="mt-2 text-sm text-surface-600 dark:text-surface-300">
          If your account already exists, paste invitation token to join another
          business workspace.
        </p>
        <div className="mt-4 grid gap-3 md:max-w-lg">
          <Input
            label="Invitation Token"
            placeholder="ti_xxx"
            value={inviteTokenInput}
            onChange={(event) => setInviteTokenInput(event.target.value)}
          />
          <Button
            type="button"
            loading={acceptInvitationMutation.isPending}
            disabled={!inviteTokenInput.trim()}
            onClick={() =>
              acceptInvitationMutation.mutate(inviteTokenInput.trim())
            }
          >
            Accept Invitation
          </Button>
        </div>
      </Card>

      <Card className="animate-fade-up [animation-delay:160ms]">
        <h3 className="font-heading text-lg font-bold text-surface-800 dark:text-surface-100">
          Session
        </h3>
        <p className="mt-2 text-sm text-surface-600 dark:text-surface-300">
          Logout clears local tokens and revokes the current refresh session.
        </p>
        <Button
          type="button"
          variant="danger"
          className="mt-4"
          onClick={() => setConfirmLogout(true)}
        >
          Logout
        </Button>
      </Card>

      <Modal
        open={confirmLogout}
        title="Confirm Logout"
        onClose={() => setConfirmLogout(false)}
      >
        <p className="text-sm text-surface-600 dark:text-surface-300">
          This will end your current session on this device.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button
            type="button"
            variant="ghost"
            onClick={() => setConfirmLogout(false)}
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="danger"
            onClick={() => logoutMutation.mutate()}
            loading={logoutMutation.isPending}
          >
            Logout
          </Button>
        </div>
      </Modal>
    </div>
  );
}
