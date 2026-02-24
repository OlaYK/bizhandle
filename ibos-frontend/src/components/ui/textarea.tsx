import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "../../lib/cn";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, error, className, ...props },
  ref
) {
  return (
    <label className="block space-y-1.5">
      {label ? <span className="text-sm font-semibold text-surface-700 dark:text-surface-100">{label}</span> : null}
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-lg border border-surface-200 bg-white px-3 py-2 text-sm text-surface-800 shadow-sm outline-none transition placeholder:text-surface-400 focus:border-surface-400 focus:ring-2 focus:ring-surface-200 dark:border-surface-600 dark:bg-surface-800 dark:text-surface-100 dark:placeholder:text-surface-300 dark:focus:border-surface-300 dark:focus:ring-surface-600",
          error ? "border-red-400 focus:border-red-400 focus:ring-red-100" : "",
          className
        )}
        {...props}
      />
      {error ? <span className="text-xs text-red-600">{error}</span> : null}
    </label>
  );
});
