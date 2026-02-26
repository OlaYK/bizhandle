import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { authService } from "../api/services";
import { MoniDeskLogo } from "../components/brand/monidesk-logo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../hooks/use-auth";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";
import { RegisterPage } from "./register-page";

const loginSchema = z.object({
  identifier: z.string().min(1, "Email or username is required"),
  password: z.string().min(1, "Password is required"),
});

type LoginFormData = z.infer<typeof loginSchema>;

export function LoginPage() {
  const navigate = useNavigate();
  const { setSession, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const [authState, setAuthState] = useState<"login" | "register">("login");
  const authInputClassName =
    "border-surface-300 bg-white text-black placeholder:text-black/60 focus:border-black focus:ring-black/10 dark:border-surface-300 dark:bg-white dark:text-black dark:placeholder:text-black/60 dark:focus:border-black dark:focus:ring-black/10";
  const authLabelClassName = "text-black dark:text-black";

  const form = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      identifier: "",
      password: "",
    },
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
        variant: "success",
      });
      navigate("/", { replace: true });
    },
    onError: (error) => {
      showToast({
        title: "Login failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  return (
    <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#0f2238_0,#17314e_45%,#203f62_100%)]">
      <div className="pointer-events-none absolute left-0 top-0 h-72 w-72 rounded-full bg-mint-300/25 blur-3xl animate-float-slow" />
      <div className="pointer-events-none absolute right-0 top-24 h-72 w-72 rounded-full bg-cobalt-300/20 blur-3xl animate-float-mid" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-56 w-56 rounded-full bg-accent-300/20 blur-3xl animate-pulse-glow" />
      <div className="flex min-h-screen w-full flex-col lg:flex-row">
        {/* Branding panel — hidden on mobile/tablet, visible on desktop */}
        <div className="hidden lg:flex w-full flex-col justify-center border-white/15 bg-white/10 p-6 px-8 text-white backdrop-blur  lg:pr-0 lg:px-12">
          <MoniDeskLogo tone="light" size="lg" className="animate-fade-up" />
          <h1 className="mt-4 font-heading max-w-lg text-2xl md:text-3xl lg:text-4xl font-black leading-tight">
            Run your money flow from one operational cockpit.
          </h1>
          <p className="mt-4 max-w-md text-sm text-surface-100/90">
            Sales, inventory, expenses, AI insights, and credit profile in one
            focused workspace.
          </p>

          <div className="mt-6 lg:mt-10 overflow-clip">
            <img
              className="rounded-md translate-x-[40px] md:translate-x-[60px] lg:translate-x-[100px]"
              src="/dashLight.png"
              alt=""
            />
          </div>
        </div>

        {/* Form card — full screen on mobile/tablet, side panel on desktop */}

        <div className="flex w-full flex-col items-center justify-center bg-white p-6 shadow-soft sm:p-8 lg:max-w-lg  min-h-screen relative overflow-hidden lg:min-h-0">
          {/* Decorative blur patches */}
          <div className="pointer-events-none absolute -left-16 -top-16 h-48 w-48 rounded-full bg-[#17314e]/40 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-16 -right-16 h-48 w-48 rounded-full bg-[#17314e]/40 blur-3xl" />
          {/* Show logo on mobile/tablet since branding panel is hidden */}
          <div className="mb-10 lg:hidden">
            <MoniDeskLogo tone="default" size="md" />
          </div>
          {/* Sign in */}
          {authState === "login" ? (
            <div className="w-full flex flex-col items-center justify-center">
              <h2 className="font-heading font-semibold text-xl md:text-2xl text-color-dark relative md:after:absolute md:after:-bottom-1.5 md:after:left-1/2 md:after:-translate-x-1/2 md:after:rounded-full md:after:h-1 md:after:w-[70%] md:after:bg-[#17314e] text-left md:text-center w-full md:w-fit  ">
                Sign in
              </h2>
              <p className="lg:mt-6 mt-0 md:text-sm text-xs hidden lg:block text-left lg:text-center w-full text-black">
                Use your email/username and password.
              </p>
              <form
                className="md:mt-6 mt-2 space-y-4 w-full sm:w-[80%]"
                onSubmit={form.handleSubmit((values) =>
                  loginMutation.mutate(values),
                )}
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
                <Button
                  type="submit"
                  className="w-full"
                  loading={loginMutation.isPending}
                >
                  Sign in
                </Button>
              </form>

              <p className="mt-4 text-sm text-black">
                No account?{" "}
                <button
                  className="font-semibold text-black underline"
                  onClick={() => setAuthState("register")}
                >
                  Create one
                </button>
              </p>
            </div>
          ) : (
            <RegisterPage setAuthState={setAuthState} />
          )}
        </div>
      </div>
    </div>
  );
}
