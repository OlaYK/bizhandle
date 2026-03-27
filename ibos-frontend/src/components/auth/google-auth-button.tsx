import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { authService } from "../../api/services";
import { type TokenOut } from "../../api/types";
import { useAuth } from "../../hooks/use-auth";
import { useToast } from "../../hooks/use-toast";
import { getApiErrorMessage } from "../../lib/api-error";
import { Button } from "../ui/button";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential?: string }) => void;
            ux_mode?: "popup" | "redirect";
            context?: "signin" | "signup" | "use";
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: "outline" | "filled_blue" | "filled_black";
              size?: "large" | "medium" | "small";
              text?:
                | "signin_with"
                | "signup_with"
                | "continue_with"
                | "signin"
                | "continue";
              shape?: "rectangular" | "pill" | "circle" | "square";
              width?: number;
              logo_alignment?: "left" | "center";
            },
          ) => void;
        };
      };
    };
  }
}

const GOOGLE_IDENTITY_SCRIPT_ID = "google-identity-service";
let googleIdentityScriptPromise: Promise<void> | null = null;

function loadGoogleIdentityScript() {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Google sign-in is only available in the browser."));
  }
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }
  if (googleIdentityScriptPromise) {
    return googleIdentityScriptPromise;
  }

  googleIdentityScriptPromise = new Promise<void>((resolve, reject) => {
    const existingScript = document.getElementById(
      GOOGLE_IDENTITY_SCRIPT_ID,
    ) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener("load", () => resolve(), { once: true });
      existingScript.addEventListener(
        "error",
        () => reject(new Error("Could not load Google sign-in.")),
        { once: true },
      );
      return;
    }

    const script = document.createElement("script");
    script.id = GOOGLE_IDENTITY_SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Could not load Google sign-in."));
    document.head.appendChild(script);
  });

  return googleIdentityScriptPromise;
}

interface GoogleAuthButtonProps {
  mode: "login" | "register";
  businessName?: string;
  username?: string;
}

export function GoogleAuthButton({
  mode,
  businessName,
  username,
}: GoogleAuthButtonProps) {
  const navigate = useNavigate();
  const { setSession } = useAuth();
  const { showToast } = useToast();
  const buttonRef = useRef<HTMLDivElement | null>(null);
  const payloadRef = useRef({
    businessName,
    username,
  });
  const [renderState, setRenderState] = useState<
    "idle" | "loading" | "ready" | "error"
  >(import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim() ? "loading" : "error");
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();

  payloadRef.current = { businessName, username };

  const googleAuthMutation = useMutation({
    mutationFn: authService.google,
    onSuccess: (tokenOut: TokenOut) => {
      setSession(tokenOut);
      showToast({
        title:
          mode === "login" ? "Signed in with Google" : "Account created with Google",
        description: "Authentication successful.",
        variant: "success",
      });
      navigate("/", { replace: true });
    },
    onError: (error) => {
      showToast({
        title: "Google authentication failed",
        description: getApiErrorMessage(error),
        variant: "error",
      });
    },
  });

  useEffect(() => {
    if (!clientId) {
      setRenderState("error");
      return;
    }

    let cancelled = false;
    setRenderState("loading");

    loadGoogleIdentityScript()
      .then(() => {
        if (cancelled || !buttonRef.current || !window.google?.accounts?.id) {
          return;
        }

        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: ({ credential }) => {
            if (!credential) {
              showToast({
                title: "Google authentication failed",
                description: "Google did not return an ID token.",
                variant: "error",
              });
              return;
            }

            googleAuthMutation.mutate({
              id_token: credential,
              business_name:
                payloadRef.current.businessName?.trim() || undefined,
              username: payloadRef.current.username?.trim() || undefined,
            });
          },
          ux_mode: "popup",
          context: mode === "login" ? "signin" : "signup",
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        buttonRef.current.innerHTML = "";
        window.google.accounts.id.renderButton(buttonRef.current, {
          theme: "outline",
          size: "large",
          text: mode === "login" ? "signin_with" : "signup_with",
          shape: "pill",
          width: Math.max(buttonRef.current.clientWidth, 280),
          logo_alignment: "left",
        });
        setRenderState("ready");
      })
      .catch(() => {
        if (!cancelled) {
          setRenderState("error");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [clientId, mode, googleAuthMutation, showToast]);

  if (!clientId) {
    return (
      <p className="text-xs text-surface-500">
        Google sign-in is not configured for this environment.
      </p>
    );
  }

  if (renderState === "error") {
    return (
      <p className="text-xs text-red-600">
        Could not load Google sign-in. Check your client ID and try again.
      </p>
    );
  }

  return (
    <div className="w-full">
      {renderState !== "ready" ? (
        <Button type="button" variant="ghost" className="w-full" disabled>
          Loading Google...
        </Button>
      ) : null}
      <div
        ref={buttonRef}
        className={renderState === "ready" ? "w-full" : "hidden"}
      />
      {googleAuthMutation.isPending ? (
        <Button type="button" className="mt-3 w-full" loading>
          Verifying Google account...
        </Button>
      ) : null}
    </div>
  );
}
