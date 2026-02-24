import type { PropsWithChildren } from "react";
import { cn } from "../../lib/cn";

interface CardProps extends PropsWithChildren {
  className?: string;
}

export function Card({ className, children }: CardProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-surface-100 bg-white p-4 shadow-soft transition duration-300 hover:-translate-y-0.5 hover:shadow-lg dark:border-surface-700 dark:bg-surface-900/80 dark:shadow-none",
        className
      )}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-[linear-gradient(90deg,transparent,rgba(248,194,13,0.8),transparent)] bg-[length:220%_100%] animate-shimmer" />
      {children}
    </div>
  );
}
