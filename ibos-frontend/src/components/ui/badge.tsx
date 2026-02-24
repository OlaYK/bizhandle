import type { PropsWithChildren } from "react";
import { cn } from "../../lib/cn";

type BadgeVariant = "neutral" | "positive" | "negative" | "info";

const variants: Record<BadgeVariant, string> = {
  neutral: "bg-surface-100 text-surface-700",
  positive: "bg-mint-100 text-mint-700",
  negative: "bg-red-100 text-red-700",
  info: "bg-accent-100 text-accent-700"
};

interface BadgeProps extends PropsWithChildren {
  variant?: BadgeVariant;
}

export function Badge({ variant = "neutral", children }: BadgeProps) {
  return (
    <span className={cn("inline-flex rounded-full px-2.5 py-1 text-xs font-semibold", variants[variant])}>
      {children}
    </span>
  );
}
