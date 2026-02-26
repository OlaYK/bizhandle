import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { authService } from "../api/services";
// import { MoniDeskLogo } from "../components/brand/monidesk-logo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { useAuth } from "../hooks/use-auth";
import { useToast } from "../hooks/use-toast";
import { getApiErrorMessage } from "../lib/api-error";

const registerSchema = z
  .object({
    email: z.string().email("Valid email is required"),
    full_name: z.string().min(2, "Full name is required"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    business_name: z.string().optional(),
    username: z.string().optional(),
    invitation_token: z.string().optional(),
  })
  .superRefine((value, context) => {
    const hasInvitation = Boolean(value.invitation_token?.trim());
    const businessName = value.business_name?.trim() ?? "";
    if (!hasInvitation && businessName.length < 2) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["business_name"],
        message: "Business name is required",
      });
    }
  });

type RegisterFormData = z.infer<typeof registerSchema>;

export function RegisterPage({
  setAuthState,
}: {
  setAuthState: (state: "login" | "register") => void;
}) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { setSession, isAuthenticated } = useAuth();
  const { showToast } = useToast();
  const authInputClassName =
    "border-surface-300 bg-white text-black placeholder:text-black/60 focus:border-black focus:ring-black/10 dark:border-surface-300 dark:bg-white dark:text-black dark:placeholder:text-black/60 dark:focus:border-black dark:focus:ring-black/10";
  const authLabelClassName = "text-black dark:text-black";

  const form = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      full_name: "",
      password: "",
      business_name: "",
      username: "",
      invitation_token: searchParams.get("invite") ?? "",
    },
  });

  const invitationToken = form.watch("invitation_token")?.trim() ?? "";

  useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true });
    }
  }, [isAuthenticated, navigate]);

  const registerMutation = useMutation({
    mutationFn: (values: RegisterFormData) => {
      const hasInvitation = Boolean(values.invitation_token?.trim());
      if (hasInvitation) {
        return authService.registerWithInvite({
          email: values.email.trim(),
          full_name: values.full_name.trim(),
          password: values.password,
          username: values.username?.trim() || undefined,
          invitation_token: values.invitation_token!.trim(),
        });
      }
      return authService.register({
        email: values.email.trim(),
        full_name: values.full_name.trim(),
        password: values.password,
        business_name: values.business_name?.trim() || undefined,
        username: values.username?.trim() || undefined,
      });
    },
    onSuccess: (tokenOut) => {
      setSession(tokenOut);
      showToast({
        title: "Account created",
        description: "You are now signed in.",
        variant: "success",
      });
      navigate("/", { replace: true });
    },
    onError: (error) => {
      showToast({
        title: "Registration failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  return (
    <div className="w-full">
      {/* <MoniDeskLogo tone="auth" size="md" className="mb-4" />*/}
      <h1 className="font-heading w-fit text-2xl font-bold text-color-dark relative md:after:absolute md:after:-bottom-[2px] md:after:left-1/2 md:after:-translate-x-1/2 md:after:rounded-full md:after:h-[3px] md:after:w-[70%] md:after:bg-[#17314e]">
        Create Account
      </h1>
      <p className="mt-3 text-sm text-color-dark">
        Set up your MoniDesk workspace.
      </p>

      <form
        className="mt-6 grid gap-4"
        onSubmit={form.handleSubmit((values) =>
          registerMutation.mutate(values),
        )}
      >
        <Input
          label="Full Name"
          placeholder="Jane Owner"
          className={authInputClassName}
          labelClassName={authLabelClassName}
          {...form.register("full_name")}
          error={form.formState.errors.full_name?.message}
        />
        <Input
          label="Email"
          placeholder="owner@example.com"
          type="email"
          className={authInputClassName}
          labelClassName={authLabelClassName}
          {...form.register("email")}
          error={form.formState.errors.email?.message}
        />
        <Input
          label="Password"
          placeholder="********"
          type="password"
          className={authInputClassName}
          labelClassName={authLabelClassName}
          {...form.register("password")}
          error={form.formState.errors.password?.message}
        />
        <Input
          label="Invitation Token (optional)"
          placeholder="ti_xxx"
          className={authInputClassName}
          labelClassName={authLabelClassName}
          {...form.register("invitation_token")}
          error={form.formState.errors.invitation_token?.message}
        />
        {!invitationToken ? (
          <Input
            label="Business Name"
            placeholder="My Shop"
            className={authInputClassName}
            labelClassName={authLabelClassName}
            {...form.register("business_name")}
            error={form.formState.errors.business_name?.message}
          />
        ) : null}
        <Input
          label="Username (optional)"
          className={authInputClassName}
          labelClassName={authLabelClassName}
          {...form.register("username")}
        />

        <Button
          type="submit"
          className="w-full"
          loading={registerMutation.isPending}
        >
          Create account
        </Button>
      </form>

      <p className="mt-4 text-sm text-black">
        Already registered?{" "}
        <button
          className="font-semibold text-black underline"
          onClick={() => setAuthState("login")}
        >
          Sign in
        </button>
      </p>
    </div>
    // <div className="relative min-h-screen overflow-hidden bg-[linear-gradient(135deg,#0f2238_0,#17314e_45%,#203f62_100%)] p-4 sm:p-6">
    //   {/* <div className="pointer-events-none absolute left-0 top-6 h-64 w-64 rounded-full bg-mint-300/25 blur-3xl animate-float-slow" />
    //   <div className="pointer-events-none absolute right-0 top-20 h-72 w-72 rounded-full bg-cobalt-300/20 blur-3xl animate-float-mid" />
    //   <div className="pointer-events-none absolute bottom-0 left-1/3 h-56 w-56 rounded-full bg-accent-300/20 blur-3xl animate-pulse-glow" />
    //   <div className="mx-auto flex min-h-[92vh] w-full max-w-5xl items-center justify-center"> */}

    //   </div>
  );
}
