interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-dashed border-surface-300 bg-surface-50 p-8 text-center dark:border-surface-600 dark:bg-surface-800/60">
      <h3 className="font-heading text-lg font-bold text-surface-700 dark:text-surface-100">{title}</h3>
      {description ? <p className="mt-2 text-sm text-surface-500 dark:text-surface-300">{description}</p> : null}
    </div>
  );
}
