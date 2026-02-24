import { CircleAlert } from "lucide-react";
import { Button } from "../ui/button";

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export function ErrorState({
  message = "Something went wrong. Please refresh.",
  onRetry
}: ErrorStateProps) {
  return (
    <div className="rounded-2xl border border-red-200 bg-red-50 p-6 dark:border-red-400/30 dark:bg-red-900/20">
      <div className="flex items-start gap-3">
        <CircleAlert className="mt-0.5 h-5 w-5 text-red-600" />
        <div className="space-y-3">
          <p className="text-sm font-medium text-red-700 dark:text-red-200">{message}</p>
          {onRetry ? (
            <Button type="button" size="sm" variant="danger" onClick={onRetry}>
              Retry
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
