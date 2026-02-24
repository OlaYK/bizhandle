import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type PropsWithChildren
} from "react";
import { CheckCircle2, CircleAlert, Info } from "lucide-react";
import { cn } from "../lib/cn";

type ToastVariant = "success" | "error" | "info";

interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  showToast: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastContextValue | undefined>(undefined);

const variantStyles: Record<ToastVariant, string> = {
  success: "border-mint-300 bg-mint-100 text-mint-700",
  error: "border-red-300 bg-red-50 text-red-700",
  info: "border-surface-200 bg-white text-surface-700"
};

const variantIcon: Record<ToastVariant, JSX.Element> = {
  success: <CheckCircle2 className="h-4 w-4" />,
  error: <CircleAlert className="h-4 w-4" />,
  info: <Info className="h-4 w-4" />
};

export function ToastProvider({ children }: PropsWithChildren) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showToast = useCallback((toast: Omit<Toast, "id">) => {
    const next: Toast = { ...toast, id: crypto.randomUUID() };
    setToasts((prev) => [...prev, next]);

    window.setTimeout(() => {
      setToasts((prev) => prev.filter((item) => item.id !== next.id));
    }, 4000);
  }, []);

  const value = useMemo(() => ({ showToast }), [showToast]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed right-4 top-4 z-50 flex w-[min(380px,90vw)] flex-col gap-3">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cn(
              "pointer-events-auto animate-fade-up rounded-xl border p-4 shadow-soft",
              variantStyles[toast.variant]
            )}
          >
            <div className="flex items-start gap-2">
              <span className="mt-0.5">{variantIcon[toast.variant]}</span>
              <div>
                <p className="font-semibold">{toast.title}</p>
                {toast.description ? (
                  <p className="text-sm opacity-90">{toast.description}</p>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within ToastProvider");
  }
  return context;
}
