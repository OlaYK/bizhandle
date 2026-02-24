import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "../../lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "sm" | "md" | "lg";

const variantClass: Record<ButtonVariant, string> = {
  primary:
    "bg-[linear-gradient(140deg,#203f62,#17314e)] text-white hover:shadow-glow focus-visible:ring-surface-500 dark:bg-[linear-gradient(140deg,#35567c,#203f62)]",
  secondary:
    "bg-[linear-gradient(140deg,#27c25c,#14823f)] text-white hover:brightness-110 focus-visible:ring-mint-300",
  ghost:
    "bg-transparent text-surface-700 hover:bg-surface-100 focus-visible:ring-surface-400 dark:text-surface-100 dark:hover:bg-surface-700/40 dark:focus-visible:ring-surface-300",
  danger: "bg-red-600 text-white hover:bg-red-700 focus-visible:ring-red-400"
};

const sizeClass: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm",
  md: "h-10 px-4 text-sm",
  lg: "h-11 px-5 text-base"
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition duration-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 active:scale-[0.98] dark:focus-visible:ring-offset-surface-900",
        variantClass[variant],
        sizeClass[size],
        disabled || loading ? "cursor-not-allowed opacity-70" : "",
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
      {children}
    </button>
  );
}
