import { Loader2 } from "lucide-react";

interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = "Loading..." }: LoadingStateProps) {
  return (
    <div className="flex min-h-[220px] items-center justify-center rounded-2xl border border-surface-100 bg-white dark:border-surface-700 dark:bg-surface-900">
      <div className="flex items-center gap-2 text-surface-600 dark:text-surface-200">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span className="text-sm font-medium">{label}</span>
      </div>
    </div>
  );
}
