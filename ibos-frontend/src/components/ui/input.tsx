import { forwardRef, type InputHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, error, className, ...props },
  ref
) {
  return (
    <label className="block space-y-1.5">
      {label ? <span className="text-sm font-semibold text-surface-700 dark:text-surface-100">{label}</span> : null}
      <input
        ref={ref}
        className={cn(
          "h-11 w-full rounded-lg border border-surface-200 bg-white px-3 text-sm text-surface-800 shadow-sm outline-none transition placeholder:text-surface-400 focus:border-surface-400 focus:ring-2 focus:ring-surface-200 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:placeholder:text-surface-300 dark:focus:border-surface-300 dark:focus:ring-surface-600",
          error ? "border-red-400 focus:border-red-400 focus:ring-red-100" : "",
          className
        )}
        {...props}
      />
      {error ? <span className="text-xs text-red-600">{error}</span> : null}
    </label>
  );
});
