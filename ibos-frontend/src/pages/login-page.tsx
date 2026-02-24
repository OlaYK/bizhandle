import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { z } from "zod";
import { authService } from "../api/services";
import { MoniDeskLogo } from "../components/brand/monidesk-logo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../hooks/use-auth";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";

const loginSchema = z.object({
  identifier: z.string().min(1, "Email or username is required"),
  password: z.string().min(1, "Password is required")
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginPage() {
  const navigate = useNavigate();
  const { setSession, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const authInputClassName =
    "border-surface-300 bg-white text-black placeholder:text-black/60 focus:border-black focus:ring-black/10 dark:border-surface-300 dark:bg-white dark:text-black dark:placeholder:text-black/60 dark:focus:border-black dark:focus:ring-black/10";
  const authLabelClassName = "text-black dark:text-black";

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      identifier: "",
      password: ""
    }
  });

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const loginMutation = useMutation({
    mutationFn: authService.login,
    onSuccess: (tokenOut) => {
      setSession(tokenOut);
      showToast({
        title: "Welcome back",
        description: "Authentication successful.",
        variant: "success"
      });
      navigate("/", { replace: true });
    },
    onError: (error) => {
      showToast({
        title: "Login failed",
        description: getApiErrorMessage(error),
        variant: "error"
      });
    }
  });

  return (
    <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#0f2238_0,#17314e_45%,#203f62_100%)] p-4 sm:p-6">
      <div className="pointer-events-none absolute left-0 top-0 h-72 w-72 rounded-full bg-mint-300/25 blur-3xl animate-float-slow" />
      <div className="pointer-events-none absolute right-0 top-24 h-72 w-72 rounded-full bg-cobalt-300/20 blur-3xl animate-float-mid" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-56 w-56 rounded-full bg-accent-300/20 blur-3xl animate-pulse-glow" />
      <div className="mx-auto flex min-h-[92vh] w-full max-w-5xl flex-col justify-center gap-8 lg:flex-row">
        <div className="rounded-3xl border border-white/15 bg-white/10 p-8 text-white backdrop-blur">
          <MoniDeskLogo tone="light" size="lg" className="animate-fade-up" />
          <h1 className="mt-2 font-heading text-4xl font-black leading-tight">
            Run your money flow from one operational cockpit.
          </h1>
          <p className="mt-4 max-w-md text-sm text-surface-100/90">
            Sales, inventory, expenses, AI insights, and credit profile in one focused workspace.
          </p>
        </div>

        <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-soft sm:p-8">
          <h2 className="font-heading text-2xl font-bold text-black">Sign in</h2>
          <p className="mt-1 text-sm text-black">Use your email/username and password.</p>

          <form
            className="mt-6 space-y-4"
            onSubmit={form.handleSubmit((values) => loginMutation.mutate(values))}
          >
            <Input
              label="Email or Username"
              placeholder="owner@example.com"
              labelClassName={authLabelClassName}
              className={authInputClassName}
              {...form.register("identifier")}
              error={form.formState.errors.identifier?.message}
            />
            <Input
              label="Password"
              placeholder="********"
              type="password"
              labelClassName={authLabelClassName}
              className={authInputClassName}
              {...form.register("password")}
              error={form.formState.errors.password?.message}
            />
            <Button type="submit" className="w-full" loading={loginMutation.isPending}>
              Sign in
            </Button>
          </form>

          <p className="mt-4 text-sm text-black">
            No account?{" "}
            <Link className="font-semibold text-black underline" to="/register">
              Create one
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
